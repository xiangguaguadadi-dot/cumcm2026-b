"""Frozen three-seed argmax calibration with shared exact-identity full tails.

Trusted evaluator owns world truth and branch handles. Neural subprocesses see
only public feature snapshots. Every seed's a* is saved before any tail labels
at that sampled state are executed or inspected.
"""
from __future__ import annotations
import argparse
import time
from .common import ROOT,REPO,SEEDS,load,save_new,atomic_json,sha,digest
from .budget import Budget,BudgetStop
from .freeze import verify_sources
from .stage_freeze import verify_preflight,verify_stage_inputs
from .features import build_snapshot
from .inference_worker import InferenceWorker
from .selection import predicted_choice
from .calibration_math import world_residual,margin_from_worlds
from .collect import classify_outcome,terminal_cost,IncompleteOutcome
from implementation.deploy.engine import CandidateWorker
from implementation.deploy.state import decode
from implementation.evaluator.runtime import run_full,run_suffix,sample_handles,ENV_PIN
from implementation.evaluator.g0_fixtures import expand_handle
from implementation.evaluator.g1 import verify_replay,continuation_identity

def chosen_models(fit):
    fit=(ROOT/fit).resolve();fit.relative_to(ROOT);summary=load(fit/'summary.json')
    if summary['status']!='three_seed_fit_complete_not_calibrated' or summary['completed_seeds']!=SEEDS:
        raise ValueError('All three complete fixed fits are required')
    result=[]
    for row in summary['results']:
        choice=row['selected'];path=fit/choice['path']
        if sha(path)!=choice['sha256']:raise ValueError('Selected weight identity changed')
        if (choice['model_source_sha256']!=sha(ROOT/'model.py') or
                choice['feature_implementation_sha256']!=sha(ROOT/'features.py')):
            raise ValueError('Chosen network was fitted with a different model/feature implementation')
        result.append(dict(seed=row['seed'],epoch=choice['epoch'],path=str(path.relative_to(ROOT)),
            sha256=choice['sha256'],parameter_sha256=choice['parameter_sha256'],
            model_source_sha256=choice['model_source_sha256'],feature_implementation_sha256=choice['feature_implementation_sha256'],
            dataset_manifest_sha256=summary['dataset_manifest_sha256']))
    if [r['seed'] for r in result]!=SEEDS:raise ValueError('Selected seed set/order differs')
    return result

def cache_identity(world,handle,action_id,pi_sha,source_sha):
    handle.verify(world)
    if action_id not in handle.prepared.choices['candidate_ids']:raise ValueError('Cache action not retained')
    value=dict(world_sha256=world['world_sha256'],world_id=world['world_id'],
        fork_bundle_sha256=handle.bundle_integrity_sha256,private_integrity_sha256=handle.private_integrity_sha256,
        resume_token_sha256=digest(handle.token.to_json()),prepared_sha256=digest(handle.prepared.to_json()),
        choice_id=handle.prepared.choice_id,action_id=action_id,continuation_policy_sha256=pi_sha,
        environment_sha256=ENV_PIN,stage_source_freeze_sha256=source_sha,
        billing='frozen-v1 integer microsecond physical ledger; complete a+C7 tail')
    return dict(identity=value,key_sha256=digest(value))

class Recorder:
    def __init__(self,out,budget,freeze):self.out=out;self.budget=budget;self.freeze=freeze;self.runs=[]
    def record(self,result,world,family,**metadata):
        path=self.out/'runs'/(result['run_id']+'.json.gz');save_new(path,result)
        row=dict(run_id=result['run_id'],path=str(path.relative_to(ROOT)),world_id=world['world_id'],
            world_sha256=world['world_sha256'],role='calibration',index=world['index'],group=world['group'],
            family=family,success=result['success'],n=result['true_terminal_n'],
            modeled_full_virtual_us=result['modeled_full_virtual_us'],kind=result['kind'],**metadata)
        self.runs.append(row);atomic_json(self.out/'index.json',dict(schema='bc-rpi-r1-calibration-runs-v1',runs=self.runs))
        verify_sources(self.freeze)
        classify_outcome(result,self.budget.data['stopped_for_unknown_acceptance'])
        return row

def world_calibration(world,out,recorder,candidate_worker,workers,models,pi_sha,source_sha):
    directory=out/'worlds'/f'w{world["index"]:03d}';prefix=f'r1_cal_v1_w{world["index"]:03d}'
    baseline,handles=run_full(world,recorder.budget,prefix+'_rollin',worker=candidate_worker,capture=True)
    recorder.record(baseline,world,'shared_c7_rollin')
    if not baseline['success']:raise ValueError('Calibration C7 roll-in failed; do not omit world')
    selected=sample_handles(handles,2)
    save_new(directory/'sampling.json',dict(world_id=world['world_id'],world_sha256=world['world_sha256'],
        rollin_run_id=baseline['run_id'],all_public_source_boundary_count=len(handles),
        all_public_boundaries=[dict(source_index=h.source_index,choice_id=h.prepared.choice_id,
            prefix_virtual_us=h.token.prefix_virtual_us,teacher_task=h.prepared.meta['teacher_task']) for h in handles],
        selected_source_indexes=[h.source_index for h in selected],max_sampled_states=2,
        sampling='m=min(2,n); floor(k*(n-1)/(m-1)); m=1 ->0; public sequence only'))
    if not selected:raise ValueError('Calibration world lacks sampled states; margin remains incomplete')
    by_seed={seed:[] for seed in SEEDS}
    for state_index,handle in enumerate(selected):
        dest=directory/f's{state_index:02d}'
        try:expand_handle(handle,candidate_worker)
        except AssertionError as exc:
            if any(str(v).startswith('generator_error:') and 'MemoryError' in str(v)
                   for v in handle.prepared.choices['rejections']):
                raise MemoryError('Frozen candidate worker reported MemoryError') from exc
            raise
        handle.verify(world)
        save_new(dest/'handle.json.gz',handle.to_json())
        snapshot=build_snapshot(handle.prepared,decode(handle.token.interface_public_state)['events'])
        save_new(dest/'public_snapshot.json',snapshot);teacher=snapshot['teacher_id'];choices=[]
        # All three public-only decisions are fixed before this state's labels.
        for model in models:
            if sha(ROOT/model['path'])!=model['sha256']:raise ValueError('Frozen selected weight changed')
            scored=workers[model['seed']].score(snapshot)
            chosen=predicted_choice(snapshot['candidate_ids'],teacher,scored['scores'])
            choices.append(dict(seed=model['seed'],checkpoint_sha256=model['sha256'],epoch=model['epoch'],
                candidate_id=chosen['candidate_id'],teacher_id=teacher,predicted_gain=chosen['predicted_gain'],
                candidate_ids=snapshot['candidate_ids'],raw_scores_float32=scored['scores'],gains=chosen['gains'],
                inference_roundtrip_wall_s=scored['roundtrip_wall_s'],forward_wall_s=scored['forward_wall_s'],
                tensor_build_wall_s=scored['tensor_build_wall_s']))
        wanted=sorted({teacher,*[c['candidate_id'] for c in choices]})
        cache={action:cache_identity(world,handle,action,pi_sha,source_sha) for action in wanted}
        frozen=dict(schema='bc-rpi-r1-calibration-fixed-argmax-v1',world_id=world['world_id'],
            world_sha256=world['world_sha256'],state_index=state_index,source_index=handle.source_index,
            choice_id=handle.prepared.choice_id,teacher_id=teacher,all_retained_candidate_ids=snapshot['candidate_ids'],
            selected_by_seed=choices,evaluated_unique_action_ids=wanted,cache_identities=cache,
            all_seed_choices_frozen_before_any_state_tail=True,
            calls_at_selection_freeze=recorder.budget.data['business_calls'],
            executions_at_selection_freeze=recorder.budget.data['executions_started'])
        save_new(dest/'selection_before_labels.json',frozen)
        results={};origin_rows={}
        for action_index,action_id in enumerate(wanted):
            verify_sources(recorder.freeze)
            if cache_identity(world,handle,action_id,pi_sha,source_sha)!=cache[action_id]:raise ValueError('Cache identity changed')
            result,_=run_suffix(world,recorder.budget,prefix+f'_s{state_index:02d}_a{action_index:02d}',
                handle,action_id,worker=candidate_worker)
            row=recorder.record(result,world,'unique_selected_or_a0_tail',state_index=state_index,
                action_id=action_id,teacher_id=teacher,choice_id=handle.prepared.choice_id,
                cache_key_sha256=cache[action_id]['key_sha256'])
            results[action_id]=result;origin_rows[action_id]=row
            if action_id==teacher:
                check=verify_replay(baseline,result,[]);save_new(dest/'a0_replay_check.json',check)
                if not all(check.values()):raise ValueError('Calibration A0 full tail not equivalent to roll-in')
        ref=terminal_cost(results[teacher],handle.token.prefix_virtual_us);seed_rows=[];uses={}
        for choice in choices:
            action=choice['candidate_id'];gain=ref-terminal_cost(results[action],handle.token.prefix_virtual_us)
            row=dict(choice,world_id=world['world_id'],world_sha256=world['world_sha256'],state_index=state_index,
                source_index=handle.source_index,choice_id=handle.prepared.choice_id,realized_gain=gain,
                optimistic_residual=choice['predicted_gain']-gain,selected_origin_run_id=results[action]['run_id'],
                reference_origin_run_id=results[teacher]['run_id'],selected_cache_key_sha256=cache[action]['key_sha256'],
                reference_cache_key_sha256=cache[teacher]['key_sha256'],prefix_virtual_us=handle.token.prefix_virtual_us,
                selected_normalized_suffix_cost=terminal_cost(results[action],handle.token.prefix_virtual_us),
                reference_normalized_suffix_cost=ref,terminal_n=baseline['true_terminal_n'],
                selected_success=results[action]['success'],reference_success=results[teacher]['success'],
                actual_new_calls_for_this_read=0,origin_actual_execution_counted_once=True)
            by_seed[choice['seed']].append(row);seed_rows.append(row)
            for role,aid in [('selected',action),('reference',teacher)]:uses.setdefault(aid,[]).append(dict(seed=choice['seed'],role=role))
        save_new(dest/'complete_labels.json',dict(status='complete',seeds=seed_rows,
            unique_action_outcomes=[dict(origin_rows[a],normalized_suffix_cost=terminal_cost(results[a],handle.token.prefix_virtual_us),
                consumers=uses[a]) for a in wanted],selection_before_labels_sha256=sha(dest/'selection_before_labels.json')))
    return [dict(seed=seed,world_id=world['world_id'],world_sha256=world['world_sha256'],index=world['index'],
        group=world['group'],status='complete',states=by_seed[seed],
        world_max_optimistic_residual=world_residual(by_seed[seed])) for seed in SEEDS]

def run(fit,out,preflight,acceptance_path):
    out=(ROOT/out).resolve();out.relative_to(ROOT)
    models=chosen_models(fit)
    required=['world_manifest.json','registration.json',str((ROOT/fit/'summary.json').relative_to(ROOT))]+[m['path'] for m in models]
    acceptance=load(acceptance_path);freeze,input_manifest=verify_preflight(preflight,acceptance,'calibration_accepted',
        stage='calibration',required=required)
    if sha(ROOT/'world_manifest.json')!=load(ROOT/'registration.json')['manifest_sha256']:
        raise ValueError('World registry no longer matches original registration')
    if acceptance.get('selected_checkpoint_sha256s')!=[m['sha256'] for m in models]:
        raise ValueError('Accepted selected-model set differs')
    worlds=[w for w in load(ROOT/'world_manifest.json')['worlds'] if w['role']=='calibration']
    if len(worlds)!=24 or len({w['world_sha256'] for w in worlds})!=24:raise ValueError('Wrong calibration registry')
    if out.exists():raise FileExistsError('Fresh calibration output required')
    out.mkdir(parents=True);source_sha=sha(ROOT/preflight/'source_freeze.json');pi=continuation_identity();pi_sha=digest(pi)
    budget=Budget();before_calls=budget.data['business_calls'];before_runs=budget.data['executions_started']
    budget.set_phase('calibration');recorder=Recorder(out,budget,freeze);candidate=CandidateWorker()
    budget.register_worker(candidate.process.pid);workers={};rows=[];status='calibrating';reason=None;active=None
    save_new(out/'registration.json',dict(schema='bc-rpi-r1-calibration-registration-v1',
        world_ids=[w['world_id'] for w in worlds],models=models,source_freeze_sha256=source_sha,
        acceptance_sha256=sha(acceptance_path),continuation_policy=pi,continuation_policy_sha256=pi_sha,
        cache_scope='exact identity within one sampled world/state only; shared actual execution, no cross-state cache',
        before_calls=before_calls,before_executions=before_runs))
    try:
        for model in models:
            worker=InferenceWorker(ROOT/model['path'],model['sha256'],seed=model['seed'],epoch=model['epoch'],
                parameter_sha=model['parameter_sha256']);workers[model['seed']]=worker;budget.register_worker(worker.process.pid)
        save_new(out/'worker_readiness.json',dict(workers=[dict(seed=s,identity=w.identity,startup_wall_s=w.startup_wall_s)
            for s,w in workers.items()]))
        for world in worlds:
            active=world['world_id'];verify_sources(freeze);verify_stage_inputs(input_manifest,'calibration',required)
            rows.extend(world_calibration(world,out,recorder,candidate,workers,models,pi_sha,source_sha))
            atomic_json(out/'world_results.json',dict(schema='bc-rpi-r1-calibration-worlds-v1',rows=rows))
            print(dict(calibration_world=world['index'],completed_worlds=len(rows)//3,calls=budget.data['business_calls']),flush=True)
        verify_stage_inputs(input_manifest,'calibration',required)
        margins=[dict(seed=seed,checkpoint_sha256=next(m['sha256'] for m in models if m['seed']==seed),
            **margin_from_worlds([r for r in rows if r['seed']==seed],[w['world_id'] for w in worlds])) for seed in SEEDS]
        save_new(out/'margins.json',dict(schema='bc-rpi-r1-frozen-calibration-margins-v1',models=models,margins=margins,
            world_results_sha256=sha(out/'world_results.json'),registration_sha256=sha(out/'registration.json')))
        status='calibration_complete_three_frozen_margins'
    except BudgetStop as exc:status='calibration_incomplete_resource';reason=str(exc)
    except MemoryError as exc:status='calibration_incomplete_resource';reason='MemoryError: '+str(exc)
    except IncompleteOutcome as exc:status='calibration_incomplete_'+exc.kind;reason=str(exc)
    except BaseException as exc:status='calibration_incomplete_engineering';reason=type(exc).__name__+': '+str(exc);raise
    finally:
        for worker in workers.values():budget.unregister_worker(worker.process.pid);worker.close()
        budget.unregister_worker(candidate.process.pid);candidate.close();budget.set_status(status)
        atomic_json(out/'world_results.json',dict(schema='bc-rpi-r1-calibration-worlds-v1',rows=rows))
        save_new(out/'summary.json',dict(status=status,stop_reason=reason,completed_worlds=len(rows)//3,
            registered_world_statuses=[dict(world_id=w['world_id'],seed=seed,
                status='complete' if any(r['world_id']==w['world_id'] and r['seed']==seed for r in rows)
                else 'incomplete' if w['world_id']==active else 'not_started_after_stop') for w in worlds for seed in SEEDS],
            registered_worlds=24,registered_seeds=SEEDS,actual_calls=budget.data['business_calls']-before_calls,
            actual_executions=budget.data['executions_started']-before_runs,current_run=budget.data['current_run'],
            unknown_cost_calls=budget.data['unknown_cost_calls'],zero_gradient_updates_in_calibration=True))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--fit',required=True);p.add_argument('--out',required=True)
    p.add_argument('--preflight',required=True);p.add_argument('--acceptance',required=True)
    a=p.parse_args();run(a.fit,a.out,a.preflight,a.acceptance)
