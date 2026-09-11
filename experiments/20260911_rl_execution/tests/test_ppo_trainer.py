"""Eight synthetic fixtures using the real shared network; no task environment."""
from pathlib import Path
import copy
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import torch
from shared import CandidateNetwork, batch_snapshots
from ppo.trainer import (BCConfig, BCTrainer, PPOConfig, PPOTrainer,
                         clipped_episode_losses, episode_from_core, masked_log_probs)


def snapshot(k=3):
    return {
        "schema_version": "rl-core-snapshot-v1", "generator_version": "synthetic-v1",
        "decision_id": 0, "state_version": 0,
        "global_features": [0.0]*16, "channel_features": [[0.0]*12 for _ in range(20)],
        "candidate_features": [[(i+1)*0.1]+[0.0]*15 for i in range(k)],
        "valid_mask": [True]*(k-1)+[False], "candidate_ids": [f"a{i}" for i in range(k)],
        "teacher_index": 0,
        "candidates": [{"kind": "source", "channel": i+1,
                        "route_successor": [100.0+i, 20.0], "state_version": 0}
                       for i in range(k)],
    }


def raw_episode(trainer, costs=(1000.0,), *, tail=9000.0, failure=False, k=3):
    decisions = []
    for i, cost in enumerate(costs):
        s = snapshot(k)
        s["decision_id"] = i
        choice = trainer.select(s)
        decisions.append({"snapshot": s, "index": choice.index,
                          "metadata": choice.metadata, "delta_time_s": cost})
    return {"decisions": decisions, "tail_time_s": tail,
            "terminal": "failure" if failure else "success", "success": not failure}


class PPOSharedNetworkFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def setUp(self):
        torch.manual_seed(811)

    def test_mask_has_zero_invalid_probability_and_no_invalid_gradient(self):
        x = torch.tensor([[2.0, float("nan"), 1.0]], requires_grad=True)
        mask = torch.tensor([[True, False, True]])
        lp = masked_log_probs(x, mask)
        self.assertEqual(float(lp.exp()[0, 1].detach()), 0)
        (-lp[0, 0]).backward()
        self.assertEqual(float(x.grad[0, 1]), 0)
        self.assertTrue(bool(torch.isfinite(x.grad).all()))
        with self.assertRaises(ValueError):
            masked_log_probs(torch.zeros(1, 2), torch.zeros(1, 2, dtype=torch.bool))

    def test_actor_episode_sum_and_detached_advantage(self):
        new = torch.zeros(4, requires_grad=True)
        old = torch.zeros(4, requires_grad=True)
        values = torch.zeros(4, requires_grad=True)
        old_values = torch.zeros(4, requires_grad=True)
        returns = torch.tensor([2.0, 2.0, 2.0, 2.0], requires_grad=True)
        ids = torch.tensor([0, 0, 0, 1])
        actor, critic = clipped_episode_losses(new, old, values, returns,
            old_values, ids, episode_count=3, clip_epsilon=.2)
        self.assertAlmostEqual(float(actor.detach()), -8/3, places=6)
        self.assertAlmostEqual(float(critic.detach()), 8/3, places=6)
        (actor+critic).backward()
        torch.testing.assert_close(new.grad, torch.full((4,), -2/3))
        self.assertIsNone(old.grad)
        self.assertIsNone(old_values.grad)
        self.assertIsNone(returns.grad)

    def test_frozen_snapshot_rejects_changed_payload_and_old_mask(self):
        trainer = PPOTrainer(CandidateNetwork(hidden_dim=8), PPOConfig(epochs=1))
        raw = raw_episode(trainer)
        before = copy.deepcopy(raw)
        episode_from_core(raw, true_n=10)
        raw["decisions"][0]["snapshot"]["candidates"][0]["route_successor"][0] += 1
        with self.assertRaisesRegex(ValueError, "snapshot changed"):
            episode_from_core(raw, true_n=10)
        raw = before
        raw["decisions"][0]["snapshot"]["valid_mask"][0] = False
        with self.assertRaisesRegex(ValueError, "snapshot changed"):
            episode_from_core(raw, true_n=10)

    def test_real_shared_ppo_update_and_stale_batch_rejection(self):
        trainer = PPOTrainer(CandidateNetwork(hidden_dim=8),
                             PPOConfig(epochs=1, value_coefficient=0), seed=16)
        raw = raw_episode(trainer)
        ep = episode_from_core(raw, true_n=10)
        row = ep.rows[0]
        before = row.old_logprob
        different_initialization = PPOTrainer(CandidateNetwork(hidden_dim=8), trainer.config)
        with self.assertRaisesRegex(ValueError, "old policy/value"):
            different_initialization.update([ep])
        result = trainer.update([ep])
        with torch.no_grad():
            batch = batch_snapshots([json.loads(row.snapshot_json)])
            logits, _ = trainer.model(**batch)
            after = float(masked_log_probs(logits, batch["mask"])[0, row.action])
        self.assertLess(after, before)  # Negative advantage lowers sampled action likelihood.
        self.assertEqual(result["optimizer_steps"], 1)
        self.assertTrue(all(bool(torch.isfinite(p).all()) for p in trainer.model.parameters()))
        with self.assertRaisesRegex(ValueError, "stale"):
            trainer.update([ep])
        saved = trainer.state_dict()
        first_key = next(iter(saved["model"]))
        frozen_parameter = saved["model"][first_key].clone()
        with torch.no_grad():
            next(trainer.model.parameters()).add_(1.0)
        torch.testing.assert_close(saved["model"][first_key], frozen_parameter)
        trainer.load_state_dict(saved)
        restored = PPOTrainer(CandidateNetwork(hidden_dim=8), trainer.config, seed=999)
        restored.load_state_dict(saved)
        self.assertEqual(restored.policy_version, trainer.policy_version)
        for _ in range(3):
            self.assertEqual(trainer.select(snapshot()).index, restored.select(snapshot()).index)

    def test_bc_increases_teacher_likelihood_on_shared_model(self):
        trainer = BCTrainer(CandidateNetwork(hidden_dim=8), BCConfig(epochs=1))
        s = snapshot()
        demo = {"terminal": "success", "success": True,
                "decisions": [{"snapshot": s, "index": 0}]}
        with torch.no_grad():
            batch = batch_snapshots([s])
            logits, _ = trainer.model(**batch)
            before = float(masked_log_probs(logits, batch["mask"])[0, 0])
        metrics = trainer.update([demo])
        with torch.no_grad():
            logits, _ = trainer.model(**batch)
            after = float(masked_log_probs(logits, batch["mask"])[0, 0])
        self.assertGreater(after, before)
        self.assertEqual(metrics["decisions"], 1)
        demo["decisions"][0]["index"] = 1
        with self.assertRaisesRegex(ValueError, "pure-C7"):
            trainer.update([demo])

    def test_microbatching_preserves_episode_weights_and_full_gradient(self):
        model = CandidateNetwork(hidden_dim=8)
        a = PPOTrainer(copy.deepcopy(model), PPOConfig(epochs=1, forward_batch_size=128))
        b = PPOTrainer(copy.deepcopy(model), PPOConfig(epochs=1, forward_batch_size=1))
        # SGD isolates gradient aggregation from Adam's sensitivity near zero.
        a.optimizer = torch.optim.SGD(a.model.parameters(), lr=.01)
        b.optimizer = torch.optim.SGD(b.model.parameters(), lr=.01)
        episodes = [episode_from_core(raw_episode(a, (1000, 2000, 3000)), true_n=10),
                    episode_from_core(raw_episode(a, (1000,), k=4), true_n=16),
                    episode_from_core(raw_episode(a, (), tail=53000), true_n=10)]
        ma, mb = a.update(episodes), b.update(episodes)
        self.assertEqual(ma["decisions"], 4)
        self.assertAlmostEqual(ma["actor_loss"], mb["actor_loss"], places=6)
        for key, value in a.model.state_dict().items():
            torch.testing.assert_close(value, b.model.state_dict()[key], atol=2e-7, rtol=1e-5)

    def test_forced_cost_affects_returns_without_fabricated_logprob(self):
        trainer = PPOTrainer(CandidateNetwork(hidden_dim=8), PPOConfig(epochs=1))
        raw = raw_episode(trainer, (1000, 2000), tail=7000, failure=True)
        raw["decisions"][1]["metadata"] = {"algorithm": "fallback", "sampled": False}
        ep = episode_from_core(raw, true_n=10)
        self.assertEqual(len(ep.rows), 1)
        self.assertEqual(ep.rows[0].return_label, -101)
        self.assertEqual(ep.cost_from_first_decision_s, 10000)

    def test_artificial_boundary_and_zero_decision_batch_do_not_update(self):
        trainer = PPOTrainer(CandidateNetwork(hidden_dim=8), PPOConfig(epochs=1))
        raw = raw_episode(trainer, ())
        ep = episode_from_core(raw, true_n=10)
        result = trainer.update([ep])
        self.assertEqual(result["optimizer_steps"], 0)
        self.assertEqual(trainer.policy_version, 0)
        raw["terminal"] = "truncated"
        with self.assertRaisesRegex(ValueError, "incomplete"):
            episode_from_core(raw, true_n=10)


if __name__ == "__main__":
    unittest.main()
