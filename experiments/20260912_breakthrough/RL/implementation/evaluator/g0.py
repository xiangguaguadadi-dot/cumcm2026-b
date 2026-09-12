"""Frozen-source G0 gate. Stops on any correctness failure; never starts G1."""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import unittest
from ..deploy import vendor,operations,q3_passthrough
from ..deploy.engine import CandidateWorker,Engine
from ..deploy.state import digest,encode,decode,canonical_events
from .budget import Budget,IMPL,atomic_json
from .runtime import (worlds,save_new,load,canonical_log,run_original,run_full,run_suffix,
                      ForkHandle,seal_handle,clone_private,BranchClock,sample_handles)
from .novelty_audit import audit as novelty_audit


def freeze_sources():
    paths=list(IMPL.rglob('*.py'))+[vendor.REPO/'local_env.py',vendor.REPO/'evaluation/manifest_v1.json',
        q3_passthrough.LATEST_Q3_ENTRY,Path(vendor.load_c7().__file__)]
    paths+=[vendor.OLD/name for name in vendor.PINS]
    return dict(schema='bc-rpi-g0-source-freeze-v1',python_executable=sys.executable,python_version=sys.version,
        no_site=sys.flags.no_site,deploy_implementation_sha256=vendor.implementation_hash(),
        files={str(p.relative_to(vendor.REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))})


def verify_sources(freeze):
    now=freeze_sources()
    if now!=freeze:raise RuntimeError('Source/dependency changed during G0; stop rather than mix versions')
    manifest=load(vendor.REPO/'evaluation/manifest_v1.json')
    for name,expected in manifest['sha256'].items():
        if hashlib.sha256((vendor.REPO/name).read_bytes()).hexdigest()!=expected:
            raise RuntimeError('Frozen v1 manifest member changed: '+name)


def pure_tests():
    suite=unittest.defaultTestLoader.loadTestsFromNames([
        'implementation.tests.test_pure','implementation.tests.test_evaluator_pure'])
    output=io.StringIO();start=time.monotonic()
    result=unittest.TextTestRunner(stream=output,verbosity=2).run(suite)
    return dict(status='pass' if result.wasSuccessful() else 'fail',tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),wall_s=time.monotonic()-start,
        actual_environment_calls=0,actual_environment_instances=0,log=output.getvalue(),
        scope='Pure public state, mock transport/counter, and evaluator-object tests only; not environment performance')


def compare(left,right,*,controller=True):
    llog,rlog=canonical_log(left['environment_log']),canonical_log(right['environment_log'])
    result=dict(both_complete=left['success'] and right['success'],
        requests_and_public_responses_equal=llog==rlog,
        microseconds_equal=left['modeled_full_virtual_us']==right['modeled_full_virtual_us'],
        cleared_equal=left['private_terminal_sources']==right['private_terminal_sources'],
        controller_equal=(left['episode']['controller_final']==right['episode']['controller_final']) if controller else None,
        left_run=left['run_id'],right_run=right['run_id'],left_calls=len(llog),right_calls=len(rlog),
        excluded_response_fields=['real_timestamp_ms','remaining_real_duration_s'])
    result['first_log_difference']=next((i for i,(a,b) in enumerate(zip(llog,rlog)) if a!=b),None)
    result['pass']=all(result[k] for k in ('both_complete','requests_and_public_responses_equal','microseconds_equal','cleared_equal')) and (not controller or result['controller_equal'])
    return result


class Recorder:
    def __init__(self,out,budget,freeze):
        self.out=out;self.budget=budget;self.freeze=freeze;self.rows=[];self.checks=[]

    def run_id(self,suffix):
        return self.out.name+'_'+suffix

    def record(self,result,world,policy,family):
        verify_sources(self.freeze)
        path=self.out/'runs'/(result['run_id']+'.json.gz')
        save_new(path,result)
        self.rows.append(dict(run_id=result['run_id'],path=str(path.relative_to(IMPL)),
            world_sha256=world['world_sha256'],mode=world['mode'],policy=policy,family=family,
            kind=result['kind'],success=result['success'],true_terminal_n=result.get('true_terminal_n'),
            modeled_full_virtual_us=result.get('modeled_full_virtual_us')))
        atomic_json(self.out/'index.json',dict(schema='bc-rpi-g0-run-index-v1',runs=self.rows))
        print(json.dumps(dict(run_id=result['run_id'],kind=result['kind'],success=result['success'],
            actual_business_calls=self.budget.data['business_calls'],executions=self.budget.data['executions_started'])),flush=True)

    def check(self,name,passed,details=None):
        row=dict(name=name,pass_=bool(passed),details=details or {})
        self.checks.append(row);atomic_json(self.out/'fixture_checks.json',dict(checks=self.checks))
        if not passed:raise AssertionError('G0 check failed: '+name)


def run(out):
    if sys.version_info<(3,10) or not sys.flags.no_site:
        raise RuntimeError('Use Python >=3.10 with -S -B; no site bootstrap')
    out=Path(out).resolve()
    out.relative_to(IMPL)  # Only the authorized implementation output tree.
    if out.exists():raise FileExistsError('Use a new G0 output directory')
    out.mkdir(parents=True)
    budget=Budget()
    try:
        freeze=freeze_sources();save_new(out/'source_freeze.json',freeze)
        verify_sources(freeze)
        tests=pure_tests();save_new(out/'pure_tests.json',tests)
        if tests['status']!='pass':raise RuntimeError('Pure test gate failed')
        novelty=novelty_audit();save_new(out/'novelty_audit.json',novelty)
        if novelty['status']!='pass':raise RuntimeError('Probe overlap precheck failed')
        from .g0_fixtures import fixture_world
        save_new(out/'fixture_registration.json',dict(world=fixture_world(),
            latest_q3_world_indexes=list(range(12)),extra_execution_cap=24,
            fixture_order=['branch_order_A0_alt_alt_A0','A1_to_A8_first_public_occurrence',
                'before_deadline_reserve','after_deadline','normal_near','partial_station_near',
                'partial_forced_A0','failure_and_no_signal','duplicate_enter_rejection','accepted_then_lost_response'],
            intervention_sampling='First public occurrence per label within complete G0 Q4 index0 then index1 trajectory; no source truth or future cost selection'))
    except BaseException as exc:
        budget.set_phase('g0_preflight_failed')
        atomic_json(out/'failure.json',dict(status='g0_preflight_failed',error=type(exc).__name__+': '+str(exc)))
        atomic_json(out/'summary.json',dict(status='g0_preflight_failed',actual_calls_this_stage=0,scope='No stage environment execution started'))
        raise
    record=Recorder(out,budget,freeze);pairs=[];anchors={};worker=CandidateWorker()
    budget.set_phase('running_g0')
    status='g0_incomplete'
    try:
        for world in worlds('g0'):
            mode,index=world['mode'],world['index'];prefix=record.run_id(f'q{mode}_w{index:02d}')
            original=run_original(world,budget,prefix+'_original_c7');record.record(original,world,'original_c7','c7_equivalence')
            candidate,handles=run_full(world,budget,prefix+'_teacher0',worker=worker,capture=(mode==4 and index<2))
            record.record(candidate,world,'teacher0','c7_equivalence')
            check=compare(original,candidate);check.update(mode=mode,index=index,world_sha256=world['world_sha256'])
            pairs.append(check);atomic_json(out/'equivalence.json',dict(pairs=pairs))
            record.check(prefix+'_exact',check['pass'],check)
            record.check(prefix+'_no_recovery',not candidate['episode']['controller_recoveries'] and candidate['episode']['fallback_reason'] is None)
            if handles:
                anchors[index]=(world,original,candidate,handles)
                save_new(out/'ready'/(prefix+'.json.gz'),dict(world_sha256=world['world_sha256'],handles=[h.to_json() for h in handles]))
        for world in [w for w in worlds('g0') if w['mode']==3 and w['index']<12]:
            prefix=record.run_id(f'q3_w{world["index"]:02d}_latest')
            direct=run_original(world,budget,prefix+'_direct',entry=q3_passthrough.LATEST_Q3_ENTRY)
            record.record(direct,world,'latest_q3_direct','latest_q3_passthrough')
            adapter=run_original(world,budget,prefix+'_passthrough',q3_passthrough=True)
            record.record(adapter,world,'latest_q3_passthrough','latest_q3_passthrough')
            check=compare(direct,adapter);check.update(mode=3,index=world['index'],world_sha256=world['world_sha256'],latest_q3=True)
            pairs.append(check);atomic_json(out/'equivalence.json',dict(pairs=pairs))
            record.check(prefix+'_exact',check['pass'],check)
        from .g0_fixtures import run_fixtures
        fixture_result=run_fixtures(record,anchors,worker)
        save_new(out/'fixture_summary.json',fixture_result)
        verify_sources(freeze)
        if fixture_result['actual_executions']>24:raise AssertionError('Extra real fixture count exceeded')
        status='g0_pass_pending_independent_review'
    except BaseException as exc:
        status='g0_failed' if not isinstance(exc,KeyboardInterrupt) else 'g0_interrupted'
        atomic_json(out/'failure.json',dict(error=type(exc).__name__+': '+str(exc),status=status))
        raise
    finally:
        worker.close()
        budget.set_phase(status)
        atomic_json(out/'summary.json',dict(status=status,scope='G0 only; no G1 or neural training executed',
            source_freeze=str((out/'source_freeze.json').relative_to(IMPL)),
            paired_c7_worlds=sum(not p.get('latest_q3') for p in pairs),
            paired_latest_q3_worlds=sum(bool(p.get('latest_q3')) for p in pairs),
            runs_recorded=len(record.rows),checks=len(record.checks),all_recorded_checks_pass=all(c['pass_'] for c in record.checks),
            actual_business_calls=budget.data['business_calls'],accepted_calls=budget.data['accepted_calls'],
            rejected_calls=budget.data['rejected_calls'],unknown_cost_calls=budget.data['unknown_cost_calls'],
            executions_started=budget.data['executions_started'],executions_completed=budget.data['executions_completed'],
            network_training_runs=0,official_runs=0))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True)
    run(parser.parse_args().out)
