"""Approved G0 continuation after a latest-Q3 machine-timing comparison error."""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
from pathlib import Path
from ..deploy import q3_passthrough
from ..deploy.engine import CandidateWorker
from ..deploy.state import decode,encode
from .budget import Budget,IMPL,atomic_json
from .runtime import load,save_new,worlds,run_original,ForkHandle
from .g0 import Recorder,freeze_sources,verify_sources,pure_tests,compare
from .g0_fixtures import run_fixtures


def compare_latest(left,right):
    result=compare(left,right,controller=False)
    a,b=decode(left['episode']['controller_final']),decode(right['episode']['controller_final'])
    av=a['counters'].pop('a1_cover_cpu_s',None);bv=b['counters'].pop('a1_cover_cpu_s',None)
    result['controller_equal']=a==b
    result['excluded_controller_fields']=['counters.a1_cover_cpu_s']
    result['raw_excluded_machine_timing_s']={'left':av,'right':bv}
    result['pass']=result['pass'] and result['controller_equal']
    return result


def run(prior,out):
    prior=Path(prior).resolve();out=Path(out).resolve();out.relative_to(IMPL)
    if out.exists():raise FileExistsError('Use a new continuation directory')
    out.mkdir(parents=True)
    budget=Budget();starting_runs=budget.data['executions_started'];starting_calls=budget.data['business_calls']
    freeze=freeze_sources();save_new(out/'source_freeze.json',freeze);verify_sources(freeze)
    old_freeze=load(prior/'source_freeze.json')
    for path,sha in old_freeze['files'].items():
        if freeze['files'].get(path)!=sha:
            raise RuntimeError('Previous G0 source changed, cannot reuse: '+path)
    test_result=pure_tests();save_new(out/'pure_tests.json',test_result)
    if test_result['status']!='pass':raise RuntimeError('Pure tests failed')
    record=Recorder(out,budget,freeze);old_index=load(prior/'index.json')
    prior_pairs=load(prior/'equivalence.json')['pairs']
    if len(prior_pairs)!=49 or any(not p['pass'] for p in prior_pairs if not p.get('latest_q3')):
        raise RuntimeError('Expected exactly 48 successful original C7 pairs and one timing-only Q3 pair')
    results={}
    for row in old_index['runs']:
        results[row['run_id']]=load(IMPL/row['path'])
        record.rows.append(dict(row,origin_run_id=row['run_id'],origin_path=row['path'],
            origin_source_freeze=str((prior/'source_freeze.json').relative_to(IMPL)),
            reused_prior_g0_evidence=True,actual_new_business_calls=0,actual_new_executions=0))
    pairs=deepcopy(prior_pairs)
    q3_pair=pairs[-1]
    corrected=compare_latest(results[q3_pair['left_run']],results[q3_pair['right_run']])
    corrected.update(mode=3,index=0,world_sha256=q3_pair['world_sha256'],latest_q3=True,
        prior_unamended_comparison=q3_pair,correction='Latest-Q3 machine-timing diagnostic only; no algorithm or physical result change')
    if not corrected['pass']:raise RuntimeError('Latest Q3 has a difference beyond the approved timing field')
    # Negative test: no ordinary counter can be hidden by this single-field rule.
    bad=deepcopy(results[q3_pair['right_run']]);state=decode(bad['episode']['controller_final'])
    state['counters']['measure']+=1;bad['episode']['controller_final']=encode(state)
    if compare_latest(results[q3_pair['left_run']],bad)['pass']:
        raise AssertionError('Latest Q3 comparer hides a non-timing difference')
    pairs[-1]=corrected
    save_new(out/'amendment.json',dict(status='coordinator_approved_before_continuation_calls',
        authority='Coordinator explicitly approved this narrow timing-comparator correction and reuse',
        exact_additional_exclusion='latest_q3 only: counters.a1_cover_cpu_s',
        source_evidence='A1/BEST_Q3_COMPONENT.py: accumulated time.perf_counter() diagnostics',
        c7_comparer_unchanged=True,raw_prior_failure_retained=str((prior/'failure.json').relative_to(IMPL)),
        reused_completed_runs=len(record.rows),reused_c7_pairs=48,reused_latest_q3_pairs=1,
        actual_new_calls_for_reuse=0,actual_new_executions_for_reuse=0,
        remaining_latest_q3_indexes=list(range(1,12)),remaining_real_fixture_cap=24,
        all_old_listed_source_hashes_unchanged=True,negative_comparer_test='non-timing measure-counter perturbation rejected'))
    atomic_json(out/'index.json',dict(schema='bc-rpi-g0-run-index-v1',runs=record.rows))
    atomic_json(out/'equivalence.json',dict(pairs=pairs))
    for pair in pairs:record.check('reused_'+pair['left_run'],pair['pass'],pair)
    anchors={}
    for index in (0,1):
        w=next(w for w in worlds('g0') if w['mode']==4 and w['index']==index)
        base=f'{prior.name}_q4_w{index:02d}'
        saved=load(prior/'ready'/(base+'.json.gz'))
        anchors[index]=(w,results[base+'_original_c7'],results[base+'_teacher0'],
                        [ForkHandle.from_json(h) for h in saved['handles']])
    status='g0_continuation_incomplete';worker=CandidateWorker();budget.set_phase('running_g0_continuation')
    try:
        for world in [w for w in worlds('g0') if w['mode']==3 and 1<=w['index']<12]:
            prefix=record.run_id(f'q3_w{world["index"]:02d}_latest')
            direct=run_original(world,budget,prefix+'_direct',entry=q3_passthrough.LATEST_Q3_ENTRY)
            record.record(direct,world,'latest_q3_direct','latest_q3_passthrough')
            adapter=run_original(world,budget,prefix+'_passthrough',q3_passthrough=True)
            record.record(adapter,world,'latest_q3_passthrough','latest_q3_passthrough')
            check=compare_latest(direct,adapter);check.update(mode=3,index=world['index'],world_sha256=world['world_sha256'],latest_q3=True)
            pairs.append(check);atomic_json(out/'equivalence.json',dict(pairs=pairs))
            record.check(prefix+'_exact_except_machine_counter',check['pass'],check)
        fixture_result=run_fixtures(record,anchors,worker);save_new(out/'fixture_summary.json',fixture_result)
        if fixture_result['actual_executions']>24:raise AssertionError('Real fixture cap exceeded')
        verify_sources(freeze)
        status='g0_pass_pending_independent_review'
    except BaseException as exc:
        status='g0_continuation_failed'
        atomic_json(out/'failure.json',dict(error=type(exc).__name__+': '+str(exc),status=status))
        raise
    finally:
        worker.close();budget.set_phase(status)
        atomic_json(out/'summary.json',dict(status=status,scope='G0 only; zero neural training and no G1 yet',
            prior_stage=str(prior.relative_to(IMPL)),reused_runs=len(old_index['runs']),
            paired_c7_worlds=sum(not p.get('latest_q3') for p in pairs),
            paired_latest_q3_worlds=sum(bool(p.get('latest_q3')) for p in pairs),runs_recorded=len(record.rows),
            checks=len(record.checks),all_recorded_checks_pass=all(c['pass_'] for c in record.checks),
            actual_calls_this_stage=budget.data['business_calls']-starting_calls,
            actual_executions_this_stage=budget.data['executions_started']-starting_runs,
            cumulative_actual_business_calls=budget.data['business_calls'],cumulative_accepted_calls=budget.data['accepted_calls'],
            cumulative_rejected_calls=budget.data['rejected_calls'],cumulative_unknown_cost_calls=budget.data['unknown_cost_calls'],
            cumulative_executions_started=budget.data['executions_started'],cumulative_executions_completed=budget.data['executions_completed'],
            network_training_runs=0,official_runs=0))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--prior',required=True);parser.add_argument('--out',required=True)
    args=parser.parse_args();run(args.prior,args.out)
