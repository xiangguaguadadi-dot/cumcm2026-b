"""Pure synthetic G1-record tests. No solver, environment, disk writes or network.

Toy observations below test audit invariants; they are not task simulations or
performance evidence. File readers are replaced by in-memory dictionaries.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

import audit_g1_headroom as audit


def encode(value):
    if type(value) is dict:
        return {"@": "dict", "v": [[encode(k), encode(v)] for k, v in value.items()]}
    if type(value) is list:
        return {"@": "list", "v": [encode(v) for v in value]}
    if type(value) is float:
        return {"@": "float", "v": value.hex()}
    return value


def event(action, seconds):
    return dict(action=action, request={}, response=dict(accepted=True, virtual_time_s=seconds,
        real_timestamp_ms=12345, remaining_real_duration_s=1199))


def result(run_id="synthetic-parent", cost=5_000_000, success=True, *, kind="full", plan=None):
    plan = deepcopy([] if plan is None else plan)
    return dict(run_id=run_id, kind=kind, success=success, true_terminal_n=10,
        modeled_full_virtual_us=cost, environment_log=[event("enter", 0), event("measure", 5), event("exit", 5)],
        episode=dict(engine_final=encode(dict(used_operation_ids=[p["action_id"] for p in plan])),
            slots_remaining=2-len(plan), macros=[], prefix_event_count=1, prefix_virtual_us=0),
        extra=dict(applied_plan=plan))


def operation_plan(choice="synthetic-choice", action="synthetic-operation"):
    return [dict(choice_id=choice, action_id=action, source_index=0, kind="measure_override", labels=[])]


class UniformPublicSampling(unittest.TestCase):
    def test_zero_to_four_boundaries_take_every_boundary(self):
        for count in range(5):
            with self.subTest(count=count):
                self.assertEqual(audit.uniform_indexes(count), list(range(count)))

    def test_more_boundaries_use_exact_inclusive_floor_spacing(self):
        for count, expected in ((5, [0, 1, 2, 4]), (6, [0, 1, 3, 5]),
                                (10, [0, 3, 6, 9]), (12, [0, 3, 7, 11]), (17, [0, 5, 10, 16])):
            with self.subTest(count=count):
                self.assertEqual(audit.uniform_indexes(count), expected)

    def test_invalid_counts_do_not_silently_coerce(self):
        for count in (-1, True, 4.0, "4"):
            with self.subTest(count=count), self.assertRaises(ValueError):
                audit.uniform_indexes(count)

    def test_large_counts_do_not_round_through_float(self):
        count = 2**60 + 3
        self.assertEqual(audit.uniform_indexes(count), [0, (count-1)//3, 2*(count-1)//3, count-1])


class ExactIntegerRank(unittest.TestCase):
    def test_failure_receives_exact_plus_100_normalized_units(self):
        for n in (10, 13, 16):
            good = result(cost=123_456_789)
            good["true_terminal_n"] = n
            failed = deepcopy(good)
            failed["success"] = False
            penalty = audit.rank(failed, [])[0] - audit.rank(good, [])[0]
            self.assertEqual(penalty, 100_000_000_000 * n)
            self.assertEqual(penalty / (1_000_000_000*n), 100)

    def test_cheap_failure_cannot_beat_successful_reference(self):
        self.assertLess(audit.rank(result(cost=5_000_000), []), audit.rank(result(cost=0, success=False), []))

    def test_microsecond_differences_above_float_precision_are_not_lost(self):
        self.assertLess(audit.rank(result(cost=2**60), []), audit.rank(result(cost=2**60+1), []))

    def test_equal_cost_prefers_fewer_interventions(self):
        self.assertLess(audit.rank(result(), []), audit.rank(result(), operation_plan()))

    def test_equal_cost_and_count_use_choice_then_action_lexicographic_tie_break(self):
        left, right = operation_plan("choice-a", "action-z"), operation_plan("choice-b", "action-a")
        self.assertLess(audit.rank(result(), left), audit.rank(result(), right))
        left, right = operation_plan("choice-a", "action-a"), operation_plan("choice-a", "action-b")
        self.assertLess(audit.rank(result(), left), audit.rank(result(), right))

    def test_invalid_source_denominators_are_rejected(self):
        for n in (0, 9, 17, True, 10.0):
            value = result()
            value["true_terminal_n"] = n
            with self.subTest(n=n), self.assertRaises(ValueError):
                audit.rank(value, [])


class FullPlanAndReplay(unittest.TestCase):
    def test_zero_one_and_two_operation_plans_match_slots_and_history(self):
        for count in range(3):
            plan = [dict(choice_id=f"c{i}", action_id=f"a{i}") for i in range(count)]
            with self.subTest(count=count):
                audit.check_plan(result(plan=plan), plan)

    def test_more_than_two_interventions_rejected(self):
        plan = [dict(choice_id=f"c{i}", action_id=f"a{i}") for i in range(3)]
        with self.assertRaises(ValueError):
            audit.check_plan(result(plan=plan), plan)

    def test_wrong_actual_operation_or_order_rejected(self):
        plan = [dict(choice_id="c0", action_id="a0"), dict(choice_id="c1", action_id="a1")]
        replay = result(plan=plan)
        replay["episode"]["engine_final"] = encode(dict(used_operation_ids=["a1", "a0"]))
        with self.assertRaises(ValueError):
            audit.check_plan(replay, plan)

    def test_wrong_remaining_slots_rejected(self):
        plan = operation_plan()
        replay = result(plan=plan)
        replay["episode"]["slots_remaining"] = 2
        with self.assertRaises(ValueError):
            audit.check_plan(replay, plan)

    def test_full_replay_must_apply_every_exact_plan_field(self):
        plan = operation_plan()
        replay = result(plan=plan)
        replay["extra"]["applied_plan"][0]["choice_id"] = "other-choice"
        with self.assertRaises(ValueError):
            audit.check_plan(replay, plan)

    def test_exact_full_replay_matches_suffix_reference(self):
        plan = operation_plan()
        audit.check_replay(result(kind="suffix", plan=plan), result("full-replay", plan=plan), plan)

    def test_successful_suffix_is_not_a_full_replay(self):
        with self.assertRaises(ValueError):
            audit.check_replay(result(), result("suffix", kind="suffix"), [])

    def test_failed_full_replay_rejected(self):
        with self.assertRaises(ValueError):
            audit.check_replay(result(), result("failed", success=False), [])

    def test_source_count_total_and_request_response_drift_rejected(self):
        for field in ("n", "cost", "request", "response"):
            replay = result("full-replay")
            if field == "n":
                replay["true_terminal_n"] = 11
            elif field == "cost":
                replay["modeled_full_virtual_us"] += 1
            elif field == "request":
                replay["environment_log"][1]["request"] = {"changed": True}
            else:
                replay["environment_log"][1]["response"]["changed"] = True
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit.check_replay(result(), replay, [])

    def test_only_reviewed_wall_clock_response_values_are_ignored(self):
        replay = result("full-replay")
        replay["environment_log"][1]["response"].update(real_timestamp_ms=98765, remaining_real_duration_s=1100)
        audit.check_replay(result(), replay, [])


class PublicMacroBoundaryReconstruction(unittest.TestCase):
    def setUp(self):
        self.parent = result()
        self.parent["environment_log"] = [event("measure", k + .125) for k in range(12)]
        kinds = ("station", "teacher_service", "measure_override", "station", "teacher_service",
                 "clear_override", "teacher_service")
        self.parent["episode"]["macros"] = [dict(payload=dict(kind=kind, channel=i+1),
            choice_id=f"choice-{i}", event_range=[i, i+1]) for i, kind in enumerate(kinds)]

    def record(self, phase="o1"):
        boundaries = audit.public_boundaries(self.parent, after_intervention=phase == "o2")
        return dict(trajectory_origin_run_id=self.parent["run_id"], stage=phase,
            after_intervention_handles_only=phase == "o2", all_public_source_boundary_count=len(boundaries),
            all_public_boundaries=[dict(source_index=b["source_index"], choice_id=b["choice_id"],
                prefix_virtual_us=b["prefix_virtual_us"], teacher_task=dict(kind="source", key=b["channel"])) for b in boundaries],
            selected_source_indexes=list(range(len(boundaries))))

    def test_all_source_entries_are_reconstructed_not_only_selected_handles(self):
        boundaries = audit.public_boundaries(self.parent, after_intervention=False)
        self.assertEqual([b["choice_id"] for b in boundaries], ["choice-1", "choice-4", "choice-6"])
        self.assertEqual([b["source_index"] for b in boundaries], [0, 1, 2])
        self.assertEqual([b["prefix_virtual_us"] for b in boundaries], [125000, 3125000, 5125000])

    def test_o2_includes_only_source_entries_after_first_actual_intervention(self):
        boundaries = audit.public_boundaries(self.parent, after_intervention=True)
        self.assertEqual([b["choice_id"] for b in boundaries], ["choice-4", "choice-6"])
        self.assertEqual([b["source_index"] for b in boundaries], [0, 1])

    def test_without_actual_intervention_o2_has_no_eligible_boundaries(self):
        self.parent["episode"]["macros"] = [m for m in self.parent["episode"]["macros"]
                                               if m["payload"]["kind"] not in ("measure_override", "clear_override")]
        self.assertEqual(audit.public_boundaries(self.parent, after_intervention=True), [])

    def test_valid_o1_and_o2_sampling_records_match_reconstruction(self):
        for phase, indexes in (("o1", [0, 1, 2]), ("o2", [0, 1])):
            with self.subTest(phase=phase):
                self.assertEqual(audit.check_sampling(self.record(phase), self.parent, phase)[0], indexes)

    def test_wrong_parent_phase_or_after_intervention_contract_rejected(self):
        for field, value in (("trajectory_origin_run_id", "other-parent"), ("stage", "o2"),
                             ("after_intervention_handles_only", True)):
            record = self.record()
            record[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit.check_sampling(record, self.parent, "o1")

    def test_missing_unsampled_or_changed_boundary_cannot_hide_from_denominator(self):
        for mutation in ("count", "list", "choice", "prefix", "source"):
            record = self.record()
            if mutation == "count":
                record["all_public_source_boundary_count"] -= 1
            elif mutation == "list":
                record["all_public_boundaries"].pop()
            elif mutation == "choice":
                record["all_public_boundaries"][0]["choice_id"] = "other"
            elif mutation == "prefix":
                record["all_public_boundaries"][0]["prefix_virtual_us"] += 1
            else:
                record["all_public_boundaries"][0]["teacher_task"]["key"] = 20
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                audit.check_sampling(record, self.parent, "o1")

    def test_cherry_picked_or_reordered_selected_indexes_rejected(self):
        for selected in ([0, 2], [2, 1, 0], [0, 0, 2]):
            record = self.record()
            record["selected_source_indexes"] = selected
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                audit.check_sampling(record, self.parent, "o1")


class CompleteActionBundleWithoutFileIO(unittest.TestCase):
    def setUp(self):
        self.impl = Path("/__synthetic_no_files__/repo/experiments/example/RL/implementation")
        self.stage = self.impl / "results/g1_synthetic"
        self.auditor = audit.Audit(self.impl, self.stage)
        self.auditor.pi = "synthetic-continuation-policy"
        self.world = dict(index=0, world_sha256="synthetic-world")
        self.parent = result()
        self.choice_id = "synthetic-source-choice"
        self.teacher_payload = dict(kind="teacher_service", channel=1)
        self.other_payload = dict(kind="measure_override", channel=1)
        payloads = sorted([self.teacher_payload, self.other_payload], key=audit.digest)
        self.ids = [audit.digest(payload) for payload in payloads]
        self.teacher, self.other = audit.digest(self.teacher_payload), audit.digest(self.other_payload)
        self.parent["episode"]["macros"] = [dict(payload=self.teacher_payload, choice_id=self.choice_id,
            action_id=self.teacher, event_range=[1, 2])]
        self.directory = self.stage / "worlds/w00"
        self.bundle_path = self.directory / "o1_s00"
        self.sampling = dict(world_sha256=self.world["world_sha256"], trajectory_origin_run_id=self.parent["run_id"],
            stage="o1", after_intervention_handles_only=False, all_public_source_boundary_count=1,
            all_public_boundaries=[dict(source_index=0, choice_id=self.choice_id, prefix_virtual_us=0,
                                        teacher_task=dict(kind="source", key=1))], selected_source_indexes=[0])
        self.handle = dict(world_sha256=self.world["world_sha256"], source_index=0,
            prepared=dict(choice_id=self.choice_id, pre_state_hash="synthetic-pre", choices=dict(
                candidate_ids=self.ids, candidates=payloads, teacher_id=self.teacher)),
            token=dict(prefix_virtual_us=0, accepted_event_count=1, semantic_pre_hash="synthetic-pre",
                       engine_state=encode(dict(used_operation_ids=[], interventions_remaining=2))))
        self.seal_token()
        self.seal_handle()
        identity = dict(world_sha256=self.world["world_sha256"], stage="o1", state_index=0, source_index=0,
            trajectory_origin_run_id=self.parent["run_id"], choice_id=self.choice_id,
            candidate_ids=self.ids, candidate_count=2, teacher_id=self.teacher,
            continuation_policy_sha256=self.auditor.pi)
        self.registration = dict(identity, status="registered_not_complete", outcomes=[])
        self.bundle = dict(identity, status="complete", outcomes=[])
        for action_id, payload in zip(self.ids, payloads):
            plan = [] if action_id == self.teacher else operation_plan(self.choice_id, action_id)
            branch = result("branch-" + action_id, cost=5_000_000 if action_id == self.teacher else 4_000_000,
                            kind="suffix", plan=plan)
            branch["episode"]["macros"] = [dict(choice_id=self.choice_id, action_id=action_id, payload=payload)]
            indexed = dict(run_id=branch["run_id"], world_sha256=self.world["world_sha256"],
                family="o1_counterfactual", action_id=action_id, choice_id=self.choice_id)
            self.auditor.results[branch["run_id"]] = branch
            self.auditor.index[branch["run_id"]] = indexed
            self.bundle["outcomes"].append(dict(indexed, plan=plan,
                paired_gain_to_current_reference=(5_000_000-branch["modeled_full_virtual_us"])/10_000_000_000))
        self.chosen = dict(selected_reference_run_id="branch-" + self.other,
            selected_modeled_full_virtual_us=4_000_000, plan=operation_plan(self.choice_id, self.other),
            bundles=[dict(directory=str(self.bundle_path.relative_to(self.impl)), candidate_count=2,
                          state_index=0, source_index=0, status="complete")])
        self.files = {self.directory / "o1_sampling.json": self.sampling,
                      self.directory / "o1_choice.json": self.chosen,
                      self.bundle_path / "registration.json": self.registration,
                      self.bundle_path / "outcomes.json": self.bundle,
                      self.bundle_path / "handle.json.gz": self.handle}
        self.auditor.load = lambda path: deepcopy(self.files[Path(path)])

    def seal_handle(self):
        self.handle.pop("bundle_integrity_sha256", None)
        self.handle["bundle_integrity_sha256"] = audit.digest(self.handle)

    def seal_token(self):
        self.handle["token"].pop("integrity_sha256", None)
        self.handle["token"]["integrity_sha256"] = audit.digest(self.handle["token"])

    def invoke(self):
        return self.auditor.search(self.world, "o1", self.parent, [])

    def test_complete_retained_set_selects_exact_best_successful_branch(self):
        winner, plan, count, failures = self.invoke()
        self.assertEqual(winner["run_id"], "branch-" + self.other)
        self.assertEqual(plan, self.chosen["plan"])
        self.assertEqual((count, failures), (2, 0))

    def test_missing_action_is_not_a_complete_bundle(self):
        self.bundle["outcomes"].pop()
        with self.assertRaises(ValueError):
            self.invoke()

    def test_incomplete_bundle_status_is_not_ranked(self):
        self.bundle["status"] = "incomplete_budget"
        with self.assertRaises(ValueError):
            self.invoke()

    def test_duplicate_or_reordered_action_rows_rejected(self):
        self.bundle["outcomes"].reverse()
        with self.assertRaises(ValueError):
            self.invoke()

    def test_missing_selected_state_bundle_rejected(self):
        self.chosen["bundles"] = []
        with self.assertRaises(ValueError):
            self.invoke()

    def test_wrong_sampling_world_rejected(self):
        self.sampling["world_sha256"] = "other-world"
        with self.assertRaises(ValueError):
            self.invoke()

    def test_wrong_handle_world_rejected_even_after_integrity_reseal(self):
        self.handle["world_sha256"] = "other-world"
        self.seal_handle()
        with self.assertRaises(ValueError):
            self.invoke()

    def test_wrong_registration_world_rejected(self):
        self.registration["world_sha256"] = "other-world"
        with self.assertRaises(ValueError):
            self.invoke()

    def test_wrong_bundle_world_rejected(self):
        self.bundle["world_sha256"] = "other-world"
        with self.assertRaises(ValueError):
            self.invoke()

    def test_bundle_cannot_borrow_an_indexed_branch_from_another_world(self):
        run_id = "branch-" + self.other
        self.auditor.index[run_id]["world_sha256"] = "other-world"
        next(row for row in self.bundle["outcomes"] if row["run_id"] == run_id)["world_sha256"] = "other-world"
        with self.assertRaises(ValueError):
            self.invoke()

    def test_tampered_handle_seal_rejected(self):
        self.handle["token"]["semantic_pre_hash"] = "changed-without-reseal"
        with self.assertRaises(ValueError):
            self.invoke()

    def test_tampered_inner_token_rejected_even_if_outer_bundle_resealed(self):
        self.handle["token"]["semantic_pre_hash"] = "changed-token"
        self.seal_handle()
        with self.assertRaises(ValueError):
            self.invoke()

    def test_inherited_operation_history_and_remaining_slots_must_match_parent(self):
        for state in (dict(used_operation_ids=["invented-prior"], interventions_remaining=2),
                      dict(used_operation_ids=[], interventions_remaining=1)):
            self.handle["token"]["engine_state"] = encode(state)
            self.seal_token()
            self.seal_handle()
            with self.subTest(state=state), self.assertRaises(ValueError):
                self.invoke()

    def test_wrong_prefix_events_or_cost_rejected(self):
        self.auditor.results["branch-" + self.other]["episode"]["prefix_virtual_us"] += 1
        with self.assertRaises(ValueError):
            self.invoke()

    def test_wrong_first_counterfactual_operation_rejected(self):
        self.auditor.results["branch-" + self.other]["episode"]["macros"][0]["action_id"] = self.teacher
        with self.assertRaises(ValueError):
            self.invoke()

    def test_failed_branch_is_counted_and_penalized_not_dropped(self):
        failed = self.auditor.results["branch-" + self.other]
        failed["success"] = False
        row = next(r for r in self.bundle["outcomes"] if r["run_id"] == failed["run_id"])
        row["paired_gain_to_current_reference"] -= 100
        self.chosen.update(selected_reference_run_id=self.parent["run_id"],
            selected_modeled_full_virtual_us=self.parent["modeled_full_virtual_us"], plan=[])
        winner, plan, count, failures = self.invoke()
        self.assertEqual((winner["run_id"], plan, count, failures), (self.parent["run_id"], [], 2, 1))

    def test_omitted_failure_penalty_in_gain_is_rejected(self):
        self.auditor.results["branch-" + self.other]["success"] = False
        with self.assertRaises(ValueError):
            self.invoke()

    def test_teacher_complete_continuation_must_match_parent_trace(self):
        self.auditor.results["branch-" + self.teacher]["environment_log"][1]["response"]["changed"] = True
        with self.assertRaises(ValueError):
            self.invoke()

    def test_selected_winner_must_be_exact_complete_enumerated_minimum(self):
        self.chosen.update(selected_reference_run_id=self.parent["run_id"],
            selected_modeled_full_virtual_us=self.parent["modeled_full_virtual_us"], plan=[])
        with self.assertRaises(ValueError):
            self.invoke()

    def test_o2_without_first_intervention_stops_without_inventing_branches(self):
        self.files[self.directory / "o2_sampling.json"] = dict(status="no_first_intervention_selected", selected_source_indexes=[])
        self.files[self.directory / "o2_choice.json"] = dict(bundles=[], plan=[],
            selected_reference_run_id=self.parent["run_id"], selected_modeled_full_virtual_us=self.parent["modeled_full_virtual_us"])
        winner, plan, count, failures = self.auditor.search(self.world, "o2", self.parent, [])
        self.assertEqual((winner["run_id"], plan, count, failures), (self.parent["run_id"], [], 0, 0))


if __name__ == "__main__":
    unittest.main()
