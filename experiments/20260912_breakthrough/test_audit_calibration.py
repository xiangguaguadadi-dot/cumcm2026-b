"""Independent synthetic argmax and empirical world-margin audit tests.

No calibration artifacts, neural worker, environment, model or trainer is read
or run. These test mathematical saved-record contracts, not calibration data.
"""
from copy import deepcopy
import math
import struct
import unittest

import audit_calibration as audit


IDS = ["a" * 64, "b" * 64, "c" * 64]


def exact_float32(value):
    return struct.unpack("!f", struct.pack("!f", value))[0]


def state(predicted=0., realized=0., *, teacher_selected=False):
    return dict(candidate_id=IDS[1] if teacher_selected else IDS[0], teacher_id=IDS[1],
        predicted_gain=predicted, realized_gain=realized,
        optimistic_residual=predicted-realized)


def world(index, residuals):
    # A zero predicted gain with a nonreference hash winner is a legal score
    # tie; positive/negative realized gain creates the prescribed residual.
    states = [state(0., -value) for value in residuals]
    return dict(world_id=f"synthetic-world-{index:02d}", status="complete", states=states,
        world_max_optimistic_residual=max(residuals))


def fixture():
    rows = [world(i, [i/1024]) for i in range(24)]
    return rows, [row["world_id"] for row in rows]


class Float32ArgmaxTests(unittest.TestCase):
    def test_teacher_reference_is_not_assumed_to_be_first(self):
        selected, gain, gains = audit.argmax(IDS, IDS[1], [.25, 0., .125])
        self.assertEqual(selected, IDS[0])
        self.assertEqual(gain, .25)
        self.assertEqual(gains, [.25, 0., .125])

    def test_identical_best_scores_tie_by_canonical_hash(self):
        scores = [exact_float32(.1), exact_float32(.1), exact_float32(.09)]
        selected, gain, gains = audit.argmax(IDS, IDS[2], scores)
        self.assertEqual(selected, IDS[0])
        self.assertEqual(gain, exact_float32(scores[0]-scores[2]))
        self.assertEqual(gains[0], gains[1])
        self.assertEqual(gains[2], 0.)

    def test_float32_difference_tie_is_resolved_after_subtraction_rounding(self):
        # Raw B > A, but both gains round to 2**24. Ranking raw float64
        # differences instead would wrongly choose B.
        selected, gain, gains = audit.argmax(IDS, IDS[2], [.25, .5, -16777216.])
        self.assertEqual(gains, [16777216., 16777216., 0.])
        self.assertEqual((selected, gain), (IDS[0], 16777216.))

    def test_zero_gain_hash_tie_does_not_force_teacher_during_argmax(self):
        selected, gain, gains = audit.argmax(IDS, IDS[2], [0., 0., 0.])
        self.assertEqual((selected, gain), (IDS[0], 0.))
        self.assertEqual(gains, [0., 0., 0.])

    def test_teacher_only_state_has_exact_zero_gain(self):
        self.assertEqual(audit.argmax([IDS[1]], IDS[1], [.125]), (IDS[1], 0., [0.]))

    def test_teacher_best_has_zero_gain_even_when_other_scores_are_negative(self):
        self.assertEqual(audit.argmax(IDS, IDS[0], [1., .5, -.5]),
                         (IDS[0], 0., [0., -.5, -1.5]))

    def test_common_exactly_representable_score_offset_cancels(self):
        first = audit.argmax(IDS, IDS[1], [.5, .25, -.25])
        second = audit.argmax(IDS, IDS[1], [8.5, 8.25, 7.75])
        self.assertEqual(first, second)

    def test_invalid_retained_set_and_length_mismatch_rejected(self):
        for ids, teacher, scores in (([], IDS[0], []), (IDS[::-1], IDS[0], [0., 0., 0.]),
                ([IDS[0], IDS[0]], IDS[0], [0., 0.]), (IDS, "d"*64, [0., 0., 0.]),
                (IDS, IDS[0], [0., 0.]), ([f"{i:064x}" for i in range(10)], "0"*64, [0.]*10)):
            with self.subTest(ids=ids, teacher=teacher), self.assertRaises(ValueError):
                audit.argmax(ids, teacher, scores)

    def test_nonfinite_boolean_and_non_float32_score_rejected(self):
        for bad in (float("nan"), float("inf"), -float("inf"), True, .1):
            with self.subTest(score=bad), self.assertRaises(ValueError):
                audit.argmax(IDS, IDS[0], [0., bad, 0.])

    def test_score_and_subtracted_gain_overflow_fail_closed(self):
        largest = exact_float32(3.4028234663852886e38)
        for scores in ([0., 1e308, 0.], [-largest, largest, 0.]):
            with self.subTest(scores=scores), self.assertRaises((ValueError, OverflowError)):
                audit.argmax(IDS, IDS[0], scores)

    def test_argmax_does_not_mutate_retained_ids_or_scores(self):
        ids, scores = list(IDS), [0., .25, .125]
        audit.argmax(ids, ids[0], scores)
        self.assertEqual(ids, IDS)
        self.assertEqual(scores, [0., .25, .125])


class WorldEmpiricalMarginTests(unittest.TestCase):
    def test_24_worlds_select_exact_22nd_rank_without_interpolation(self):
        rows, expected = fixture()
        margin, ordered = audit.empirical_margin(rows, expected)
        self.assertEqual(margin, 21/1024)
        self.assertEqual(ordered, [i/1024 for i in range(24)])
        self.assertNotEqual(margin, ordered[-1])

    def test_max_each_world_then_rank_not_pooled_states_or_world_average(self):
        rows = [world(i, [0., i/1024]) for i in range(24)]
        margin, ordered = audit.empirical_margin(rows, [r["world_id"] for r in rows])
        self.assertEqual(margin, 21/1024)
        self.assertEqual(ordered, [i/1024 for i in range(24)])
        pooled = sorted(s["optimistic_residual"] for r in rows for s in r["states"])
        self.assertNotEqual(margin, pooled[math.ceil(.9*len(pooled))-1])
        self.assertNotEqual(margin, (21/1024)/2)

    def test_one_or_two_states_per_world_have_same_world_weight(self):
        rows, expected = fixture()
        for i in range(0, 24, 2):
            rows[i]["states"].append(state(0., 1.))
        margin, ordered = audit.empirical_margin(rows, expected)
        self.assertEqual(margin, 21/1024)
        self.assertEqual(ordered, [i/1024 for i in range(24)])

    def test_world_and_state_order_do_not_change_rank_or_max(self):
        rows = [world(i, [0., i/1024]) for i in range(24)]
        expected = [r["world_id"] for r in rows]
        reference = audit.empirical_margin(rows, expected)
        rows.reverse()
        for row in rows:
            row["states"].reverse()
        self.assertEqual(audit.empirical_margin(rows, expected), reference)

    def test_negative_quantile_clamps_margin_but_preserves_raw_negative_order_statistics(self):
        rows = [world(i, [-(24-i)/1024]) for i in range(24)]
        margin, ordered = audit.empirical_margin(rows, [r["world_id"] for r in rows])
        self.assertEqual(margin, 0.)
        self.assertEqual(ordered[21], -3/1024)
        self.assertTrue(all(value < 0 for value in ordered))

    def test_all_A0_states_are_valid_zero_residual_worlds(self):
        rows, expected = fixture()
        for row in rows:
            row["states"] = [state(teacher_selected=True)]
            row["world_max_optimistic_residual"] = 0.
        self.assertEqual(audit.empirical_margin(rows, expected), (0., [0.]*24))

    def test_A0_cannot_hide_equal_nonzero_predicted_and_realized_gain(self):
        rows, expected = fixture()
        rows[0]["states"] = [state(.25, .25, teacher_selected=True)]
        rows[0]["world_max_optimistic_residual"] = 0.
        with self.assertRaisesRegex(ValueError, "A0"):
            audit.empirical_margin(rows, expected)

    def test_A0_predicted_or_realized_nonzero_is_rejected(self):
        for predicted, realized in ((.125, 0.), (0., .125), (-.125, 0.)):
            rows, expected = fixture()
            rows[0]["states"] = [state(predicted, realized, teacher_selected=True)]
            rows[0]["world_max_optimistic_residual"] = predicted-realized
            with self.subTest(predicted=predicted, realized=realized), self.assertRaisesRegex(ValueError, "A0"):
                audit.empirical_margin(rows, expected)

    def test_real_failure_penalty_residual_is_retained_in_the_world_quantile(self):
        rows, expected = fixture()
        for row in rows[-3:]:
            row["states"] = [state(.125, -100.)]
            row["world_max_optimistic_residual"] = 100.125
        margin, ordered = audit.empirical_margin(rows, expected)
        self.assertEqual(margin, 100.125)
        self.assertEqual(ordered[-3:], [100.125]*3)

    def test_missing_extra_duplicate_or_substituted_world_is_rejected(self):
        for mutation in ("missing", "extra", "duplicate", "substitute"):
            rows, expected = fixture()
            if mutation == "missing":
                rows.pop()
            elif mutation == "extra":
                rows.append(world(24, [0.]))
            elif mutation == "duplicate":
                rows[-1] = deepcopy(rows[0])
            else:
                rows[-1]["world_id"] = "not-registered"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                audit.empirical_margin(rows, expected)

    def test_expected_registry_must_itself_have_24_unique_worlds(self):
        rows, expected = fixture()
        for registry in (expected[:-1], expected+["extra"], expected[:-1]+[expected[0]]):
            with self.subTest(registry=registry), self.assertRaises(ValueError):
                audit.empirical_margin(rows, registry)

    def test_incomplete_world_is_not_dropped_or_treated_as_zero(self):
        rows, expected = fixture()
        rows[0]["status"] = "incomplete_resource"
        with self.assertRaises(ValueError):
            audit.empirical_margin(rows, expected)

    def test_empty_or_more_than_two_sampled_states_rejected(self):
        for count in (0, 3):
            rows, expected = fixture()
            rows[0]["states"] = [state()] * count
            with self.subTest(count=count), self.assertRaises(ValueError):
                audit.empirical_margin(rows, expected)

    def test_nonfinite_or_boolean_predicted_and_realized_gain_rejected(self):
        for key in ("predicted_gain", "realized_gain"):
            for value in (float("nan"), float("inf"), -float("inf"), True):
                rows, expected = fixture()
                rows[0]["states"][0][key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    audit.empirical_margin(rows, expected)

    def test_finite_inputs_with_overflowing_residual_are_rejected(self):
        rows, expected = fixture()
        rows[0]["states"] = [state(1e308, -1e308)]
        rows[0]["world_max_optimistic_residual"] = float("inf")
        with self.assertRaisesRegex(ValueError, "Nonfinite residual"):
            audit.empirical_margin(rows, expected)

    def test_stored_state_residual_is_recomputed_not_trusted(self):
        rows, expected = fixture()
        rows[0]["states"][0]["optimistic_residual"] = .01
        with self.assertRaisesRegex(ValueError, "Stored residual"):
            audit.empirical_margin(rows, expected)

    def test_stored_world_average_cannot_replace_the_world_maximum(self):
        rows, expected = fixture()
        rows[0] = world(0, [0., .25])
        rows[0]["world_max_optimistic_residual"] = .125
        with self.assertRaisesRegex(ValueError, "within-world maximum"):
            audit.empirical_margin(rows, expected)

    def test_nonfinite_stored_residual_or_world_maximum_is_rejected(self):
        for field in ("state", "world"):
            for value in (float("nan"), float("inf"), -float("inf")):
                rows, expected = fixture()
                if field == "state":
                    rows[0]["states"][0]["optimistic_residual"] = value
                else:
                    rows[0]["world_max_optimistic_residual"] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    audit.empirical_margin(rows, expected)

    def test_margin_audit_does_not_mutate_world_rows_or_registry(self):
        rows, expected = fixture()
        original_rows, original_ids = deepcopy(rows), list(expected)
        audit.empirical_margin(rows, expected)
        self.assertEqual(rows, original_rows)
        self.assertEqual(expected, original_ids)


def selected_model_fixture():
    accepted = dict(status="three_real_fits_and_fit_val_selection_verified", results=[])
    models = []
    for seed in audit.SEEDS:
        checkpoints = [dict(epoch=epoch, checkpoint_sha256=f"{seed*epoch:064x}",
                            parameter_sha256=f"{seed*epoch+1:064x}") for epoch in (5, 10, 20)]
        selected = checkpoints[1]
        accepted["results"].append(dict(seed=seed, selected_epoch=10,
            selected_checkpoint_sha256=selected["checkpoint_sha256"], checkpoints=checkpoints))
        models.append(dict(seed=seed, epoch=10, sha256=selected["checkpoint_sha256"],
                           parameter_sha256=selected["parameter_sha256"]))
    return models, accepted


class AuditedSelectedModelBindingTests(unittest.TestCase):
    def test_exact_three_audited_fit_val_winners_are_accepted(self):
        models, accepted = selected_model_fixture()
        audit.verify_selected_models(models, accepted)

    def test_other_genuinely_listed_checkpoint_cannot_replace_fit_val_winner(self):
        models, accepted = selected_model_fixture()
        alternative = accepted["results"][0]["checkpoints"][0]
        models[0].update(epoch=alternative["epoch"], sha256=alternative["checkpoint_sha256"],
                         parameter_sha256=alternative["parameter_sha256"])
        with self.assertRaisesRegex(ValueError, "audited fit_val"):
            audit.verify_selected_models(models, accepted)

    def test_changed_checkpoint_epoch_or_parameter_identity_rejected(self):
        for key, value in (("epoch", 20), ("sha256", "f"*64), ("parameter_sha256", "e"*64)):
            models, accepted = selected_model_fixture()
            models[1][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                audit.verify_selected_models(models, accepted)

    def test_missing_duplicate_reordered_or_unregistered_model_seed_rejected(self):
        for mutation in ("missing", "duplicate", "reorder", "unregistered"):
            models, accepted = selected_model_fixture()
            if mutation == "missing":
                models.pop()
            elif mutation == "duplicate":
                models[-1] = deepcopy(models[0])
            elif mutation == "reorder":
                models.reverse()
            else:
                models[0]["seed"] = 123
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                audit.verify_selected_models(models, accepted)

    def test_incomplete_fit_audit_or_wrong_audit_seed_set_rejected(self):
        for mutation in ("status", "missing_seed", "reordered_seed"):
            models, accepted = selected_model_fixture()
            if mutation == "status":
                accepted["status"] = "fit_incomplete_resource"
            elif mutation == "missing_seed":
                accepted["results"].pop()
            else:
                accepted["results"].reverse()
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                audit.verify_selected_models(models, accepted)

    def test_model_binding_does_not_rewrite_registration_or_prior_audit(self):
        models, accepted = selected_model_fixture()
        before = deepcopy((models, accepted))
        audit.verify_selected_models(models, accepted)
        self.assertEqual((models, accepted), before)


class PrelabelLedgerChronologyTests(unittest.TestCase):
    def setUp(self):
        self.unique = [dict(action_id=IDS[0], run_id="lexical-first-but-executed-later"),
                       dict(action_id=IDS[1], run_id="actual-earliest")]
        self.calls = {"lexical-first-but-executed-later": 120, "actual-earliest": 100}
        self.runs = {"lexical-first-but-executed-later": 7, "actual-earliest": 6}
        self.fixed = dict(calls_at_selection_freeze=100, executions_at_selection_freeze=6)

    def invoke(self):
        return audit.verify_prelabel_freeze(self.fixed, self.unique, self.calls, self.runs)

    def test_freeze_is_bound_to_earliest_paid_execution_not_lexical_first_action(self):
        self.invoke()

    def test_old_lexical_first_freeze_after_another_tail_was_executed_is_rejected(self):
        self.fixed.update(calls_at_selection_freeze=120, executions_at_selection_freeze=7)
        with self.assertRaisesRegex(ValueError, "before state label calls"):
            self.invoke()

    def test_permuting_action_records_does_not_change_the_actual_freeze_boundary(self):
        self.unique.reverse()
        self.invoke()

    def test_both_attempted_call_and_started_execution_counts_are_bound(self):
        original = deepcopy(self.fixed)
        for key in ("calls_at_selection_freeze", "executions_at_selection_freeze"):
            for delta in (-1, 1):
                self.fixed = deepcopy(original)
                self.fixed[key] += delta
                with self.subTest(key=key, delta=delta), self.assertRaises(ValueError):
                    self.invoke()

    def test_same_call_counter_does_not_hide_a_later_execution_boundary(self):
        self.calls["lexical-first-but-executed-later"] = 100
        self.fixed["executions_at_selection_freeze"] = 7
        with self.assertRaises(ValueError):
            self.invoke()

    def test_empty_duplicate_or_unregistered_tail_run_fails_closed(self):
        original = deepcopy(self.unique)
        for mutation in ("empty", "duplicate", "unregistered"):
            self.unique = deepcopy(original)
            if mutation == "empty":
                self.unique = []
            elif mutation == "duplicate":
                self.unique.append(deepcopy(self.unique[0]))
            else:
                self.unique[0]["run_id"] = "unregistered"
            with self.subTest(mutation=mutation), self.assertRaises((ValueError, KeyError)):
                self.invoke()


if __name__ == "__main__":
    unittest.main()
