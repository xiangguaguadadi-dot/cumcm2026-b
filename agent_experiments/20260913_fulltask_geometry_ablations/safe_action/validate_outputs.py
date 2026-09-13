#!/usr/bin/env python3
"""Independent raw-row, geometry-audit, provenance and summary validation."""
from __future__ import annotations

import hashlib
import json
import math
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUN = HERE / "full_1200"


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path): return json.loads(Path(path).read_text())
def jsonl(path): return [json.loads(x) for x in Path(path).read_text().splitlines()]


def close(a, b, tol=1e-10): return abs(a - b) <= tol


def main():
    checks = []
    def check(name, ok, detail=None):
        checks.append({"name": name, "passed": bool(ok), "detail": detail})
        assert ok, name

    reg = load(HERE / "registration.json")
    for item in reg["frozen_inputs"]:
        check("registered input hash: " + item["path"], sha(ROOT / item["path"]) == item["sha256"])
    for name, item in reg["arms"].items():
        check("registered arm hash: " + name, sha(HERE / item["path"]) == item["sha256"])
    check("registered runner hash", sha(HERE / reg["runner"]["path"]) == reg["runner"]["sha256"])

    cases = [c for c in load(ROOT / "evaluation/cases_v1.json") if c["mode"] == 3]
    case_ids = {c["case_id"] for c in cases}
    rows, pairs, audits = jsonl(RUN / "rows.jsonl"), jsonl(RUN / "pairs.jsonl"), jsonl(RUN / "execution_geometry_audit.jsonl")
    summary, geom = load(RUN / "summary.json"), load(RUN / "execution_geometry_audit_summary.json")
    check("1200 frozen Q3 cases", len(cases) == 1200)
    check("2400 primary strategy rows", len(rows) == 2400)
    for arm in ("full_C_clear", "mec_center"):
        part = [r for r in rows if r["arm"] == arm]
        check(arm + " has every case exactly once", len(part) == 1200 and {r["case_id"] for r in part} == case_ids)
    check("1200 aligned pairs", len(pairs) == 1200 and {p["case_id"] for p in pairs} == case_ids)
    check("all primary runs complete", all(r["complete"] and r["exit_reason"] == "user_exit" and r["error"] is None and r["cleared_count"] == r["source_count"] for r in rows))
    check("all accounting errors bounded", max(r["accounting_error_s"] for r in rows) <= 2e-5)

    by_arm = {a: [r for r in rows if r["arm"] == a] for a in ("full_C_clear", "mec_center")}
    full_mean = statistics.fmean(r["seconds_per_source"] for r in by_arm["full_C_clear"])
    center_mean = statistics.fmean(r["seconds_per_source"] for r in by_arm["mec_center"])
    check("full mean recomputed", close(full_mean, summary["mean_s_per_source"]["full_C_clear"]))
    check("center mean recomputed", close(center_mean, summary["mean_s_per_source"]["mec_center"]))
    check("paired delta recomputed", close(statistics.fmean(p["full_minus_center_seconds_per_source"] for p in pairs), summary["full_minus_center_mean_s_per_source"]))

    check("vertex-level replay has every recorded event", len(audits) == geom["events"] == 16611)
    recomputed_max = max(max(math.dist(a["selected_point"], v) for v in a["feasible_polygon_vertices"]) for a in audits)
    check("all polygon vertices covered independently", recomputed_max <= 20.0 + 1e-8, recomputed_max)
    check("all audited points were actual certified clear actions", all(a["selected_point_was_actual_certified_clear"] for a in audits))
    check("all center-arm points equal MEC center", all(a["center_point_exact"] is True for a in audits if a["arm"] == "mec_center"))
    check("audit replay exactly reproduces primary virtual times", geom["all_primary_virtual_times_reproduced_exactly"] is True)

    candidate_sources = (HERE / "full_safe_action.py").read_text() + (HERE / "mec_center.py").read_text()
    forbidden = ("cases_v1", "_sources", "case_id", "source_count", "true_direction")
    check("candidate wrappers contain no truth/test identifiers", not any(x in candidate_sources for x in forbidden))
    check("planner interface documented as InterfaceOnly", geom["planner_interface"] == "InterfaceOnly(enter, measure, clear, exit)")

    historical_path = ROOT / "experiments/20260913_q2_transfer/B_improved/results/B3_full/case_metrics.json"
    historical = {r["case_id"]: r for r in load(historical_path) if r["mode"] == 3}
    current_full = {r["case_id"]: r for r in by_arm["full_C_clear"]}
    historical_exact = all(close(historical[k]["total_virtual_time_s"], current_full[k]["total_virtual_time_s"], 1e-12)
                           and historical[k]["cleared_count"] == current_full[k]["cleared_count"] for k in case_ids)
    check("instrumented full arm exactly matches saved B3 Q3 results", historical_exact,
          {"historical_path": str(historical_path.relative_to(ROOT)), "historical_sha256": sha(historical_path)})

    values = {k: [] for k in ("move", "measure", "switch", "clear")}
    indexed = {a: {r["case_id"]: r for r in by_arm[a]} for a in by_arm}
    for case_id in case_ids:
        f, c = indexed["full_C_clear"][case_id], indexed["mec_center"][case_id]
        n = f["source_count"]
        values["move"].append((f["movement_distance_m"] - c["movement_distance_m"]) / 5 / n)
        values["measure"].append((f["measure_count"] - c["measure_count"]) * 5 / n)
        values["switch"].append((f["channel_switches"] - c["channel_switches"]) / n)
        values["clear"].append((f["optical_clear_attempts"] - c["optical_clear_attempts"]) * 3 / n)
    decomposition = {k: statistics.fmean(v) for k, v in values.items()}
    check("virtual-time decomposition closes", close(sum(decomposition.values()), summary["full_minus_center_mean_s_per_source"], 5e-9), decomposition)

    output = {
        "all_passed": all(c["passed"] for c in checks), "checks_passed": sum(c["passed"] for c in checks),
        "checks_total": len(checks), "checks": checks,
        "recomputed": {
            "full_mean_s_per_source": full_mean, "center_mean_s_per_source": center_mean,
            "full_minus_center_s_per_source": full_mean - center_mean,
            "maximum_vertex_distance_m": recomputed_max,
            "per_source_delta_decomposition_s": decomposition,
        },
        "evidence_boundary": "exposed deterministic LOCAL-v1 Q3 regression; not blind or official",
    }
    (HERE / "VALIDATION.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"all_passed": output["all_passed"], "checks": len(checks), "decomposition": decomposition}, ensure_ascii=False))


if __name__ == "__main__": main()
