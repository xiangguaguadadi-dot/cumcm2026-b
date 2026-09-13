#!/usr/bin/env python3
"""Cross-check the two full-task Q3 geometry ablations."""

from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def load(relative: str):
    return json.loads((HERE / relative).read_text())


def near(a: float, b: float, tolerance: float = 5e-7) -> bool:
    return abs(a - b) <= tolerance


multi = load("multidisc/summary.json")
multi_validation = load("multidisc/VALIDATION.json")
safe = load("safe_action/full_1200/summary.json")
safe_validation = load("safe_action/VALIDATION.json")
report = (HERE / "RESULTS.md").read_text()

mc = multi["comparison"]
checks = {
    "master_report_exists": (HERE / "RESULTS.md").is_file(),
    "multidisc_1200_pairs": mc["cases"] == 1200 and multi["fresh_runs"] == 2400,
    "multidisc_all_complete": mc["all_complete"],
    "multidisc_delta": near(mc["delta_seconds_per_source_mean"], -0.6753761277156497),
    "multidisc_ci_below_zero": mc["delta_seconds_per_source_ci95"]["upper"] < 0,
    "multidisc_switch_isolated": mc["on_adaptive_multidisc_executions"] > 0 and mc["off_adaptive_multidisc_executions"] == 0,
    "multidisc_validation": multi_validation["status"] == "pass" and multi_validation["registered_input_hashes_unchanged"],
    "safe_1200_pairs": safe["worlds"] == 1200 and safe["strategy_executions"] == 2400,
    "safe_all_complete": safe["all_complete"] and safe["all_error_free"],
    "safe_delta": near(safe["full_minus_center_mean_s_per_source"], -0.7082706067562583),
    "safe_ci_below_zero": safe["seed_cluster_bootstrap_95pct_full_minus_center_s_per_source"][1] < 0,
    "safe_geometry": safe["all_selected_points_cover_feasible_polygon_vertices"] and safe["all_center_arm_points_equal_mec_center"],
    "safe_validation": safe_validation["all_passed"] and safe_validation["checks_passed"] == safe_validation["checks_total"] == 31,
    "common_b3_mean": near(mc["on_mean_seconds_per_source"], safe["mean_s_per_source"]["full_C_clear"]),
    "nonadditivity_boundary_in_report": "不能直接相加" in report,
    "exposed_boundary_in_report": "不是盲测或官方Windows成绩" in report,
}

out = {
    "status": "pass" if all(checks.values()) else "fail",
    "checks": checks,
    "checks_passed": sum(checks.values()),
    "checks_total": len(checks),
    "scope": "Cross-experiment arithmetic, isolation outcomes, geometry audit status, and reporting boundaries.",
}
(HERE / "VALIDATION.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(out, ensure_ascii=False, indent=2))
raise SystemExit(0 if out["status"] == "pass" else 1)
