"""Synthetic Q label/replay checks. No task environment, world generation, or training."""
import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from q_learning import (
    FrozenSnapshot, InvalidSupport, ReplayTransition, behavior_support,
    build_replay_episode, double_q_target, masked_argmax, masked_probabilities,
    normalized_rewards, replay_from_episode, undiscounted_returns,
)


def snapshot(decision=0, reverse=False):
    ids = [f"source-{decision}", f"station-{decision}"]
    payloads = [
        {"kind": "source", "channel": 2, "route_successor": [30, 40], "state_version": decision},
        {"kind": "station", "index": 3, "route_successor": None, "state_version": decision},
    ]
    if reverse:
        ids.reverse()
        payloads.reverse()
    return {
        "schema_version": "rl-core-snapshot-v1", "generator_version": "synthetic-v1",
        "decision_id": decision, "state_version": decision,
        "global_features": [0.0] * 16, "channel_features": [[0.0] * 12 for _ in range(20)],
        "candidate_features": [[0.0] * 16 for _ in range(2)],
        "candidate_ids": ids, "candidates": payloads, "valid_mask": [True, True],
        "teacher_index": 1 if reverse else 0,
    }


class QMathTests(unittest.TestCase):
    def test_normalized_three_step_n10(self):
        rewards = normalized_rewards([10, 20, 30], 10)
        self.assertEqual(rewards, (-0.001, -0.002, -0.003))
        self.assertEqual(undiscounted_returns(rewards), (-0.006, -0.005, -0.003))

    def test_normalized_three_step_n16(self):
        rewards = normalized_rewards([10, 20, 30], 16)
        self.assertEqual(rewards, (-0.000625, -0.00125, -0.001875))
        self.assertAlmostEqual(undiscounted_returns(rewards)[0], -0.00375)

    def test_failure_penalty_once_not_per_step(self):
        rewards = normalized_rewards([10, 20, 30], 10, failed=True)
        self.assertAlmostEqual(sum(rewards), -100.006)
        self.assertEqual(rewards[:2], (-0.001, -0.002))
        self.assertAlmostEqual(undiscounted_returns(rewards)[0], -100.006)

    def test_true_terminal_never_bootstraps(self):
        self.assertEqual(double_q_target(-100.1, True, [math.nan], [math.inf], [False]), -100.1)

    def test_double_q_online_selects_target_evaluates(self):
        self.assertEqual(double_q_target(-1, False, [4, 2], [-50, 300], [True, True]), -51)
        self.assertEqual(double_q_target(-1, False, [4, 2], [-50, 300], [False, True]), 299)

    def test_mask_blocks_large_invalid_q(self):
        self.assertEqual(masked_argmax([math.nan, 2, 2], [False, True, True]), 1)
        self.assertEqual(masked_probabilities([math.inf, 1000, 1000], [False, True, True]), (0, 0.5, 0.5))

    def test_all_masked_is_error_not_fake_terminal(self):
        with self.assertRaises(InvalidSupport):
            double_q_target(-1, False, [5], [7], [False])

    def test_relative_support_keeps_teacher_and_maximum(self):
        self.assertEqual(behavior_support([.95, .049, .001], [True] * 3, 2, kappa=1), (True, False, True))
        self.assertEqual(behavior_support([.95, .049, .001], [True] * 3, 2, kappa=0), (True, True, True))
        self.assertEqual(behavior_support([.9, .1], [True, False], 1), (True, False))

    def test_invalid_probability_or_label_is_rejected(self):
        for count in [0, -1, 17, True, 10.0]:
            with self.assertRaises(ValueError):
                normalized_rewards([10], count)
        for values in [[0, 0], [math.nan, .1], [-.1, .1]]:
            with self.assertRaises(ValueError):
                behavior_support(values, [True, True], 0)
        with self.assertRaises(ValueError):
            normalized_rewards([-1], 10)

    def test_snapshot_deep_copies_complete_successor_payload(self):
        raw = snapshot()
        frozen = FrozenSnapshot.capture(raw)
        raw["candidates"][0]["route_successor"][0] = 999
        raw["candidate_ids"].reverse()
        self.assertEqual(frozen.thaw()["candidates"][0]["route_successor"], [30, 40])
        self.assertEqual(frozen.candidate_ids[0], "source-0")
        changed = snapshot()
        changed["candidates"][0]["route_successor"][0] = 999
        self.assertNotEqual(frozen.sha256, FrozenSnapshot.capture(changed).sha256)

    def test_identity_mismatch_not_resolved_by_old_index(self):
        with self.assertRaises(ValueError):
            build_replay_episode([{"snapshot": snapshot(reverse=True), "index": 0,
                                   "candidate_id": "source-0", "delta_time_s": 10}],
                                 tail_time_s=0, true_source_count=10, failed=False)

    def test_complete_tail_folded_once_with_terminal_d1(self):
        raw = [{"snapshot": snapshot(i), "index": 0, "delta_time_s": c}
               for i, c in enumerate([10, 20])]
        ep = build_replay_episode(raw, tail_time_s=30, true_source_count=10,
                                  failed=False, total_time_s=60)
        self.assertEqual([t.raw_cost_s for t in ep.transitions], [10, 50])
        self.assertEqual([t.reward for t in ep.transitions], [-.001, -.005])
        self.assertEqual([t.mc_return for t in ep.transitions], [-.006, -.005])
        self.assertFalse(ep.transitions[0].terminated)
        self.assertTrue(ep.transitions[-1].terminated)
        self.assertIsNone(ep.transitions[-1].next_snapshot)
        self.assertEqual(ep.transitions[0].next_snapshot.sha256, ep.transitions[1].snapshot.sha256)
        self.assertNotIn("true_source_count", ep.transitions[0].snapshot.thaw())

    def test_double_counted_tail_fails_ledger_check(self):
        with self.assertRaises(ValueError):
            build_replay_episode([{"snapshot": snapshot(), "index": 0, "delta_time_s": 60}],
                                 tail_time_s=30, total_time_s=60, true_source_count=10, failed=False)

    def test_empty_fallback_episode_has_no_synthetic_choice(self):
        ep = build_replay_episode([], tail_time_s=100, true_source_count=10, failed=True)
        self.assertEqual(ep.transitions, ())
        self.assertEqual(ep.total_time_s, 100)

    def test_predecision_prefix_is_ledger_not_future_q_cost(self):
        ep = build_replay_episode([{"snapshot": snapshot(), "index": 0, "delta_time_s": 10}],
                                 tail_time_s=20, prefix_time_s=5, total_time_s=35,
                                 true_source_count=10, failed=False)
        self.assertAlmostEqual(ep.transitions[0].mc_return, -.003)
        self.assertEqual(ep.total_time_s, 35)

    def test_artificial_pause_cannot_enter_complete_replay(self):
        for terminal in [False, None, "incomplete", "truncated", "paused", "unknown"]:
            with self.assertRaises(ValueError):
                replay_from_episode({"decisions": [], "terminal": terminal, "success": False}, 10)
        frozen = FrozenSnapshot.capture(snapshot())
        with self.assertRaises(ValueError):
            ReplayTransition(frozen, 0, "source-0", 0, 0, 0, False, None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
