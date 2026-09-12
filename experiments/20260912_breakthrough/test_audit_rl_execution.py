"""Independent pure-record tests; no solver/environment, campaign, files or network.

All worlds, source records and responses below are deliberately synthetic.  The
one-source examples test accounting invariants, not the official world model.
Run: python3.12 -S -B -m unittest discover -s experiments/20260912_breakthrough
     -p 'test_audit_rl_execution.py' -v
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import zipfile

import audit_rl_execution as audit


def accepted(action, time_s, args=None):
    response = dict(accepted=True, virtual_time_s=time_s,
                    real_timestamp_ms=12345, remaining_real_duration_s=1199)
    if action == "exit":
        response["exit_reason"] = "user_exit"
    if action == "clear":
        response["clear_result"] = "success"
    if action == "measure":
        response["measure_result"] = "direction"
    return dict(action=action, args=[] if args is None else list(args),
                result=dict(event="call_response", accepted=True, response=response))


def journal(calls, *, run_id="synthetic", kind="full", success=True,
            unknown_cost=False, offset=0, metadata=None, finish=True):
    """Construct records directly; this never invokes a backend or Budget."""
    rows = [dict(event="run_start", run_id=run_id, kind=kind,
                 metadata=dict(metadata or {"world_sha256": "synthetic-world"}))]
    accepted_count = 0
    for sequence, call in enumerate(calls, offset):
        rows.append(dict(event="call_start", run_id=run_id, sequence=sequence,
                         action=call["action"], args=deepcopy(call["args"])))
        if "result" in call:
            result = deepcopy(call["result"])
            result.update(run_id=run_id, sequence=sequence)
            rows.append(result)
            accepted_count += result.get("event") == "call_response" and result.get("accepted") is True
    if finish:
        rows.append(dict(event="run_finish", run_id=run_id, attempted=len(calls),
                         accepted=accepted_count, success=success, unknown_cost=unknown_cost))
    return rows


def event_log(calls):
    """Construct the expected log without reusing the audited request mapper."""
    log = []
    for call in calls:
        action, args = call["action"], call["args"]
        request = {} if action in ("enter", "exit") else dict(
            position=dict(x=args[0], y=args[1]), channel=args[2])
        log.append(dict(action=action, request=request,
                        response=deepcopy(call["result"]["response"])))
    return log


def full_fixture(*, suffix=False):
    """A ten-second toy episode; inherited prefix has five seconds for suffix."""
    calls = [accepted("enter", 0), accepted("measure", 5, [0., 0., 1]),
             accepted("clear", 10, [0., 0., 1]), accepted("exit", 10)]
    log = event_log(calls)
    prefix = 2 if suffix else 1
    prefix_us = 5_000_000 if suffix else 0
    start = prefix
    macros = []
    for end in range(prefix + 1, len(log)):
        before = round(log[start - 1]["response"]["virtual_time_s"] * 1e6)
        after = round(log[end - 1]["response"]["virtual_time_s"] * 1e6)
        macros.append(dict(event_range=[start, end], delta_us=after - before))
        start = end
    episode = dict(prefix_event_count=prefix, prefix_virtual_us=prefix_us,
                   total_virtual_us=10_000_000, tail_virtual_us=0,
                   cost_partition_error_us=0, macros=macros, events=deepcopy(log),
                   suffix_accepted_events=len(log) - prefix, slots_remaining=2, error=None)
    kind = "suffix" if suffix else "full"
    paid = calls[prefix:] if suffix else calls
    rows = journal(paid, kind=kind, metadata=dict(world_sha256="synthetic-world",
                   prefix_virtual_us=prefix_us, prefix_event_count=prefix))
    _, runs = audit.audit_journal(rows)
    result = dict(schema="bc-rpi-evaluator-outcome-v1", run_id="synthetic", kind=kind,
                  environment_log=log, episode=episode,
                  private_terminal_sources={"1": {"cleared": True}}, true_terminal_n=1,
                  cleared=1, stats=dict(n=1, cleared=1, time_s=10.),
                  modeled_full_virtual_us=10_000_000, seconds_per_source=10.,
                  normal_exit=True, success=True)
    return result, runs["synthetic"], rows


def partial_interface_fixture(*, resumed=False, lost_public_response=False):
    """A deliberately incomplete toy task whose fixture assertions may pass."""
    prefix_calls = [accepted("enter", 0), accepted("measure", 5, [0., 0., 1])]
    calls = prefix_calls + [accepted("measure", 10, [0., 0., 1])] if resumed else prefix_calls
    prefix = 2 if resumed else 0
    log = event_log(calls)
    metadata = dict(world_sha256="synthetic-partial-world", prefix_event_count=prefix,
                    prefix_virtual_us=5_000_000 if resumed else 0)
    _, runs = audit.audit_journal(journal(calls[prefix:], kind="fixture", metadata=metadata))
    checks = dict(expected_partial_state=True, physical_call_count_preserved=True)
    public_events = log[:1] if lost_public_response else log
    result = dict(schema="bc-rpi-real-interface-fixture-v1", run_id="synthetic", kind="fixture",
        success=True, normal_exit=False, checks=checks,
        verification_kind="synthetic_expected_partial_semantics_not_solver_performance",
        environment_log=log, modeled_full_virtual_us=10_000_000 if resumed else 5_000_000,
        detail=dict(public_events=deepcopy(public_events)))
    return result, runs["synthetic"]


class JournalAccounting(unittest.TestCase):
    def test_four_physical_outcomes_are_partitioned_not_double_counted(self):
        accepted_call = accepted("measure", 5, [0, 0, 1])
        rejection = dict(action="measure", args=[0, 0, 1], result=dict(
            event="call_response", accepted=False,
            response=dict(accepted=False, virtual_time_s=0)))
        known = dict(action="measure", args=[0, 0, 1], result=dict(
            event="call_exception", acceptance="known_no_accept", error="synthetic invalid input"))
        unknown = dict(action="measure", args=[0, 0, 1], result=dict(
            event="call_exception", acceptance="unknown", error="synthetic ambiguous failure"))
        counts, runs = audit.audit_journal(journal(
            [accepted_call, rejection, known, unknown], success=False, unknown_cost=True))
        self.assertEqual(counts["business_calls"], 4)
        self.assertEqual(counts["accepted_calls"], 1)
        self.assertEqual(counts["rejected_calls"], 2)  # Response rejection + known-no-accept.
        self.assertEqual(counts["unknown_calls"], 1)
        self.assertEqual(counts["exception_calls"], 2)  # Orthogonal diagnostic, not added again.
        self.assertEqual(counts["unresolved_calls"], 0)
        self.assertEqual(sum(counts[k] for k in
            ("accepted_calls", "rejected_calls", "unknown_calls", "unresolved_calls")), 4)
        self.assertEqual(runs["synthetic"]["counts"]["business_calls"], 4)

    def test_absent_exception_acceptance_remains_unknown(self):
        call = dict(action="measure", args=[0, 0, 1], result=dict(event="call_exception"))
        counts, _ = audit.audit_journal(journal([call], success=False, unknown_cost=True))
        self.assertEqual((counts["unknown_calls"], counts["rejected_calls"]), (1, 0))

    def test_known_no_accept_is_not_unknown(self):
        call = dict(action="measure", args=[0, 0, 1], result=dict(
            event="call_exception", acceptance="known_no_accept"))
        counts, _ = audit.audit_journal(journal([call], success=False))
        self.assertEqual((counts["rejected_calls"], counts["unknown_calls"]), (1, 0))

    def test_unknown_cannot_be_marked_success_or_known_cost(self):
        call = dict(action="measure", args=[0, 0, 1], result=dict(
            event="call_exception", acceptance="unknown"))
        for success, unknown_cost in ((True, True), (False, False), (True, False)):
            with self.subTest(success=success, unknown_cost=unknown_cost), self.assertRaises(ValueError):
                audit.audit_journal(journal([call], success=success, unknown_cost=unknown_cost))

    def test_pending_is_unresolved_not_accepted_rejected_or_unknown(self):
        counts, _ = audit.audit_journal(journal([dict(action="enter", args=[])], finish=False))
        self.assertEqual((counts["unfinished_runs"], counts["unresolved_calls"]), (1, 1))
        self.assertEqual(sum(counts[k] for k in ("accepted_calls", "rejected_calls", "unknown_calls")), 0)

    def test_pending_call_cannot_settle(self):
        with self.assertRaises(ValueError):
            audit.audit_journal(journal([dict(action="enter", args=[])]))

    def test_duplicate_run_rejected(self):
        with self.assertRaises(ValueError):
            audit.audit_journal(journal([]) + journal([]))

    def test_overlapping_run_rejected(self):
        with self.assertRaises(ValueError):
            audit.audit_journal(journal([], finish=False) + journal([], run_id="second"))

    def test_duplicate_response_rejected(self):
        rows = journal([accepted("enter", 0)])
        rows.insert(3, deepcopy(rows[2]))
        with self.assertRaises(ValueError):
            audit.audit_journal(rows)

    def test_response_wrong_sequence_or_run_rejected(self):
        for key, value in (("sequence", 7), ("run_id", "other")):
            rows = journal([accepted("enter", 0)])
            rows[2][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                audit.audit_journal(rows)

    def test_duplicate_or_gapped_sequence_rejected(self):
        rows = journal([accepted("enter", 0), accepted("exit", 0)])
        for sequence in (0, 3):
            altered = deepcopy(rows)
            altered[3]["sequence"] = sequence
            with self.subTest(sequence=sequence), self.assertRaises(ValueError):
                audit.audit_journal(altered)

    def test_sequence_requires_integer_not_bool_or_float(self):
        for value in (0.0, False):
            rows = journal([accepted("enter", 0)])
            rows[1]["sequence"] = rows[2]["sequence"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                audit.audit_journal(rows)

    def test_finish_counts_require_integers_not_booleans(self):
        for field in ("attempted", "accepted"):
            rows = journal([accepted("enter", 0)])
            rows[-1][field] = True
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit.audit_journal(rows)

    def test_result_flag_must_match_response(self):
        rows = journal([accepted("enter", 0)])
        rows[2]["accepted"] = False
        with self.assertRaises(ValueError):
            audit.audit_journal(rows)

    def test_finish_attempt_and_accept_counts_match_actual(self):
        for key in ("attempted", "accepted"):
            rows = journal([accepted("enter", 0)])
            rows[-1][key] += 1
            with self.subTest(key=key), self.assertRaises(ValueError):
                audit.audit_journal(rows)

    def test_enter_count_only_actual_accepted_enter(self):
        reject = dict(action="enter", args=[], result=dict(event="call_response",
            accepted=False, response=dict(accepted=False, virtual_time_s=0)))
        counts, _ = audit.audit_journal(journal([reject, accepted("enter", 0)]))
        self.assertEqual(counts["entered"], 1)

    def test_repeated_worlds_do_not_add_unique_worlds(self):
        rows = journal([accepted("enter", 0)]) + journal([accepted("enter", 0)], run_id="again", offset=1)
        counts, _ = audit.audit_journal(rows)
        self.assertEqual(counts["executions_started"], 2)
        self.assertEqual(counts["unique_worlds_actually_started"], 1)

    def test_unknown_event_action_and_exception_class_rejected(self):
        for mutation in ("event", "action", "acceptance"):
            rows = journal([accepted("enter", 0)])
            if mutation == "event":
                rows[1]["event"] = "unexpected"
            elif mutation == "action":
                rows[1]["action"] = "private_state"
            else:
                rows[2] = dict(event="call_exception", run_id="synthetic", sequence=0, acceptance="known_accepted")
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                audit.audit_journal(rows)


class OutcomeAlignment(unittest.TestCase):
    def test_full_log_matches_all_actual_calls(self):
        result, run, _ = full_fixture()
        finding = audit.audit_outcome(result, run)
        self.assertEqual((finding["accepted_calls"], finding["prefix_events_not_recounted"]), (4, 0))

    def test_suffix_reuses_prefix_without_billing_it_again(self):
        result, run, _ = full_fixture(suffix=True)
        finding = audit.audit_outcome(result, run)
        self.assertEqual(len(result["environment_log"]), 4)
        self.assertEqual((finding["accepted_calls"], finding["prefix_events_not_recounted"]), (2, 2))
        self.assertEqual(run["counts"]["business_calls"], 2)

    def test_original_full_report_without_episode_prefix_is_supported(self):
        result, run, _ = full_fixture()
        result["episode"] = dict(error=None)
        self.assertEqual(audit.audit_outcome(result, run)["accepted_calls"], 4)

    def test_only_machine_clock_fields_are_ignored(self):
        result, run, _ = full_fixture()
        for event in result["environment_log"] + result["episode"]["events"]:
            event["response"]["real_timestamp_ms"] += 54321
            event["response"]["remaining_real_duration_s"] -= 1
        audit.audit_outcome(result, run)
        result["environment_log"][1]["response"]["virtual_time_s"] += .1
        with self.assertRaises(ValueError):
            audit.audit_outcome(result, run)

    def test_request_misalignment_is_rejected(self):
        result, run, _ = full_fixture()
        result["environment_log"][1]["request"]["channel"] = 2
        with self.assertRaises(ValueError):
            audit.audit_outcome(result, run)

    def test_missing_accepted_event_is_rejected(self):
        result, run, _ = full_fixture()
        result["environment_log"].pop(1)
        with self.assertRaises(ValueError):
            audit.audit_outcome(result, run)

    def test_suffix_prefix_cannot_be_billed_again(self):
        result, run, _ = full_fixture(suffix=True)
        result["episode"]["prefix_event_count"] = 0
        with self.assertRaises(ValueError):
            audit.audit_outcome(result, run)

    def test_suffix_cannot_reenter_even_if_logs_align(self):
        result, _, _ = full_fixture(suffix=True)
        result["environment_log"][2] = dict(action="enter", request={}, response=dict(accepted=True, virtual_time_s=10.))
        result["episode"]["events"] = deepcopy(result["environment_log"])
        rows = journal([accepted("enter", 10), accepted("exit", 10)], kind="suffix",
                       metadata=dict(prefix_virtual_us=5_000_000, prefix_event_count=2))
        _, runs = audit.audit_journal(rows)
        with self.assertRaises(ValueError):
            audit.audit_outcome(result, runs["synthetic"])

    def test_suffix_prefix_cost_must_match_registration(self):
        result, run, _ = full_fixture(suffix=True)
        result["episode"]["prefix_virtual_us"] += 1
        with self.assertRaises(ValueError):
            audit.audit_outcome(result, run)

    def test_suffix_prefix_cost_must_also_match_real_prefix_log(self):
        result, run, _ = full_fixture(suffix=True)
        result["episode"]["prefix_virtual_us"] -= 1_000_000
        run["start"]["metadata"]["prefix_virtual_us"] -= 1_000_000
        result["episode"]["tail_virtual_us"] += 1_000_000
        with self.assertRaises(ValueError):
            audit.audit_outcome(result, run)

    def test_full_cannot_claim_inherited_paid_prefix(self):
        result, run, _ = full_fixture()
        episode = result["episode"]
        episode.update(prefix_event_count=2, prefix_virtual_us=5_000_000,
                       suffix_accepted_events=2, macros=episode["macros"][1:])
        with self.assertRaises(ValueError):
            audit.audit_outcome(result, run)

    def test_success_must_agree_with_run_finish(self):
        result, run, _ = full_fixture()
        run["finish"]["success"] = False
        with self.assertRaises(ValueError):
            audit.audit_outcome(result, run)

    def test_success_requires_an_actual_normal_exit(self):
        result, _, rows = full_fixture()
        rows = rows[:-3]  # Drop exit call_start, call_response, run_finish.
        rows.append(dict(event="run_finish", run_id="synthetic", attempted=3,
                         accepted=3, unknown_cost=False, success=True))
        _, runs = audit.audit_journal(rows)
        result["environment_log"].pop()
        result["episode"]["events"] = deepcopy(result["environment_log"])
        result["episode"]["suffix_accepted_events"] -= 1
        with self.assertRaises(ValueError):
            audit.audit_outcome(result, runs["synthetic"])

    def test_success_cannot_hide_uncleared_source(self):
        result, run, _ = full_fixture()
        result["private_terminal_sources"]["1"]["cleared"] = False
        result["cleared"] = result["stats"]["cleared"] = 0
        with self.assertRaises(ValueError):
            audit.audit_outcome(result, run)

    def test_success_cannot_hide_error_or_non_normal_exit(self):
        for field in ("error", "normal_exit"):
            result, run, _ = full_fixture()
            if field == "error":
                result["episode"]["error"] = "synthetic failure"
            else:
                result["normal_exit"] = False
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit.audit_outcome(result, run)

    def test_full_source_and_time_denominators_are_bound(self):
        for mutation in ("true_terminal_n", "cleared", "seconds_per_source", "total"):
            result, run, _ = full_fixture()
            if mutation == "true_terminal_n":
                result["true_terminal_n"] = 2
            elif mutation == "cleared":
                result["cleared"] = 0
            elif mutation == "seconds_per_source":
                result["seconds_per_source"] = 5.
            else:
                result["modeled_full_virtual_us"] += 1
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                audit.audit_outcome(result, run)

    def test_macro_ranges_reject_overlap_gap_and_out_of_bounds(self):
        for start, end in ((0, 2), (2, 2), (1, 5)):
            result, run, _ = full_fixture()
            result["episode"]["macros"][0]["event_range"] = [start, end]
            with self.subTest(event_range=[start, end]), self.assertRaises(ValueError):
                audit.audit_outcome(result, run)

    def test_macro_fee_cannot_be_shifted_into_tail(self):
        result, run, _ = full_fixture()
        result["episode"]["macros"][0]["delta_us"] -= 1
        result["episode"]["tail_virtual_us"] += 1
        with self.assertRaises(ValueError):
            audit.audit_outcome(result, run)

    def test_macro_total_partition_error_and_event_count_rejected(self):
        for field in ("total_virtual_us", "tail_virtual_us", "cost_partition_error_us", "suffix_accepted_events"):
            result, run, _ = full_fixture()
            result["episode"][field] += 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit.audit_outcome(result, run)

    def test_macro_public_private_event_sequences_must_match(self):
        result, run, _ = full_fixture()
        result["episode"]["events"][2]["request"]["channel"] = 2
        with self.assertRaises(ValueError):
            audit.audit_outcome(result, run)

    def test_hidden_operation_cannot_be_relabelled_as_unexplained_tail(self):
        result, run, _ = full_fixture()
        result["episode"]["macros"].pop()
        result["episode"]["tail_virtual_us"] = 5_000_000
        with self.assertRaises(ValueError):
            audit.audit_outcome(result, run)

    def test_declared_fallback_tail_preserves_actual_cost(self):
        result, run, _ = full_fixture()
        result["episode"]["macros"].pop()
        result["episode"].update(tail_virtual_us=5_000_000,
                                 fallback_reason="synthetic explicitly declared fallback")
        finding = audit.audit_outcome(result, run)
        self.assertEqual(finding["accepted_calls"], 4)

    def test_fabricated_physical_cost_rejected_even_when_all_totals_agree(self):
        result, run, _ = full_fixture()
        for index in (2, 3):
            result["environment_log"][index]["response"]["virtual_time_s"] = 11.
            run["calls"][index]["result"]["response"]["virtual_time_s"] = 11.
        result.update(modeled_full_virtual_us=11_000_000, seconds_per_source=11.)
        result["stats"]["time_s"] = 11.
        result["episode"]["total_virtual_us"] = 11_000_000
        result["episode"]["macros"][-1]["delta_us"] = 6_000_000
        result["episode"]["events"] = deepcopy(result["environment_log"])
        with self.assertRaises(ValueError):
            audit.audit_outcome(result, run)

    def test_intervention_slots_cannot_exceed_bound(self):
        for value in (-1, 3, 1.5, True):
            result, run, _ = full_fixture()
            result["episode"]["slots_remaining"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                audit.audit_outcome(result, run)


class IndependentPrimitiveCosts(unittest.TestCase):
    def test_move_switch_and_clear_channel_rules(self):
        calls = [accepted("enter", 0), accepted("measure", 7, [5., 0., 2]),
                 accepted("clear", 12, [5., 0., 3]),
                 accepted("measure", 17, [5., 0., 2]), accepted("exit", 17)]
        result = audit.audit_physical_costs(event_log(calls))
        self.assertEqual(result["total_virtual_us"], 17_000_000)
        self.assertEqual(result["cleared_channels"], {3})

    def test_failed_clear_pays_three_not_five_seconds(self):
        failed_clear = accepted("clear", 5, [10., 0., 1])
        failed_clear["result"]["response"]["clear_result"] = "no_target_in_range"
        calls = [accepted("enter", 0), failed_clear,
                 accepted("measure", 10, [10., 0., 1]), accepted("exit", 10)]
        result = audit.audit_physical_costs(event_log(calls))
        self.assertEqual(result["total_virtual_us"], 10_000_000)
        self.assertEqual(result["cleared_channels"], set())

    def test_half_microsecond_rounds_up_per_primitive(self):
        calls = [accepted("enter", 0), accepted("measure", 5.000001, [0.0000025, 0., 1]),
                 accepted("exit", 5.000001)]
        self.assertEqual(audit.audit_physical_costs(event_log(calls))["total_virtual_us"], 5_000_001)

    def test_duplicate_successful_clear_rejected(self):
        calls = [accepted("enter", 0), accepted("clear", 5, [0., 0., 1]),
                 accepted("clear", 10, [0., 0., 1]), accepted("exit", 10)]
        with self.assertRaises(ValueError):
            audit.audit_physical_costs(event_log(calls))

    def test_result_cannot_invent_an_uncleared_channel_as_cleared(self):
        result, run, _ = full_fixture()
        result["private_terminal_sources"] = {"2": {"cleared": True}}
        with self.assertRaises(ValueError):
            audit.audit_outcome(result, run)

    def test_accepted_event_before_enter_or_after_exit_rejected(self):
        for calls in ([accepted("measure", 5, [0., 0., 1])],
                      [accepted("enter", 0), accepted("exit", 0), accepted("measure", 5, [0., 0., 1])]):
            with self.subTest(calls=calls), self.assertRaises(ValueError):
                audit.audit_physical_costs(event_log(calls))

    def test_rejected_response_cannot_enter_accepted_log(self):
        log = event_log([accepted("enter", 0)])
        log[0]["response"]["accepted"] = False
        with self.assertRaises(ValueError):
            audit.audit_physical_costs(log)

    def test_invalid_coordinate_or_channel_in_accepted_log_rejected(self):
        for args in ([float("nan"), 0, 1], [2_000_001, 0, 1], [True, 0, 1], [0, 0, True], [0, 0, 1.5]):
            log = event_log([accepted("enter", 0), accepted("measure", 5, args)])
            with self.subTest(args=args), self.assertRaises(ValueError):
                audit.audit_physical_costs(log)


class PartialInterfaceFixtures(unittest.TestCase):
    def test_expected_partial_fixture_pass_is_not_full_clear_success(self):
        result, run = partial_interface_fixture()
        finding = audit.audit_fixture_outcome(result, run)
        self.assertTrue(finding["assertions_passed"])
        self.assertFalse(finding["physical_exit_observed"])
        self.assertEqual(finding["accepted_calls"], 2)
        self.assertNotIn("source_count", finding)
        self.assertNotIn("cleared", finding)
        self.assertNotIn("success", finding)
        self.assertIn("not full-clear solver performance", finding["scope"])

    def test_lost_public_response_does_not_erase_known_accepted_cost(self):
        result, run = partial_interface_fixture(lost_public_response=True)
        self.assertEqual(len(result["detail"]["public_events"]), 1)
        finding = audit.audit_fixture_outcome(result, run)
        self.assertEqual(finding["accepted_calls"], 2)
        self.assertEqual(run["counts"]["accepted_calls"], 2)
        self.assertEqual(result["modeled_full_virtual_us"], 5_000_000)

    def test_actual_accepted_event_cannot_also_disappear_from_evaluator_log(self):
        result, run = partial_interface_fixture(lost_public_response=True)
        result["environment_log"].pop()
        result["modeled_full_virtual_us"] = 0
        with self.assertRaises(ValueError):
            audit.audit_fixture_outcome(result, run)

    def test_restored_fixture_prefix_is_not_charged_as_new_calls(self):
        result, run = partial_interface_fixture(resumed=True)
        finding = audit.audit_fixture_outcome(result, run)
        self.assertEqual(len(result["environment_log"]), 3)
        self.assertEqual((finding["accepted_calls"], finding["prefix_events_not_recounted"]), (1, 2))
        self.assertEqual(run["counts"]["business_calls"], 1)

    def test_restored_fixture_prefix_cost_mismatch_is_rejected(self):
        result, run = partial_interface_fixture(resumed=True)
        run["start"]["metadata"]["prefix_virtual_us"] = 0
        with self.assertRaises(ValueError):
            audit.audit_fixture_outcome(result, run)

    def test_false_or_invalid_checks_cannot_manufacture_success(self):
        for checks in ({"expected": False}, {"expected": 1}, {}):
            result, run = partial_interface_fixture()
            result["checks"] = checks
            with self.subTest(checks=checks), self.assertRaises(ValueError):
                audit.audit_fixture_outcome(result, run)

    def test_fixture_assertion_failure_can_be_recorded_honestly(self):
        result, run = partial_interface_fixture()
        result["checks"]["expected_partial_state"] = False
        result["success"] = run["finish"]["success"] = False
        finding = audit.audit_fixture_outcome(result, run)
        self.assertFalse(finding["assertions_passed"])
        self.assertFalse(finding["physical_exit_observed"])

    def test_fixture_success_must_match_its_settled_run(self):
        result, run = partial_interface_fixture()
        run["finish"]["success"] = False
        with self.assertRaises(ValueError):
            audit.audit_fixture_outcome(result, run)


class CampaignStatusWithoutFileIO(unittest.TestCase):
    """Mock the auditor's readers, not its counting/validation functions."""
    def setUp(self):
        self.result, _, self.rows = full_fixture()
        self.status = dict(business_calls=4, accepted_calls=4, entered=1,
            full_runs=1, suffix_runs=0, fixture_runs=0, executions_started=1,
            executions_completed=1, failed_runs=0, unknown_cost_runs=0,
            rejected_calls=0, unknown_cost_calls=0, current_run=None,
            reserved_calls=0, network_training_runs=0,
            limits=dict(business_calls=100, executions=10))
        self.impl = Path("/__synthetic_no_files__/implementation")
        self.stage = Path("/__synthetic_no_files__/stage")
        self.outcome_paths = [self.stage / "runs/example.json.gz"]

    def invoke(self):
        def read(path):
            path = Path(path)
            if path == self.impl / "execution_status.json":
                return deepcopy(self.status)
            if path in self.outcome_paths:
                return deepcopy(self.result)
            raise AssertionError("Unexpected synthetic read: " + str(path))

        payload = "\n".join(json.dumps(row) for row in self.rows)
        with patch.object(audit, "read_json", side_effect=read), \
                patch.object(audit, "sha256", return_value="synthetic-source-hash"), \
                patch.object(Path, "read_text", return_value=payload), \
                patch.object(Path, "glob", return_value=self.outcome_paths):
            return audit.audit(self.impl, self.stage)

    def test_full_campaign_and_one_saved_outcome_are_consistent(self):
        result = self.invoke()
        self.assertEqual(result["outcomes_checked"], 1)
        self.assertEqual(result["counts"]["business_calls"], 4)
        self.assertTrue(result["not_a_g0_acceptance_by_itself"])

    def test_prior_stage_execution_is_still_counted_without_current_stage_outcome(self):
        prior = deepcopy(self.rows)
        for row in prior:
            row["run_id"] = "prior-stage-paid-run"
        current = deepcopy(self.rows)
        for row in current:
            if "sequence" in row:
                row["sequence"] += 4
        self.rows = prior + current
        self.status.update(business_calls=8, accepted_calls=8, entered=2,
                           full_runs=2, executions_started=2, executions_completed=2)
        result = self.invoke()
        self.assertEqual(result["counts"]["business_calls"], 8)
        self.assertEqual(result["counts"]["executions_completed"], 2)
        self.assertEqual(result["outcomes_checked"], 1)
        self.assertEqual(result["journal_run_ids_without_outcome_in_this_stage"], ["prior-stage-paid-run"])

    def test_prior_full_plus_current_suffix_count_only_new_suffix_attempts(self):
        prior = deepcopy(self.rows)
        for row in prior:
            row["run_id"] = "prior-stage-full"
        self.result, _, current = full_fixture(suffix=True)
        for row in current:
            if "sequence" in row:
                row["sequence"] += 4
        self.rows = prior + current
        self.status.update(business_calls=6, accepted_calls=6, entered=1,
                           full_runs=1, suffix_runs=1, executions_started=2, executions_completed=2)
        result = self.invoke()
        self.assertEqual(result["counts"]["business_calls"], 6)  # Four prior + two new, not eight.
        self.assertEqual(result["outcomes"][0]["accepted_calls"], 2)
        self.assertEqual(result["outcomes"][0]["prefix_events_not_recounted"], 2)
        self.assertEqual(result["journal_run_ids_without_outcome_in_this_stage"], ["prior-stage-full"])

    def test_in_flight_journal_cannot_be_accepted_as_final(self):
        self.rows = self.rows[:-2]  # Keep the pending exit call_start, no result/finish.
        with self.assertRaises(ValueError):
            self.invoke()

    def test_duplicate_outcome_identity_is_rejected(self):
        self.outcome_paths.append(self.stage / "runs/duplicate.json.gz")
        with self.assertRaises(ValueError):
            self.invoke()

    def test_outcome_unknown_to_campaign_is_rejected(self):
        self.result["run_id"] = "not-in-journal"
        with self.assertRaises(ValueError):
            self.invoke()

    def test_status_counter_mismatch_is_rejected(self):
        self.status["accepted_calls"] += 1
        with self.assertRaises(ValueError):
            self.invoke()

    def test_missing_required_zero_count_is_not_invented(self):
        del self.status["fixture_runs"]
        with self.assertRaises(ValueError):
            self.invoke()

    def test_pending_reservation_is_not_final(self):
        self.status["reserved_calls"] = 1
        with self.assertRaises(ValueError):
            self.invoke()

    def test_no_outcomes_is_not_success(self):
        self.outcome_paths = []
        with self.assertRaises(ValueError):
            self.invoke()

    def test_training_or_exceeded_execution_budget_rejected(self):
        for field in ("training", "calls", "executions"):
            status = deepcopy(self.status)
            if field == "training":
                self.status["network_training_runs"] = 1
            elif field == "calls":
                self.status["limits"]["business_calls"] = 3
            else:
                self.status["limits"]["executions"] = 0
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.invoke()
            self.status = status


class ReviewedQ3MachineCounter(unittest.TestCase):
    @staticmethod
    def controller(cpu=0.02, measures=12):
        return {"@": "dict", "v": [["counters", {"@": "dict", "v": [
            ["a1_cover_cpu_s", {"@": "float", "v": cpu.hex()}],
            ["measure", measures]]}], ["position", {"@": "tuple", "v": [0, 0]}]]}

    def test_only_latest_q3_cpu_value_is_excluded_without_mutating_sources(self):
        left, right = self.controller(), self.controller(0.03)
        before = deepcopy(left)
        self.assertNotEqual(audit.comparable_controller(left), audit.comparable_controller(right))
        self.assertEqual(audit.comparable_controller(left, latest_q3=True),
                         audit.comparable_controller(right, latest_q3=True))
        self.assertEqual(left, before)

    def test_task_counter_and_missing_cpu_field_are_not_ignored(self):
        left, right = self.controller(), self.controller(0.03, measures=13)
        self.assertNotEqual(audit.comparable_controller(left, latest_q3=True),
                            audit.comparable_controller(right, latest_q3=True))
        del right["v"][0][1]["v"][0]
        self.assertNotEqual(audit.comparable_controller(left, latest_q3=True),
                            audit.comparable_controller(right, latest_q3=True))

    def test_cpu_value_must_be_finite_nonnegative_float(self):
        for value in (-0.01, float("inf"), float("nan")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                audit.comparable_controller(self.controller(value), latest_q3=True)


class G0PairIdentityWithoutFileIO(unittest.TestCase):
    """Synthetic registered pairs test identity, not solver effectiveness."""
    def setUp(self):
        self.impl = Path("/__synthetic_no_files__/repo/experiments/example/RL/implementation")
        self.stage = self.impl / "results/g0_final"
        self.probes = [dict(world_sha256=f"world-{i}", phase="g0", mode=3 if i < 24 else 4,
                            index=i % 24) for i in range(48)]
        self.index = dict(schema="bc-rpi-g0-run-index-v1", runs=[])
        self.runs, self.results = {}, {}
        for world in self.probes:
            families = [("c7_equivalence", ("original_c7", "teacher0"))]
            if world["mode"] == 3 and world["index"] < 12:
                families.append(("latest_q3_passthrough", ("latest_q3_direct", "latest_q3_passthrough")))
            for family, policies in families:
                for policy in policies:
                    run_id = f"{world['world_sha256']}-{policy}"
                    path = f"results/g0_v1/runs/{run_id}.json.gz"
                    self.index["runs"].append(dict(run_id=run_id, world_sha256=world["world_sha256"],
                        mode=world["mode"], policy=policy, family=family, path=path))
                    self.runs[run_id] = dict(start=dict(run_id=run_id, kind="full", metadata=dict(
                        world_sha256=world["world_sha256"], mode=world["mode"], policy=policy)))
                    self.results[self.impl / path] = dict(run_id=run_id, kind="full", success=True,
                        environment_log=[], modeled_full_virtual_us=0, private_terminal_sources={},
                        episode=dict(controller_final=ReviewedQ3MachineCounter.controller(),
                            controller_recoveries=[], fallback_reason=None))

    def invoke(self):
        def read(path):
            path = Path(path)
            if path == self.stage / "index.json":
                return deepcopy(self.index)
            if path == self.impl / "evaluator/probes_v1.json":
                return dict(worlds=deepcopy(self.probes))
            if path == self.impl / "execution_registration.json":
                return dict(world_registry_sha256="synthetic-probe-hash")
            if path in self.results:
                return deepcopy(self.results[path])
            raise AssertionError("Unexpected synthetic pair read: " + str(path))
        with patch.object(audit, "read_json", side_effect=read), \
                patch.object(audit, "sha256", return_value="synthetic-probe-hash"):
            return audit.audit_g0_pairs(self.impl, self.stage, self.runs)

    def test_all_48_c7_and_12_q3_registered_pairs_are_aligned(self):
        result = self.invoke()
        self.assertEqual(len(result["pairs"]), 60)
        self.assertEqual((result["paired_c7_worlds"], result["paired_latest_q3_worlds"]), (48, 12))

    def test_index_policy_must_match_actual_journal_policy(self):
        row = self.index["runs"][0]
        self.runs[row["run_id"]]["start"]["metadata"]["policy"] = "unregistered-policy"
        with self.assertRaises(ValueError):
            self.invoke()

    def test_equivalence_pair_requires_actual_full_runs_not_resumed_suffixes(self):
        row = self.index["runs"][0]
        for target in (self.runs[row["run_id"]]["start"], self.results[self.impl / row["path"]]):
            target["kind"] = "suffix"
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.invoke()
            target["kind"] = "full"

    def test_index_world_must_match_actual_journal_world(self):
        row = self.index["runs"][0]
        self.runs[row["run_id"]]["start"]["metadata"]["world_sha256"] = "wrong-world"
        with self.assertRaises(ValueError):
            self.invoke()

    def test_missing_registered_pair_member_rejected(self):
        self.index["runs"].pop()
        with self.assertRaises(ValueError):
            self.invoke()

    def test_duplicate_run_in_index_rejected(self):
        self.index["runs"].append(deepcopy(self.index["runs"][0]))
        with self.assertRaises(ValueError):
            self.invoke()

    def test_swapped_outcome_run_identity_rejected(self):
        row = self.index["runs"][0]
        self.results[self.impl / row["path"]]["run_id"] = "not-that-run"
        with self.assertRaises(ValueError):
            self.invoke()

    def test_controller_task_difference_not_ignored_for_latest_q3(self):
        row = next(r for r in self.index["runs"] if r["policy"] == "latest_q3_passthrough")
        self.results[self.impl / row["path"]]["episode"]["controller_final"] = \
            ReviewedQ3MachineCounter.controller(measures=13)
        with self.assertRaises(ValueError):
            self.invoke()

    def test_teacher_fallback_cannot_pass_equivalence(self):
        row = next(r for r in self.index["runs"] if r["policy"] == "teacher0")
        self.results[self.impl / row["path"]]["episode"]["fallback_reason"] = "synthetic-failure"
        with self.assertRaises(ValueError):
            self.invoke()


class G0HistoricalArchivesWithoutFileIO(unittest.TestCase):
    """Real in-memory ZIPs, synthetic bytes; nothing read from or written to disk."""
    def setUp(self):
        self.impl = Path("/__synthetic_no_files__/repo/experiments/example/RL/implementation")
        self.repo = self.impl.parents[3]
        self.stage = self.impl / "results/g0_final"
        self.name = "g0_historical"
        self.archive_path = self.impl / f"results/{self.name}/sources.zip"
        self.freeze_path = self.impl / f"results/{self.name}/source_freeze.json"
        self.member = "experiments/example/RL/implementation/deploy/policy.py"
        self.source_bytes = b"# synthetic archived source; never executed\n"
        self.source_hash = hashlib.sha256(self.source_bytes).hexdigest()
        self.freeze = dict(deploy_implementation_sha256="synthetic-deploy-hash",
                           files={self.member: self.source_hash})
        self.embedded = dict(files=deepcopy(self.freeze["files"]),
                            provenance="synthetic-before-execution", reconstructed_members=[])
        self.entry = dict(stage=self.name, sha256="computed-in-invoke", members=1,
                          provenance=self.embedded["provenance"], reconstructed_members=[])
        self.registry = dict(archives=[self.entry], deploy_implementation_sha256="synthetic-deploy-hash")
        self.index = dict(runs=[dict(path=f"results/{self.name}/runs/example.json.gz")])
        self.stored_bytes = self.source_bytes
        self.current_hash = self.source_hash
        self.extra_member = None

    def invoke(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr(self.member, self.stored_bytes)
            archive.writestr("_SOURCE_ARCHIVE_MANIFEST.json", json.dumps(self.embedded))
            if self.extra_member is not None:
                archive.writestr(self.extra_member, b"unexpected")
        archive_bytes = stream.getvalue()
        self.entry["sha256"] = hashlib.sha256(archive_bytes).hexdigest()
        real_zipfile = zipfile.ZipFile

        def open_archive(path):
            self.assertEqual(path, self.archive_path)
            return real_zipfile(io.BytesIO(archive_bytes))

        def read(path):
            values = {self.stage / "source_archives.json": self.registry,
                      self.stage / "index.json": self.index, self.freeze_path: self.freeze}
            return deepcopy(values[Path(path)])

        def digest(path):
            if Path(path) == self.archive_path:
                return hashlib.sha256(archive_bytes).hexdigest()
            self.assertEqual(Path(path), self.repo / self.member)
            return self.current_hash

        with patch.object(audit, "read_json", side_effect=read), \
                patch.object(audit, "sha256", side_effect=digest), \
                patch.object(audit.zipfile, "ZipFile", side_effect=open_archive):
            return audit.audit_g0_archives(self.impl, self.stage)

    def test_historical_archive_bytes_and_current_deployment_are_verified(self):
        findings, sources = self.invoke()
        self.assertEqual(findings[0]["source_members_verified"], 1)
        self.assertIn(self.archive_path, sources)
        self.assertIn(self.freeze_path, sources)

    def test_changed_archived_member_is_rejected_even_with_new_zip_digest(self):
        self.stored_bytes = b"different synthetic source"
        with self.assertRaises(ValueError):
            self.invoke()

    def test_changed_current_deployment_is_rejected(self):
        self.current_hash = "different-current-deployment"
        with self.assertRaises(ValueError):
            self.invoke()

    def test_evaluator_and_test_files_are_not_blanket_exempt_from_current_hash_checks(self):
        for role in ("evaluator/runtime.py", "tests/test_g0.py"):
            self.member = "experiments/example/RL/implementation/" + role
            self.freeze["files"] = {self.member: self.source_hash}
            self.embedded["files"] = deepcopy(self.freeze["files"])
            self.current_hash = "different-current-source"
            with self.subTest(role=role), self.assertRaises(ValueError):
                self.invoke()

    def test_embedded_manifest_provenance_must_match_registry(self):
        self.embedded["provenance"] = "different-provenance"
        with self.assertRaises(ValueError):
            self.invoke()

    def test_unexpected_zip_member_rejected(self):
        self.extra_member = "unregistered.py"
        with self.assertRaises(ValueError):
            self.invoke()

    def test_historical_stage_deployment_hash_must_match_campaign(self):
        self.freeze["deploy_implementation_sha256"] = "different-deploy"
        with self.assertRaises(ValueError):
            self.invoke()

    def test_outcome_stage_without_verified_archive_rejected(self):
        self.index["runs"][0]["path"] = "results/unarchived/runs/example.json.gz"
        with self.assertRaises(ValueError):
            self.invoke()

    def test_normalized_outcome_stage_cannot_borrow_another_stage_archive(self):
        self.index["runs"][0]["path"] = f"results/{self.name}/../unarchived/runs/example.json.gz"
        with self.assertRaises(ValueError):
            self.invoke()

    def invoke_two_historical_orchestration_versions(self, *, current_version=2, damage_old=False):
        member = "experiments/example/RL/implementation/evaluator/g0.py"
        versions = [b"# synthetic historical version 1\n", b"# synthetic historical version 2\n"]
        digests = [hashlib.sha256(payload).hexdigest() for payload in versions]
        real_zipfile = zipfile.ZipFile
        reads, archives, entries, expected_sources = {}, {}, [], {}
        for ordinal, payload in enumerate(versions):
            name = f"g0_version{ordinal + 1}"
            stage_dir = self.impl / "results" / name
            freeze = dict(files={member: digests[ordinal]},
                          deploy_implementation_sha256="same-deployment")
            embedded = dict(files=freeze["files"], provenance="synthetic", reconstructed_members=[])
            stream = io.BytesIO()
            with real_zipfile(stream, "w") as archive:
                archive.writestr(member, b"damaged-old-copy" if damage_old and ordinal == 0 else payload)
                archive.writestr("_SOURCE_ARCHIVE_MANIFEST.json", json.dumps(embedded))
            archive_path = stage_dir / "sources.zip"
            archives[archive_path] = stream.getvalue()
            expected_sources[archive_path] = hashlib.sha256(archives[archive_path]).hexdigest()
            reads[stage_dir / "source_freeze.json"] = freeze
            entries.append(dict(stage=name, sha256=expected_sources[archive_path], members=1,
                                provenance="synthetic", reconstructed_members=[]))
        reads[self.stage / "source_archives.json"] = dict(archives=entries,
            deploy_implementation_sha256="same-deployment")
        reads[self.stage / "index.json"] = dict(runs=[dict(path=f"results/{entry['stage']}/runs/example.json.gz")
                                                       for entry in entries])
        expected_sources[self.repo / member] = digests[current_version - 1]
        with patch.object(audit, "read_json", side_effect=lambda path: deepcopy(reads[Path(path)])), \
                patch.object(audit, "sha256", side_effect=lambda path: expected_sources[Path(path)]), \
                patch.object(audit.zipfile, "ZipFile", side_effect=lambda path: real_zipfile(io.BytesIO(archives[Path(path)]))):
            return audit.audit_g0_archives(self.impl, self.stage)

    def test_newer_frozen_orchestration_replaces_current_expectation_without_erasing_history(self):
        findings, _ = self.invoke_two_historical_orchestration_versions()
        self.assertEqual([row["stage"] for row in findings], ["g0_version1", "g0_version2"])

    def test_current_orchestration_must_match_last_stage_not_any_historical_version(self):
        with self.assertRaises(ValueError):
            self.invoke_two_historical_orchestration_versions(current_version=1)

    def test_replaced_historical_orchestration_bytes_remain_individually_verified(self):
        with self.assertRaises(ValueError):
            self.invoke_two_historical_orchestration_versions(damage_old=True)


if __name__ == "__main__":
    unittest.main()
