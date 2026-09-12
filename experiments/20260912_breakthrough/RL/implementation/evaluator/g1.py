"""G1 finite, privileged O1/O2 headroom diagnostic. No neural training exists here."""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import statistics
import sys
import time
import unittest
from ..deploy import vendor,operations
from ..deploy.engine import CandidateWorker
from ..deploy.state import digest,decode
from .budget import Budget,BudgetStop,IMPL,atomic_json
from .runtime import (load,save_new,worlds,run_full,run_suffix,sample_handles,canonical_log)
from .g0 import freeze_sources,verify_sources
from .g0_fixtures import expand_handle
from .source_archive import archive_sources


def continuation_identity():
    return dict(type='frozen_pi0_A0_only',teacher_sha256=vendor.C7_SHA256,
        deploy_implementation_sha256=vendor.implementation_hash(),generator_sha256=operations.source_hash(),
        gamma=1,neural_weights=None,online_exploration=False)


def normalized_cost(result):
    n=result['true_terminal_n']
    if type(n) is not int or not 10<=n<=16:raise ValueError('Invalid terminal source-count label')
    return result['modeled_full_virtual_us']/(1_000_000_000*n)+(0. if result['success'] else 100.)


def oracle_key(result,plan):
    # Zero intervention wins exact cost ties; remaining ties use retained IDs.
    return (normalized_cost(result),len(plan),tuple((p['choice_id'],p['action_id']) for p in plan))


def should_replace(best_result,best_plan,result,plan):
    return oracle_key(result,plan)<oracle_key(best_result,best_plan)


def verify_replay(reference,replay,plan):
    used=decode(replay['episode']['engine_final'])['used_operation_ids']
    expected=[p['action_id'] for p in plan]
    full_plan=replay.get('extra',{}).get('applied_plan')
    applied=used==expected and (replay['kind']=='suffix' or full_plan==plan)
    return dict(all_cleared=bool(replay['success']),
        exact_total_us=reference['modeled_full_virtual_us']==replay['modeled_full_virtual_us'],
        exact_requests_and_observations=canonical_log(reference['environment_log'])==canonical_log(replay['environment_log']),
        source_count_same=reference['true_terminal_n']==replay['true_terminal_n'],
        all_planned_interventions_applied=applied,
        slots_exact=replay['episode']['slots_remaining']==2-len(plan))


def aggregate(world_rows,registered_count=24):
    complete=[r for r in world_rows if r['status']=='complete']
    if len(complete)!=registered_count:
        return dict(status='inconclusive_incomplete_registered_world_set',completed_worlds=len(complete),
            registered_worlds=registered_count,whole_set_means=None,
            conclusion='No positive-headroom or no-headroom conclusion from a partial set')
    c7=statistics.mean(r['c7_seconds_per_source'] for r in complete)
    o1=statistics.mean(r['o1_seconds_per_source'] for r in complete)
    o2=statistics.mean(r['o2_seconds_per_source'] for r in complete)
    g1=100*(1-o1/c7);g2=100*(1-o2/c7)
    groups={}
    for group in sorted({r['group'] for r in complete}):
        rows=[r for r in complete if r['group']==group]
        groups[group]=dict(worlds=len(rows),c7=statistics.mean(r['c7_seconds_per_source'] for r in rows),
            o1=statistics.mean(r['o1_seconds_per_source'] for r in rows),o2=statistics.mean(r['o2_seconds_per_source'] for r in rows))
    return dict(status='positive_finite_headroom_stop_before_g2' if max(g1,g2)>=2 else 'below_2pct_stop_current_action_space',
        completed_worlds=len(complete),registered_worlds=registered_count,
        whole_set_means=dict(c7_seconds_per_source=c7,o1_seconds_per_source=o1,o2_seconds_per_source=o2),
        o1_relative_improvement_pct=g1,o2_relative_improvement_pct=g2,
        aggregation='Arithmetic mean of each world total_virtual_seconds / true source count; relative difference of those means',
        total_source_count=sum(r['n'] for r in complete),groups=groups,
        branch_failures_retained=sum(r['failed_branches'] for r in complete),
        interpretation='O1 is finite hindsight optimum over up to four C7 source boundaries and retained operations; O2 is greedy two-intervention hindsight on the changed trajectory, not a global two-step optimum or observable policy',
        next_stage_authorized=False,neural_training_executed=False)


class CampaignBudget(Budget):
    def __init__(self,stage,pi_sha):
        super().__init__();self.stage=stage;self.pi_sha=pi_sha

    def start(self,run_id,kind,metadata=None):
        return super().start(run_id,kind,dict(metadata or {},stage=self.stage,
            continuation_policy_sha256=self.pi_sha,teacher_anchor_sha256=vendor.C7_SHA256))


class G1Recorder:
    def __init__(self,out,budget,freeze):
        self.out=out;self.budget=budget;self.freeze=freeze;self.rows=[];self.world_rows=[]
        self.costs=[]

    def run_id(self,suffix):return self.out.name+'_'+suffix

    def record(self,result,world,family,**metadata):
        verify_sources(self.freeze)
        path=self.out/'runs'/(result['run_id']+'.json.gz')
        start=time.monotonic();cpu=time.process_time();save_new(path,result)
        serialization_wall=time.monotonic()-start;serialization_cpu=time.process_time()-cpu
        row=dict(run_id=result['run_id'],path=str(path.relative_to(IMPL)),mode=world['mode'],
            world_id=world['world_id'],world_sha256=world['world_sha256'],group=world['group'],index=world['index'],
            kind=result['kind'],family=family,success=result['success'],
            policy=('one_retained_operation_then_frozen_c7' if result['kind']=='suffix' else
                    'privileged_replay' if result['extra'].get('applied_plan') else 'teacher0'),
            continuation_policy_sha256=self.budget.pi_sha,
            n=result['true_terminal_n'],modeled_full_virtual_us=result['modeled_full_virtual_us'],
            seconds_per_source=result['seconds_per_source'],normalized_cost_with_failure_penalty=normalized_cost(result),
            artifact_serialization_wall_s=serialization_wall,artifact_serialization_main_cpu_s=serialization_cpu,
            actual_execution_wall_s=result['actual_execution_wall_s'],**metadata)
        self.rows.append(row);atomic_json(self.out/'index.json',dict(schema='bc-rpi-g1-run-index-v1',runs=self.rows))
        return row

    def save_progress(self):
        atomic_json(self.out/'world_results.json',dict(schema='bc-rpi-g1-world-results-v1',worlds=self.world_rows))
        atomic_json(self.out/'progress.json',dict(completed_worlds=sum(r['status']=='complete' for r in self.world_rows),
            recorded_worlds=len(self.world_rows),actual_business_calls=self.budget.data['business_calls'],
            executions_started=self.budget.data['executions_started'],network_training_runs=0))


def sampled_states(recorder,world,handles,stage,trajectory_run_id):
    selected=sample_handles(handles,4)
    record=dict(world_sha256=world['world_sha256'],stage=stage,all_public_source_boundary_count=len(handles),
        trajectory_origin_run_id=trajectory_run_id,after_intervention_handles_only=stage=='o2',
        sampling='m=min(4,n); floor(k*(n-1)/(m-1)) for k=0..m-1; m=1 ->0',
        all_public_boundaries=[dict(source_index=h.source_index,choice_id=h.prepared.choice_id,
            prefix_virtual_us=h.token.prefix_virtual_us,teacher_task=h.prepared.meta['teacher_task']) for h in handles],
        selected_source_indexes=[h.source_index for h in selected],
        selection_reads='Public source-entry count/index only; not true locations, source type, future cost, or measured benefit')
    save_new(recorder.out/'worlds'/f'w{world["index"]:02d}'/(stage+'_sampling.json'),record)
    return selected


def search_stage(recorder,world,handles,base_result,base_plan,stage,worker):
    selected=sampled_states(recorder,world,handles,stage,base_result['run_id'])
    best_result,best_plan=base_result,list(base_plan);bundles=[];failed=0
    for state_index,handle in enumerate(selected):
        start=time.monotonic();cpu=time.process_time();expand_handle(handle,worker)
        feature_wall=time.monotonic()-start;feature_cpu=time.process_time()-cpu
        handle.verify(world)
        directory=recorder.out/'worlds'/f'w{world["index"]:02d}'/f'{stage}_s{state_index:02d}'
        save_new(directory/'handle.json.gz',handle.to_json())
        choices=handle.prepared.choices;ids=choices['candidate_ids'];teacher_id=choices['teacher_id']
        bundle=dict(world_sha256=world['world_sha256'],stage=stage,state_index=state_index,
            trajectory_origin_run_id=base_result['run_id'],
            source_index=handle.source_index,choice_id=handle.prepared.choice_id,
            continuation_policy_sha256=recorder.budget.pi_sha,candidate_ids=ids,
            candidate_count=len(ids),teacher_id=teacher_id,status='registered_not_complete',outcomes=[],
            feature_generation_wall_s=feature_wall,feature_generation_main_cpu_s=feature_cpu,
            worker_cpu_s=None,model_forward_s=0.,fit_s=0.)
        save_new(directory/'registration.json',deepcopy(bundle))
        try:
            for action_index,action_id in enumerate(ids):
                run_id=recorder.run_id(f'w{world["index"]:02d}_{stage}_s{state_index:02d}_a{action_index:02d}')
                result,_=run_suffix(world,recorder.budget,run_id,handle,action_id,worker=worker)
                payload=choices['candidates'][action_index]
                plan=list(base_plan)
                if action_id!=teacher_id:
                    plan.append(dict(choice_id=handle.prepared.choice_id,action_id=action_id,
                        source_index=handle.source_index,kind=payload['kind'],labels=payload.get('labels',[])))
                row=recorder.record(result,world,stage+'_counterfactual',state_index=state_index,
                    source_index=handle.source_index,choice_id=handle.prepared.choice_id,action_id=action_id,teacher_id=teacher_id,
                    labels=payload.get('labels',[]),prefix_virtual_us=handle.token.prefix_virtual_us,
                    prefix_event_count=handle.token.accepted_event_count,
                    full_continuation_policy_sha256=recorder.budget.pi_sha)
                failed+=not result['success']
                gain=normalized_cost(base_result)-normalized_cost(result)
                bundle['outcomes'].append(dict(row,paired_gain_to_current_reference=gain,
                    terminal_label_units='1 normalized unit = 1000 seconds/source; failed branch cost receives +100',
                    plan=plan))
                if action_id==teacher_id:
                    checks=verify_replay(base_result,result,base_plan)
                    if not all(checks.values()):
                        raise AssertionError('A0 tail differs from its actual roll-in policy: '+repr(checks))
                if should_replace(best_result,best_plan,result,plan):best_result,best_plan=result,plan
                atomic_json(directory/'outcomes.json',bundle)
            bundle['status']='complete';atomic_json(directory/'outcomes.json',bundle)
        except BudgetStop:
            bundle['status']='incomplete_budget';atomic_json(directory/'outcomes.json',bundle);raise
        except BaseException:
            bundle['status']='incomplete_engineering_failure';atomic_json(directory/'outcomes.json',bundle);raise
        bundles.append(dict(directory=str(directory.relative_to(IMPL)),state_index=state_index,
            source_index=handle.source_index,candidate_count=len(ids),status='complete'))
        print(json.dumps(dict(world=world['index'],stage=stage,state=state_index,candidates=len(ids),
            calls=recorder.budget.data['business_calls'],executions=recorder.budget.data['executions_started'])),flush=True)
    return best_result,best_plan,bundles,failed


def execute_world(recorder,world,worker):
    directory=recorder.out/'worlds'/f'w{world["index"]:02d}'
    baseline,handles=run_full(world,recorder.budget,recorder.run_id(f'w{world["index"]:02d}_c7_rollin'),worker=worker,capture=True)
    recorder.record(baseline,world,'c7_rollin')
    if not baseline['success']:raise AssertionError('C7 diagnostic roll-in failed; do not rank a successful subset')
    one,plan1,bundles1,failed1=search_stage(recorder,world,handles,baseline,[],'o1',worker)
    del handles
    save_new(directory/'o1_choice.json',dict(selected_reference_run_id=one['run_id'],plan=plan1,
        selected_modeled_full_virtual_us=one['modeled_full_virtual_us'],bundles=bundles1,
        definition='Finite hindsight minimum over zero or one action at up to four C7 source boundaries'))
    replay1,changed_handles=run_full(world,recorder.budget,recorder.run_id(f'w{world["index"]:02d}_o1_replay'),
                                   worker=worker,capture=True,plan=plan1,after_intervention=True)
    recorder.record(replay1,world,'o1_full_replay',plan=plan1)
    check1=verify_replay(one,replay1,plan1);save_new(directory/'o1_replay_check.json',check1)
    if not all(check1.values()):raise AssertionError('O1 full replay does not match its selected complete continuation')
    if plan1:
        two,plan2,bundles2,failed2=search_stage(recorder,world,changed_handles,replay1,plan1,'o2',worker)
    else:
        # This is intentionally greedy: no first action means no synergistic
        # two-action search. It is not an upper bound on every two-step policy.
        two,plan2,bundles2,failed2=replay1,[],[],0
        save_new(directory/'o2_sampling.json',dict(status='no_first_intervention_selected',
            selected_source_indexes=[],all_public_source_boundary_count=0,
            definition='Greedy O2 stops when finite O1 selects zero interventions; does not search synergistic pairs'))
    del changed_handles
    save_new(directory/'o2_choice.json',dict(selected_reference_run_id=two['run_id'],plan=plan2,
        selected_modeled_full_virtual_us=two['modeled_full_virtual_us'],bundles=bundles2,
        definition='Greedy second intervention searched only on the actual O1-replayed altered trajectory'))
    replay2,_=run_full(world,recorder.budget,recorder.run_id(f'w{world["index"]:02d}_o2_replay'),worker=worker,plan=plan2)
    recorder.record(replay2,world,'o2_full_replay',plan=plan2)
    check2=verify_replay(two,replay2,plan2);save_new(directory/'o2_replay_check.json',check2)
    if not all(check2.values()):raise AssertionError('O2 full replay does not match its selected complete continuation')
    if len(plan1)>1 or len(plan2)>2:raise AssertionError('Intervention-count contract violated')
    return dict(status='complete',world_id=world['world_id'],world_sha256=world['world_sha256'],index=world['index'],
        mode=4,group=world['group'],n=baseline['true_terminal_n'],
        c7_run_id=baseline['run_id'],o1_replay_run_id=replay1['run_id'],o2_replay_run_id=replay2['run_id'],
        c7_total_virtual_us=baseline['modeled_full_virtual_us'],o1_total_virtual_us=replay1['modeled_full_virtual_us'],
        o2_total_virtual_us=replay2['modeled_full_virtual_us'],c7_seconds_per_source=baseline['seconds_per_source'],
        o1_seconds_per_source=replay1['seconds_per_source'],o2_seconds_per_source=replay2['seconds_per_source'],
        o1_plan=plan1,o2_plan=plan2,o1_states=len(bundles1),o2_states=len(bundles2),
        o1_branches=sum(b['candidate_count'] for b in bundles1),o2_branches=sum(b['candidate_count'] for b in bundles2),
        failed_branches=failed1+failed2,all_selected_full_replays_complete=True)


def run(out,acceptance_path):
    if sys.version_info<(3,10) or not sys.flags.no_site:raise RuntimeError('Use Python >=3.10 -S -B')
    acceptance_path=Path(acceptance_path).resolve();acceptance=load(acceptance_path)
    if acceptance.get('g0_accepted') is not True:raise RuntimeError('Independent coordinator G0 acceptance is required')
    if acceptance.get('accepted_deploy_implementation_sha256')!=vendor.implementation_hash():
        raise RuntimeError('Accepted deploy identity differs; new G0 required')
    out=Path(out).resolve();out.relative_to(IMPL)
    if out.exists():raise FileExistsError('Use a fresh G1 output directory')
    out.mkdir(parents=True)
    identity=continuation_identity();pi_sha=digest(identity);budget=CampaignBudget(out.name,pi_sha)
    initial_calls=budget.data['business_calls'];initial_runs=budget.data['executions_started']
    freeze=freeze_sources();save_new(out/'source_freeze.json',freeze);verify_sources(freeze)
    save_new(out/'source_archive.json',archive_sources(freeze,out/'sources.zip'))
    registered=worlds('g1')
    inputs=[acceptance_path,IMPL/'execution_registration.json',IMPL/'evaluator/probes_v1.json']
    for name in ('independent_record_audit','settled_g0_ledger_snapshot'):
        entry=acceptance[name];path=acceptance_path.parent.parent/entry['path']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:
            raise RuntimeError('G0 accepted audit/snapshot hash changed: '+name)
        inputs.append(path)
    input_hashes={str(p.relative_to(vendor.REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    save_new(out/'input_archive.json',archive_sources(dict(files=input_hashes),out/'inputs.zip'))
    suite=unittest.defaultTestLoader.loadTestsFromNames(['implementation.tests.test_pure','implementation.tests.test_evaluator_pure','implementation.tests.test_g1'])
    text=io.StringIO();tested=unittest.TextTestRunner(stream=text,verbosity=2).run(suite)
    save_new(out/'pure_tests.json',dict(tests=tested.testsRun,success=tested.wasSuccessful(),actual_environment_calls=0,log=text.getvalue()))
    if not tested.wasSuccessful():raise RuntimeError('G1 pure preflight failed')
    save_new(out/'registration.json',dict(schema='bc-rpi-g1-registration-v1',continuation_policy=identity,
        continuation_policy_sha256=pi_sha,inputs=input_hashes,world_ids=[w['world_id'] for w in registered],
        world_content_hashes=[w['world_sha256'] for w in registered],world_count=24,
        initial_cumulative_calls=initial_calls,initial_cumulative_executions=initial_runs,
        state_sampling='Four uniformly spaced indexes of public source-entry sequence; changed trajectory only for O2',
        tie_break='normalized complete cost including failure penalty, then fewer interventions, then retained choice/action IDs',
        branch_order='world index0..23, source sampled index order, canonical action hash order',
        stopping='Stop after complete G1, any incomplete-budget set, or engineering failure; never start G2',
        score='Exact full prefix + full suffix; equal-world mean T/N after complete 24-world set',
        cost_accounting='All actual calls in campaign journal, including failed branches/replays. Reused prefix is modeled score only, not fabricated actual calls.',
        resources=budget.data['limits'],neural_training_runs=0,official_runs=0))
    recorder=G1Recorder(out,budget,freeze);worker=CandidateWorker();budget.set_phase('running_g1_finite_headroom')
    status='g1_incomplete';active_index=None;stop_reason=None
    try:
        for world in registered:
            active_index=world['index'];verify_sources(freeze)
            row=execute_world(recorder,world,worker)
            recorder.world_rows.append(row);recorder.save_progress()
            print(json.dumps(dict(world=active_index,status='complete',c7=row['c7_seconds_per_source'],
                o1=row['o1_seconds_per_source'],o2=row['o2_seconds_per_source'],calls=budget.data['business_calls'])),flush=True)
        status=aggregate(recorder.world_rows)['status']
    except BudgetStop as exc:
        status='g1_budget_inconclusive';stop_reason=str(exc)
    except BaseException as exc:
        status='g1_engineering_inconclusive';stop_reason=type(exc).__name__+': '+str(exc)
        raise
    finally:
        worker.close()
        completed={r['index'] for r in recorder.world_rows}
        for world in registered:
            if world['index'] not in completed:
                recorder.world_rows.append(dict(status='incomplete_budget' if status=='g1_budget_inconclusive' and world['index']==active_index
                    else 'incomplete_engineering' if world['index']==active_index else 'not_started_budget' if status=='g1_budget_inconclusive' else 'not_started_after_failure',
                    index=world['index'],world_id=world['world_id'],world_sha256=world['world_sha256'],group=world['group']))
        recorder.save_progress();budget.set_phase(status)
        conclusion=aggregate(recorder.world_rows)
        save_new(out/'summary.json',dict(status=status,stop_reason=stop_reason,conclusion=conclusion,
            actual_calls_this_stage=budget.data['business_calls']-initial_calls,
            actual_executions_this_stage=budget.data['executions_started']-initial_runs,
            cumulative_actual_business_calls=budget.data['business_calls'],cumulative_accepted_calls=budget.data['accepted_calls'],
            cumulative_known_rejected_calls=budget.data['rejected_calls'],cumulative_unknown_cost_calls=budget.data['unknown_cost_calls'],
            cumulative_executions_started=budget.data['executions_started'],cumulative_executions_completed=budget.data['executions_completed'],
            current_run=budget.data['current_run'],source_freeze=str((out/'source_freeze.json').relative_to(IMPL)),
            continuation_policy_sha256=pi_sha,network_training_runs=0,official_runs=0,
            full_trace_results=str((out/'index.json').relative_to(IMPL))))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--g0-acceptance',required=True)
    a=p.parse_args();run(a.out,a.g0_acceptance)
