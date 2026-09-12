"""Pure synthetic adapter, branch accounting and commit/fallback checks."""
import copy
import importlib.util
from pathlib import Path
import unittest

from test_adapter_synthetic import SyntheticProtocol

PATH = Path(__file__).resolve().parents[1] / "candidate_joint.py"
spec = importlib.util.spec_from_file_location("joint", PATH)
joint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(joint)


class FakeVerifier:
    """Fixture may mark prospective plan valid, actual completion unknown."""
    def __init__(self, finish="certified"):
        self.finish = finish

    def propose(self, snapshot, options=None):
        return []

    def verify(self, snapshot, plan, **kw):
        if plan["snapshot_hash"] != snapshot["snapshot_hash"]:
            return {"status": "unknown", "reason": "stale_hash"}
        return {"status": "certified" if plan["stations"] else self.finish,
                "fixture_only": True}


class JointTests(unittest.TestCase):
    def test_zero_intervention_matches_frozen_parent(self):
        for mode in (3, 4):
            old_env, new_env = SyntheticProtocol(), SyntheticProtocol()
            old = joint._D._PARENT.Solver(old_env, mode=mode)
            new = joint.Solver(new_env, mode=mode, jointplan_intervention_limit=0)
            a, b = old.run(), new.run()
            self.assertEqual(old_env.calls, new_env.calls)
            self.assertEqual(a["virtual_time_s"], b["virtual_time_s"])

    def test_b_only_retains_all_geometric_obligations(self):
        for mode in (3, 4):
            env = SyntheticProtocol()
            solver = joint.Solver(env, mode=mode, jointplan_geometry=False)
            result = solver.run()
            self.assertTrue(result["completion_certified"])
            self.assertEqual(len(solver.scanned[20]), len(solver.points))
            self.assertTrue(solver.jointplan_decisions)

    def _replay(self, finish):
        base = joint._D.Solver(SyntheticProtocol(), mode=3)
        base.run()
        snapshot = base.jointplan_snapshots[1]
        plan = joint._base_plan(snapshot)
        plan["stations"][0]["point"][0] += 20.
        plan["replaced_ids"] = [plan["stations"][0]["id"]]
        env = SyntheticProtocol()
        solver = joint.Solver(env, mode=3, jointplan_geometry_provider=FakeVerifier(finish),
                              jointplan_replay={"snapshot_hash": snapshot["snapshot_hash"], "plan": plan})
        result = solver.run()
        return base, solver, env, result

    def test_exact_prefix_commit_is_once_and_does_not_reenter(self):
        base, solver, env, result = self._replay("certified")
        self.assertEqual(solver.jointplan_diagnostics()["replay_status"], "committed_once")
        self.assertEqual(solver._jp_interventions, 1)
        self.assertEqual(sum(c[0] == "enter" for c in env.calls), 1)
        self.assertTrue(result["completion_certified"])

    def test_unknown_final_certificate_pays_original_layout_fallback(self):
        base, solver, env, result = self._replay("unknown")
        self.assertTrue(solver._jp_fallback_complete)
        self.assertEqual(solver.counters["jointplan_paid_coverage_fallbacks"], 1)
        self.assertGreater(result["virtual_time_s"], base.virtual_time)
        self.assertEqual(sum(c[0] == "enter" for c in env.calls), 1)
        self.assertTrue(result["completion_certified"])

    def test_unmatched_prefix_executes_no_new_action(self):
        env = SyntheticProtocol()
        solver = joint.Solver(env, mode=3, jointplan_replay={"snapshot_hash": "missing", "plan": {}})
        solver.run()
        base_env = SyntheticProtocol()
        joint._D._PARENT.Solver(base_env, mode=3).run()
        self.assertEqual(env.calls, base_env.calls)
        self.assertEqual(solver.jointplan_diagnostics()["replay_status"], "not_matched")

    def test_scan_fees_include_channel_switch_and_actual_movement(self):
        snapshot = {"position": [0., 0.], "channel": 1, "mode": 3, "snapshot_hash": "fixture",
                    "stations": [{"id": 1, "point": [50., 0.], "channels": [1, 3, 4]}], "source_tasks": []}
        cost = joint._M.route_cost(snapshot, [("station", 1)])
        self.assertEqual(cost["total_s"], 27.)  # 10 movement + 15 measures + 2 switches
        self.assertEqual(cost["breakdown"]["switches"], 2)


if __name__ == "__main__":
    unittest.main()
