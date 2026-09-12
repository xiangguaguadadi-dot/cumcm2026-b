"""One remaining predeclared G0 fixture: accepted partial override never refunds b."""
import argparse
from copy import deepcopy
from pathlib import Path
from ..deploy import vendor
from ..deploy.engine import Engine,CandidateWorker
from ..deploy.state import decode
from .budget import Budget,CountedBackend,IMPL,atomic_json
from .runtime import load,save_new,worlds,ForkHandle,clone_private,BranchClock
from .g0 import Recorder,freeze_sources,verify_sources,pure_tests
from .source_archive import archive_sources


def run(prior,out):
    prior=Path(prior).resolve();out=Path(out).resolve();out.relative_to(IMPL)
    if out.exists():raise FileExistsError('Use a fresh supplemental output directory')
    out.mkdir(parents=True)
    budget=Budget();freeze=freeze_sources();save_new(out/'source_freeze.json',freeze);verify_sources(freeze)
    save_new(out/'source_archive.json',archive_sources(freeze,out/'sources.zip'))
    old=load(prior/'source_freeze.json')
    if any(freeze['files'].get(p)!=sha for p,sha in old['files'].items()):
        raise RuntimeError('Existing G0 source changed')
    tests=pure_tests();save_new(out/'pure_tests.json',tests)
    if tests['status']!='pass':raise RuntimeError('Pure preflight failed')
    world=next(w for w in worlds('g0') if w['mode']==4 and w['index']==0)
    source=load(prior/'ready'/(prior.name+'_q4_w00.json.gz'))
    handle=ForkHandle.from_json(source['handles'][0]);handle.verify(world)
    save_new(out/'registration.json',dict(scope='One additional real G0 fixture, within 24 cap',
        cumulative_extra_fixtures_after_this=21,world_sha256=world['world_sha256'],
        source_ready_path=str((prior/'ready'/(prior.name+'_q4_w00.json.gz')).relative_to(IMPL)),
        intervention='retained A6, request cap = prefix accepted learning requests + 1',
        expected='one accepted request, partial macro, b=1 retained, independent fallback once, complete cost',
        unchanged_deploy_implementation_sha256=vendor.implementation_hash()))
    record=Recorder(out,budget,freeze);run_id=record.run_id('partial_override_A6');worker=CandidateWorker()
    budget.start(run_id,'fixture',dict(world_sha256=world['world_sha256'],mode=4,fixture='partial_override_A6',
        prefix_event_count=handle.token.accepted_event_count,prefix_virtual_us=handle.token.prefix_virtual_us))
    clock=BranchClock();env=clone_private(handle,clock)
    e=Engine.restore(CountedBackend(env,budget),handle.token,clock=clock,worker=worker)
    e.api.guard=vendor.GuardConfig(learning_request_cap=e.api.learning_requests+1)
    prepared=e.prepare();e.expand(prepared)
    action=next(a for a,p in zip(prepared.choices['candidate_ids'],prepared.choices['candidates']) if 'A6' in p.get('labels',[]))
    clock.start()
    try:episode=e.run(initial_action=(prepared,action))
    finally:worker.close()
    first=episode['macros'][0];state=decode(episode['engine_final'])
    checks=dict(partial_macro=not first['macro_completed'],one_accepted_request=first['event_range'][1]-first['event_range'][0]==1,
        slot_consumed_before_failure=first['slots_after']==1,slot_not_refunded=episode['slots_remaining']==1,
        operation_retained_in_history=state['used_operation_ids']==[action],
        guard_takeover=episode['fallback_reason']=='learning_primitive_cap',
        independent_tail_completed=episode['success'] and episode['tail_virtual_us']>0,
        no_controller_recovery=not episode['controller_recoveries'],
        exact_microsecond_partition=episode['cost_partition_error_us']==0)
    success=all(checks.values());budget.finish(success,dict(checks=checks,fixture='partial_override_A6'))
    result=dict(schema='bc-rpi-real-interface-fixture-v1',run_id=run_id,kind='fixture',success=success,
        modeled_full_virtual_us=env._virtual_us,checks=checks,episode=episode,environment_log=env.log,
        prefix_event_count=handle.token.accepted_event_count,prefix_virtual_us=handle.token.prefix_virtual_us,
        verification_kind='controlled_request_cap_after_actual_retained_override')
    record.record(result,world,'partial_override_A6','real_interface_fixture');record.check('partial_override_nonrefund',success,checks)
    verify_sources(freeze)
    status='g0_supplement_pass_pending_independent_review' if success else 'g0_supplement_failed'
    budget.set_phase(status)
    save_new(out/'summary.json',dict(status=status,checks=checks,new_actual_executions=1,
        new_actual_business_calls=budget.data['runs'][-1]['attempted'],
        cumulative_actual_business_calls=budget.data['business_calls'],cumulative_executions=budget.data['executions_started'],
        actual_extra_g0_fixture_executions=21,unknown_cost_calls=budget.data['unknown_cost_calls'],network_training_runs=0))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prior',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();run(a.prior,a.out)
