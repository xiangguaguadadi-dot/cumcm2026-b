"""G0 synthetic control fixtures. These are not valid full competition worlds."""
from __future__ import annotations
import copy
import math
from pathlib import Path
import sys
import unittest

EXEC=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(EXEC))
from core import run_episode,teacher_selector
from core.engine import load_c7,build_snapshot
from core.schema import (GLOBAL_DIM,CHANNEL_DIM,CANDIDATE_DIM,validate_snapshot,
                         CANDIDATE_FEATURE_NAMES,GLOBAL_FEATURE_NAMES,freeze_copy)
from core.geometry import discovery_stations,optical_grid,fallback_paper_bounds
from core.interface import MeteredInterface,GuardConfig,FallbackRequired,InterfaceFailure
from core.fallback import run_fallback

class ScriptedInterface:
    """No hidden-world generation: returns preset results and analytic costs."""
    def __init__(self,measure_kind='no_signal',clear_success=False):
        self.position=(0.,0.);self.channel=1;self.t=0.;self.requests=[]
        self.measure_kind=measure_kind;self.clear_success=clear_success
        self.transport_attempts=0;self.reject=False;self.extra_cost=0.
    def _r(self,kind,cost=0.,**fields):
        self.requests.append(kind)
        if self.reject:return {'accepted':False,'virtual_time_s':self.t}
        self.t=round(self.t+cost+self.extra_cost,6)
        return {'accepted':True,'virtual_time_s':self.t,**fields}
    def enter(self):return self._r('enter',remaining_real_duration_s=1200)
    def measure(self,x,y,ch):
        cost=math.dist(self.position,(x,y))/5+5+int(ch!=self.channel)
        if not self.reject:self.position=(x,y);self.channel=ch
        self.transport_attempts+=2  # a retry internal to the adapter, one response
        return self._r('measure',cost,measure_result=self.measure_kind,svd_deg=0.)
    def clear(self,x,y,ch):
        cost=math.dist(self.position,(x,y))/5+3+2*self.clear_success
        if not self.reject:self.position=(x,y)
        return self._r('clear',cost,clear_result='success' if self.clear_success else 'no_target_in_range')
    def exit(self):return self._r('exit',exit_reason='user_exit')

class GeometryFixtures(unittest.TestCase):
    def test_01_discovery_grid_contract(self):
        p=discovery_stations();self.assertEqual(len(p),49);self.assertEqual(len(set(p)),49)
        self.assertEqual({x for x,y in p},set(range(-1800,1801,600)))
        self.assertEqual({y for x,y in p},set(range(-1800,1801,600)))
    def test_02_discovery_path_bound(self):
        p=discovery_stations();self.assertEqual(sum(math.dist(a,b) for a,b in zip(p,p[1:])),28800.)
    def test_03_optical_grid_contract(self):
        p=optical_grid((0.,0.),0.);self.assertEqual(len(p),304)
        self.assertEqual({x for x,y in p},set(range(0,1501,20)))
        self.assertEqual({y for x,y in p},{-30.,-10.,10.,30.})
    def test_04_optical_path_with_paid_return(self):
        p=optical_grid((120.,-30.),73.);origin=(120.,-30.)
        length=math.dist(origin,p[0])+sum(math.dist(a,b) for a,b in zip(p,p[1:]))+math.dist(p[-1],origin)
        self.assertLess(length,7591.)
    def test_05_rounding_margin_extreme_grid(self):
        bound=fallback_paper_bounds();beta=bound['max_transverse_m']
        self.assertLess(beta,27.)
        point=(1490.,beta)
        self.assertLess(min(math.dist(point,q) for q in optical_grid((0.,0.),0.)),20.)
    def test_06_boundary_direction_is_discoverable(self):
        source=(1800.,0.);axis=(1.,0.)
        hits=[p for p in discovery_stations() if math.dist(source,p)<=1000 and
              sum((p[k]-source[k])*axis[k] for k in (0,1))>=0]
        self.assertTrue(hits)
        self.assertLess(fallback_paper_bounds()['virtual_bound_s'],53000.)

class MeterFixtures(unittest.TestCase):
    def meter(self,**kwargs):
        b=ScriptedInterface();a=MeteredInterface(b,**kwargs);a.enter();return b,a
    def test_07_measure_cost_and_switch(self):
        b,a=self.meter();a.measure(30.,40.,3)
        self.assertEqual(a.virtual_time,16.);self.assertEqual(a.channel,3)
    def test_08_clear_does_not_switch_channel(self):
        b,a=self.meter();b.clear_success=True;a.clear(30.,40.,4)
        self.assertEqual(a.virtual_time,15.);self.assertEqual(a.channel,1);self.assertEqual(a.cleared,{4})
    def test_09_paid_repeat_and_internal_retry(self):
        b,a=self.meter();a.measure(10.,0.,2);a.measure(0.,0.,3);a.measure(10.,0.,2)
        self.assertEqual(len(a.events),4);self.assertEqual(b.transport_attempts,6)
        self.assertEqual(a.learning_requests,3)
    def test_10_post_primitive_cap_keeps_accepted_event(self):
        b,a=self.meter(guard=GuardConfig(learning_request_cap=1))
        with self.assertRaises(FallbackRequired):a.measure(10.,0.,2)
        self.assertEqual(a.position,(10.,0.));self.assertEqual(a.learning_requests,1)
        self.assertEqual(len(a.events),2);self.assertEqual(a.virtual_time,8.)
    def test_11_box_blocks_before_request(self):
        b,a=self.meter()
        with self.assertRaises(FallbackRequired):a.measure(4000.1,0.,1)
        self.assertEqual(b.requests,['enter'])
    def test_12_virtual_cap_blocks_before_request(self):
        b,a=self.meter(guard=GuardConfig(learning_time_limit_s=0))
        with self.assertRaises(FallbackRequired):a.measure(0.,0.,1)
        self.assertEqual(b.requests,['enter'])
    def test_13_real_reserve_is_conditional(self):
        now=[0.];b,a=self.meter(clock=lambda:now[0]);now[0]=1171.
        with self.assertRaises(FallbackRequired):a.measure(0.,0.,1)
        self.assertEqual(a.takeover_reason,'fallback_real_reserve')
    def test_14_exit_requires_certificate(self):
        b,a=self.meter()
        with self.assertRaises(InterfaceFailure):a.exit()
        self.assertEqual(b.requests,['enter'])
    def test_15_rejection_keeps_physical_ledger(self):
        b,a=self.meter();b.reject=True
        with self.assertRaises(InterfaceFailure):a.measure(20.,0.,2)
        self.assertEqual(a.position,(0.,0.));self.assertEqual(a.virtual_time,0.);self.assertEqual(a.learning_requests,0)
    def test_16_cost_disagreement_is_not_hidden(self):
        b,a=self.meter();b.extra_cost=1.
        with self.assertRaises(InterfaceFailure):a.measure(0.,0.,1)
        self.assertEqual(len(a.events),2);self.assertEqual(a.events[-1]['accounting_error_s'],1.)
    def test_17_contract_cannot_be_silently_weakened(self):
        with self.assertRaises(ValueError):GuardConfig(box_m=4001.)
        with self.assertRaises(ValueError):GuardConfig(learning_request_cap=10001)
        with self.assertRaises(ValueError):GuardConfig(no_progress_limit=33)
        with self.assertRaises(ValueError):GuardConfig(real_reserve_s=float('nan'))
        with self.assertRaises(ValueError):GuardConfig(deterministic_request_bound_s=-1)

class EngineFixtures(unittest.TestCase):
    def snapshot(self,mode=3):
        b=ScriptedInterface();api=MeteredInterface(b);s=load_c7().Solver(api,mode=mode)
        s.route_successor=None
        return s,api,build_snapshot(s,set(range(len(s.points))),api,0,0,0.)[0]
    def test_18_snapshot_dimensions(self):
        s,a,x=self.snapshot();self.assertTrue(validate_snapshot(x))
        self.assertEqual((GLOBAL_DIM,CHANNEL_DIM,CANDIDATE_DIM),(16,12,16))
    def test_19_candidate_enumeration_no_effects(self):
        s,a,x=self.snapshot();self.assertEqual(a.events,[]);self.assertIsNone(s.route_successor)
        self.assertEqual(s.counters['measure'],0)
    def test_20_stable_sort_without_teacher_feature(self):
        s,a,x=self.snapshot();self.assertEqual(x['candidate_ids'],sorted(x['candidate_ids']))
        self.assertNotIn('teacher',str(CANDIDATE_FEATURE_NAMES)+str(GLOBAL_FEATURE_NAMES))
        self.assertTrue(x['valid_mask'][x['teacher_index']])
    def test_21_payload_service_identity(self):
        s,a,x=self.snapshot(mode=4);p=x['candidates'][x['teacher_index']]
        for k in ('route_successor','stage','state_version','service_state','controller_patch','stop_contract'):
            self.assertIn(k,p)
        self.assertIn('config',x['observable_state'])
    def test_22_snapshot_detached_mutation(self):
        s,a,x=self.snapshot();x['observable_state']['position'][0]=999
        x['candidates'][0]['target'][0]=999
        self.assertEqual(s.position,(0.,0.));self.assertIsNone(s.route_successor)
    def test_23_synthetic_no_signal_episode_partition(self):
        r=run_episode(ScriptedInterface(),mode=3)
        self.assertFalse(r['success']);self.assertEqual(r['cleared_count'],0)
        self.assertFalse(r['true_completeness_checked']);self.assertIn('lower bound',r['error'])
        self.assertAlmostEqual(r['prefix_time_s']+sum(d['delta_time_s'] for d in r['decisions'])+r['tail_time_s'],r['total_time_s'])
    def test_24_forced_fallback_at_entry_partition(self):
        r=run_episode(ScriptedInterface(),mode=4,guard=GuardConfig(learning_request_cap=0))
        self.assertFalse(r['success']);self.assertEqual(r['decisions'],[])
        self.assertIn('lower bound',r['error'])
        self.assertEqual(r['business_primitive_count'],981)
        self.assertEqual(r['tail_time_s'],r['total_time_s'])
    def test_25_selector_fallback_is_one_real_macro_choice(self):
        def choose(x):
            return {'index':next(i for i,p in enumerate(x['candidates']) if p['kind']=='fallback'),
                    'metadata':{'old_logprob':-1.}}
        r=run_episode(ScriptedInterface(),mode=3,selector=choose)
        self.assertFalse(r['success']);self.assertEqual(len(r['decisions']),1)
        self.assertEqual(r['decisions'][0]['delta_time_s'],0.)
        self.assertEqual(r['tail_time_s'],r['total_time_s'])
    def test_26_invalid_selector_is_failure_not_fake_sample(self):
        r=run_episode(ScriptedInterface(),mode=3,selector=lambda x:-1)
        self.assertFalse(r['success']);self.assertEqual(r['terminal'],'failure')
        self.assertEqual(r['decisions'],[]);self.assertIn('invalid candidate',r['error'])
    def test_27_selector_mutation_does_not_change_execution(self):
        def choose(x):
            i=x['teacher_index'];x['candidates'][i]['target']=[999.,999.]
            return i
        a=run_episode(ScriptedInterface(),mode=3)
        b=run_episode(ScriptedInterface(),mode=3,selector=choose)
        self.assertFalse(b['success']);self.assertIn('lower bound',b['error'])
        self.assertEqual(a['total_time_s'],b['total_time_s'])
        self.assertEqual([e['request'] for e in a['events']],[e['request'] for e in b['events']])

    def test_28_positive_history_cannot_become_absent(self):
        b=ScriptedInterface();a=MeteredInterface(b);a.enter()
        a.cleared=set(range(1,11));a.positive_observations.add((11,0.,0.,'direction'))
        a.start_fallback('synthetic_contradiction')
        with self.assertRaisesRegex(InterfaceFailure,'Positive history'):
            run_fallback(a)
        self.assertFalse(a.exited)
    def test_29_seventeenth_success_is_public_contradiction(self):
        b=ScriptedInterface(clear_success=True);a=MeteredInterface(b);a.enter()
        a.cleared=set(range(1,17))
        with self.assertRaisesRegex(InterfaceFailure,'upper bound'):
            a.clear(0.,0.,17)
        self.assertEqual(len(a.events),2)

if __name__=='__main__':unittest.main()
