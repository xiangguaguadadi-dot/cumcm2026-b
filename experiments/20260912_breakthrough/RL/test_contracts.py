"""Synthetic specification fixtures only, NOT tests of an implemented solver.

All trajectories, events, model scores and clocks below are constructed toy data.
No local_env, solver, torch, API, training, or real world dataset is executed.
"""
from __future__ import annotations
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import json
import math
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent


def linear_params(*dims):
    return sum(a * b + b for a, b in zip(dims, dims[1:]))


def huber_normalized(error, scale=0.002):
    z = error / scale
    return 0.5 * z * z if abs(z) <= 1 else abs(z) - 0.5


def huber_gradient(error, scale=0.002):
    z = error / scale
    return max(-1, min(1, z)) / scale


def branch_slots(start_b, action):
    if isinstance(start_b, bool) or not isinstance(start_b, int) or not 0 <= start_b <= 2:
        raise ValueError("invalid slot schema: cannot authorize override")
    if action != "A0" and start_b == 0:
        raise ValueError("no override slots")
    return start_b - (action != "A0")


def terminal_cost(suffix_seconds, terminal_n, failed=False):
    if terminal_n <= 0:
        raise ValueError("training label requires evaluator terminal N")
    return suffix_seconds / (1000 * terminal_n) + 100 * failed


def canonical_coordinate(value):
    if not math.isfinite(value):
        raise ValueError("nonfinite coordinate")
    d = Decimal(str(float(value))).quantize(Decimal("0.0000001"), rounding=ROUND_HALF_EVEN)
    if d == 0:
        d = abs(d)
    return format(d, ".7f")


def action_key(kind, channel, x, y):
    return kind, channel, canonical_coordinate(x), canonical_coordinate(y)


def canonical_hash(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def margin_nearest_rank(residuals):
    if len(residuals) < 24 or not all(math.isfinite(v) for v in residuals):
        raise ValueError("incomplete calibration")
    return max(0, sorted(residuals)[math.ceil(0.9 * len(residuals)) - 1])


def event_age_feature(now_us, event_end_us):
    if event_end_us > now_us:
        raise ValueError("future event")
    return (now_us - event_end_us) / 1_000_000 / 10000


def world_equal_mean(rows):
    # rows: world -> state -> action errors/losses
    return sum(sum(sum(a) / len(a) for a in states) / len(states)
               for states in rows.values()) / len(rows)


def finish_macro(events, start, end, kind, accepted=True):
    selected = events[start:end]
    if not accepted:
        return {"kind": kind, "status": "unknown_cost", "event_count": len(selected), "delta_us": None}
    return {"kind": kind, "status": "complete", "event_count": len(selected),
            "delta_us": sum(e["delta_us"] for e in selected)}


def commit_once_fixture(state, prepared):
    if state["last_committed_choice_id"] == prepared["choice_id"]:
        raise ValueError("duplicate commit")
    if canonical_hash(state) != prepared["pre_state_hash"]:
        raise ValueError("not the frozen pre-prepare state")
    state["controller"].update(deepcopy(prepared["patch"]))
    state["last_committed_choice_id"] = prepared["choice_id"]
    state["decision_counter"] += 1


def progress_fixture(state, kind, key, complete):
    # Synthetic semantics, not code imported from any controller.
    if not complete:
        state["phase"] = "fallback"
        return
    if kind == "station":
        state["todo"].remove(key)
        state["visited"].append(key)
    elif kind == "teacher_service":
        state["forced"].discard(key)


class ContractTests(unittest.TestCase):
    def test_01_parameter_arithmetic(self):
        events = linear_params(14, 32, 32) + linear_params(64, 64)
        polygon = linear_params(2, 32, 32) + linear_params(64, 64)
        channels = linear_params(12, 32, 32) + linear_params(64, 64)
        total = events + polygon + channels + linear_params(20, 32, 32) + linear_params(14, 32, 32) + linear_params(256, 128, 64, 1)
        self.assertEqual(total, 61121)

    def test_02_feature_dimensions(self):
        self.assertEqual(10 + 2 + 2 + 1 + 1 + 1 + 2 + 1, 20)
        self.assertEqual(6 + 2 + 1 + 1 + 1 + 1, 12)
        self.assertEqual(5 + 2 + 2 + 1 + 1 + 1 + 1 + 1, 14)
        self.assertEqual(3 + 2 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1, 14)
        self.assertEqual(3 * 64 + 32 + 32, 256)

    def test_03_dimensionless_loss(self):
        self.assertAlmostEqual(huber_normalized(0.001), 0.125)
        self.assertAlmostEqual(huber_normalized(0.002), 0.5)
        self.assertAlmostEqual(huber_normalized(0.004), 1.5)
        self.assertAlmostEqual(huber_normalized(-0.004), 1.5)
        self.assertAlmostEqual(huber_gradient(0.001), 250)
        self.assertAlmostEqual(0.1 * math.log(2), 0.06931471805599453)
        # The obsolete unnormalized regression was ~1e5 smaller than ranking.
        self.assertGreater((0.1 * math.log(2)) / (0.5 * 0.001 ** 2), 100000)

    def test_04_label_units_prefix_and_failure(self):
        prefix, reference_suffix, alternative_suffix, n = 500, 300, 280, 10
        gain = terminal_cost(reference_suffix, n) - terminal_cost(alternative_suffix, n)
        self.assertAlmostEqual(gain, 0.002)  # 2 seconds/source -> 0.002 normalized
        self.assertAlmostEqual((prefix + reference_suffix) / n - (prefix + alternative_suffix) / n, 2)
        self.assertGreater(terminal_cost(1, n, failed=True), terminal_cost(10000, n))
        with self.assertRaises(ValueError):
            terminal_cost(5, 0)

    def test_05_reference_and_alternative_own_slots(self):
        self.assertEqual(branch_slots(2, "A0"), 2)
        self.assertEqual(branch_slots(2, "A4"), 1)
        # If pi_j selects an override, reference consumes its OWN slot too.
        self.assertEqual(branch_slots(1, "A7"), 0)
        self.assertEqual(branch_slots(1, "A0"), 1)
        with self.assertRaises(ValueError):
            branch_slots(0, "A1")

    def test_06_unknown_slot_rejected(self):
        for b in (None, True, -1, 3, 1.0):
            with self.assertRaises(ValueError):
                branch_slots(b, "A4")

    def test_07_near_has_two_paid_events(self):
        events = [{"delta_us": 6_000_000}, {"delta_us": 5_000_000}]
        macro = finish_macro(events, 0, 2, "measure_override")
        self.assertEqual(macro["event_count"], 2)
        self.assertEqual(macro["delta_us"], 11_000_000)
        self.assertEqual(branch_slots(2, "A3"), 1)  # one operation, two requests

    def test_08_station_and_teacher_same_finalizer(self):
        events = [{"delta_us": v} for v in (5_000_000, 6_000_000, 3_000_000)]
        station = finish_macro(events, 0, 2, "station")
        teacher = finish_macro(events, 2, 3, "teacher_service")
        self.assertEqual(station["delta_us"] + teacher["delta_us"], 14_000_000)
        self.assertEqual(station["event_count"] + teacher["event_count"], len(events))

    def test_09_unknown_cost_never_zero(self):
        result = finish_macro([], 0, 0, "partial", accepted=False)
        self.assertEqual(result["status"], "unknown_cost")
        self.assertIsNone(result["delta_us"])

    def test_10_common_prepared_patch_fixture(self):
        public = {"route_successor": None, "e2_progress": {"4": 1}, "cleared": []}
        patch = {"route_successor": [1, 2]}
        prepared = {**deepcopy(public), **deepcopy(patch)}
        branch_a, branch_ref = deepcopy(prepared), deepcopy(prepared)
        self.assertEqual(canonical_hash(branch_a), canonical_hash(branch_ref))
        branch_a["cleared"].append(4)
        self.assertEqual(branch_ref["cleared"], [])
        self.assertEqual(branch_a["e2_progress"], public["e2_progress"])

    def test_11_canonical_coordinates_and_action_identity(self):
        self.assertEqual(canonical_coordinate(-0.00000001), "0.0000000")
        self.assertEqual(canonical_coordinate(1.23456785), "1.2345678")
        self.assertEqual(canonical_coordinate(1.23456795), "1.2345680")
        self.assertEqual(action_key("measure", 2, 1.00000001, 0), action_key("measure", 2, 1, 0))
        self.assertNotEqual(action_key("measure", 2, 1, 0), action_key("clear", 2, 1, 0))
        with self.assertRaises(ValueError):
            canonical_coordinate(float("nan"))

    def test_12_payload_hash_is_order_independent(self):
        a = {"kind": "measure", "target": ["1.0000000", "0.0000000"]}
        b = {"target": ["1.0000000", "0.0000000"], "kind": "measure"}
        self.assertEqual(canonical_hash(a), canonical_hash(b))

    def test_13_nearest_rank_and_insufficient_calibration(self):
        self.assertEqual(margin_nearest_rank(list(range(24))), 21)  # 22nd, one-based
        self.assertEqual(margin_nearest_rank([-1] * 24), 0)
        for xs in (list(range(23)), [0] * 23 + [float("inf")]):
            with self.assertRaises(ValueError):
                margin_nearest_rank(xs)

    def test_14_event_age_is_virtual_seconds(self):
        self.assertAlmostEqual(event_age_feature(31_000_000, 11_000_000), 0.002)
        with self.assertRaises(ValueError):
            event_age_feature(10, 11)

    def test_15_world_equal_not_branch_equal(self):
        # World a contributes 100 actions and world b one action, yet equal world weight.
        rows = {"a": [[0] * 100], "b": [[10]]}
        self.assertEqual(world_equal_mean(rows), 5)
        self.assertNotEqual(world_equal_mean(rows), 10 / 101)

    def test_16_fit_val_roles_permanent(self):
        roles = {}
        fit_sets = []
        for round_id in range(3):
            new_fit = {f"fit_r{round_id}_{i}" for i in range(24 if round_id == 0 else 12)}
            old_fit = set() if round_id == 0 else set(sorted(fit_sets[-1])[:12])
            fit = new_fit | old_fit
            fit_val = {f"fitval_r{round_id}_{i}" for i in range(12)}
            self.assertEqual(len(fit), 24)
            self.assertEqual(len(fit_val), 12)
            self.assertFalse(fit & fit_val)
            for ids, role in ((fit, "fit"), (fit_val, "fit_val")):
                for world_id in ids:
                    self.assertIn(roles.get(world_id), (None, role))
                    roles[world_id] = role
            fit_sets.append(fit)
        self.assertEqual(len(roles), 84)

    def test_17_budget_arithmetic(self):
        self.assertEqual(350000 + 1500000 + 1500000 + 550000 + 1100000, 5000000)
        self.assertEqual((3 * 3 * 120 * 2 + 240 + 240) * 263, 694320)
        self.assertEqual((4800 + 1200 * 3 + 96) * 263, 2234448)
        self.assertEqual(36 * 4 * 9 * 3 * 3, 11664)
        self.assertEqual(24 * 2 * 2 * 3 * 3 * 2, 1728)
        self.assertEqual(23328 + 648 + 432 + 3000 + 2000 + 2640, 32048)
        self.assertLess(32048, 40000)

    def test_18_budget_incomplete_rows_preserved(self):
        rows = [{"id": str(i), "status": "complete" if i < 2 else "not_started_budget"} for i in range(4)]
        self.assertEqual(len(rows), 4)
        self.assertFalse(all(r["status"] == "complete" for r in rows))
        self.assertEqual(sum(r["status"] == "not_started_budget" for r in rows), 2)

    def test_19_branch_clock_ignores_queue_not_prefix(self):
        prefix_elapsed, own_runtime, queue_delay = 17, 5, 40
        remaining_a = 1200 - prefix_elapsed - own_runtime
        remaining_b = 1200 - prefix_elapsed - own_runtime
        self.assertEqual(remaining_a, remaining_b)
        self.assertNotEqual(remaining_a, 1200 - own_runtime)
        self.assertEqual(prefix_elapsed + own_runtime + queue_delay, 62)  # actual research time stays recorded

    def test_20_current_theta_no_old_policy_chain_fixture(self):
        scores = {"A0": 4, "A3": 4.002, "A6": 3.9}
        selected = max(scores, key=lambda a: scores[a] - scores["A0"])
        self.assertEqual(selected, "A3")
        self.assertAlmostEqual(scores["A0"] - scores["A0"], 0)
        self.assertEqual(set(scores), {"A0", "A3", "A6"})

    def test_21_corpus_counts_identity_and_reading(self):
        corpus = json.loads((ROOT / "literature.json").read_text())
        records = corpus["records"]
        self.assertEqual(len(records), 16)
        self.assertEqual(len({r["stable_id"] for r in records}), 16)
        self.assertEqual(sum(r["corpus_layer"] == "core" for r in records), 9)
        self.assertEqual(sum(r["previous_corpus_match"] is None for r in records), 7)
        self.assertEqual(corpus["counts"]["union_with_previous"], 48)
        for record in records:
            for key in ("title", "authors", "publication_date", "paper_url", "reading_scope", "problem", "core_method", "limitations_and_unproved"):
                self.assertTrue(record[key])
            self.assertEqual(len(record["primary_classification_path"]), 4)

    def test_22_prepare_select_commit_once_even_empty_patch(self):
        pre = {"controller": {"route_successor": None}, "decision_counter": 1,
               "last_committed_choice_id": None}
        prepared = {"choice_id": "toy-choice-1", "pre_state_hash": canonical_hash(pre), "patch": {}}
        # Prepare and selection do not mutate live pre-state.
        a, ref = deepcopy(pre), deepcopy(pre)
        self.assertEqual(canonical_hash(a), prepared["pre_state_hash"])
        commit_once_fixture(a, prepared)
        commit_once_fixture(ref, prepared)
        self.assertEqual(a, ref)
        self.assertEqual(a["decision_counter"], 2)
        with self.assertRaises(ValueError):
            commit_once_fixture(a, prepared)
        bad_pre = deepcopy(pre)
        bad_pre["controller"]["route_successor"] = [9, 9]
        with self.assertRaises(ValueError):
            commit_once_fixture(bad_pre, prepared)

    def test_23_restore_guard_and_clock_do_not_reset_budget(self):
        public = {"learning_requests": 9999, "phase": "learning", "takeover_reason": None,
                  "started": True, "exited": False, "positive_observations": [[1, 0, 0]],
                  "accounting_max_error_s": 0.000001, "pending_timing_settled": True}
        offsets = {"elapsed": 1170, "interface_remaining": 30,
                   "controller_remaining": 25, "response_age": 2}
        now = 5000
        restored = deepcopy(public)
        restored.update(started_at=now - offsets["elapsed"],
                        deadline=now + offsets["interface_remaining"],
                        controller_deadline=now + offsets["controller_remaining"],
                        last_response_at=now - offsets["response_age"])
        self.assertEqual(restored["learning_requests"], 9999)
        self.assertEqual(10000 - restored["learning_requests"], 1)
        self.assertEqual(restored["deadline"] - now, 30)
        self.assertEqual(restored["controller_deadline"] - now, 25)
        self.assertEqual(now - restored["started_at"], 1170)
        self.assertEqual(now - restored["last_response_at"], 2)

    def test_24_partial_station_and_failed_teacher_keep_obligations(self):
        initial = {"todo": {1, 2}, "visited": [], "forced": {4}, "phase": "learning"}
        station, teacher = deepcopy(initial), deepcopy(initial)
        progress_fixture(station, "station", 1, complete=False)
        self.assertEqual(station["todo"], {1, 2})
        self.assertEqual(station["visited"], [])
        self.assertEqual(station["phase"], "fallback")
        progress_fixture(teacher, "teacher_service", 4, complete=False)
        self.assertEqual(teacher["forced"], {4})
        self.assertEqual(teacher["phase"], "fallback")

    def test_25_only_complete_return_finalizes_obligations(self):
        state = {"todo": {1, 2}, "visited": [], "forced": {4}, "phase": "learning"}
        progress_fixture(state, "station", 1, complete=True)
        self.assertEqual(state["todo"], {2})
        self.assertEqual(state["visited"], [1])
        progress_fixture(state, "teacher_service", 4, complete=True)
        self.assertEqual(state["forced"], set())


if __name__ == "__main__":
    unittest.main(verbosity=2)
