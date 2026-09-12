"""Predeclared real G0 fixtures; all LocalEnv calls go through the campaign budget."""
from copy import deepcopy
import math
import time
from ..deploy import vendor
from ..deploy.engine import Engine
from ..deploy.state import controller_state,encode,decode,digest
from .budget import CountedBackend
from .runtime import (new_env,run_full,run_suffix,clone_private,BranchClock,seal_handle,
                      canonical_log,capture_private)


def fixture_world():
    # Fixed before outcomes: one guaranteed origin-near emitter plus nine others.
    sources=[dict(channel=1,x=0.,y=0.,radius=1000.,direction=None,cleared=False)]
    for c in range(2,11):
        angle=2*math.pi*(c-2)/9
        sources.append(dict(channel=c,x=600*math.cos(angle),y=600*math.sin(angle),radius=1000.,
                            direction=0. if c==2 else None,cleared=False))
    world=dict(mode=4,seed=730019,noise='positive',sources=sources)
    world.update(world_sha256=digest(world),role='registered_rule_fixture_not_performance_probe',
                 world_id='bc-rpi-g0-origin-near-fixture-v1',index=0,group='constructed_origin_near')
    return world


def expand_handle(handle,worker):
    # No interface invocation: only a detached public generator for this saved h.
    clock=BranchClock();e=Engine.restore(vendor.NoCalls(),handle.token,clock=clock,worker=worker)
    e.expand(handle.prepared)
    seal_handle(handle)
    if any(r.startswith('generator_error') for r in handle.prepared.choices['rejections']):
        raise AssertionError('Candidate generation failed on actual public history: '+repr(handle.prepared.choices['rejections']))


def direct_fixture(record,world,name,operation):
    run_id=record.run_id(name)
    record.budget.start(run_id,'fixture',dict(world_sha256=world['world_sha256'],mode=4,fixture=name))
    started=time.monotonic();env=new_env(world);backend=CountedBackend(env,record.budget)
    checks,detail=operation(env,backend)
    passed=all(checks.values())
    record.budget.finish(passed,dict(fixture=name,checks=checks,physical_task_finished=env.finished,
                                    physical_exit_reason=env.exit_reason))
    result=dict(schema='bc-rpi-real-interface-fixture-v1',run_id=run_id,kind='fixture',success=passed,
        verification_kind='expected_partial_or_failure_semantics_not_solver_performance',
        fixture_source_count=len(env._sources),normal_exit=env.exit_reason=='user_exit',
        modeled_full_virtual_us=env._virtual_us,checks=checks,detail=detail,environment_log=env.log,
        actual_execution_wall_s=time.monotonic()-started)
    record.record(result,world,name,'real_interface_fixture');record.check(name,passed,checks)
    return result


def run_fixtures(record,anchors,worker):
    start_runs=record.budget.data['executions_started'];summary={};world,original,teacher,handles=anchors[0]
    first=deepcopy(handles[0]);expand_handle(first,worker)
    choice=first.prepared.choices;tid=choice['teacher_id']
    aid=next(x for x in choice['candidate_ids'] if x!=tid)
    four=[]
    for index,action in enumerate((tid,aid,aid,tid)):
        result,_=run_suffix(world,record.budget,record.run_id(f'branch_order_{index}'),first,action,worker=worker)
        record.record(result,world,'A0' if action==tid else 'retained_alternative','branch_order')
        record.check(f'branch_order_{index}_complete',result['success'] and not result['episode']['controller_recoveries'])
        four.append(result)
    record.check('fork_A0_matches_original_full',canonical_log(four[0]['environment_log'])==canonical_log(original['environment_log']))
    record.check('branch_order_independent_A0',canonical_log(four[0]['environment_log'])==canonical_log(four[3]['environment_log']))
    record.check('branch_order_independent_alternative',canonical_log(four[1]['environment_log'])==canonical_log(four[2]['environment_log']))
    record.check('suffix_did_not_enter',all(all(e['action']!='enter' for e in r['episode']['events'][r['episode']['prefix_event_count']:]) for r in four))
    c1,c2=BranchClock(),BranchClock();a,b=clone_private(first,c1),clone_private(first,c2)
    ch=next(iter(a._sources));before=b._sources[ch].cleared;a._sources[ch].cleared=not before
    record.check('private_sources_and_logs_not_shared',b._sources[ch].cleared==before and a._sources is not b._sources and a.log is not b.log)
    summary['branch_order_runs']=[r['run_id'] for r in four]

    # First public occurrence of each registered label in the first two fixed
    # probe trajectories; never select by future time, source truth, or outcome.
    opportunities={}
    for anchor_index in sorted(anchors):
        w,_,_,history=anchors[anchor_index]
        for original_handle in history:
            handle=deepcopy(original_handle);expand_handle(handle,worker)
            for action_id,payload in zip(handle.prepared.choices['candidate_ids'],handle.prepared.choices['candidates']):
                for label in payload.get('labels',[]):
                    if label!='A0':opportunities.setdefault(label,(w,handle,action_id))
            if len(opportunities)==8:break
        if len(opportunities)==8:break
    record.check('all_eight_operation_labels_available',set(opportunities)=={f'A{i}' for i in range(1,9)},dict(labels=sorted(opportunities)))
    smoke=[];forced_seen=False;failed_clear_seen=False
    for label in sorted(opportunities):
        w,handle,action_id=opportunities[label]
        result,_=run_suffix(w,record.budget,record.run_id('operation_'+label),handle,action_id,worker=worker)
        record.record(result,w,label,'force_operation_smoke')
        macro=result['episode']['macros'][0];events=result['episode']['events'][slice(*macro['event_range'])]
        kind=macro['payload']['kind']
        expected_max=2 if kind=='measure_override' else 1
        record.check(label+'_complete',result['success'] and not result['episode']['controller_recoveries'])
        record.check(label+'_direct_call_contract',1<=len(events)<=expected_max,
            dict(events=[e['action'] for e in events],delta_us=macro['delta_us']))
        record.check(label+'_slot_exactly_one',macro['slots_after']==1)
        record.check(label+'_service_progress_not_incremented',macro['service_progress_before']==macro['service_progress_after'])
        if kind=='measure_override' and len(events)==2:
            record.check(label+'_near_extra_clear',events[0]['response']['measure_result']=='near' and events[1]['action']=='clear' and events[1]['response']['clear_result']=='success')
        failed_clear_seen|=any(e['action']=='clear' and e['response']['clear_result']=='no_target_in_range' for e in events)
        # A no-progress override is required to hand the next service to A0.
        next_same=[m for m in result['episode']['macros'][1:] if m['payload'].get('channel')==macro['payload']['channel']]
        before,after=macro['observable_progress_before'],macro['observable_progress_after']
        no_progress=not (after[0]>before[0] or after[1]>before[1] or after[3]<before[3]-1e-6)
        if no_progress and next_same:
            channel=macro['payload']['channel']
            correct=(channel in macro['forced_teacher_after'] and next_same[0]['payload']['kind']=='teacher_service'
                and next_same[0]['macro_completed'] and channel not in next_same[0]['forced_teacher_after'])
            record.check(label+'_observed_no_progress_forced_then_released',correct,
                dict(progress_before=before,progress_after=after,forced_after=macro['forced_teacher_after'],
                     next_teacher_forced_after=next_same[0]['forced_teacher_after']))
            forced_seen|=correct
        smoke.append(dict(label=label,run_id=result['run_id'],event_count=len(events),delta_us=macro['delta_us']))
    record.check('repeat_measure_then_teacher_service',forced_seen)
    summary['operation_smoke']=smoke;summary['smoke_failed_clear_seen']=failed_clear_seen

    # Identical prefix budget, one branch inside real reserve and one after expiry.
    for label,remaining in [('before_deadline_reserve',29.),('after_deadline',-0.1)]:
        advance=first.token.clock_offsets['interface_deadline_remaining_s']-remaining-first.prepared.prepare_wall_s
        result,_=run_suffix(world,record.budget,record.run_id(label),first,tid,worker=worker,clock_advance_s=advance)
        record.record(result,world,label,'controlled_clock')
        if remaining>0:
            record.check(label,result['success'] and result['episode']['fallback_reason']=='fallback_real_reserve' and result['episode']['tail_virtual_us']>0)
        else:
            record.check(label,not result['success'] and result['episode']['error'] is not None and record.budget.data['unknown_cost_calls']==0)
        record.check(label+'_cost_partition',result['episode']['cost_partition_error_us']==0)

    fixed=fixture_world()
    def normal_near(env,backend):
        e=Engine(backend,4);e.enter();progress=deepcopy(e.s._e2_progress)
        result=e.s.measure((0.,0.),1)
        return dict(near=result=='near',auto_clear=e.s.cleared=={1},
            exactly_two_requests=[x['action'] for x in e.api.events[1:]]==['measure','clear'],
            full_ten_seconds=round(e.api.virtual_time*1e6)==10000000,
            no_fake_service_progress=e.s._e2_progress==progress),dict(events=e.api.events,controller=encode(controller_state(e.s)))
    direct_fixture(record,fixed,'normal_near_autoclear',normal_near)

    result,_=run_full(fixed,record.budget,record.run_id('near_partial_station'),guard=vendor.GuardConfig(learning_request_cap=1))
    record.record(result,fixed,'near_post_guard_before_auto_clear','real_interface_fixture')
    ep=result['episode'];macro=ep['macros'][0];state=decode(ep['engine_final'])
    record.check('partial_station_retains_obligation',not macro['macro_completed'] and macro['payload']['index'] in state['todo'])
    record.check('near_guard_prevents_unaccounted_auto_clear',macro['delta_us']==5000000 and macro['event_range'][1]-macro['event_range'][0]==1)
    record.check('fallback_once_complete_tail',result['success'] and ep['tail_virtual_us']>0 and ep['cost_partition_error_us']==0 and ep['fallback_reason']=='learning_primitive_cap')

    # Controlled public forced-A0 marker and request cap on a valid saved world.
    run_id=record.run_id('partial_forced_A0');record.budget.start(run_id,'fixture',dict(world_sha256=world['world_sha256'],mode=4,fixture='partial_forced_A0',
        prefix_event_count=first.token.accepted_event_count,prefix_virtual_us=first.token.prefix_virtual_us))
    clock=BranchClock();env=clone_private(first,clock)
    e=Engine.restore(CountedBackend(env,record.budget),first.token,clock=clock)
    active=first.prepared.meta['teacher_task']['key']
    e.state['forced_teacher_channels'].add(active)
    e.api.guard=vendor.GuardConfig(learning_request_cap=e.api.learning_requests+1)
    p=e.prepare();clock.start();ep=e.run(initial_action=(p,p.choices['teacher_id']))
    checks=dict(forced_marker_retained=active in decode(ep['engine_final'])['forced_teacher_channels'],
        incomplete_A0=not ep['macros'][0]['macro_completed'],full_tail=ep['success'] and ep['tail_virtual_us']>0,
        no_slot_refund=ep['slots_remaining']==2,cost_partition=ep['cost_partition_error_us']==0)
    passed=all(checks.values());record.budget.finish(passed,dict(checks=checks,fixture='partial_forced_A0'))
    result=dict(schema='bc-rpi-real-interface-fixture-v1',run_id=run_id,kind='fixture',success=passed,
        modeled_full_virtual_us=env._virtual_us,checks=checks,episode=ep,environment_log=env.log,
        prefix_event_count=first.token.accepted_event_count,prefix_virtual_us=first.token.prefix_virtual_us,
        verification_kind='controlled_public_forced_marker_and_guard_on_saved_private_world')
    record.record(result,world,'partial_forced_A0','real_interface_fixture');record.check('partial_forced_A0',passed,checks)

    def failure_bookkeeping(env,backend):
        e=Engine(backend,4);e.enter();e.s.measure((100.,0.),1)
        before=deepcopy(e.s._e2_progress);failed=e.s.clear((3999.,3999.),1,certified=False)
        no_signal=e.s.measure((3999.,3999.),20)
        return dict(clear_failed=not failed,failed_ledger=(3999.,3999.) in e.s._e2_failed_clear[1],
            no_signal=no_signal=='no_signal',unknown_not_cleared=20 not in e.s.cleared,
            station_coverage_not_faked=not e.s.scanned[20],service_progress_unchanged=e.s._e2_progress==before),dict(events=e.api.events,controller=encode(controller_state(e.s)))
    direct_fixture(record,fixed,'failure_and_no_signal_ledgers',failure_bookkeeping)

    def rejected_request(env,backend):
        first_response=backend.enter();second_response=backend.enter()
        return dict(first_accepted=first_response['accepted'],second_proved_rejected=second_response['accepted'] is False,
                    no_extra_effect=len(env.log)==1 and env._virtual_us==0),dict(first=first_response,second=second_response)
    direct_fixture(record,fixed,'real_duplicate_enter_rejection',rejected_request)

    def accepted_then_lost_response(env,backend):
        class TransportFault:
            enter=staticmethod(backend.enter);clear=staticmethod(backend.clear);exit=staticmethod(backend.exit)
            @staticmethod
            def measure(*args):
                backend.measure(*args)
                raise TimeoutError('G0 injected response loss AFTER actual LocalEnv accepted; evaluator journal still knows cost')
        e=Engine(TransportFault(),4);e.enter();errors=[]
        for _ in range(2):
            try:e.s.measure((100.,0.),1)
            except vendor.InterfaceFailure as exc:errors.append(str(exc))
        return dict(both_failures_caught=len(errors)==2,one_actual_measure=env.measures==1,
            no_blind_fallback=e.api.takeover_reason is None,
            unresolved_public_interface=e.api.unknown_backend_failure is not None,
            actual_accepted_cost_not_zero=env._virtual_us==25000000,
            response_not_fabricated=len(e.api.events)==1),dict(errors=errors,public_events=e.api.events,
                evaluator_known_accepted_response=env.log[-1],injection='local transport fixture, not an official HTTP test')
    direct_fixture(record,fixed,'accepted_then_lost_response',accepted_then_lost_response)
    summary['actual_executions']=record.budget.data['executions_started']-start_runs
    summary['scope']='Actual LocalEnv calls, exact saved-history suffixes, and registered constructed interface fixtures; no neural training'
    return summary
