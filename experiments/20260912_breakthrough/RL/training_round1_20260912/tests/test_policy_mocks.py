"""Pure Policy branch tests: mocked feature builder, engine, worker and clock.

No inference subprocess, evaluator, environment, training module or saved world
is imported or constructed. The real pure retained-ID threshold rule is used.
"""
from copy import deepcopy
import math
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from .. import policy as policy_module
from ..selection import float32


IDS = ["a" * 64, "b" * 64, "c" * 64]


class Clock:
    def __init__(self):
        self.value = 100.

    def __call__(self):
        self.value += .125
        return self.value


def response(scores=None):
    return dict(scores=list(scores) if scores is not None else [0., float32(.01), float32(.005)],
        roundtrip_wall_s=.025, forward_wall_s=.01, forward_cpu_s=.009,
        tensor_build_wall_s=.005, tensor_build_cpu_s=.004)


class PolicyMockTests(unittest.TestCase):
    def setUp(self):
        self.prepared = SimpleNamespace(choice_id="synthetic-source-choice", prepare_wall_s=.25,
            choices=dict(teacher_id=IDS[0], candidate_ids=list(IDS), eligible=True, rejections=[]),
            meta=dict(teacher_task=dict(kind="source", key=7)))
        self.engine = SimpleNamespace(s=SimpleNamespace(mode=4),
            state=dict(interventions_remaining=2, forced_teacher_channels=set()),
            api=SimpleNamespace(events=[{"synthetic_public_event": True}]),
            expand=Mock(name="expand"))
        self.snapshot = dict(candidate_ids=list(IDS), teacher_id=IDS[0],
            diagnostics=dict(events_dropped=11), features={"synthetic": True})
        self.worker = SimpleNamespace(disabled=False, checkpoint_sha="d" * 64,
            score=Mock(name="score", return_value=response()))
        self.policy = policy_module.Policy(self.worker, margin=0.)
        self.builder = self.enterContext(patch.object(policy_module, "build_snapshot",
            side_effect=lambda prepared, events: deepcopy(self.snapshot)))
        self.enterContext(patch.object(policy_module.time, "monotonic", Clock()))

    def recorded(self, selected):
        self.assertEqual(len(self.policy.decisions), 1, "Every select path needs one decision row")
        row = self.policy.decisions[0]
        self.assertEqual(row["choice_id"], self.prepared.choice_id)
        self.assertEqual(row["selected_id"], selected)
        self.assertIs(type(row["model_scored"]), bool)
        self.assertEqual(row["model_scored"], "scores" in row)
        selector = row["selector_wall_s"]
        total = row["complete_prepare_feature_ipc_forward_selection_wall_s"]
        self.assertTrue(math.isfinite(selector) and selector >= 0.)
        self.assertEqual(total, self.prepared.prepare_wall_s + selector)
        return row

    def select(self):
        selected = self.policy.select(self.engine, self.prepared)
        return selected, self.recorded(selected)

    def fallback(self, *, reason=None, expanded=False):
        selected, row = self.select()
        self.assertEqual(selected, self.prepared.choices["teacher_id"])
        self.assertTrue(row["rejection"])
        self.assertFalse(row["model_scored"])
        if reason is not None:
            self.assertEqual(row["rejection"], reason)
        if expanded:
            self.engine.expand.assert_called_once_with(self.prepared)
        else:
            self.engine.expand.assert_not_called()
        self.builder.assert_not_called()
        self.worker.score.assert_not_called()
        return row

    def test_constructor_rejects_invalid_calibration_margin(self):
        for margin in (-1., float("nan"), float("inf"), True, "0.1", None):
            with self.subTest(margin=margin), self.assertRaises(ValueError):
                policy_module.Policy(self.worker, margin)

    def test_non_source_entry_is_teacher_without_expansion_or_scoring(self):
        self.prepared.meta["teacher_task"]["kind"] = "station"
        self.fallback()

    def test_q3_source_entry_is_teacher_without_expansion_or_scoring(self):
        self.engine.s.mode = 3
        self.fallback()

    def test_invalid_slot_count_is_not_cast_or_used_for_inference(self):
        for slots in (-1, 3, True, 1.5, "1", None):
            self.engine.state["interventions_remaining"] = slots
            self.policy.reset_episode()
            with self.subTest(slots=slots):
                self.fallback(reason="invalid_slots")

    def test_b0_is_teacher_without_expansion_or_scoring(self):
        self.engine.state["interventions_remaining"] = 0
        self.fallback(reason="slots_or_forced_teacher")

    def test_active_forced_teacher_channel_is_not_scored(self):
        self.engine.state["forced_teacher_channels"] = {7}
        self.fallback(reason="slots_or_forced_teacher")

    def test_other_forced_teacher_channel_does_not_block_active_source(self):
        self.engine.state["forced_teacher_channels"] = {8}
        selected, row = self.select()
        self.assertEqual(selected, IDS[1])
        self.assertIsNone(row["rejection"])
        self.worker.score.assert_called_once()

    def test_one_remaining_slot_can_select_without_spending_the_slot(self):
        self.engine.state["interventions_remaining"] = 1
        selected, row = self.select()
        self.assertEqual(selected, IDS[1])
        self.assertEqual(row["slots_before"], 1)
        self.assertEqual(self.engine.state["interventions_remaining"], 1)

    def test_disabled_policy_never_reuses_even_an_enabled_worker(self):
        self.policy.disabled = True
        self.fallback(reason="neural_worker_disabled")

    def test_disabled_worker_is_not_expanded_or_scored(self):
        self.worker.disabled = True
        self.fallback(reason="neural_worker_disabled")

    def test_ineligible_expanded_source_falls_back_before_feature_construction(self):
        self.prepared.choices["eligible"] = False
        self.fallback(reason="not_eligible_or_teacher_only", expanded=True)

    def test_teacher_only_expanded_source_is_retained_without_scoring(self):
        self.prepared.choices["candidate_ids"] = [IDS[0]]
        self.fallback(reason="not_eligible_or_teacher_only", expanded=True)

    def test_generator_error_falls_back_before_feature_construction(self):
        self.prepared.choices["rejections"] = ["generator_error: synthetic geometry failure"]
        row = self.fallback(expanded=True)
        self.assertIn("ValueError:", row["rejection"])

    def test_non_error_candidate_rejections_do_not_disable_complete_retained_set(self):
        self.prepared.choices["rejections"] = ["duplicate_candidate", "not_retained"]
        selected, row = self.select()
        self.assertEqual(selected, IDS[1])
        self.assertIsNone(row["rejection"])

    def test_expand_exception_keeps_teacher_and_complete_timing(self):
        self.engine.expand.side_effect = ValueError("synthetic expand failure")
        row = self.fallback(expanded=True)
        self.assertIn("synthetic expand failure", row["rejection"])

    def test_feature_exception_keeps_teacher_and_complete_timing(self):
        self.builder.side_effect = ValueError("synthetic public feature failure")
        selected, row = self.select()
        self.assertEqual(selected, IDS[0])
        self.assertIn("synthetic public feature failure", row["rejection"])
        self.worker.score.assert_not_called()

    def test_exact_prepared_choice_and_full_public_events_reach_builder(self):
        selected, row = self.select()
        self.assertEqual(selected, IDS[1])
        self.engine.expand.assert_called_once_with(self.prepared)
        self.builder.assert_called_once_with(self.prepared, self.engine.api.events)
        self.worker.score.assert_called_once_with(self.snapshot)
        self.assertEqual(row["events_dropped"], 11)

    def test_valid_intervention_records_checkpoint_scores_and_all_latency_components(self):
        selected, row = self.select()
        self.assertEqual(selected, IDS[1])
        self.assertEqual(row["teacher_id"], IDS[0])
        self.assertEqual(row["slots_before"], 2)
        self.assertEqual(row["batch_size"], 1)
        self.assertTrue(row["model_scored"])
        self.assertEqual(row["checkpoint_sha256"], self.worker.checkpoint_sha)
        self.assertEqual(row["candidate_ids"], IDS)
        self.assertEqual(row["scores"], self.worker.score.return_value["scores"])
        self.assertEqual(row["inference_roundtrip_wall_s"], .025)
        self.assertEqual(row["model_forward_wall_s"], .01)
        self.assertEqual(row["model_forward_cpu_s"], .009)
        self.assertEqual(row["tensor_build_wall_s"], .005)
        self.assertEqual(row["tensor_build_cpu_s"], .004)
        self.assertGreaterEqual(row["candidate_and_feature_wall_s"], 0.)
        self.assertLessEqual(row["candidate_and_feature_wall_s"], row["selector_wall_s"])
        self.assertIsNone(row["rejection"])

    def test_equal_strict_threshold_keeps_teacher(self):
        gain = float32(1 / 1024)
        self.policy.margin = gain - .0005
        self.worker.score.return_value = response([0., gain, -gain])
        selected, row = self.select()
        self.assertEqual(row["strict_threshold"], gain)
        self.assertEqual(row["predicted_gain"], gain)
        self.assertEqual(row["predicted_candidate_id"], IDS[1])
        self.assertEqual(selected, IDS[0])
        self.assertTrue(row["model_scored"], "A threshold rejection still used the model")

    def test_gain_strictly_above_threshold_intervenes(self):
        self.worker.score.return_value = response([0., float32(1 / 1024), 0.])
        self.assertEqual(self.select()[0], IDS[1])

    def test_positive_gain_below_threshold_does_not_intervene(self):
        self.worker.score.return_value = response([0., float32(1 / 4096), 0.])
        selected, row = self.select()
        self.assertEqual(selected, IDS[0])
        self.assertGreater(row["predicted_gain"], 0.)

    def test_teacher_best_score_keeps_teacher(self):
        self.worker.score.return_value = response([float32(.02), float32(.01), 0.])
        selected, row = self.select()
        self.assertEqual(selected, IDS[0])
        self.assertEqual(row["predicted_candidate_id"], IDS[0])
        self.assertEqual(row["predicted_gain"], 0.)

    def test_equal_nonreference_scores_tie_by_hash_with_nonzero_teacher_index(self):
        self.prepared.choices["teacher_id"] = self.snapshot["teacher_id"] = IDS[2]
        self.worker.score.return_value = response([float32(.01), float32(.01), 0.])
        selected, row = self.select()
        self.assertEqual(selected, IDS[0])
        self.assertEqual(row["teacher_id"], IDS[2])
        self.assertEqual(row["gains"][2], 0.)

    def test_force_teacher_probe_still_expands_builds_scores_and_records_predicted_intervention(self):
        self.policy.force_teacher = True
        selected, row = self.select()
        self.assertEqual(selected, IDS[0])
        self.assertEqual(row["predicted_candidate_id"], IDS[1])
        self.assertGreater(row["predicted_gain"], row["strict_threshold"])
        self.assertTrue(row["force_teacher_probe"])
        self.assertTrue(row["model_scored"], "A forced-teacher probe must count actual validated scoring")
        self.engine.expand.assert_called_once_with(self.prepared)
        self.builder.assert_called_once()
        self.worker.score.assert_called_once()

    def test_force_teacher_probe_does_not_bypass_exhausted_slots(self):
        self.policy.force_teacher = True
        self.engine.state["interventions_remaining"] = 0
        self.fallback(reason="slots_or_forced_teacher")

    def test_invalid_or_nonfinite_scores_revert_to_teacher(self):
        for scores in ([0., float("nan"), 0.], [0., float("inf"), 0.],
                       [0., True, 0.], [0., .1, 0.], [0.], (0., 0., 0.), "invalid"):
            self.policy.reset_episode()
            self.worker.score.return_value = dict(response(), scores=scores)
            with self.subTest(scores=scores):
                selected, row = self.select()
                self.assertEqual(selected, IDS[0])
                self.assertIn("ValueError:", row["rejection"])

    def test_missing_or_malformed_worker_response_reverts_to_teacher(self):
        for output in (None, {}, {"scores": [0., float32(.01), 0.]}, []):
            self.policy.reset_episode()
            self.worker.score.return_value = output
            with self.subTest(output=output):
                selected, row = self.select()
                self.assertEqual(selected, IDS[0])
                self.assertTrue(row["rejection"])

    def test_worker_timeout_latches_disabled_and_is_never_reused(self):
        def timeout(snapshot):
            self.worker.disabled = True
            raise TimeoutError("synthetic IPC timeout")
        self.worker.score.side_effect = timeout
        selected, row = self.select()
        self.assertEqual(selected, IDS[0])
        self.assertIn("TimeoutError:", row["rejection"])
        self.assertTrue(self.policy.disabled)
        self.policy.reset_episode()
        self.engine.expand.reset_mock()
        self.builder.reset_mock()
        self.worker.score.reset_mock()
        self.worker.disabled = False  # A sticky policy latch must also prevent reuse.
        self.fallback(reason="neural_worker_disabled")

    def test_reset_episode_clears_decisions_not_margin_probe_or_worker_identity(self):
        self.policy.force_teacher = True
        self.select()
        self.policy.disabled = True
        self.policy.reset_episode()
        self.assertEqual(self.policy.decisions, [])
        self.assertEqual(self.policy.margin, 0.)
        self.assertTrue(self.policy.force_teacher)
        self.assertIs(self.policy.worker, self.worker)
        self.assertTrue(self.policy.disabled)
        self.worker.score.assert_called_once()

    def test_selector_does_not_spend_slots_or_mutate_public_engine_history(self):
        before_state = deepcopy(self.engine.state)
        before_events = deepcopy(self.engine.api.events)
        self.select()
        self.assertEqual(self.engine.state, before_state)
        self.assertEqual(self.engine.api.events, before_events)

    def test_repeated_calls_keep_separate_rows_and_each_actual_prepare_cost(self):
        self.select()
        first = deepcopy(self.policy.decisions[0])
        self.prepared.choice_id = "synthetic-second-choice"
        self.prepared.prepare_wall_s = .75
        self.assertEqual(self.policy.select(self.engine, self.prepared), IDS[1])
        self.assertEqual(len(self.policy.decisions), 2)
        self.assertEqual(self.policy.decisions[0], first)
        second = self.policy.decisions[1]
        self.assertEqual(second["choice_id"], "synthetic-second-choice")
        self.assertEqual(second["complete_prepare_feature_ipc_forward_selection_wall_s"],
                         .75 + second["selector_wall_s"])

    def test_memory_error_is_recorded_with_timing_and_propagated_not_hidden_as_c7_success(self):
        for stage in ("expand", "features", "worker"):
            self.policy.reset_episode()
            self.engine.expand.side_effect = None
            self.builder.side_effect = lambda prepared, events: deepcopy(self.snapshot)
            self.worker.score.side_effect = None
            error = MemoryError("synthetic resource stop")
            if stage == "expand":
                self.engine.expand.side_effect = error
            elif stage == "features":
                self.builder.side_effect = error
            else:
                self.worker.score.side_effect = error
            with self.subTest(stage=stage), self.assertRaisesRegex(MemoryError, "synthetic resource stop"):
                self.policy.select(self.engine, self.prepared)
            row = self.recorded(IDS[0])
            self.assertIn("MemoryError:", row["rejection"])


if __name__ == "__main__":
    unittest.main()
