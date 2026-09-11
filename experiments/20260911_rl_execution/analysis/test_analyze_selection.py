"""Exactly three synthetic statistical fixtures; zero task worlds or training."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_selection as analysis


def synthetic_plan():
    # Names are synthetic and intentionally are not environment recipes.
    worlds = [dict(world_id=f"fixture:q{mode}:{index}", mode=mode, group=f"synthetic_group_{index % 12:02d}")
              for index in range(96) for mode in (3, 4)]
    return dict(initialization_seeds=[81001, 81002, 81003], selection=worlds,
                ppo=dict(checkpoint_episodes=[128, 256, 512, 1024]),
                q=dict(checkpoint_episodes=[128, 256, 512, 1024]),
                selection_protocol=dict(worlds=192, worlds_per_question=96,
                    bootstrap=dict(resamples=10000, seed=84771, method="stratified paired worlds")))


def synthetic_row(world, average=100.0):
    return dict(world_id=world["world_id"], mode=world["mode"], group=world["group"],
                success=True, n=10, cleared=10, average_s=average, virtual_time_s=10*average,
                business_primitives=3, execution_wall_s=0.01, fallback_reason=None, error=None)


def synthetic_ledgers(plan):
    result = {}
    for spec in analysis.part_specs(plan):
        rows = [synthetic_row(world) for world in plan["selection"]]
        result[spec["key"]] = (rows, [], dict(path=spec["key"]+"/rows.jsonl", exists=True, sha256="synthetic", bytes=0))
    return result


def change_time(rows, value, mode=None):
    for row in rows:
        if mode is None or row["mode"] == mode:
            row["average_s"] = value
            row["virtual_time_s"] = value*row["cleared"]


class SelectionStatisticsFixtures(unittest.TestCase):
    def test_stratified_paired_bootstrap_and_world_mean_before_resampling(self):
        """Fixture 1: exact interval and independently reconstructed group resampling."""
        plan = synthetic_plan()
        _, modes, settings = analysis.plan_contract(plan)
        worlds = modes[3]
        constant = analysis.paired_statistics([98.0]*96, [100.0]*96, worlds, settings)
        self.assertEqual(constant["difference_ci95_s_per_source"], [-2.0, -2.0])
        self.assertEqual(constant["improvement_percent"], 2.0)
        # Three anticorrelated initialization errors cancel within each world.
        noise = np.arange(96, dtype=float)-47.5
        candidates = np.stack([95+noise, 95-noise, np.full(96, 95.0)])
        averaged = candidates.mean(axis=0)
        merged = analysis.paired_statistics(averaged.tolist(), [100.0]*96, worlds, settings)
        self.assertEqual(merged["worlds"], 96)
        self.assertEqual(merged["difference_ci95_s_per_source"], [-5.0, -5.0])
        varied = np.arange(96, dtype=float)/13.0-5
        actual = analysis.paired_statistics((100+varied).tolist(), [100.0]*96, worlds, settings)
        rng = np.random.default_rng(84771)
        sampled_means = np.zeros(10000)
        for group in sorted({w["group"] for w in worlds}):
            indices = [i for i, w in enumerate(worlds) if w["group"] == group]
            draws = rng.integers(0, len(indices), (10000, len(indices)))
            sampled_means += varied[indices][draws].sum(axis=1)/96
        np.testing.assert_allclose(actual["difference_ci95_s_per_source"],
                                   np.quantile(sampled_means, [0.025, 0.975], method="linear"), atol=1e-12)

    def test_identity_failure_missing_and_cost_integrity_are_not_success_subset_rankings(self):
        """Fixture 2: one ledger with independently observable defects, no omitted costs."""
        plan = synthetic_plan()
        _, modes, _ = analysis.plan_contract(plan)
        worlds = plan["selection"]
        rows = [synthetic_row(w) for w in worlds]
        removed = rows.pop(0)  # Missing Q3 world.
        rows.append(copy.deepcopy(rows[2]))  # Duplicate another Q4 world.
        failed = next(r for r in rows if r["mode"] == 3)
        failed.update(success=False, cleared=0, average_s=None, error="recorded_failure")
        inconsistent = next(r for r in rows if r["mode"] == 4)
        inconsistent["average_s"] = 1.0
        rows.append(dict(synthetic_row(worlds[0]), world_id="not-registered", mode=99))
        spec = analysis.part_specs(plan)[0]
        source = dict(path="synthetic", exists=True, sha256="synthetic", bytes=0)
        checked = analysis.audit_part(spec, rows, [], source, modes, {})
        q3, q4 = checked["questions"]["3"], checked["questions"]["4"]
        self.assertEqual(q3["missing_world_ids"], [removed["world_id"]])
        self.assertFalse(q3["eligible_for_selection"])
        self.assertFalse(q4["eligible_for_selection"])
        self.assertEqual(len(q3["failed_rows"]), 1)
        self.assertTrue(q4["duplicate_world_ids"])
        self.assertTrue(q4["invalid_rows"])
        self.assertIsNone(q3["mean_seconds_per_source"])
        self.assertIsNone(q4["mean_seconds_per_source"])
        self.assertEqual(checked["recorded_cost"]["business_primitives"], len(rows)*3)
        absent = analysis.audit_part(spec, [], [], dict(source, exists=False), modes, {})
        self.assertEqual(len(absent["questions"]["3"]["missing_world_ids"]), 96)

    def test_selection_gate_complete_positions_failures_missing_initialization_and_saved_report(self):
        """Fixture 3: complete end-to-end synthetic selection and its refusal boundaries."""
        plan = synthetic_plan()
        ledgers = synthetic_ledgers(plan)
        for seed in plan["initialization_seeds"]:
            # PPO ties at 256/512; the earlier checkpoint must win. A much faster
            # failed 1024 checkpoint must not leak into the successful subset.
            for ep, value in ((128, 97.0), (256, 94.0), (512, 94.0), (1024, 50.0)):
                rows = ledgers[f"ppo_init{seed}_ep{ep:04d}"][0]
                change_time(rows, value)
                if ep == 1024:
                    for mode in (3, 4):
                        next(r for r in rows if r["mode"] == mode)["success"] = False
            for ep in (128, 256, 512, 1024):
                # Q beats C7 by 4%, but beats its stronger BC by less than 2%.
                change_time(ledgers[f"q_init{seed}_ep{ep:04d}"][0], 96.0)
            change_time(ledgers[f"bc_init{seed}"][0], 97.0)
        result = analysis.summarize(plan, ledgers)
        self.assertEqual(result["planned_model_checkpoints"], 24)
        self.assertEqual(len(result["parts"]), 30)
        for mode in ("3", "4"):
            ppo = result["algorithms"]["ppo"][mode]
            self.assertTrue(ppo["meets_preregistered_selection_gate"])
            self.assertEqual(ppo["aggregate"]["independent_worlds"], 96)
            self.assertEqual(ppo["promotion_checks"]["initializations_improving_both_baselines"], 3)
            self.assertTrue(all(r["selected_episode_count"] == 256 for r in ppo["initialization_choices"].values()))
            self.assertFalse(result["algorithms"]["q"][mode]["meets_preregistered_selection_gate"])
        # Remove every checkpoint of one initialization: two winners alone are
        # insufficient, and no two-initialization aggregate may be promoted.
        missing = copy.deepcopy(ledgers)
        for ep in (128, 256, 512, 1024):
            key = f"ppo_init81003_ep{ep:04d}"
            missing[key] = ([], [], dict(missing[key][2], exists=False))
        incomplete = analysis.summarize(plan, missing)
        self.assertFalse(incomplete["algorithms"]["ppo"]["3"]["meets_preregistered_selection_gate"])
        self.assertIsNone(incomplete["algorithms"]["ppo"]["3"]["aggregate"])
        # Exercise the actual saved-file reader/writer against this same synthetic
        # fixture; no controller or world generation is imported or called.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            analysis.dump(root/"data/g2_plan.json", plan)
            for spec in analysis.part_specs(plan):
                path = root/"results/g2_selection"/spec["category"]/spec["key"]/"rows.jsonl"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("".join(json.dumps(row)+"\n" for row in ledgers[spec["key"]][0]))
            saved = analysis.analyze_saved(root, root/"results/g2_selection", root/"data/g2_plan.json")
            analysis.dump(root/"analysis/selection_summary.json", saved)
            report = analysis.render_report(saved)
            self.assertIn("24个模型检查点", report)
            self.assertIn("选择偏差", report)
            self.assertIn("ppo_init81001_ep1024", report)
            self.assertEqual(saved["provenance"]["environment_world_executions"], 0)
            self.assertEqual(saved["recorded_evaluation_cost"]["episode_rows"], 30*192)


if __name__ == "__main__":
    unittest.main()
