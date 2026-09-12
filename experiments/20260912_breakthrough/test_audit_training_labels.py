"""Independent synthetic label tests, with no files, environments or trainers.

Toy traces test saved-label contracts only; physical request accounting is tested
separately. No real labels, worlds, or score values are embedded in this suite.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import unittest

import audit_training_labels as audit


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def encode(value):
    if type(value) is dict:
        return {"@": "dict", "v": [[k, encode(v)] for k, v in sorted(value.items())]}
    if type(value) is list:
        return {"@": "list", "v": [encode(v) for v in value]}
    if type(value) is float:
        return {"@": "float", "v": value.hex()}
    return value


def event(action, seconds):
    response = dict(accepted=True, virtual_time_s=seconds,
                    real_timestamp_ms=1234, remaining_real_duration_s=1000)
    if action == "exit":
        response["exit_reason"] = "user_exit"
    return dict(action=action, request={}, response=response)


def synthetic_world():
    # These are invented dictionaries for identity comparison, not simulator
    # inputs. The auditor must preserve every field except mutable cleared.
    sources = [dict(channel=c, x=31. * c, y=-17. * c, radius=1100.,
                    direction_deg=None if c % 2 else 45., cleared=False)
               for c in range(1, 11)]
    return dict(world_id="synthetic-world", world_sha256="synthetic-hash", role="fit",
                seed=42, noise="synthetic-fixed-noise", sources=sources)


def outcome(run_id="synthetic-result", *, total=1_000_000_000, prefix=400_000_000,
            success=True, kind="suffix", used=None):
    return dict(run_id=run_id, kind=kind, true_terminal_n=10, cleared=10 if success else 9,
        success=success, normal_exit=True, modeled_full_virtual_us=total,
        environment_log=[event("enter", 0), event("measure", prefix/1e6),
                         event("measure", total/1e6), event("exit", total/1e6)],
        episode=dict(error=None, prefix_event_count=2, prefix_virtual_us=prefix,
            slots_remaining=2-len(used or []), engine_final=encode(dict(used_operation_ids=used or [])),
            controller_final=encode(dict(position=[0., 0.], counters=dict(measure=2))),
            controller_recoveries=[], fallback_reason=None, macros=[]))


class TerminalCostUnits(unittest.TestCase):
    def test_microseconds_are_normalized_by_1000_seconds_and_terminal_n_once(self):
        self.assertEqual(audit.terminal_cost(outcome()), .1)
        self.assertEqual(audit.terminal_cost(outcome(), 400_000_000), .06)

    def test_full_prefix_difference_cancels_in_paired_gain(self):
        reference = outcome(total=1_020_000_000)
        alternative = outcome(total=1_000_000_000)
        full_gain = audit.terminal_cost(reference) - audit.terminal_cost(alternative)
        suffix_gain = audit.terminal_cost(reference, 400_000_000) - audit.terminal_cost(alternative, 400_000_000)
        self.assertAlmostEqual(full_gain, .002, places=14)
        self.assertAlmostEqual(suffix_gain, .002, places=14)

    def test_failure_penalty_is_plus_100_after_normalization(self):
        self.assertEqual(audit.terminal_cost(outcome(success=False)), 100.1)
        self.assertEqual(audit.terminal_cost(outcome(success=False), 400_000_000), 100.06)

    def test_resource_and_budget_interruptions_are_not_failed_training_labels(self):
        for error in ("MemoryError:", "BudgetStop: no reserve", "OSError: disk full", "IOError: interrupted"):
            value = outcome(success=False)
            value["episode"]["error"] = error
            with self.subTest(error=error), self.assertRaises(ValueError):
                audit.terminal_cost(value)

    def test_unknown_or_missing_accepted_terminal_evidence_rejected(self):
        for mutation in ("empty", "normal_exit", "rejected", "reason", "not_exit"):
            value = outcome(success=False)
            if mutation == "empty":
                value["environment_log"] = []
            elif mutation == "normal_exit":
                value["normal_exit"] = False
            elif mutation == "rejected":
                value["environment_log"][-1]["response"]["accepted"] = False
            elif mutation == "reason":
                value["environment_log"][-1]["response"]["exit_reason"] = "unproven_timeout"
            else:
                value["environment_log"][-1]["action"] = "measure"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                audit.terminal_cost(value)

    def test_controller_or_ledger_errors_cannot_be_disguised_as_terminal_cost(self):
        for field in ("error", "ledger_error"):
            value = outcome()
            if field == "error":
                value["episode"]["error"] = "Unclassified engineering failure"
            else:
                value["ledger_error"] = "prefix mismatch"
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit.terminal_cost(value)

    def test_invalid_n_cleared_and_success_flags_rejected(self):
        for changes in ({"true_terminal_n": 9}, {"true_terminal_n": 17}, {"true_terminal_n": 10.0},
                        {"true_terminal_n": True}, {"cleared": 11}, {"cleared": 9}, {"success": False}):
            value = outcome()
            value.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                audit.terminal_cost(value)

    def test_prefix_cannot_exceed_actual_full_cost(self):
        with self.assertRaises(ValueError):
            audit.terminal_cost(outcome(), 1_000_000_001)


class SamplingReconstructedFromMacros(unittest.TestCase):
    def setUp(self):
        self.world = dict(world_id="synthetic-world-id", world_sha256="synthetic-world-hash", role="fit")
        self.parent = outcome("synthetic-rollin", kind="full")
        self.parent["environment_log"] = [event("measure", i+.125) for i in range(8)] + [event("exit", 1000)]
        self.parent["episode"]["macros"] = [dict(choice_id=f"source-{i}", event_range=[i+1, i+2],
            payload=dict(kind="teacher_service", channel=1 if i < 2 else i+1)) for i in range(7)]
        self.sampling = dict(self.world, rollin_run_id=self.parent["run_id"],
            all_public_source_boundary_count=7, all_public_boundaries=[dict(source_index=i,
                choice_id=f"source-{i}", prefix_virtual_us=i*1_000_000+125_000,
                teacher_task=dict(kind="source", key=1 if i < 2 else i+1)) for i in range(7)],
            selected_source_indexes=[0, 2, 4, 6], zero_states_are_retained=True)

    def invoke(self):
        return audit.verify_sampling(self.sampling, self.parent, self.world)

    def test_uniform_rule_uses_all_source_entries_including_repeated_channel(self):
        selected, boundaries = self.invoke()
        self.assertEqual(selected, [0, 2, 4, 6])
        self.assertEqual(len(boundaries), 7)

    def test_wrong_world_role_or_parent_trajectory_rejected(self):
        for field in ("world_id", "world_sha256", "role", "rollin_run_id"):
            before = self.sampling[field]
            self.sampling[field] = "wrong-identity"
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.invoke()
            self.sampling[field] = before

    def test_missing_unselected_source_boundary_is_not_hidden_by_selected_set(self):
        self.sampling["all_public_boundaries"].pop(1)
        with self.assertRaises(ValueError):
            self.invoke()

    def test_declared_boundary_count_must_match_actual_trace(self):
        self.sampling["all_public_source_boundary_count"] = 4
        with self.assertRaises(ValueError):
            self.invoke()

    def test_boundary_identity_prefix_and_teacher_channel_must_match(self):
        for field in ("source_index", "choice_id", "prefix_virtual_us", "teacher_task"):
            original = deepcopy(self.sampling["all_public_boundaries"][1])
            if field == "teacher_task":
                self.sampling["all_public_boundaries"][1][field]["key"] = 20
            elif field == "choice_id":
                self.sampling["all_public_boundaries"][1][field] = "different-choice"
            else:
                self.sampling["all_public_boundaries"][1][field] += 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.invoke()
            self.sampling["all_public_boundaries"][1] = original

    def test_cherry_picked_or_reordered_uniform_indexes_rejected(self):
        for selected in ([0, 1, 4, 6], [6, 4, 2, 0], [0, 2, 2, 6]):
            self.sampling["selected_source_indexes"] = selected
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                self.invoke()

    def test_zero_source_entries_remain_an_explicit_valid_world(self):
        self.parent["episode"]["macros"] = [dict(payload=dict(kind="station"), event_range=[0, 1])]
        self.sampling.update(all_public_source_boundary_count=0, all_public_boundaries=[], selected_source_indexes=[])
        self.assertEqual(self.invoke(), ([], []))


class HandleIdentityAndSeals(unittest.TestCase):
    def setUp(self):
        self.world = synthetic_world()
        self.private = dict(seed=self.world["seed"], noise=self.world["noise"],
            _virtual_us=400_000_000,
            _sources={s["channel"]: deepcopy(s) for s in self.world["sources"]})
        self.boundary = dict(source_index=0, choice_id="synthetic-choice", prefix_virtual_us=400_000_000, channel=1)
        self.teacher_payload = dict(kind="teacher_service", channel=1, labels=["A0"])
        self.other_payload = dict(kind="measure_override", channel=1, labels=["A1"])
        candidates = sorted([self.teacher_payload, self.other_payload], key=digest)
        self.teacher = digest(self.teacher_payload)
        self.handle = dict(world_sha256=self.world["world_sha256"], source_index=0,
            private=encode(self.private),
            prepared=dict(choice_id="synthetic-choice", pre_state_hash="synthetic-pre", expanded=True,
                choices=dict(candidate_ids=[digest(p) for p in candidates], candidates=candidates,
                             teacher_id=self.teacher)),
            token=dict(prefix_virtual_us=400_000_000, accepted_event_count=2, semantic_pre_hash="synthetic-pre",
                engine_state=encode(dict(used_operation_ids=[], interventions_remaining=2))))
        self.seal_token()
        self.seal_handle()

    def seal_token(self):
        token = self.handle["token"]
        token.pop("integrity_sha256", None)
        token["integrity_sha256"] = digest(token)

    def seal_handle(self):
        self.handle.pop("bundle_integrity_sha256", None)
        self.handle["bundle_integrity_sha256"] = digest(self.handle)

    def invoke(self):
        return audit.verify_handle(self.handle, self.world, self.boundary, 0)

    def test_exact_expanded_handle_returns_its_complete_retained_ids(self):
        prepared, token, ids, teacher = self.invoke()
        self.assertEqual(ids, sorted([digest(self.teacher_payload), digest(self.other_payload)]))
        self.assertEqual(teacher, self.teacher)
        self.assertEqual(token["accepted_event_count"], 2)
        self.assertTrue(prepared["expanded"])

    def test_outer_bundle_mutation_rejected_without_reseal(self):
        self.handle["world_sha256"] = "changed"
        with self.assertRaises(ValueError):
            self.invoke()

    def test_inner_token_mutation_rejected_even_if_outer_handle_is_resealed(self):
        self.handle["token"]["accepted_event_count"] += 1
        self.seal_handle()
        with self.assertRaises(ValueError):
            self.invoke()

    def test_wrong_world_or_source_rejected_even_with_valid_seal(self):
        for field, value in (("world_sha256", "other-world"), ("source_index", 1)):
            old = self.handle[field]
            self.handle[field] = value
            self.seal_handle()
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.invoke()
            self.handle[field] = old
            self.seal_handle()

    def test_choice_prefix_and_semantic_prestate_must_match_original_boundary(self):
        for field in ("choice_id", "prefix_virtual_us", "pre_state_hash"):
            saved = deepcopy(self.handle)
            if field == "prefix_virtual_us":
                self.handle["token"][field] += 1
                self.seal_token()
            else:
                self.handle["prepared"][field] = "different"
            self.seal_handle()
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.invoke()
            self.handle = saved

    def test_pi0_handle_cannot_inherit_previous_interventions_or_spent_slots(self):
        for state in (dict(used_operation_ids=["prior-action"], interventions_remaining=2),
                      dict(used_operation_ids=[], interventions_remaining=1)):
            self.handle["token"]["engine_state"] = encode(state)
            self.seal_token()
            self.seal_handle()
            with self.subTest(state=state), self.assertRaises(ValueError):
                self.invoke()

    def test_unexpanded_candidate_set_rejected(self):
        self.handle["prepared"]["expanded"] = False
        self.seal_handle()
        with self.assertRaises(ValueError):
            self.invoke()

    def test_missing_duplicate_or_out_of_order_candidate_ids_rejected(self):
        original = deepcopy(self.handle)
        for mutation in ("missing", "duplicate", "order", "payload", "teacher"):
            self.handle = deepcopy(original)
            choices = self.handle["prepared"]["choices"]
            if mutation == "missing":
                choices["candidate_ids"].pop()
            elif mutation == "duplicate":
                choices["candidate_ids"].append(choices["candidate_ids"][0])
                choices["candidates"].append(deepcopy(choices["candidates"][0]))
            elif mutation == "order":
                choices["candidate_ids"].reverse()
                choices["candidates"].reverse()
            elif mutation == "payload":
                choices["candidates"][0]["channel"] = 2
            else:
                choices["teacher_id"] = "not-retained"
            self.seal_handle()
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.invoke()

    def test_teacher_only_state_is_valid_and_still_retained(self):
        self.handle["prepared"]["choices"].update(candidate_ids=[self.teacher],
            candidates=[deepcopy(self.teacher_payload)])
        self.seal_handle()
        self.assertEqual(self.invoke()[2], [self.teacher])


    def test_private_seed_noise_and_prefix_must_match_even_with_valid_seals(self):
        original = deepcopy(self.handle)
        for field, value in (("seed", 43), ("noise", "different-noise"),
                             ("_virtual_us", 400_000_001)):
            self.handle = deepcopy(original)
            private = deepcopy(self.private)
            private[field] = value
            self.handle["private"] = encode(private)
            self.seal_handle()
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "Fork seed/noise/prefix"):
                self.invoke()

    def test_same_n_resealed_private_world_cannot_change_source_geometry(self):
        private = deepcopy(self.private)
        private["_sources"][1]["x"] += 1.
        self.handle["private"] = encode(private)
        self.seal_handle()
        with self.assertRaisesRegex(ValueError, "source geometry"):
            self.invoke()

    def test_actual_past_clear_flags_do_not_change_private_world_identity(self):
        private = deepcopy(self.private)
        private["_sources"][1]["cleared"] = True
        self.handle["private"] = encode(private)
        self.seal_handle()
        self.invoke()


class RegisteredWorldGeometry(unittest.TestCase):
    def setUp(self):
        self.world = synthetic_world()
        self.result = dict(private_terminal_sources={str(s["channel"]): deepcopy(s)
                                                     for s in self.world["sources"]})

    def invoke(self):
        return audit.verify_world_sources(self.result, self.world)

    def test_identical_world_geometry_passes(self):
        self.invoke()

    def test_only_cleared_flags_may_differ_from_registered_initial_world(self):
        for index, source in enumerate(self.result["private_terminal_sources"].values()):
            source["cleared"] = index % 2 == 0
        self.invoke()

    def test_source_order_and_integer_versus_json_string_keys_are_not_identity(self):
        self.world["sources"].reverse()
        self.result["private_terminal_sources"] = {
            int(c): s for c, s in self.result["private_terminal_sources"].items()}
        self.invoke()

    def test_same_source_count_different_geometry_is_not_the_same_world(self):
        original = deepcopy(self.result)
        for field, value in (("x", 32.), ("y", -18.), ("radius", 1101.),
                             ("direction_deg", 46.), ("channel", 11)):
            self.result = deepcopy(original)
            self.result["private_terminal_sources"]["1"][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "source geometry"):
                self.invoke()

    def test_missing_or_extra_source_rejected(self):
        original = deepcopy(self.result)
        for mutation in ("missing", "extra"):
            self.result = deepcopy(original)
            if mutation == "missing":
                self.result["private_terminal_sources"].pop("1")
            else:
                extra = deepcopy(self.result["private_terminal_sources"]["1"])
                extra["channel"] = 11
                self.result["private_terminal_sources"]["11"] = extra
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, "source geometry"):
                self.invoke()

    def test_mapping_channel_cannot_hide_another_source_under_same_n(self):
        sources = self.result["private_terminal_sources"]
        sources["1"], sources["2"] = sources["2"], sources["1"]
        with self.assertRaisesRegex(ValueError, "source geometry"):
            self.invoke()

    def test_unrecognized_source_geometry_field_cannot_be_silently_ignored(self):
        self.result["private_terminal_sources"]["1"]["additional_geometry"] = 1
        with self.assertRaisesRegex(ValueError, "source geometry"):
            self.invoke()


def label_fixture(*, teacher_action=False, failed=False):
    teacher_payload = dict(kind="teacher_service", channel=1, labels=["A0"])
    alternative_payload = dict(kind="measure_override", channel=1, labels=["A1"])
    teacher = digest(teacher_payload)
    payload = teacher_payload if teacher_action else alternative_payload
    action_id = digest(payload)
    token = dict(prefix_virtual_us=400_000_000, accepted_event_count=2)
    reference = outcome("synthetic-a0-reference", total=1_020_000_000, used=[])
    reference["episode"]["macros"] = [dict(action_id=teacher, choice_id="synthetic-choice", payload=teacher_payload)]
    value = deepcopy(reference) if teacher_action else outcome("synthetic-alternative", total=1_000_000_000,
        success=not failed, used=[action_id])
    value["episode"]["macros"] = [dict(action_id=action_id, choice_id="synthetic-choice", payload=payload)]
    suffix = .062 if teacher_action else .06 + (100 if failed else 0)
    full = .102 if teacher_action else .1 + (100 if failed else 0)
    gain = 0. if teacher_action else .002 - (100 if failed else 0)
    row = dict(run_id=value["run_id"], action_id=action_id, choice_id="synthetic-choice",
        terminal_normalized_suffix_cost=suffix, terminal_normalized_full_cost=full, paired_gain_to_A0=gain,
        reference_origin_run_id=reference["run_id"], actual_slot_cost=int(not teacher_action),
        terminal_classification="proven_normal_exit_incomplete_clear_failure" if failed else "normal_complete_success",
        labels=payload["labels"])
    return value, row, reference, token, payload, teacher


class FullTailPairedLabel(unittest.TestCase):
    def invoke(self, values):
        return audit.verify_label(*values)

    def test_full_tail_label_uses_shared_prefix_and_terminal_source_count(self):
        suffix, gain = self.invoke(label_fixture())
        self.assertAlmostEqual(suffix, .06, places=14)
        self.assertAlmostEqual(gain, .002, places=14)

    def test_a0_has_exact_zero_gain_zero_spent_slots_and_original_reference(self):
        suffix, gain = self.invoke(label_fixture(teacher_action=True))
        self.assertAlmostEqual(suffix, .062, places=14)
        self.assertEqual(gain, 0.)

    def test_normal_terminal_failure_keeps_penalty_and_negative_paired_gain(self):
        suffix, gain = self.invoke(label_fixture(failed=True))
        self.assertAlmostEqual(suffix, 100.06, places=12)
        self.assertAlmostEqual(gain, -99.998, places=12)

    def test_resource_failure_cannot_pass_as_plus_100_label(self):
        values = label_fixture(failed=True)
        values[0]["episode"]["error"] = "MemoryError: resource stop"
        with self.assertRaises(ValueError):
            self.invoke(values)

    def test_wrong_units_missing_penalty_or_double_prefix_subtraction_rejected(self):
        for field, value in (("terminal_normalized_suffix_cost", .006),
                             ("terminal_normalized_full_cost", .06),
                             ("paired_gain_to_A0", .02)):
            values = label_fixture()
            values[1][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.invoke(values)
        values = label_fixture(failed=True)
        values[1]["paired_gain_to_A0"] = .002
        with self.assertRaises(ValueError):
            self.invoke(values)

    def test_nonfinite_or_boolean_normalized_label_rejected(self):
        for value in (float("nan"), float("inf"), True):
            values = label_fixture()
            values[1]["paired_gain_to_A0"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.invoke(values)

    def test_different_source_denominator_rejected(self):
        values = label_fixture()
        values[2]["true_terminal_n"] = values[2]["cleared"] = 11
        with self.assertRaises(ValueError):
            self.invoke(values)

    def test_wrong_reference_run_or_action_id_rejected(self):
        for field in ("reference_origin_run_id", "action_id", "run_id"):
            values = label_fixture()
            values[1][field] = "wrong-identity"
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.invoke(values)

    def test_wrong_slot_charge_terminal_class_or_provenance_labels_rejected(self):
        for field, value in (("actual_slot_cost", 0), ("terminal_classification", "normal_failure"), ("labels", ["A0"])):
            values = label_fixture()
            values[1][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.invoke(values)

    def test_full_execution_is_not_a_paid_suffix(self):
        values = label_fixture()
        values[0]["kind"] = "full"
        with self.assertRaises(ValueError):
            self.invoke(values)


class PrefixAndContinuationIntegrity(unittest.TestCase):
    def test_prefix_count_and_cost_must_match_the_sealed_token(self):
        for field in ("prefix_event_count", "prefix_virtual_us"):
            values = label_fixture()
            values[0]["episode"][field] += 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit.verify_label(*values)

    def test_same_prefix_cost_is_not_enough_when_actual_observations_differ(self):
        values = label_fixture()
        values[0]["environment_log"][1]["response"]["measure_result"] = "changed-observation"
        with self.assertRaises(ValueError):
            audit.verify_label(*values)

    def test_only_declared_nondeterministic_response_clock_fields_are_ignored(self):
        values = label_fixture()
        values[0]["environment_log"][1]["response"].update(real_timestamp_ms=9999, remaining_real_duration_s=777)
        audit.verify_label(*values)

    def test_first_actual_macro_must_be_exact_retained_operation_at_labeled_choice(self):
        for field in ("action_id", "choice_id", "payload"):
            values = label_fixture()
            first = values[0]["episode"]["macros"][0]
            first[field] = {} if field == "payload" else "wrong"
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit.verify_label(*values)

    def test_extra_future_intervention_is_not_frozen_c7_continuation(self):
        values = label_fixture()
        action_id = values[1]["action_id"]
        values[0]["episode"]["engine_final"] = encode(dict(used_operation_ids=[action_id, "second-action"]))
        with self.assertRaises(ValueError):
            audit.verify_label(*values)

    def test_a0_cannot_spend_a_hidden_intervention(self):
        values = label_fixture(teacher_action=True)
        values[0]["episode"]["engine_final"] = encode(dict(used_operation_ids=["hidden-action"]))
        with self.assertRaises(ValueError):
            audit.verify_label(*values)

    def test_remaining_slot_count_must_agree_with_actual_intervention_history(self):
        values = label_fixture()
        values[0]["episode"]["slots_remaining"] = 2
        with self.assertRaises(ValueError):
            audit.verify_label(*values)


if __name__ == "__main__":
    unittest.main()
