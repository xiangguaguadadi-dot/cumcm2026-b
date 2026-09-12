"""Registered teacher-equivalence probes and all 120x5 closed-loop development.

No gradients, model/epoch selection, threshold tuning or sealed final testing.
Frozen simulator truth lives only here; Policy/InferenceWorker are public-only.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import math
import time
from .common import ROOT,SEEDS,load,save_new,atomic_json,sha,digest
from .budget import Budget,BudgetStop
from .freeze import verify_sources
from .stage_freeze import verify_preflight,verify_stage_inputs
from .inference_worker import InferenceWorker
from .policy import Policy
from .collect import classify_outcome,IncompleteOutcome
from implementation.deploy import vendor
from implementation.deploy.engine import Engine,CandidateWorker
from implementation.deploy.state import decode
from implementation.evaluator.runtime import new_env,outcome,run_original,canonical_log
from implementation.evaluator.budget import CountedBackend

R2_PATH=ROOT.parent.parent/'A2/BEST_R2.py'
R2_SHA='789096af68fcf470e3973fd93757c556d81d60f3fe3910c5991c537def3f91cc'

def frozen_models(calibration):
    directory=(ROOT/calibration).resolve();directory.relative_to(ROOT)
    summary=load(directory/'summary.json');margins=load(directory/'margins.json')
    if summary['status']!='calibration_complete_three_frozen_margins' or summary['completed_worlds']!=24:
        raise ValueError('Complete 24-world calibration required for all three policies')
    if margins['world_results_sha256']!=sha(directory/'world_results.json'):
        raise ValueError('Frozen calibration rows changed')
    if margins['registration_sha256']!=sha(directory/'registration.json'):
        raise ValueError('Frozen calibration registration changed')
    if [m['seed'] for m in margins['models']]!=SEEDS or [m['seed'] for m in margins['margins']]!=SEEDS:
        raise ValueError('Frozen seed set/order differs')
    models=[]
    for model,margin in zip(margins['models'],margins['margins']):
        if sha(ROOT/model['path'])!=model['sha256'] or margin['checkpoint_sha256']!=model['sha256']:
            raise ValueError('Frozen checkpoint/margin identity mismatch')
        q=margin['margin']
        if type(q) not in (int,float) or not math.isfinite(q) or q<0 or margin['world_count']!=24:
            raise ValueError('Invalid frozen margin')
        definition=dict(seed=model['seed'],checkpoint_sha256=model['sha256'],margin=q,strict_extra_gain=.0005,
            selector_sha256=sha(ROOT/'policy.py'),selection_sha256=sha(ROOT/'selection.py'),
            feature_sha256=sha(ROOT/'features.py'),actor_worker_sha256=sha(ROOT/'actor_worker.py'),
            max_interventions=2,teacher_sha256=vendor.C7_SHA256)
        models.append(dict(model,margin=float(q),policy_definition=definition,policy_sha256=digest(definition)))
    return models

class AuditedWorker:
    """Record the exact already-built public input; no extra neural forward.

    Input capture happens inside the instrumented selector timer. Public
    prepared-state copying happens afterwards and is reported separately.
    """
    def __init__(self,worker):self.inner=worker;self.records=[];self.choice_id=None;self.prefix_event_count=None
    def __getattr__(self,name):return getattr(self.inner,name)
    def reset_episode(self):self.records=[];self.choice_id=None;self.prefix_event_count=None
    def score(self,snapshot):
        started=time.monotonic()
        row=dict(choice_id=self.choice_id,public_prefix_event_count=self.prefix_event_count,
            public_snapshot=deepcopy(snapshot),public_snapshot_sha256=digest(snapshot),
            checkpoint_sha256=self.inner.checkpoint_sha)
        row['input_capture_wall_s_inside_selector']=time.monotonic()-started
        self.records.append(row)
        try:
            response=self.inner.score(snapshot)
            row.update(success=True,worker_request_id=response['request_id'],raw_scores_float32=list(response['scores']))
            return response
        except BaseException as exc:
            row.update(success=False,error=type(exc).__name__+': '+str(exc));raise

def run_neural(world,budget,run_id,model,policy,candidate_worker):
    if sha(ROOT/model['path'])!=model['sha256']:raise ValueError('Frozen weight file changed before run')
    budget.start(run_id,'full',dict(world_sha256=world['world_sha256'],mode=world['mode'],
        policy='round1_neural_'+str(model['seed']),policy_sha256=model['policy_sha256'],
        checkpoint_sha256=model['sha256'],force_teacher_probe=policy.force_teacher))
    started=time.monotonic();cpu_started=time.process_time();env=new_env(world);policy.reset_episode()
    scorer=policy.worker;scorer.reset_episode();audit_capture_wall_s=0.
    engine=Engine(CountedBackend(env,budget),world['mode'],worker=candidate_worker)
    def select_with_public_audit(e,p):
        nonlocal audit_capture_wall_s
        before=time.monotonic();scorer.choice_id=p.choice_id;scorer.prefix_event_count=len(e.api.events)
        audit_capture_wall_s+=time.monotonic()-before
        try:return policy.select(e,p)
        finally:
            before=time.monotonic()
            if scorer.records and scorer.records[-1]['choice_id']==p.choice_id:
                if len(e.api.events)!=scorer.prefix_event_count:raise ValueError('Selector changed public interface history')
                record=scorer.records[-1];record['prepared_public']=deepcopy(p.to_json())
                record['prepared_public_sha256']=digest(record['prepared_public'])
                record['post_selection_capture_wall_s_outside_selector']=time.monotonic()-before
            audit_capture_wall_s+=time.monotonic()-before
    try:
        engine.enter();report=engine.run(select=select_with_public_audit)
    except Exception as exc:
        engine.error=type(exc).__name__+': '+str(exc);report=engine.report()
    result=outcome(env,report,run_id=run_id,kind='full',wall_s=time.monotonic()-started,
        extra=dict(actual_policy_id='round1_neural_'+str(model['seed']),policy_sha256=model['policy_sha256'],
            checkpoint_sha256=model['sha256'],margin=model['margin'],force_teacher_probe=policy.force_teacher,
            selector_decisions=policy.decisions,main_process_cpu_s=time.process_time()-cpu_started,
            selector_public_input_audit=scorer.records,
            evaluator_public_audit_capture_wall_s_outside_selector=audit_capture_wall_s,
            selector_input_capture_wall_s_included=sum(r['input_capture_wall_s_inside_selector'] for r in scorer.records),
            candidate_worker_cpu_s=None,worker_cold_start_excluded_from_episode=True))
    if report['total_virtual_us']!=env._virtual_us:
        result['success']=False;result['ledger_error']='private/public total differs'
    budget.finish(result['success'],dict(world_sha256=world['world_sha256'],mode=world['mode'],
        virtual_us=env._virtual_us,error=report['error'],policy_sha256=model['policy_sha256']))
    return result

class Recorder:
    def __init__(self,out,budget,freeze):self.out=out;self.budget=budget;self.freeze=freeze;self.runs=[]
    def record(self,result,world,policy_id,**identity):
        path=self.out/'runs'/(result['run_id']+'.json.gz');save_new(path,result)
        row=dict(run_id=result['run_id'],path=str(path.relative_to(ROOT)),world_id=world['world_id'],
            world_sha256=world['world_sha256'],role=world['role'],mode=world['mode'],index=world['index'],
            group=world['group'],actual_policy_id=policy_id,success=result['success'],n=result['true_terminal_n'],
            cleared=result['cleared'],normal_exit=result['normal_exit'],kind=result['kind'],
            modeled_full_virtual_us=result['modeled_full_virtual_us'],
            seconds_per_source=result['modeled_full_virtual_us']/1e6/result['true_terminal_n'],
            actual_execution_wall_s=result['actual_execution_wall_s'],
            fallback_reason=result['episode'].get('fallback_reason'),error=result['episode'].get('error'),**identity)
        self.runs.append(row);atomic_json(self.out/'index.json',dict(schema='bc-rpi-r1-closedloop-runs-v1',runs=self.runs))
        verify_sources(self.freeze);classify_outcome(result,self.budget.data['stopped_for_unknown_acceptance'])
        return row

def exact_teacher_probe(direct,neural):
    episode=neural['episode'];used=decode(episode['engine_final'])['used_operation_ids']
    return dict(both_normal_allclear=direct['success'] and neural['success'],
        exact_requests_and_observations=canonical_log(direct['environment_log'])==canonical_log(neural['environment_log']),
        exact_total_virtual_us=direct['modeled_full_virtual_us']==neural['modeled_full_virtual_us'],
        same_source_denominator=direct['true_terminal_n']==neural['true_terminal_n'],
        zero_interventions=used==[] and episode['slots_remaining']==2,
        every_selector_forced_teacher=all(r['selected_id']==r['teacher_id'] for r in neural['extra']['selector_decisions']),
        actual_public_neural_forward_seen=any(r.get('model_scored') for r in neural['extra']['selector_decisions']))

def create_workers(models,budget):
    workers={}
    try:
        for model in models:
            worker=InferenceWorker(ROOT/model['path'],model['sha256'],seed=model['seed'],epoch=model['epoch'],
                parameter_sha=model['parameter_sha256'])
            workers[model['seed']]=worker;budget.register_worker(worker.process.pid)
        return workers
    except BaseException:
        for worker in workers.values():budget.unregister_worker(worker.process.pid);worker.close()
        raise

def run(stage,calibration,out,preflight,acceptance_path,compatibility=None):
    if stage not in ('compatibility','development'):raise ValueError('Wrong registered evaluation stage')
    out=(ROOT/out).resolve();out.relative_to(ROOT);acceptance=load(acceptance_path)
    models=frozen_models(calibration)
    required=['world_manifest.json','registration.json','compatibility_registration.json']+[
        str((ROOT/calibration/name).relative_to(ROOT)) for name in ('summary.json','margins.json','world_results.json','registration.json')]
    required+=[m['path'] for m in models]
    if stage=='development':
        if compatibility is None:raise ValueError('Completed teacher-equivalence compatibility required')
        required.append(compatibility)
        if acceptance.get('compatibility_summary_sha256')!=sha(ROOT/compatibility/'summary.json'):
            raise ValueError('Coordinator did not accept this exact compatibility result')
    freeze,input_manifest=verify_preflight(preflight,acceptance,'evaluation_accepted',stage='evaluation',required=required)
    if sha(ROOT/'world_manifest.json')!=load(ROOT/'registration.json')['manifest_sha256']:
        raise ValueError('World registry no longer matches original registration')
    margins_sha=sha(ROOT/calibration/'margins.json')
    if acceptance.get('calibration_margins_sha256')!=margins_sha:
        raise ValueError('Accepted frozen margins differ')
    if sha(R2_PATH)!=R2_SHA:raise ValueError('Latest registered non-RL Q4 R2 changed')
    if stage=='compatibility':
        worlds=load(ROOT/'compatibility_registration.json')['worlds'];expected=12
    else:
        if compatibility is None:raise ValueError('Completed teacher-equivalence compatibility required')
        compat=load(ROOT/compatibility/'summary.json')
        if compat['status']!='compatibility_complete_exact_teacher_equivalence' or compat['completed_worlds']!=12:
            raise ValueError('Compatibility not fully accepted')
        if compat['source_freeze_sha256']!=sha(ROOT/preflight/'source_freeze.json') or compat['margins_sha256']!=margins_sha:
            raise ValueError('Compatibility used a different evaluation implementation or model/margin')
        worlds=[w for w in load(ROOT/'world_manifest.json')['worlds'] if w['role']=='development'];expected=120
    if len(worlds)!=expected or len({w['world_sha256'] for w in worlds})!=expected:
        raise ValueError('Registered closed-loop world set differs')
    if out.exists():raise FileExistsError('Fresh evaluation output required')
    out.mkdir(parents=True);budget=Budget();before_calls=budget.data['business_calls'];before_runs=budget.data['executions_started']
    budget.set_phase(stage);recorder=Recorder(out,budget,freeze)
    candidate_launch_started=time.monotonic();candidate=CandidateWorker()
    candidate_launch_wall_s=time.monotonic()-candidate_launch_started;budget.register_worker(candidate.process.pid)
    workers={};world_rows=[];status='running_'+stage;reason=None;active=None
    save_new(out/'registration.json',dict(schema='bc-rpi-r1-'+stage+'-registration-v1',
        world_ids=[w['world_id'] for w in worlds],models=models,calibration_margins_sha256=margins_sha,
        policy_order=['c7','neural_912101_teacher_forced'] if stage=='compatibility' else ['c7','q4_r2']+['neural_'+str(s) for s in SEEDS],
        c7_sha256=vendor.C7_SHA256,q4_r2_sha256=R2_SHA,
        source_freeze_sha256=sha(ROOT/preflight/'source_freeze.json'),acceptance_sha256=sha(acceptance_path),
        before_calls=before_calls,before_executions=before_runs,
        no_selection_or_tuning_from_this_stage=True,no_deployment_promotion=True))
    try:
        workers=create_workers(models[:1] if stage=='compatibility' else models,budget)
        policies={m['seed']:Policy(AuditedWorker(workers[m['seed']]),m['margin'],force_teacher=stage=='compatibility')
            for m in models if m['seed'] in workers}
        save_new(out/'worker_readiness.json',dict(neural_workers=[dict(seed=s,identity=w.identity,startup_wall_s=w.startup_wall_s)
            for s,w in workers.items()],candidate_worker_pid=candidate.process.pid,
            candidate_process_launch_wall_s=candidate_launch_wall_s,candidate_ready_wall_s=None,
            candidate_has_no_readiness_handshake=True,candidate_first_request_lazy_setup_in_selector_latency=True,
            note='Cold neural ready time is measured outside episode time. Candidate process launch is not proof of ready time; its first lazy setup remains in the measured selector.'))
        for world in worlds:
            active=world['world_id'];verify_sources(freeze);verify_stage_inputs(input_manifest,'evaluation',required)
            prefix=f'r1_{stage}_v1_w{world["index"]:03d}';rows=[]
            direct=run_original(world,budget,prefix+'_c7');rows.append(recorder.record(direct,world,'c7',entry_sha256=vendor.C7_SHA256))
            if stage=='compatibility':
                model=models[0];result=run_neural(world,budget,prefix+'_teacher_probe',model,policies[model['seed']],candidate)
                rows.append(recorder.record(result,world,'neural_912101_teacher_forced',policy_sha256=model['policy_sha256']))
                check=exact_teacher_probe(direct,result);save_new(out/'checks'/f'w{world["index"]:03d}.json',
                    dict(world_id=world['world_id'],checks=check))
                if not all(check.values()):raise ValueError('New selector exact-teacher compatibility failed')
            else:
                latest=run_original(world,budget,prefix+'_q4_r2',entry=R2_PATH)
                # Legacy runtime labels an arbitrary entry as latest_q3_direct;
                # mode=4 plus exact entry SHA and this index identify actual R2.
                rows.append(recorder.record(latest,world,'q4_r2',entry_sha256=R2_SHA,
                    legacy_runtime_policy_label_is_not_actual_identity=True))
                for model in models:
                    result=run_neural(world,budget,prefix+'_seed_'+str(model['seed']),model,policies[model['seed']],candidate)
                    rows.append(recorder.record(result,world,'neural_'+str(model['seed']),policy_sha256=model['policy_sha256'],
                        checkpoint_sha256=model['sha256'],margin=model['margin']))
            world_rows.append(dict(world_id=world['world_id'],world_sha256=world['world_sha256'],index=world['index'],
                group=world['group'],role=world['role'],status='complete',all_policies_normal_allclear=all(r['success'] for r in rows),runs=rows))
            atomic_json(out/'world_results.json',dict(schema='bc-rpi-r1-closedloop-worlds-v1',worlds=world_rows))
            print(dict(stage=stage,completed_worlds=len(world_rows),registered_worlds=expected,
                calls=budget.data['business_calls'],runs=budget.data['executions_started']),flush=True)
        verify_stage_inputs(input_manifest,'evaluation',required)
        status='compatibility_complete_exact_teacher_equivalence' if stage=='compatibility' else 'development_complete_no_tuning_or_promotion'
    except BudgetStop as exc:status=stage+'_incomplete_resource';reason=str(exc)
    except MemoryError as exc:status=stage+'_incomplete_resource';reason='MemoryError: '+str(exc)
    except IncompleteOutcome as exc:status=stage+'_incomplete_'+exc.kind;reason=str(exc)
    except BaseException as exc:status=stage+'_incomplete_engineering';reason=type(exc).__name__+': '+str(exc);raise
    finally:
        for worker in workers.values():budget.unregister_worker(worker.process.pid);worker.close()
        budget.unregister_worker(candidate.process.pid);candidate.close();budget.set_status(status)
        atomic_json(out/'world_results.json',dict(schema='bc-rpi-r1-closedloop-worlds-v1',worlds=world_rows))
        save_new(out/'summary.json',dict(status=status,stop_reason=reason,registered_worlds=expected,
            completed_worlds=len(world_rows),registered_seeds=SEEDS,
            registered_world_statuses=[dict(world_id=w['world_id'],
                status='complete' if any(r['world_id']==w['world_id'] for r in world_rows)
                else 'incomplete' if w['world_id']==active else 'not_started_after_stop') for w in worlds],
            source_freeze_sha256=sha(ROOT/preflight/'source_freeze.json'),margins_sha256=margins_sha,
            actual_calls=budget.data['business_calls']-before_calls,
            actual_executions=budget.data['executions_started']-before_runs,current_run=budget.data['current_run'],
            unknown_cost_calls=budget.data['unknown_cost_calls'],real_failed_runs_retained=sum(not r['success'] for r in recorder.runs),
            zero_gradient_updates=True,no_checkpoint_threshold_selection=True,no_deployment_promotion=True))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=('compatibility','development'),required=True)
    p.add_argument('--calibration',required=True);p.add_argument('--out',required=True);p.add_argument('--preflight',required=True)
    p.add_argument('--acceptance',required=True);p.add_argument('--compatibility')
    a=p.parse_args();run(a.stage,a.calibration,a.out,a.preflight,a.acceptance,a.compatibility)
