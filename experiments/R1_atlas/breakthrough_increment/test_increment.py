"""Synthetic aggregation tests only. Never instantiate a solver or environment."""
import unittest
from build_increment import EvidenceError, equivalent, execution_journal_counts, row_effects, sha, verify_append


def row(case_id, total=100., n=10, cleared=10, complete=True, error=None):
    return dict(case_id=case_id, mode=4, group="synthetic", source_count=n,
                cleared_count=cleared, total_virtual_time_s=total,
                average_clear_time_s=total / cleared if cleared else None,
                complete=complete, exit_reason="user_exit", error=error)


class Aggregation(unittest.TestCase):
    def test_per_case_mean_not_pooled_ratio(self):
        result = row_effects([row("a"), row("b", total=400, n=20, cleared=20)], suite="synthetic")[0]
        self.assertEqual(result["mean_s_per_source"], 15)
        self.assertEqual(result["source_count"], 30)

    def test_failed_rows_are_not_filtered(self):
        result = row_effects([row("a"), row("b", cleared=0, complete=False, error="failed")], suite="synthetic")[0]
        self.assertIsNone(result["mean_s_per_source"])
        self.assertEqual(result["failed_case_ids"], ["b"])
        self.assertEqual(result["cases"], 2)

    def test_duplicate_id_rejected(self):
        with self.assertRaises(EvidenceError):
            row_effects([row("a"), row("a")], suite="synthetic")

    def test_formula_rejected(self):
        record = row("a")
        record["average_clear_time_s"] += 1
        with self.assertRaises(EvidenceError):
            row_effects([record], suite="synthetic")

    def test_reference_alignment(self):
        with self.assertRaises(EvidenceError):
            row_effects([row("a")], suite="synthetic", reference=[row("b")])

    def test_reference_denominator_alignment(self):
        with self.assertRaises(EvidenceError):
            row_effects([row("a")], suite="synthetic", reference=[row("a", n=11)])

    def test_zero_denominator_is_null(self):
        record = row("a", cleared=0, complete=False)
        record["average_clear_time_s"] = 0
        with self.assertRaises(EvidenceError):
            row_effects([record], suite="synthetic")

    def test_failure_prevents_paired_ranking(self):
        result = row_effects([row("a")], suite="synthetic", reference=[row("a", complete=False)])[0]
        self.assertFalse(result["comparison_valid"])
        self.assertNotIn("delta_s_per_source", result)

    def test_missing_does_not_become_zero(self):
        record = row("a", cleared=0, complete=False)
        record["cleared_count"] = None
        result = row_effects([record], suite="synthetic")[0]
        self.assertIsNone(result["cleared_count"])
        self.assertEqual(result["unknown_clearance_rows"], 1)
        self.assertFalse(equivalent(None, 0))

    def test_actual_parent_and_component_both_verified(self):
        verify_append(b"parent", b"parent\ncomponent", sha(b"component"))
        with self.assertRaises(EvidenceError):
            verify_append(b"other", b"parent\ncomponent", sha(b"component"))
        with self.assertRaises(EvidenceError):
            verify_append(b"parent", b"parent\nchanged", sha(b"component"))

    def test_journal_unknown_call_not_zero_or_failure(self):
        counts = execution_journal_counts([
            dict(event="run_start", run_id="a"),
            dict(event="call_start", run_id="a", sequence=0),
        ])
        self.assertEqual(counts["business_calls"], 1)
        self.assertEqual(counts["unresolved_calls"], 1)
        self.assertEqual(counts["accepted_calls"], 0)
        self.assertEqual(counts["failed_calls"], 0)
        self.assertEqual(counts["unfinished_runs"], 1)

    def test_journal_success_rejection_and_exception(self):
        records = [dict(event="run_start", run_id="a")]
        for sequence, event, accepted in ((0, "call_response", True), (1, "call_response", False), (2, "call_exception", None)):
            records.extend([dict(event="call_start", run_id="a", sequence=sequence),
                            dict(event=event, run_id="a", sequence=sequence, accepted=accepted)])
        records.append(dict(event="run_finish", run_id="a"))
        counts = execution_journal_counts(records)
        self.assertEqual((counts["business_calls"], counts["accepted_calls"], counts["failed_calls"]), (3, 1, 2))
        self.assertEqual(counts["unresolved_calls"], 0)
        self.assertEqual(counts["executions_completed"], 1)

    def test_journal_duplicate_or_misaligned_responses_rejected(self):
        prefix = [dict(event="run_start", run_id="a"), dict(event="call_start", run_id="a", sequence=0)]
        response = dict(event="call_response", run_id="a", sequence=0, accepted=True)
        with self.assertRaises(EvidenceError):
            execution_journal_counts(prefix + [response, response])
        with self.assertRaises(EvidenceError):
            execution_journal_counts(prefix + [dict(response, run_id="b")])

    def test_journal_sequence_gap_rejected(self):
        with self.assertRaises(EvidenceError):
            execution_journal_counts([dict(event="run_start", run_id="a"),
                                      dict(event="call_start", run_id="a", sequence=1)])

    def test_journal_unsettled_finish_rejected(self):
        with self.assertRaises(EvidenceError):
            execution_journal_counts([dict(event="run_start", run_id="a"),
                                      dict(event="call_start", run_id="a", sequence=0),
                                      dict(event="run_finish", run_id="a")])

    def test_journal_unknown_event_rejected(self):
        with self.assertRaises(EvidenceError):
            execution_journal_counts([dict(event="unknown", run_id="a")])


if __name__ == "__main__":
    unittest.main()
