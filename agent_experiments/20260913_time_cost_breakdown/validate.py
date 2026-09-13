#!/usr/bin/env python3
"""Independent integrity and accounting checks for the saved decomposition."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    provenance = json.loads((HERE / "provenance.json").read_text())
    source = ROOT / provenance["source"]
    packaged = ROOT / provenance["equivalent_packaged_copy"]
    checks = []

    def check(name: str, condition: bool, detail: object) -> None:
        checks.append({"name": name, "passed": bool(condition), "detail": detail})
        if not condition:
            raise AssertionError(f"{name}: {detail}")

    check("source_sha256", sha(source) == provenance["source_sha256"], sha(source))
    check("packaged_copy_same_hash", sha(packaged) == sha(source), sha(packaged))
    check("frozen_local_env_sha256", sha(ROOT / provenance["local_env"]) == provenance["local_env_sha256"], provenance["local_env_sha256"])
    check("frozen_evaluate_sha256", sha(ROOT / provenance["evaluate"]) == provenance["evaluate_sha256"], provenance["evaluate_sha256"])

    with (HERE / "per_case_costs.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    check("row_count", len(rows) == 4800, len(rows))
    check("unique_case_ids", len({r["case_id"] for r in rows}) == 4800, len({r["case_id"] for r in rows}))
    max_error = max(abs(float(r["accounting_error_s"])) for r in rows)
    check("per_case_five_part_reconciliation", max_error <= 1e-5, {"max_abs_error_s": max_error, "tolerance_s": 1e-5})
    check("integer_switch_counts", all(float(r["switch_time_s"]).is_integer() for r in rows), True)
    check("switches_do_not_exceed_measures", all(int(r["channel_switch_count"]) <= int(r["measure_count"]) for r in rows), True)

    chart = json.loads((HERE / "chart_data.json").read_text())
    by = {(r["question"], r["component_key"]): r for r in chart}
    expected_means = {"Q3": 229.66984347891437, "Q4": 450.98042212586375}
    audited = {}
    for mode in (3, 4):
        q = f"Q{mode}"
        selected = [r for r in rows if int(r["mode"]) == mode]
        direct = statistics.fmean(float(r["time_per_source_s"]) for r in selected)
        component_sum = sum(float(by[(q, key)]["mean_s_per_source"]) for key in ("movement", "bearing", "switch", "optical", "laser"))
        source_count = sum(int(r["source_count"]) for r in selected)
        check(f"{q}_case_count", len(selected) == 2400, len(selected))
        check(f"{q}_source_count", source_count == 30970, source_count)
        check(f"{q}_reported_mean", math.isclose(direct, expected_means[q], abs_tol=1e-12, rel_tol=0), direct)
        check(f"{q}_aggregate_five_part_reconciliation", abs(component_sum - direct) <= 1e-7, {"component_sum": component_sum, "direct_mean": direct})
        audited[q] = {"cases": len(selected), "sources": source_count, "mean_s_per_source": direct, "five_part_sum_s_per_source": component_sum}

    png = HERE / provenance["chart"]["png"]
    svg = HERE / provenance["chart"]["svg"]
    with png.open("rb") as f:
        signature = f.read(24)
    check("png_signature", signature[:8] == b"\x89PNG\r\n\x1a\n", signature[:8].hex())
    dimensions = list(struct.unpack(">II", signature[16:24]))
    check("png_high_resolution", dimensions[0] >= 2500 and dimensions[1] >= 1800, dimensions)
    check("svg_exists_and_nonempty", svg.stat().st_size > 5_000, svg.stat().st_size)
    check("png_exists_and_nonempty", png.stat().st_size > 50_000, png.stat().st_size)

    output = {
        "status": "PASS",
        "data_role": "本地已暴露模拟回归；非盲测、非官方Windows成绩",
        "policy_rerun": False,
        "checks_passed": sum(c["passed"] for c in checks),
        "checks_total": len(checks),
        "checks": checks,
        "audited_summary": audited,
        "artifact_sha256": {
            name: sha(HERE / name)
            for name in ("chart_data.csv", "chart_data.json", "question_summary.csv", "per_case_costs.csv", "time_cost_breakdown_q3_q4.svg", "time_cost_breakdown_q3_q4.png")
        },
    }
    (HERE / "VALIDATION.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": output["status"], "checks": f"{output['checks_passed']}/{output['checks_total']}", "max_accounting_error_s": max_error, "audited_summary": audited}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
