#!/usr/bin/env python3
import hashlib
import importlib.util
import itertools
import json
import math
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODE = HERE.parents[2]
spec = importlib.util.spec_from_file_location("q3g_run", HERE / "run_experiments.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    checks = []
    reg = json.loads((HERE / "registration.json").read_text())
    for rel, meta in reg["inputs"].items():
        got = sha(CODE / rel)
        checks.append({"name": "input_hash:" + rel, "passed": got == meta["sha256"], "actual": got})

    summary = json.loads((HERE / "summary.json").read_text())
    route_rows = [json.loads(x) for x in (HERE / "routing_rows.jsonl").read_text().splitlines()]
    checks += [
        {"name": "routing_row_count", "passed": len(route_rows) == 480, "actual": len(route_rows)},
        {"name": "routing_permutations", "passed": all(sorted(x["heuristic_route"]) == list(range(x["n"])) for x in route_rows)},
        {"name": "mst_is_lower_bound", "passed": all(x["mst_lower_bound_m"] <= x["exact_length_m"] + 1e-7 for x in route_rows)},
        {"name": "exact_le_heuristic_le_nearest", "passed": all(
            x["exact_length_m"] <= x["heuristic_length_m"] + 1e-7 and
            x["heuristic_length_m"] <= x["nearest_length_m"] + 1e-7 for x in route_rows)},
    ]
    # Independent factorial cross-check on 20 small states.
    brute_ok = 0
    for x in [r for r in route_rows if r["n"] <= 8][:20]:
        brute = min(mod.route_length(x["start"], x["points"], list(p))
                    for p in itertools.permutations(range(x["n"])))
        brute_ok += abs(brute - x["exact_length_m"]) <= 1e-7
    checks.append({"name": "held_karp_vs_bruteforce_20", "passed": brute_ok == 20, "actual": brute_ok})

    fg = [json.loads(x) for x in (HERE / "failure_geometry_rows.jsonl").read_text().splitlines()]
    hp = [json.loads(x) for x in (HERE / "failure_historical_pairs.jsonl").read_text().splitlines()]
    checks += [
        {"name": "failure_fixture_rows", "passed": len(fg) == 2000, "actual": len(fg)},
        {"name": "failure_fixture_sample_denominator", "passed": sum(x["checked_admissible_points"] for x in fg) == 256000},
        {"name": "failure_fixture_nonnegative_reduction", "passed": all(0 <= x["kept_cells"] <= x["all_cells"] for x in fg)},
        {"name": "historical_pair_rows", "passed": len(hp) == 2400 and len({x["case_id"] for x in hp}) == 2400},
        {"name": "historical_both_complete", "passed": all(x["parent_complete"] and x["feedback_complete"] for x in hp)},
        {"name": "summary_false_exclusions_zero", "passed": summary["failure_geometry"]["false_exclusions"] == 0},
    ]
    for name, meta in summary["artifacts"].items():
        checks.append({"name": "artifact_hash:" + name, "passed": sha(HERE / name) == meta["sha256"]})

    bench = json.loads((HERE / "exact_tail_summary.json").read_text())
    checks += [
        {"name": "exact_tail_batch1_denominator", "passed": bench["batch1_calls"] == 600},
        {"name": "exact_tail_all_complete", "passed": bench["all_routes_complete"]},
        {"name": "exact_tail_n10_p95_recorded", "passed": 0 < bench["latency_ms"]["10"]["p95"] < 1000,
         "actual": bench["latency_ms"]["10"]["p95"]},
    ]
    result = {"status": "passed" if all(x["passed"] for x in checks) else "failed",
              "checks": checks, "checks_passed": sum(x["passed"] for x in checks), "checks_total": len(checks),
              "note": "Geometric zero-false-exclusion count comes from deterministic run output; theorem and strict-margin condition are stated in RESULTS.md."}
    (HERE / "VALIDATION.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
