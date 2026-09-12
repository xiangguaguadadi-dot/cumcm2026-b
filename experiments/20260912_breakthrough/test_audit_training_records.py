"""Pure synthetic business-record checks; no environment, trainer or filesystem I/O."""
from __future__ import annotations

from copy import deepcopy
import gzip
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import audit_training_records as audit
from test_audit_rl_execution import full_fixture


class TrainingBusinessRecordsWithoutFileIO(unittest.TestCase):
    def setUp(self):
        self.campaign = Path("/__synthetic_no_files__/training_round")
        self.ledger = self.campaign / "ledger"
        self.result, _, self.rows = full_fixture()
        self.rows[0]["metadata"]["stage"] = "labels"
        self.status = dict(business_calls=4, accepted_calls=4, entered=1,
            full_runs=1, suffix_runs=0, fixture_runs=0, executions_started=1,
            executions_completed=1, failed_runs=0, unknown_cost_runs=0,
            rejected_calls=0, unknown_cost_calls=0, current_run=None,
            reserved_calls=0, network_training_runs=3,
            phase_calls=dict(labels=4, calibration=0, development=0, compatibility=0),
            phase_executions=dict(labels=1, calibration=0, development=0, compatibility=0),
            limits=dict(business_calls=100_000, executions=10, run_call_reserve=15_846,
                        phase_calls=dict(labels=50_000, calibration=20_000, development=20_000, compatibility=20_000),
                        compatibility_executions=24))
        self.outcome_paths = [self.campaign / "results/runs/synthetic.json.gz"]
        self.outcomes = {self.outcome_paths[0]: self.result}
        self.compressed = False
        self.change_during_read = False

    def invoke(self, *, outcome_root=None):
        payload = "\n".join(json.dumps(row) for row in self.rows).encode()
        status_bytes = json.dumps(self.status).encode()
        status_reads = 0

        def read_bytes(path):
            nonlocal status_reads
            if path == self.ledger / "execution_status.json":
                status_reads += 1
                return status_bytes + b" " if self.change_during_read and status_reads > 1 else status_bytes
            if path == self.ledger / "execution_calls.jsonl" and not self.compressed:
                return payload
            if path == self.ledger / "execution_calls.jsonl.gz" and self.compressed:
                return gzip.compress(payload, mtime=0)
            raise AssertionError("Unexpected synthetic byte read: " + str(path))

        def exists(path):
            self.assertEqual(path, self.ledger / "execution_calls.jsonl")
            return not self.compressed

        with patch.object(Path, "read_bytes", autospec=True, side_effect=read_bytes), \
                patch.object(Path, "exists", autospec=True, side_effect=exists), \
                patch.object(Path, "rglob", return_value=self.outcome_paths), \
                patch.object(audit, "read_json", side_effect=lambda path: deepcopy(self.outcomes[Path(path)])), \
                patch.object(audit, "sha256", return_value="synthetic-hash"):
            return audit.audit_campaign(self.campaign, self.ledger, outcome_root=outcome_root)

    def test_nonzero_training_counter_is_allowed_but_not_proof_of_updates(self):
        report = self.invoke()
        self.assertEqual(report["declared_network_training_runs"], 3)
        self.assertFalse(report["training_counter_verified_against_updates"])
        self.assertEqual(report["actual_policy_executions_by_this_auditor"], 0)
        self.assertEqual(report["outcomes_checked"], 1)
        self.assertEqual(report["counts"]["business_calls"], 4)

    def test_gzip_ledger_uses_same_real_call_denominator(self):
        self.compressed = True
        report = self.invoke()
        self.assertEqual(report["counts"]["business_calls"], 4)

    def test_status_counter_disagreement_rejected(self):
        self.status["accepted_calls"] = 3
        with self.assertRaises(ValueError):
            self.invoke()

    def test_required_zero_status_counter_cannot_be_missing(self):
        del self.status["fixture_runs"]
        with self.assertRaises(ValueError):
            self.invoke()

    def test_status_count_boolean_is_not_an_integer_count(self):
        self.status["full_runs"] = True
        with self.assertRaises(ValueError):
            self.invoke()

    def test_invalid_training_counter_rejected(self):
        for value in (-1, True, 3.0):
            self.status["network_training_runs"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.invoke()

    def test_boolean_partition_and_stage_counts_are_not_valid_integer_counters(self):
        original = deepcopy(self.status)
        for field in ("rejected_calls", "unknown_cost_calls", "phase_calls", "phase_executions"):
            self.status = deepcopy(original)
            if field in ("phase_calls", "phase_executions"):
                self.status[field]["calibration"] = False  # Would equal the genuine zero numerically.
            else:
                self.status[field] = False
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.invoke()

    def test_pending_reservation_rejected(self):
        self.status["reserved_calls"] = 1
        with self.assertRaises(ValueError):
            self.invoke()

    def test_unfinished_actual_call_cannot_be_declared_settled(self):
        self.rows = self.rows[:-2]
        with self.assertRaises(ValueError):
            self.invoke()

    def test_exceeded_global_call_budget_rejected(self):
        self.status["limits"]["business_calls"] = 3
        with self.assertRaises(ValueError):
            self.invoke()

    def test_exceeded_global_execution_budget_rejected(self):
        self.status["limits"]["executions"] = 0
        with self.assertRaises(ValueError):
            self.invoke()

    def test_paid_execution_without_saved_outcome_rejected(self):
        self.outcome_paths = []
        with self.assertRaises(ValueError):
            self.invoke()

    def test_duplicate_saved_outcome_for_one_execution_rejected(self):
        duplicate = self.campaign / "results/runs/duplicate.json.gz"
        self.outcome_paths.append(duplicate)
        self.outcomes[duplicate] = deepcopy(self.result)
        with self.assertRaises(ValueError):
            self.invoke()

    def test_outcome_with_no_actual_execution_rejected(self):
        self.result["run_id"] = "invented-run"
        with self.assertRaises(ValueError):
            self.invoke()

    def test_non_outcome_artifacts_cannot_stand_in_for_paid_outcomes(self):
        self.result["schema"] = "synthetic-unrelated-feature-bundle"
        with self.assertRaises(ValueError):
            self.invoke()

    def test_concurrent_ledger_change_rejected(self):
        self.change_during_read = True
        with self.assertRaises(ValueError):
            self.invoke()

    def test_outcome_root_cannot_escape_the_new_campaign(self):
        with self.assertRaises(ValueError):
            self.invoke(outcome_root=Path("/__synthetic_no_files__/old_campaign"))

    def test_stages_partition_actual_calls_without_adding_training_updates(self):
        second = deepcopy(self.rows)
        for row in second:
            row["run_id"] = "calibration-run"
            if "sequence" in row:
                row["sequence"] += 4
        second[0]["metadata"]["stage"] = "calibration"
        self.rows += second
        self.status.update(business_calls=8, accepted_calls=8, entered=2, full_runs=2,
                           executions_started=2, executions_completed=2)
        self.status["phase_calls"]["calibration"] = 4
        self.status["phase_executions"]["calibration"] = 1
        second_path = self.campaign / "results/runs/calibration.json.gz"
        self.outcome_paths.append(second_path)
        second_result = deepcopy(self.result)
        second_result["run_id"] = "calibration-run"
        self.outcomes[second_path] = second_result
        report = self.invoke()
        self.assertEqual(report["per_recorded_stage"]["labels"]["business_calls"], 4)
        self.assertEqual(report["per_recorded_stage"]["calibration"]["business_calls"], 4)
        self.assertEqual(report["counts"]["business_calls"], 8)
        self.assertEqual(report["declared_network_training_runs"], 3)

    def test_stage_without_full_tail_reserve_rejected_even_if_final_cost_is_small(self):
        self.status["limits"]["phase_calls"]["labels"] = 15_845
        with self.assertRaises(ValueError):
            self.invoke()

    def test_total_without_full_tail_reserve_rejected_even_if_final_cost_is_small(self):
        self.status["limits"]["business_calls"] = 15_845
        with self.assertRaises(ValueError):
            self.invoke()

    def test_stage_record_count_must_match_actual_journal(self):
        self.status["phase_calls"]["labels"] = 3
        with self.assertRaises(ValueError):
            self.invoke()

    def test_stage_outside_registered_budget_rejected(self):
        self.rows[0]["metadata"]["stage"] = "unregistered-experiment"
        with self.assertRaises(ValueError):
            self.invoke()

    def test_unknown_acceptance_forbids_later_calls_even_in_same_run(self):
        # Direct reservation-audit fixture; audit_journal separately checks settlement.
        rows = [dict(event="run_start", metadata=dict(stage="labels")),
                dict(event="call_start"), dict(event="call_exception", acceptance="unknown"),
                dict(event="call_start")]
        with self.assertRaises(ValueError):
            audit.audit_reservations(self.status, rows)

    def test_compatibility_execution_cap_cannot_be_bypassed_with_zero_call_runs(self):
        rows = [dict(event="run_start", metadata=dict(stage="compatibility")) for _ in range(25)]
        status = deepcopy(self.status)
        status["limits"]["executions"] = 100
        with self.assertRaises(ValueError):
            audit.audit_reservations(status, rows)


if __name__ == "__main__":
    unittest.main()
