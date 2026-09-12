"""Trusted local evaluator. Private fork state never enters deploy/worker inputs."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
from ..deploy import vendor
from ..deploy.engine import Engine, PreparedChoice
from ..deploy.state import ResumeToken, controller_state, encode, decode, digest
from .budget import Budget, CountedBackend, IMPL, atomic_json

REPO=vendor.REPO
ENV_PATH=REPO/'local_env.py'
ENV_PIN='99587518fa378e1bef2fbbaa9425ee907bea80885a69666b3765311cbcf4f42a'
if hashlib.sha256(ENV_PATH.read_bytes()).hexdigest()!=ENV_PIN:
    raise RuntimeError('Frozen local environment changed')
spec=importlib.util.spec_from_file_location('_bc_rpi_private_local_env',ENV_PATH)
local=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=local
spec.loader.exec_module(local)


def save_new(path,value):
    path=Path(path)
    if path.exists():raise FileExistsError('Immutable run artifact already exists: '+str(path))
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.suffix=='.gz':
        with gzip.open(path,'wt',encoding='utf-8') as stream:
            json.dump(value,stream,ensure_ascii=False,separators=(',',':'),allow_nan=False)
    else:atomic_json(path,value)


def load(path):
    path=Path(path)
    if path.suffix=='.gz':
        with gzip.open(path,'rt',encoding='utf-8') as stream:return json.load(stream)
    return json.loads(path.read_text())


def worlds(phase):
    manifest=load(IMPL/'evaluator/probes_v1.json')
    registration=load(IMPL/'execution_registration.json')
    if hashlib.sha256((IMPL/'evaluator/probes_v1.json').read_bytes()).hexdigest()!=registration['world_registry_sha256']:
        raise RuntimeError('Frozen probe manifest changed')
    return [w for w in manifest['worlds'] if w['phase']==phase]


def new_env(world,clock=time.monotonic):
    return local.LocalEnv([local.Source(**s) for s in world['sources']],seed=world['seed'],
                         noise=world['noise'],keep_log=True,clock=clock)


def canonical_log(log):
    return [dict(action=e['action'],request=e['request'],
        response={k:v for k,v in e['response'].items() if k not in ('real_timestamp_ms','remaining_real_duration_s')}) for e in log]


class BranchClock:
    """Queue time excluded, prefix time retained; only local fork research uses this."""
    def __init__(self,base=1000000.):
        self.base=float(base)
        self.running_since=None

    def __call__(self):
        return self.base+(0. if self.running_since is None else time.monotonic()-self.running_since)

    def advance(self,seconds):
        if seconds<0:raise ValueError('Cannot move branch clock backward')
        self.base+=float(seconds)

    def start(self):
        if self.running_since is not None:raise ValueError('Branch clock started twice')
        self.running_since=time.monotonic()


@dataclass
class ForkHandle:
    """Training-only private object; it is never sent to CandidateWorker."""
    token: ResumeToken
    prepared: PreparedChoice
    private: dict
    clock_offsets: dict
    source_index: int
    capture_wall_s: float
    private_integrity_sha256: str
    world_sha256: str
    bundle_integrity_sha256: str

    def to_json(self):
        return dict(token=self.token.to_json(),prepared=self.prepared.to_json(),private=encode(self.private),
            clock_offsets=self.clock_offsets,source_index=self.source_index,capture_wall_s=self.capture_wall_s,
            private_integrity_sha256=self.private_integrity_sha256,world_sha256=self.world_sha256,
            bundle_integrity_sha256=self.bundle_integrity_sha256)

    def verify(self,world):
        if self.world_sha256!=world['world_sha256']:
            raise ValueError('Fork handle belongs to a different registered world')
        value=self.to_json();expected=value.pop('bundle_integrity_sha256')
        if digest(value)!=expected:
            raise ValueError('Fork world/token/prepared bundle integrity mismatch')
        if self.prepared.pre_state_hash!=self.token.semantic_pre_hash:
            raise ValueError('Prepared choice belongs to a different pre-token')
        self.token.verify_integrity()

    @classmethod
    def from_json(cls,value):
        value=deepcopy(value)
        value['token']=ResumeToken.from_json(value['token'])
        value['prepared']=PreparedChoice.from_json(value['prepared'])
        value['private']=decode(value['private'])
        return cls(**value)


def capture_private(environment,engine,token,prepared,index,world_sha256):
    started=time.monotonic()
    token.verify_integrity()
    # Preparation is detached and makes no calls; physical state is unchanged.
    if len(environment.log)!=token.accepted_event_count or environment._virtual_us!=token.prefix_virtual_us:
        raise ValueError('Cannot fork: private/public prefix ledger differs')
    fork_now=engine.api.started_at+token.clock_offsets['task_elapsed_real_s']
    offsets=dict(task_elapsed_real_s=fork_now-environment._t0,
        ready_age_real_s=fork_now-environment._ready_at,
        deadline_remaining_real_s=environment._deadline-fork_now)
    private={k:deepcopy(v) for k,v in environment.__dict__.items()
             if k not in ('_clock','_t0','_deadline','_ready_at','_sources')}
    private['_sources']={c:vars(s).copy() for c,s in environment._sources.items()}
    integrity=digest(encode(dict(private=private,clock_offsets=offsets)))
    handle=ForkHandle(token,deepcopy(prepared),private,offsets,index,
                      time.monotonic()-started,integrity,world_sha256,'')
    seal_handle(handle)
    return handle


def seal_handle(handle):
    value=handle.to_json();value.pop('bundle_integrity_sha256')
    handle.bundle_integrity_sha256=digest(value)


def clone_private(handle,clock):
    if digest(encode(dict(private=handle.private,clock_offsets=handle.clock_offsets)))!=handle.private_integrity_sha256:
        raise ValueError('Private fork payload integrity mismatch')
    env=object.__new__(local.LocalEnv)
    values=deepcopy(handle.private)
    sources=values.pop('_sources')
    env.__dict__=values
    env._sources={c:local.Source(**s) for c,s in sources.items()}
    now=clock()
    env._clock=clock
    env._t0=now-handle.clock_offsets['task_elapsed_real_s']
    env._ready_at=now-handle.clock_offsets['ready_age_real_s']
    env._deadline=now+handle.clock_offsets['deadline_remaining_real_s']
    if env._virtual_us!=handle.token.prefix_virtual_us or len(env.log)!=handle.token.accepted_event_count:
        raise ValueError('Cloned private ledger differs from token')
    return env


class CaptureCollector:
    def __init__(self,environment,world_sha256,*,after_intervention=False):
        self.environment=environment
        self.world_sha256=world_sha256
        self.after_intervention=after_intervention
        self.handles=[]

    def on_choice(self,engine,token,prepared,_):
        if prepared.meta['teacher_task']['kind']!='source':return
        if self.after_intervention and not engine.state['used_operation_ids']:return
        self.handles.append(capture_private(self.environment,engine,token,prepared,len(self.handles),self.world_sha256))


def sample_handles(handles,max_states=4):
    n=len(handles);m=min(max_states,n)
    indexes=([0] if m==1 else [k*(n-1)//(m-1) for k in range(m)]) if m else []
    return [handles[i] for i in indexes]


def outcome(env,report,*,run_id,kind,wall_s,extra=None):
    stats=env.stats()
    success=(env.finished and env.exit_reason=='user_exit' and stats['cleared']==stats['n']
        and report.get('success',True) and not report.get('error'))
    return dict(schema='bc-rpi-evaluator-outcome-v1',run_id=run_id,kind=kind,success=success,
        true_terminal_n=stats['n'],cleared=stats['cleared'],normal_exit=env.exit_reason=='user_exit',
        modeled_full_virtual_us=env._virtual_us,seconds_per_source=env._virtual_us/1e6/stats['n'],
        actual_execution_wall_s=wall_s,stats=stats,episode=report,environment_log=env.log,
        private_terminal_sources={str(c):vars(s) for c,s in env._sources.items()},extra=extra or {})


def run_original(world,budget,run_id,*,entry=None,q3_passthrough=False):
    policy='latest_q3_passthrough' if q3_passthrough else 'original_c7' if entry is None else 'latest_q3_direct'
    from ..deploy.q3_passthrough import LATEST_Q3_ENTRY,LATEST_Q3_SHA256
    source_sha=LATEST_Q3_SHA256 if q3_passthrough else hashlib.sha256(Path(entry).read_bytes()).hexdigest() if entry is not None else vendor.C7_SHA256
    budget.start(run_id,'full',dict(world_sha256=world['world_sha256'],mode=world['mode'],policy=policy,entry_sha256=source_sha))
    started=time.monotonic(); env=new_env(world)
    module=vendor.load_c7()
    if q3_passthrough:
        from ..deploy import q3_passthrough as passthrough
        module=passthrough
    if entry is not None:
        spec=importlib.util.spec_from_file_location('_bc_rpi_nonrl_'+run_id,entry)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    solver=module.Solver(CountedBackend(env,budget),mode=world['mode'])
    error=None
    try:solver.run()
    except Exception as exc:error=type(exc).__name__+': '+str(exc)
    report=dict(error=error,success=error is None,controller_final=encode({k:v for k,v in solver.__dict__.items() if k not in ('env','deadline')}))
    result=outcome(env,report,run_id=run_id,kind='full',wall_s=time.monotonic()-started)
    budget.finish(result['success'],dict(world_sha256=world['world_sha256'],mode=world['mode'],virtual_us=env._virtual_us,error=error))
    return result


def run_full(world,budget,run_id,*,worker=None,capture=False,plan=None,after_intervention=False,guard=None):
    budget.start(run_id,'full',dict(world_sha256=world['world_sha256'],mode=world['mode'],policy='teacher0' if not plan else 'privileged_replay'))
    started=time.monotonic(); env=new_env(world)
    engine=Engine(CountedBackend(env,budget),world['mode'],worker=worker,guard=guard)
    collector=CaptureCollector(env,world['world_sha256'],after_intervention=after_intervention)
    applied=[]
    def select(e,p):
        target=next((x for x in (plan or []) if x['choice_id']==p.choice_id),None)
        if target is None:return p.choices['teacher_id']
        e.expand(p)
        if target['action_id'] not in p.choices['candidate_ids']:
            raise ValueError('Replay action missing from retained public choice')
        applied.append(target)
        return target['action_id']
    try:
        engine.enter()
        report=engine.run(capture=capture,on_choice=collector.on_choice if capture else None,
                          select=select if plan else None)
    except Exception as exc:
        engine.error=type(exc).__name__+': '+str(exc);report=engine.report()
    if plan and len(applied)!=len(plan):
        report['error']='Replay did not apply every registered intervention'
    result=outcome(env,report,run_id=run_id,kind='full',wall_s=time.monotonic()-started,
                   extra=dict(applied_plan=applied,source_boundary_count=len(collector.handles)))
    budget.finish(result['success'],dict(world_sha256=world['world_sha256'],mode=world['mode'],virtual_us=env._virtual_us,error=report['error']))
    return result,collector.handles


def run_suffix(world,budget,run_id,handle,action_id,*,worker=None,capture=False,clock_advance_s=0.):
    handle.verify(world)
    if action_id not in handle.prepared.choices['candidate_ids']:
        raise ValueError('Suffix action not in frozen retained set')
    budget.start(run_id,'suffix',dict(world_sha256=world['world_sha256'],mode=world['mode'],
        policy='one_retained_operation_then_frozen_c7',choice_id=handle.prepared.choice_id,
        action_id=action_id,prefix_virtual_us=handle.token.prefix_virtual_us))
    started=time.monotonic(); clock=BranchClock()
    clone_start=time.monotonic(); env=clone_private(handle,clock)
    engine=Engine.restore(CountedBackend(env,budget),handle.token,clock=clock,worker=worker)
    clone_wall=time.monotonic()-clone_start
    prepared=deepcopy(handle.prepared)
    # Every branch receives the same real preparation duration. Queue time and
    # evaluator cloning/serialization are recorded separately as study costs.
    clock.advance(prepared.prepare_wall_s+clock_advance_s)
    collector=CaptureCollector(env,world['world_sha256'])
    clock.start()
    report=engine.run(initial_action=(prepared,action_id),capture=capture,
                      on_choice=collector.on_choice if capture else None)
    result=outcome(env,report,run_id=run_id,kind='suffix',wall_s=time.monotonic()-started,
        extra=dict(clone_cpu_wall_s=clone_wall,capture_wall_s=handle.capture_wall_s,
            common_prepare_clock_charge_s=prepared.prepare_wall_s,
            additional_controlled_clock_advance_s=clock_advance_s,
            queue_time_excluded_from_branch_clock=True,source_boundary_count=len(collector.handles)))
    if report['total_virtual_us']!=env._virtual_us:
        result['success']=False;result['ledger_error']='private/public total differs'
    budget.finish(result['success'],dict(world_sha256=world['world_sha256'],mode=world['mode'],virtual_us=env._virtual_us,error=report['error']))
    return result,collector.handles
