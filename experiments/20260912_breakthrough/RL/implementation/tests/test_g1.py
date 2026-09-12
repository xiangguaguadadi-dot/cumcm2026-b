"""G1 oracle/aggregation/replay arithmetic tests; no environment construction."""
from copy import deepcopy
import unittest
from ..deploy.state import encode
from ..evaluator.g1 import normalized_cost,should_replace,verify_replay,aggregate


def result(us=1000000000,success=True,plan=None,kind='full'):
    plan=plan or []
    return dict(modeled_full_virtual_us=us,true_terminal_n=10,success=success,kind=kind,
        environment_log=[dict(action='enter',request={},response=dict(accepted=True,virtual_time_s=0.,real_timestamp_ms=123))],
        episode=dict(slots_remaining=2-len(plan),engine_final=encode(dict(used_operation_ids=[p['action_id'] for p in plan]))),
        extra=dict(applied_plan=plan) if kind=='full' else {})


class G1PureContracts(unittest.TestCase):
    def test_normalization_once_and_failed_tail_penalty(self):
        self.assertEqual(normalized_cost(result(1000000000)),0.1)
        self.assertEqual(normalized_cost(result(0,False)),100.)
        with self.assertRaises(ValueError):normalized_cost(dict(result(),true_terminal_n=0))

    def test_no_intervention_wins_tie_and_failure_never_looks_fast(self):
        plan=[dict(choice_id='a'*64,action_id='b'*64)]
        self.assertFalse(should_replace(result(),[],result(),plan))
        self.assertTrue(should_replace(result(),[],result(999999999),plan))
        self.assertFalse(should_replace(result(),[],result(0,False),plan))

    def test_suffix_A0_uses_observed_prefix_intervention_history(self):
        plan=[dict(choice_id='a'*64,action_id='b'*64)]
        self.assertTrue(all(verify_replay(result(plan=plan),result(plan=plan,kind='suffix'),plan).values()))
        bad=result(plan=plan,kind='suffix');bad['episode']['engine_final']=encode(dict(used_operation_ids=[]))
        self.assertFalse(verify_replay(result(plan=plan),bad,plan)['all_planned_interventions_applied'])

    def test_full_replay_checks_entire_plan_not_just_length(self):
        plan=[dict(choice_id='a'*64,action_id='b'*64)]
        bad=result(plan=plan);bad['extra']['applied_plan']=[dict(choice_id='c'*64,action_id='b'*64)]
        self.assertFalse(verify_replay(result(plan=plan),bad,plan)['all_planned_interventions_applied'])

    def test_replay_ignores_only_machine_response_fields(self):
        a=result();b=deepcopy(a);b['environment_log'][0]['response']['real_timestamp_ms']=999
        self.assertTrue(all(verify_replay(a,b,[]).values()))
        b['environment_log'][0]['request']['channel']=2
        self.assertFalse(verify_replay(a,b,[])['exact_requests_and_observations'])

    def test_partial_world_set_has_no_headroom_conclusion(self):
        report=aggregate([dict(status='incomplete_budget',index=0)],registered_count=24)
        self.assertIsNone(report['whole_set_means'])
        self.assertEqual(report['completed_worlds'],0)

    def test_equal_world_means_not_mean_of_percentages(self):
        rows=[dict(status='complete',group='a',n=10,failed_branches=0,c7_seconds_per_source=100.,o1_seconds_per_source=50.,o2_seconds_per_source=40.),
              dict(status='complete',group='b',n=16,failed_branches=1,c7_seconds_per_source=200.,o1_seconds_per_source=190.,o2_seconds_per_source=180.)]
        report=aggregate(rows,registered_count=2)
        self.assertAlmostEqual(report['o1_relative_improvement_pct'],20.)
        self.assertEqual(report['total_source_count'],26)
        self.assertEqual(report['branch_failures_retained'],1)
        self.assertFalse(report['next_stage_authorized'])


if __name__=='__main__':unittest.main()
