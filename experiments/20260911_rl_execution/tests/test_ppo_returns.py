"""Synthetic mathematical fixtures: no task worlds or simulator interactions."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ppo.returns import complete_episode_returns, episode_equal_sum


class CompleteEpisodeReturnTests(unittest.TestCase):
    def test_fallback_is_one_cost_tail_not_extra_decisions(self):
        labels = complete_episode_returns([1000, 2000], tail_time_s=7000,
                                         true_n=10, terminal="success")
        self.assertEqual(labels.returns, (-1.0, -0.9))
        self.assertEqual(len(labels.returns), 2)
        self.assertEqual(labels.accounted_cost_s, 10000)

    def test_explicit_tail_and_once_folded_tail_are_identical(self):
        separate = complete_episode_returns([1000, 2000], tail_time_s=7000,
                                             true_n=10, terminal="success")
        folded = complete_episode_returns([1000, 9000], tail_time_s=0,
                                          true_n=10, terminal="success")
        self.assertEqual(separate.returns, folded.returns)

    def test_failure_penalty_added_once_without_bootstrap(self):
        labels = complete_episode_returns([1000, 2000], tail_time_s=7000,
                                         true_n=10, terminal="failure")
        self.assertEqual(labels.returns, (-101.0, -100.9))
        self.assertEqual(labels.terminal_penalty, -100.0)

    def test_true_n_normalizes_once_not_cleared_count(self):
        a = complete_episode_returns([16000], tail_time_s=0, true_n=16,
                                     terminal="failure")
        self.assertEqual(a.returns, (-101.0,))

    def test_artificial_partial_episode_is_not_trainable(self):
        with self.assertRaisesRegex(ValueError, "resume"):
            complete_episode_returns([1000], tail_time_s=0, true_n=10,
                                     terminal="incomplete")

    def test_no_selector_decisions_do_not_create_logprob_rows(self):
        labels = complete_episode_returns([], tail_time_s=53000, true_n=10,
                                          terminal="success")
        self.assertEqual(labels.returns, ())
        self.assertEqual(labels.accounted_cost_s, 53000)
        self.assertEqual(labels.normalized_tail, -5.3)

    def test_episode_weighting_does_not_divide_actor_by_length(self):
        self.assertEqual(episode_equal_sum([[2, 2, 2], [2]]), 4)
        self.assertEqual(episode_equal_sum([[2, 2, 2], []]), 3)

    def test_invalid_costs_and_training_labels_rejected(self):
        for cost in [-1, float("nan"), float("inf"), True]:
            with self.subTest(cost=cost), self.assertRaises(ValueError):
                complete_episode_returns([cost], tail_time_s=0, true_n=10,
                                         terminal="success")
        for n in [0, True, 2.5, 17]:
            with self.subTest(n=n), self.assertRaises(ValueError):
                complete_episode_returns([1], tail_time_s=0, true_n=n,
                                         terminal="success")


if __name__ == "__main__":
    unittest.main()
