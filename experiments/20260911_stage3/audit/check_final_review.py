"""Review-pipeline checks using existing cases; never draws final seeds."""
from __future__ import annotations
import copy
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import final_review as review


def main():
    cases = review.read(HERE.parent / "exposed_cases.json")
    baseline = review.read(HERE.parent / "baseline/expected_rows.json")
    byid = {r["case_id"]: r for r in baseline}
    v1cases = [c for c in cases if c["exposure_suite"] == "v1"]
    rows = review.normalize_rows(v1cases, [byid[c["case_id"]] for c in v1cases])
    cells = review.paired(rows, rows)
    assert len(cells) == 26 and all(c["valid_comparison"] and c["delta_s_per_source"] == 0 for c in cells)
    assert all(c["saved_s_per_source_seed_cluster_95ci"] == [0, 0] and c["reduction_fraction_seed_cluster_95ci"] == [0, 0]
               for c in cells if c["group"] == "ALL")
    scaled = copy.deepcopy(rows)
    for r in scaled:
        r["average_clear_time_s"] *= 0.9
        r["total_virtual_time_s"] *= 0.9
    synthetic = review.paired(scaled, rows)
    assert all(abs(c["reduction_fraction"] - 0.1) < 1e-12 for c in synthetic)
    assert all(abs(x - 0.1) < 1e-12 for c in synthetic if c["group"] == "ALL" for x in c["reduction_fraction_seed_cluster_95ci"])
    failure = copy.deepcopy(rows)
    r = failure[0]
    r.update(complete=False, error="worker_timeout", cleared_count=None, average_clear_time_s=None, total_virtual_time_s=None)
    r.pop("exit_reason")
    r.pop("group")
    repaired = review.normalize_rows(v1cases, failure)
    assert repaired[0]["error"] == "worker_timeout" and not review.valid(repaired[0]) and "exit_reason" not in repaired[0]
    failed_cells = review.paired(repaired, rows)
    bad = [c for c in failed_cells if not c["valid_comparison"]]
    assert len(bad) == 2 and all("candidate_mean_s_per_source" not in c for c in bad)
    false_complete = dict(rows[0], error="latent_error")
    assert not review.valid(false_complete)
    duplicate_rejected = False
    try:
        review.paired(rows[:-1] + [rows[0]], rows)
    except AssertionError:
        duplicate_rejected = True
    assert duplicate_rejected
    out = Path(tempfile.mkdtemp(prefix="cumcm_stage3_pipeline_smoke_"))
    first_seed = v1cases[0]["seed"]
    smoke_cases = [c for c in v1cases if c["seed"] == first_seed]
    assert len(smoke_cases) == 24
    review.save(out / "existing_cases.json", smoke_cases)
    provenance = review.read(HERE.parent / "baseline/provenance.json")
    deps = {str(HERE.parent / "baseline" / name): digest for name, digest in provenance["files"].items() if name != "S0.py"}
    summary = review.execute(HERE.parent / "baseline/S0.py", deps, out / "existing_cases.json", out / "result",
                             "S0_existing_case_pipeline_smoke", "control",
                             data_role="existing_exposed_cases_pipeline_smoke")
    smoke = review.read(out / "result/case_metrics.json")
    fields = ["case_id", "mode", "group", "cleared_count", "source_count", "cleared_fraction", "average_clear_time_s",
              "total_virtual_time_s", "complete", "exit_reason", "error", "coverage_certificate", "requests", "distance_m", "clear_failures"]
    for r in smoke:
        assert all(r[k] == byid[r["case_id"]][k] for k in fields)
    report = dict(status="pass", self_comparison_26_cells_zero=True, constant_ratio_bootstrap_correct=True,
                  failed_mode_and_group_unranked=True, missing_crash_metadata_recovered_without_changing_failure=True,
                  duplicate_ids_rejected=True, latent_error_complete_flag_rejected=True,
                  actual_existing_case_smoke_runs=24, source_seed=first_seed, checked_task_fields=15,
                  all_complete=summary["all_valid_completion"], smoke_result_path=str(out / "result"),
                  smoke_wall_seconds=summary["wall_seconds"], runner_sha256=review.sha(review.__file__),
                  cases_drawn_for_final=0, note="Scaling and failure fixtures are checker tests, not policy performance. Only 24 already-exposed S0 cases executed.")
    review.save(HERE / "final_review_pipeline_check.json", report)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
