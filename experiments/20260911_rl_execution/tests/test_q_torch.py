"""Six synthetic network/update fixtures; no task world or policy rollout is run."""
import copy
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import torch
from shared import CandidateNetwork, batch_snapshots
from q_learning import build_replay_episode
from q_learning.policy import FeatureBounds, QSelector, TrainingExplorer, FEATURE_RANGE_CONTRACT
from q_learning.trainer import QTrainer


def snap(number=0, values=(1.0, 3.0), valid=(True, True)):
    candidates = [{"kind": "source", "channel": i + 1, "route_successor": [v, number],
                   "state_version": number} for i, v in enumerate(values)]
    return {"schema_version": "rl-core-snapshot-v1", "generator_version": "synthetic-v1",
            "decision_id": number, "state_version": number,
            "global_features": [float(number)] + [0.0] * 15,
            "channel_features": [[0.0] * 12 for _ in range(20)],
            "candidate_features": [[v] + [0.0] * 15 for v in values],
            "candidate_ids": [f"{number}-{v}" for v in values], "candidates": candidates,
            "teacher_index": 0, "valid_mask": list(valid)}


def episode(costs=(10, 20), *, failure=False):
    decisions = [{"snapshot": snap(i), "index": 0, "delta_time_s": c}
                 for i, c in enumerate(costs)]
    return build_replay_episode(decisions, tail_time_s=30, true_source_count=10, failed=failure)


class LinearScores(torch.nn.Module):
    def __init__(self, weight=1.0):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.tensor(float(weight)))

    def forward(self, global_features, candidate_features, mask, channel_features=None):
        scores = (candidate_features[..., 0] * self.weight).masked_fill(~mask, float("-inf"))
        return scores, torch.zeros(scores.shape[0], device=scores.device)


class QTorchTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        torch.manual_seed(71)

    def test_shared_network_mc_updates_and_frozen_support(self):
        model, behavior = CandidateNetwork(), CandidateNetwork()
        trainer = QTrainer(model, behavior)
        before = {k: v.detach().clone() for k, v in trainer.network.state_dict().items()}
        support_before = {k: v.detach().clone() for k, v in trainer.support_model.state_dict().items()}
        metrics = trainer.update([episode()], kind="mc")
        self.assertTrue(metrics["optimizer_step"])
        self.assertTrue(math.isfinite(metrics["loss"]))
        self.assertTrue(any(not torch.equal(before[k], v) for k, v in trainer.network.state_dict().items()))
        self.assertTrue(all(torch.equal(support_before[k], v) for k, v in trainer.support_model.state_dict().items()))
        self.assertTrue(all(p.grad is None and not p.requires_grad for p in trainer.support_model.parameters()))
        self.assertTrue(all(p.grad is None and not p.requires_grad for p in trainer.target.parameters()))
        self.assertTrue(all(p.grad is None for p in trainer.network.value_head.parameters()))

    def test_torch_double_q_uses_saved_next_identity_and_terminal(self):
        trainer = QTrainer(LinearScores(1), LinearScores(0), feature_bounds=FeatureBounds.fit([snap(0)]))
        with torch.no_grad():
            trainer.target.weight.fill_(10)
        next_snap = snap(1, values=(3.0, 1.0))
        next_snap["teacher_index"] = 1
        decisions = [{"snapshot": snap(0), "index": 0, "delta_time_s": 10},
                     {"snapshot": next_snap, "index": 1, "delta_time_s": 20}]
        ep = build_replay_episode(decisions, tail_time_s=30, true_source_count=10, failed=False)
        # Outside training range: both deployment and TD use teacher 1, target Q=10.
        deployment = trainer.make_selector()
        self.assertEqual(deployment(next_snap)["index"], 1)
        targets = trainer.targets(ep.transitions).tolist()
        self.assertAlmostEqual(targets[0], 9.999, places=4)
        self.assertAlmostEqual(targets[1], -.005, places=6)
        # Only actual training observations extend the range, synchronizing existing selectors.
        trainer.register_training_snapshots([next_snap])
        self.assertEqual(deployment(next_snap)["index"], 0)
        self.assertAlmostEqual(trainer.targets(ep.transitions)[0].item(), 29.999, places=4)
        clock_next = copy.deepcopy(next_snap)
        clock_next["global_features"][6] = .8
        clock_next["global_features"][14] = .2
        clock_decisions = [decisions[0], dict(decisions[1], snapshot=clock_next)]
        clock_ep = build_replay_episode(clock_decisions, tail_time_s=30, true_source_count=10, failed=False)
        self.assertEqual(deployment(clock_next)["index"], 0)
        self.assertAlmostEqual(trainer.targets(clock_ep.transitions)[0].item(), 29.999, places=4)
        # Invalid online scores invoke the identical teacher rule, still evaluated by target Q.
        with torch.no_grad():
            trainer.network.weight.fill_(float("nan"))
        self.assertEqual(deployment(next_snap)["index"], 1)
        self.assertAlmostEqual(trainer.targets(ep.transitions)[0].item(), 9.999, places=4)
        with torch.no_grad():
            trainer.target.weight.fill_(float("nan"))
        with self.assertRaises(FloatingPointError):
            trainer.targets(ep.transitions)
        # True-terminal targets never inspect next snapshots or invalid network parameters.
        self.assertAlmostEqual(trainer.targets(ep.transitions[-1:]).item(), -.005, places=6)

    def test_selector_range_guard_nonfinite_and_feature_allowlist(self):
        s = snap()
        bounds = FeatureBounds.fit([s])
        selector = QSelector(LinearScores(1), LinearScores(0), feature_bounds=bounds)
        base = selector(s)
        self.assertEqual(base["index"], 1)
        leaked_metadata = copy.deepcopy(s)
        leaked_metadata.update({"true_N": 16, "seed": 999, "normalized_reward": -100})
        self.assertEqual(selector(leaked_metadata)["index"], base["index"])
        for key, tensor in batch_snapshots([s]).items():
            self.assertTrue(torch.equal(tensor, batch_snapshots([leaked_metadata])[key]))
        outside = copy.deepcopy(s)
        outside["global_features"][0] = 2
        guarded_range = selector(outside)
        self.assertEqual(guarded_range["metadata"]["selection_reason"], "outside_behavior_feature_range")
        violation = guarded_range["metadata"]["feature_range_violations"][0]
        self.assertEqual(violation["feature_index"], 0)
        self.assertEqual(violation["observed_max"], 2)
        self.assertEqual(violation["training_max"], 0)
        self.assertTrue(violation["field"].startswith("global_features."))
        extended = bounds.extend([outside])
        self.assertTrue(extended.contains(outside))
        self.assertEqual(extended.snapshot_count, 2)
        self.assertEqual(extended.revision, 2)
        self.assertFalse(bounds.contains(outside))
        self.assertEqual(FeatureBounds.from_dict(extended.to_dict()), extended)
        # Pre-G2 v2: load-dependent wall clocks do not use empirical extrema.
        shifted_clock = copy.deepcopy(s)
        shifted_clock["global_features"][6] = .75
        shifted_clock["global_features"][14] = .25
        clock_choice = selector(shifted_clock)
        self.assertEqual(clock_choice["index"], 1)
        self.assertEqual(clock_choice["metadata"]["selection_reason"], "supported_q_argmax")
        self.assertTrue(bounds.contains(shifted_clock))
        checks = clock_choice["metadata"]["clock_feature_checks"]
        self.assertEqual([r["feature_index"] for r in checks], [6, 14])
        self.assertTrue(all(r["empirical_minmax_skipped"] and r["skip_reason"] for r in checks))
        self.assertEqual([r["observed_value"] for r in checks], [.75, .25])
        self.assertEqual(clock_choice["metadata"]["feature_range_contract"], FEATURE_RANGE_CONTRACT)
        tensor = batch_snapshots([shifted_clock])["global_features"]
        self.assertEqual(tensor[0, 6].item(), .75)
        self.assertEqual(tensor[0, 14].item(), .25)
        for j in (6, 14):
            for value in (0., 1., -.5e-6, 1.+.5e-6):
                boundary = copy.deepcopy(shifted_clock)
                boundary["global_features"][j] = value
                self.assertTrue(bounds.contains(boundary))
            for value in (-2e-6, 1.+2e-6, float("nan"), float("inf")):
                invalid_clock = copy.deepcopy(shifted_clock)
                invalid_clock["global_features"][j] = value
                bad = selector(invalid_clock)
                self.assertEqual(bad["index"], 0)
                self.assertEqual(bad["metadata"]["selection_reason"], "invalid_physical_clock_range")
                self.assertFalse(bounds.contains(invalid_clock, tolerance=.1))
                self.assertEqual(bad["metadata"]["feature_range_violations"][0]["feature_index"], j)
        # The remaining 14 global dimensions retain the empirical min/max gate.
        for j in set(range(16)) - {6, 14}:
            other = copy.deepcopy(s)
            other["global_features"][j] = .1
            self.assertFalse(bounds.contains(other))
        old_contract = extended.to_dict()
        old_contract.pop("gate_contract")
        with self.assertRaises(ValueError):
            FeatureBounds.from_dict(old_contract)
        with torch.no_grad():
            selector.network.weight.fill_(float("nan"))
        guarded = selector(s)
        self.assertEqual(guarded["index"], 0)
        self.assertFalse(guarded["metadata"]["behavior_support_is_confidence"])

    def test_training_mixture_exact_probabilities_and_eight_deviation_cap(self):
        s = snap()
        trainer = QTrainer(LinearScores(1), LinearScores(0), feature_bounds=FeatureBounds.fit([s]))
        explorer = trainer.make_selector(training=True, seed=5)
        self.assertTrue(explorer.q_selector.enforce_bounds)
        with self.assertRaises(RuntimeError):
            explorer(s)
        explorer.start_episode(0)
        choices = [explorer(s) for _ in range(100)]
        self.assertEqual(sum(row["index"] != 0 for row in choices), 8)
        self.assertEqual(choices[-1]["metadata"]["sample_probability"], 1.0)
        for row in choices:
            self.assertIn(row["metadata"]["sample_probability"], (.2, .8, 1.0))
            self.assertTrue(row["metadata"]["training_only"])
        explorer.start_episode(128)
        late = [explorer(s) for _ in range(20)]
        self.assertTrue(all(row["metadata"]["sample_probability"] in (.1, .9) for row in late))
        self.assertEqual(explorer.deviations, 0)
        outside = snap(2)
        self.assertEqual(explorer.q_selector(outside)["index"], 0)
        trainer.register_training_snapshots([outside], source="q_training")
        self.assertEqual(explorer.q_selector(outside)["index"], 1)
        self.assertEqual(explorer.q_selector.feature_bounds.revision, 2)
        with self.assertRaises(ValueError):
            trainer.register_training_snapshots([outside], source="selection")

    def test_checkpoint_is_detached_and_round_trips_shared_architecture(self):
        model, behavior = CandidateNetwork(), CandidateNetwork()
        trainer = QTrainer(model, behavior, feature_bounds=FeatureBounds.fit([snap()]))
        trainer.register_training_snapshots([snap(1)])
        record = trainer.checkpoint()
        expected = {k: v.clone() for k, v in record["network"].items()}
        with torch.no_grad():
            for p in trainer.network.parameters():
                p.add_(1)
        self.assertTrue(all(torch.equal(expected[k], v) for k, v in record["network"].items()))
        restored = QTrainer.from_checkpoint(record)
        self.assertTrue(all(torch.equal(expected[k], v) for k, v in restored.network.state_dict().items()))
        self.assertGreater(record["architecture"]["state_value_head_parameters"], 0)
        self.assertFalse(record["label_contract"]["true_N_is_deployment_input"])
        self.assertEqual(restored.feature_bounds, trainer.feature_bounds)
        self.assertEqual(restored.feature_range_history, trainer.feature_range_history)
        self.assertEqual(record["next_action_contract"], "deployment_bounds_teacher_supported_argmax_v2_clock_physical")
        self.assertEqual(record["feature_range_contract"], FEATURE_RANGE_CONTRACT)

    def test_microbatch_keeps_episode_sum_weight_and_same_update(self):
        first = CandidateNetwork()
        other = copy.deepcopy(first)
        support = CandidateNetwork()
        t1 = QTrainer(first, support, microbatch_size=1)
        t2 = QTrainer(other, support, microbatch_size=128)
        episodes = [episode((10, 20)), episode((40,))]
        transitions = [t for ep in episodes for t in ep.transitions]
        with torch.no_grad():
            scores, _ = first(**batch_snapshots([t.snapshot.thaw() for t in transitions]))
            expected = ((scores[:, 0] - t1.targets(transitions, kind="mc")) ** 2).sum().item() / 2
        m1 = t1.update(episodes, kind="mc")
        m2 = t2.update(episodes, kind="mc")
        self.assertAlmostEqual(m1["loss"], expected, places=6)
        self.assertAlmostEqual(m1["loss"], m2["loss"], places=6)
        self.assertTrue(all(torch.allclose(a, b, atol=1e-6, rtol=1e-5)
                            for a, b in zip(first.parameters(), other.parameters())))


if __name__ == "__main__":
    unittest.main(verbosity=2)
