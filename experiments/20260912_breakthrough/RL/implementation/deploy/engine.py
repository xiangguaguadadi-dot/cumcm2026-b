"""Explicit READY_PREPARE / commit-once controller, with C7 task rules intact."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import selectors
import subprocess
import sys
import time
from . import operations, vendor
from .interface import PublicLedger
from .state import (ResumeToken, assert_ready, canonical_events, controller_state, decode,
                    digest, encode, make_token, restore_controller, semantic_state_hash)


def source_hash():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


class CandidateWorker:
    """The actor-side generator sees only the explicit JSON request, in exec'd Python."""
    def __init__(self):
        root = Path(__file__).resolve().parents[2]
        self.process = subprocess.Popen([sys.executable, '-S', '-B', '-m', 'implementation.deploy.worker'],
            cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        self.sequence=0
        self.disabled=False

    def generate(self, request):
        if self.disabled:
            raise RuntimeError('Public worker disabled after a protocol failure')
        self.sequence+=1
        request_id=str(self.sequence)
        self.process.stdin.write(json.dumps(dict(request_id=request_id,payload=request), allow_nan=False, separators=(',', ':')) + '\n')
        self.process.stdin.flush()
        ready = selectors.DefaultSelector()
        ready.register(self.process.stdout, selectors.EVENT_READ)
        try:
            if not ready.select(10):
                self.disabled=True
                self.process.kill()
                self.process.wait(timeout=2)
                raise RuntimeError('Public candidate worker timeout')
            line = self.process.stdout.readline()
        finally:
            ready.close()
        if not line:
            raise RuntimeError('Public worker terminated: ' + self.process.stderr.read()[-2000:])
        response = json.loads(line)
        if response.get('request_id')!=request_id:
            self.disabled=True
            self.process.kill()
            self.process.wait(timeout=2)
            raise ValueError('Worker response does not match request ID')
        if not response.get('ok'):
            raise ValueError(response.get('error', 'Public generator failed'))
        return response['choice']

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            try:self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        self.process.stdout.close()
        self.process.stderr.close()


@dataclass
class PreparedChoice:
    choice_id: str
    pre_state_hash: str
    prepared_state_hash: str
    common_patch: dict
    meta: dict
    public_controller: dict
    public_engine: dict
    choices: dict
    prepare_wall_s: float
    expanded: bool = False

    def to_json(self):
        return dict(choice_id=self.choice_id, pre_state_hash=self.pre_state_hash,
            prepared_state_hash=self.prepared_state_hash, common_patch=encode(self.common_patch),
            meta=self.meta, public_controller=self.public_controller, public_engine=self.public_engine,
            choices=self.choices, prepare_wall_s=self.prepare_wall_s, expanded=self.expanded)

    @classmethod
    def from_json(cls, value):
        value = deepcopy(value)
        value['common_patch'] = decode(value['common_patch'])
        return cls(**value)


class Engine:
    def __init__(self, backend, mode, *, guard=None, clock=time.monotonic, worker=None):
        self.api = PublicLedger(backend, guard=guard, clock=clock)
        self.s = vendor.make_controller(self.api, mode)
        self.worker = worker
        self.state = dict(boundary_phase='NOT_ENTERED', todo=set(range(len(self.s.points))), visited=[],
            no_progress=0, previous_macro_seconds=0., decision_counter=0, last_committed_choice_id=None,
            interventions_remaining=2, forced_teacher_channels=set(), used_operation_ids=[])
        self.macros = []
        self.prefix_us = 0
        self.prefix_events = 0
        self.tail_us = 0
        self.error = None
        self.recoveries = []
        self.fallback_details = None

    def enter(self):
        started = self.api.clock()
        response = self.s._accept(self.api.enter())
        self.s.deadline = started + max(0., float(response.get('remaining_real_duration_s',1200))-5)
        self.state['boundary_phase'] = 'READY_PREPARE'
        self.prefix_us = round(self.api.virtual_time*1e6)
        self.prefix_events = len(self.api.events)

    @classmethod
    def restore(cls, backend, token, *, clock=time.monotonic, worker=None):
        token.verify_integrity()
        if token.schema != 'bc-rpi-engine-state-v1' or token.boundary_phase != 'READY_PREPARE':
            raise ValueError('Unsupported resume boundary')
        if (token.teacher_sha256,token.engine_sha256,token.generator_sha256) != (
                vendor.C7_SHA256,source_hash(),operations.source_hash()):
            raise ValueError('Resume implementation hash mismatch')
        if token.implementation_sha256 != vendor.implementation_hash():
            raise ValueError('Resume deploy dependency hash mismatch')
        offsets = token.clock_offsets
        expected_offsets = {'task_elapsed_real_s','interface_deadline_remaining_s',
                            'controller_deadline_remaining_s','last_response_age_real_s'}
        import math
        if set(offsets) != expected_offsets or any(
                v is not None and (type(v) not in (int,float) or not math.isfinite(v))
                for v in offsets.values()):
            raise ValueError('Invalid clock offset schema')
        if offsets['task_elapsed_real_s'] is None or offsets['interface_deadline_remaining_s'] is None:
            raise ValueError('Missing required clock offset')
        if offsets['task_elapsed_real_s'] < 0 or (offsets['last_response_age_real_s'] or 0) < 0:
            raise ValueError('Negative elapsed clock offset')
        controller = decode(token.controller_public_state)
        instance = cls(backend, controller['mode'], guard=vendor.GuardConfig(**token.guard), clock=clock, worker=worker)
        public = decode(token.interface_public_state)
        original_window = (float(public['events'][0]['response'].get('remaining_real_duration_s',1200))
                           if public['events'] and public['events'][0]['action']=='enter' else 1200.)
        original_window=max(0.,min(1200.,original_window))
        if abs(offsets['task_elapsed_real_s']+offsets['interface_deadline_remaining_s']-original_window)>1e-5:
            raise ValueError('Resume deadline does not preserve original entered window')
        if (offsets['controller_deadline_remaining_s'] is not None and
                offsets['task_elapsed_real_s']+offsets['controller_deadline_remaining_s']>original_window-5+1e-5):
            raise ValueError('Resume controller deadline restores extra budget')
        for key, value in public.items():
            setattr(instance.api, key, deepcopy(value))
        now = clock()
        instance.api.started_at = now-offsets['task_elapsed_real_s']
        instance.api.deadline = now+offsets['interface_deadline_remaining_s']
        instance.api._last_response_at = (None if offsets['last_response_age_real_s'] is None else now-offsets['last_response_age_real_s'])
        instance.s = restore_controller(instance.api, controller['mode'], controller)
        instance.s.deadline = (None if offsets['controller_deadline_remaining_s'] is None else now+offsets['controller_deadline_remaining_s'])
        instance.state = decode(token.engine_state)
        instance.prefix_us = token.prefix_virtual_us
        instance.prefix_events = token.accepted_event_count
        assert_ready(instance.s, instance.api, instance.state)
        if (type(token.accepted_event_count) is not int or type(token.prefix_virtual_us) is not int
                or token.accepted_event_count != len(instance.api.events)
                or token.prefix_virtual_us != round(instance.api.virtual_time*1e6)):
            raise ValueError('Resume prefix event/cost denominator mismatch')
        if digest(canonical_events(instance.api.events)) != token.public_ledger_digest:
            raise ValueError('Public ledger digest mismatch')
        if instance.pre_hash() != token.semantic_pre_hash:
            raise ValueError('Restored semantic pre-state differs')
        return instance

    def pre_hash(self):
        return semantic_state_hash(self.s, self.api, self.state)

    def token(self):
        return make_token(self.s,self.api,self.state,source_hash(),operations.source_hash())

    def has_obligations(self):
        if self.s.config.get('upper_bound_stop',True) and len(self.api.cleared)>=16:
            return False
        return bool(self.state['todo'] or vendor.engine._pending(self.s))

    def ready(self):
        self.api.check_learning()
        if self.state['no_progress']>=self.api.guard.no_progress_limit:
            self.api.request_takeover('no_progress_decision_cap')
        vendor.engine._waive_discovery(self.s,self.state['todo'])
        return self.has_obligations()

    def prepare(self):
        assert_ready(self.s,self.api,self.state)
        start = self.api.clock()
        pre_hash = self.pre_hash()
        detached = restore_controller(vendor.NoCalls(),self.s.mode,controller_state(self.s))
        kind,key,defer = vendor.engine._teacher_task(detached,set(self.state['todo']))
        patch = vendor.engine._controller_patch(self.s,detached)
        prepared_hash = digest(encode(controller_state(detached)))
        meta = dict(pre_state_hash=pre_hash,prepared_state_hash=prepared_hash,
            controller_patch_hash=digest(encode(patch)),route_successor=getattr(detached,'route_successor',None),
            teacher_task=dict(kind=kind,key=key,defer=defer))
        if kind=='source':
            center,_ = vendor.engine._circle(detached,detached.polygons[key])
            payload=operations.base_payload(meta,'teacher_service',key,list(center),['A0'])
            payload['budget_cost_slots']=0
            payload['service_state']=encode({name:getattr(detached,name,{}).get(key) for name in
                ('_e2_progress','_e2_failed_clear','failed_clear_points')})
            payload['original_localize_source_sha256']=vendor.C7_SHA256
        else:
            payload=dict(kind='station',index=key,defer=defer,target=list(detached.points[key]),
                         budget_cost_slots=0,pre_state_hash=pre_hash,prepared_state_hash=prepared_hash)
        teacher_id=digest(payload)
        choices=dict(schema='bc-rpi-choice-v1',generator_sha256=operations.source_hash(),
            teacher_id=teacher_id,candidate_ids=[teacher_id],candidates=[payload],eligible=False,rejections=[])
        if self.pre_hash()!=pre_hash:
            raise ValueError('Detached preparation mutated live state')
        return PreparedChoice(choice_id=digest(dict(pre=pre_hash,counter=self.state['decision_counter'])),
            pre_state_hash=pre_hash,prepared_state_hash=prepared_hash,common_patch=patch,meta=meta,
            public_controller=encode(controller_state(detached)),public_engine=encode(self.state),choices=choices,
            prepare_wall_s=max(0.,self.api.clock()-start))

    def expand(self, prepared):
        if prepared.meta['teacher_task']['kind']!='source' or self.s.mode!=4:
            return prepared
        if prepared.expanded:
            return prepared
        if self.worker is None:
            raise ValueError('Independent public candidate worker required')
        start = time.monotonic()
        try:
            result=self.worker.generate(dict(controller=prepared.public_controller,engine=prepared.public_engine,meta=prepared.meta))
            if result['teacher_id']!=prepared.choices['teacher_id'] or result['generator_sha256']!=operations.source_hash():
                raise ValueError('Public worker teacher identity/version mismatch')
            if result['candidate_ids'] != sorted(digest(p) for p in result['candidates']):
                raise ValueError('Public worker retained payload identity/order mismatch')
            prepared.choices=result
        except Exception as exc:
            prepared.choices['rejections'].append('generator_error:' + type(exc).__name__ + ':' + str(exc))
        prepared.expanded=True
        prepared.prepare_wall_s += time.monotonic()-start
        return prepared

    def compare_and_commit(self, prepared):
        if self.state['last_committed_choice_id']==prepared.choice_id:
            raise ValueError('Duplicate prepared-choice commit')
        if self.pre_hash()!=prepared.pre_state_hash or self.state['boundary_phase']!='READY_PREPARE':
            raise ValueError('Prepared choice does not match live pre-state')
        staged = controller_state(self.s)
        staged.update(deepcopy(prepared.common_patch))
        verified = restore_controller(vendor.NoCalls(), self.s.mode, staged)
        if digest(encode(controller_state(verified)))!=prepared.prepared_state_hash:
            raise ValueError('Common patch produced wrong prepared state')
        deadline, api = self.s.deadline, self.s.env
        self.s.__dict__ = staged
        self.s.deadline, self.s.env = deadline, api
        self.state['last_committed_choice_id']=prepared.choice_id
        self.state['decision_counter']+=1
        self.state['boundary_phase']='COMMITTED'

    def execute(self, prepared, action_id):
        if action_id not in prepared.choices['candidate_ids']:
            action_id=prepared.choices['teacher_id']
            rejected_choice=True
        else:
            rejected_choice=False
        index=prepared.choices['candidate_ids'].index(action_id)
        payload=deepcopy(prepared.choices['candidates'][index])
        if digest(payload)!=action_id:
            raise ValueError('Retained action payload changed')
        self.compare_and_commit(prepared)
        before=vendor.engine._progress(self.s,self.api)
        forced_before=sorted(self.state['forced_teacher_channels'])
        before_us=round(self.api.virtual_time*1e6)
        event_start=len(self.api.events)
        service_progress_before=deepcopy(getattr(self.s,'_e2_progress',{}))
        success=False
        is_override=payload['kind'] in ('measure_override','clear_override')
        if is_override:
            if self.s.mode!=4 or type(self.state['interventions_remaining']) is not int or self.state['interventions_remaining']<=0:
                raise ValueError('No valid override budget')
            self.state['interventions_remaining']-=1
            self.state['used_operation_ids'].append(action_id)
        self.state['boundary_phase']='EXECUTING'
        try:
            if payload['kind']=='station':
                self.s.scan_station(payload['index'],defer=payload['defer'])
            elif payload['kind']=='teacher_service':
                self.s.localize(payload['channel'])
            elif payload['kind']=='measure_override':
                self.s.measure(tuple(float(x) for x in payload['target']),payload['channel'])
            elif payload['kind']=='clear_override':
                self.s.clear(tuple(float(x) for x in payload['target']),payload['channel'],certified=payload['certified_before_action'])
            else:
                raise ValueError('Unknown retained operation')
            success=True
        finally:
            delta_us=round(self.api.virtual_time*1e6)-before_us
            record=dict(choice_id=prepared.choice_id,action_id=action_id,payload=payload,
                macro_completed=success,delta_us=delta_us,event_range=[event_start,len(self.api.events)],
                slots_after=self.state['interventions_remaining'],invalid_choice_fell_back=rejected_choice,
                prepare_wall_s=prepared.prepare_wall_s)
            self.macros.append(record)
            if success:
                if payload['kind']=='station':
                    self.state['todo'].remove(payload['index'])
                    self.state['visited'].append(payload['index'])
                elif payload['kind']=='teacher_service':
                    self.state['forced_teacher_channels'].discard(payload['channel'])
                after=vendor.engine._progress(self.s,self.api)
                progressed=vendor.engine._has_progress(before,after)
                self.state['previous_macro_seconds']=delta_us/1e6
                self.state['no_progress']=0 if progressed else self.state['no_progress']+1
                if is_override and not (after[0]>before[0] or after[1]>before[1] or after[3]<before[3]-1e-6):
                    self.state['forced_teacher_channels'].add(payload['channel'])
                self.state['boundary_phase']='READY_PREPARE'
            else:
                self.state['boundary_phase']='PARTIAL_OR_UNKNOWN'
            record['forced_teacher_after']=sorted(self.state['forced_teacher_channels'])
            record['forced_teacher_before']=forced_before
            record['observable_progress_before']=before
            record['observable_progress_after']=after if success else None
            record['service_progress_before']=service_progress_before
            record['service_progress_after']=deepcopy(getattr(self.s,'_e2_progress',{}))
            record['todo_after']=sorted(self.state['todo'])
        return record

    def _takeover(self, reason):
        self.state['boundary_phase']='FALLBACK'
        start=round(self.api.virtual_time*1e6)
        self.api.start_fallback(reason)
        try:
            self.fallback_details=vendor.fallback.run_fallback(self.api)
        except Exception as exc:
            self.error=type(exc).__name__+': '+str(exc)
        finally:
            self.tail_us=round(self.api.virtual_time*1e6)-start

    def run(self, *, on_pre_ready=None, on_choice=None, select=None, capture=False, initial_action=None):
        """Continuation never enters. Call enter() explicitly only for full runs."""
        try:
            if initial_action is not None:
                prepared, action_id = initial_action
                self.execute(prepared,action_id)
            while self.has_obligations() and self.ready():
                token=self.token() if capture or on_pre_ready else None
                captured=on_pre_ready(self,token) if on_pre_ready else None
                prepared=self.prepare()
                if on_choice:
                    on_choice(self,token,prepared,captured)
                action_id=select(self,prepared) if select else prepared.choices['teacher_id']
                self.execute(prepared,action_id)
            certificate=vendor.engine._c7_certificate(self.s,self.api)
            if certificate is None:
                self.api.request_takeover('c7_completion_certificate_missing')
            self.api.exit_certificate=certificate
            self.api.exit()
            self.state['boundary_phase']='EXIT'
        except vendor.FallbackRequired as exc:
            self._takeover(str(exc))
        except vendor.InterfaceFailure as exc:
            self.error=type(exc).__name__+': '+str(exc)
            self.state['boundary_phase']='FAILED_INTERFACE'
        except (RuntimeError,TimeoutError) as exc:
            self.recoveries.append(type(exc).__name__+': '+str(exc))
            self._takeover('c7_controller_recovery')
        except Exception as exc:
            self.error=type(exc).__name__+': '+str(exc)
            self.state['boundary_phase']='FAILED_OTHER'
        return self.report()

    def report(self):
        total_us=round(self.api.virtual_time*1e6)
        accounted=self.prefix_us+sum(m['delta_us'] for m in self.macros)+self.tail_us
        if accounted!=total_us:
            self.error=(self.error+'; ' if self.error else '')+'Microsecond macro partition mismatch'
        return dict(schema='bc-rpi-observable-episode-v1',mode=self.s.mode,
            success=self.api.exited and self.api.exit_certificate is not None and self.error is None,
            normal_exit=self.api.exited,observed_cleared=len(self.api.cleared),
            observed_cleared_channels=sorted(self.api.cleared),certificate=self.api.exit_certificate,
            total_virtual_us=total_us,prefix_virtual_us=self.prefix_us,
            suffix_virtual_us=total_us-self.prefix_us,tail_virtual_us=self.tail_us,
            cost_partition_error_us=total_us-accounted,macros=self.macros,
            events=self.api.events,prefix_event_count=self.prefix_events,
            suffix_accepted_events=len(self.api.events)-self.prefix_events,
            slots_remaining=self.state['interventions_remaining'],fallback_reason=self.api.takeover_reason,
            fallback_details=self.fallback_details,error=self.error,controller_recoveries=self.recoveries,
            runtime_s=self.api.elapsed_real_s,accounting_max_error_s=self.api.accounting_max_error_s,
            controller_final=encode(controller_state(self.s)),engine_final=encode(self.state))
