#!/usr/bin/env python3
"""Validate the cross-experiment claims cited by the round-two report."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DOC = ROOT.parents[1] / "docs" / "第二至四问_新增五项亮点验证.md"


def load(relative: str):
    return json.loads((ROOT / relative).read_text())


def near(value: float, target: float, tolerance: float = 5e-7) -> bool:
    return abs(value - target) <= tolerance


info = load("information_control/summary.json")
info_validation = load("information_control/VALIDATION.json")
route = load("q3_geometry/summary.json")
tail = load("q3_geometry/exact_tail_summary.json")
route_validation = load("q3_geometry/VALIDATION.json")
q4 = load("q4_structure/summary.json")
q4_audit = load("q4_structure/FINAL_AUDIT.json")
failure = load("failed_clear_feedback/summary.json")
failure_audit = load("failed_clear_feedback/FINAL_AUDIT.json")
failure_peer = load("information_control/FAILED_CLEAR_PEER_REVIEW.json")
doc_text = DOC.read_text()

checks = {
    "report_exists": DOC.is_file(),
    "five_main_rows": all(f"| {i} |" in doc_text for i in range(1, 6)),
    "info_raw_validation": info_validation["checks"]["all_pass"],
    "gate_all_complete": info["station_retest_gate"]["all_complete"],
    "gate_delta": near(info["station_retest_gate"]["b3_saving_vs_ablation_s_per_source"], 2.2694622951315018),
    "replan_all_complete": info["preemptive_replanning"]["all_complete"],
    "replan_delta": near(info["preemptive_replanning"]["b3_saving_vs_ablation_s_per_source"], 2.1897666837783203),
    "routing_validation": route_validation["status"] == "passed" and route_validation["checks_passed"] == route_validation["checks_total"] == 23,
    "routing_states": route["routing"]["states"] == 480,
    "routing_exact_hits": route["routing"]["exact_optimum_hits"] == 461,
    "exact_tail": tail["threshold_n"] == 10 and tail["states_strictly_improved"] == 11 and near(tail["latency_ms"]["10"]["p95"], 11.8909146),
    "q4_all_complete": q4["all_closed_loop_complete"],
    "q4_count_stop_delta": near(q4["count_stop"]["paired_difference_s_per_source"], -13.741907685520834),
    "q4_heading_retention": q4["heading_certificate"]["true_headings_retained"] == q4["heading_certificate"]["full_directional_sources"] == 7885,
    "q4_audit": q4_audit["status"] == "pass" and all(item.get("all_complete_recomputed", True) and item.get("directional_exclusions_recomputed", 0) == 0 for item in q4_audit["checks"]),
    "failed_clear_audit": failure_audit["status"] == "pass" and failure_audit["all_event_sources_retained"],
    "failed_clear_ci_crosses_zero": failure["full"]["paired"]["seed_cluster_ci95"][0] < 0 < failure["full"]["paired"]["seed_cluster_ci95"][1],
    "failed_clear_peer_boundary": failure_peer["verdict"] == "pass_with_preregistration_provenance_caveat",
    "closed_loop_execution_total": 4920 + info["total_new_full_strategy_runs"] + info["total_new_quick_strategy_runs"] + q4["total_closed_loop_executions"] == 10008,
}

result = {
    "status": "pass" if all(checks.values()) else "fail",
    "checks": checks,
    "checks_passed": sum(checks.values()),
    "checks_total": len(checks),
    "report": str(DOC.relative_to(ROOT.parents[1])),
    "report_sha256": hashlib.sha256(DOC.read_bytes()).hexdigest(),
    "evidence_boundary": "Cross-file arithmetic and source audits; exposed local simulations are not blind or official results.",
}
(ROOT / "VALIDATION.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if result["status"] == "pass" else 1)

