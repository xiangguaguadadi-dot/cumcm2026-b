#!/usr/bin/env python3
"""Run the preregistered paired 1200-world Q3 safe-action ablation."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import random
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from local_env import InterfaceOnly, LocalEnv, Source
import evaluate


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def import_arm(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def execute(case, module, arm):
    env = LocalEnv([Source(**s) for s in case["sources"]], case["seed"], case["noise"], keep_log=False)
    solver = module.Solver(InterfaceOnly(env), mode=3, **module.OPTIMIZED_CONFIGS[3])
    started = time.perf_counter()
    error = None
    result = {}
    try:
        result = solver.run()
    except Exception as exc:
        error = type(exc).__name__ + ": " + str(exc)
    wall = time.perf_counter() - started
    if env.started and not env.finished:
        env._finish("strategy_exception" if error else "missing_exit")
    stats = env.stats()
    complete = stats["cleared"] == stats["n"] and env.exit_reason == "user_exit" and error is None
    audits = getattr(solver, "safe_action_audit", [])
    return {
        "case_id": case["case_id"], "mode": 3, "group": case["group"], "seed": case["seed"],
        "seed_cluster": case["seed"], "noise": case["noise"], "arm": arm,
        "source_count": stats["n"], "cleared_count": stats["cleared"],
        "complete": complete, "exit_reason": env.exit_reason, "error": error,
        "total_virtual_time_s": stats["time_s"], "seconds_per_source": stats["average_s"],
        "measure_count": stats["measures"], "optical_clear_attempts": stats["clear_attempts"],
        "failed_clear_attempts": stats["clear_failures"], "movement_distance_m": stats["distance_m"],
        "channel_switches": stats["switches"], "accounting_error_s": stats["accounting_error_s"],
        "worker_runtime_s": wall, "coverage_complete": result.get("coverage_complete", False),
        "safe_action_events": len(audits), "solver_counters": dict(getattr(solver, "counters", {})),
    }, audits


def percentile(values, q):
    values = sorted(values)
    x = (len(values) - 1) * q
    lo, hi = math.floor(x), math.ceil(x)
    return values[lo] if lo == hi else values[lo] * (hi - x) + values[hi] * (x - lo)


def cluster_bootstrap(pairs, key, repetitions=20000):
    clusters = sorted({p["seed_cluster"] for p in pairs})
    by = {s: [p[key] for p in pairs if p["seed_cluster"] == s] for s in clusters}
    assert all(len(by[s]) == 12 for s in clusters)
    rng = random.Random(2026091304)
    values = []
    for _ in range(repetitions):
        selected = [rng.choice(clusters) for _ in clusters]
        values.append(statistics.fmean(x for s in selected for x in by[s]))
    return [percentile(values, 0.025), percentile(values, 0.975)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=None, help="Smoke-only prefix; omit for preregistered full run")
    args = ap.parse_args()
    reg = load(HERE / "registration.json")
    registration_hash = sha(HERE / "registration.json")
    for item in reg["frozen_inputs"]:
        assert sha(ROOT / item["path"]) == item["sha256"], item["path"]
    for name, item in reg["arms"].items():
        assert sha(HERE / item["path"]) == item["sha256"], name
    assert sha(__file__) == reg["runner"]["sha256"]
    evaluate.verify()
    cases = [c for c in load(ROOT / "evaluation/cases_v1.json") if c["mode"] == 3]
    assert len(cases) == 1200
    if args.limit is not None:
        cases = cases[:args.limit]
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    invocation = {
        "registration_sha256": registration_hash, "runner_sha256": sha(__file__),
        "full_preregistered_run": args.limit is None, "case_count": len(cases),
        "planned_strategy_executions": 2 * len(cases), "case_ids": [c["case_id"] for c in cases],
        "python": platform.python_version(), "platform": platform.platform(), "started_unix_s": time.time(),
    }
    dump(out / "invocation.json", invocation)
    modules = {name: import_arm(HERE / spec["path"], "safe_action_" + name) for name, spec in reg["arms"].items()}
    assert all(module.OPTIMIZED_CONFIGS[3].get("lens_clear") == "route" for module in modules.values())
    forbidden = ("cases_v1", "_sources", "case_id", "source_count", "true_direction")
    for item in reg["arms"].values():
        source = (HERE / item["path"]).read_text()
        assert not any(token in source for token in forbidden), item["path"]
    rows, action_audits = [], []
    started = time.perf_counter()
    # Interleave arms within each deterministic world. The local virtual result is deterministic.
    for i, case in enumerate(cases, 1):
        for arm in ("full_C_clear", "mec_center"):
            row, audits = execute(case, modules[arm], arm)
            rows.append(row)
            for j, audit in enumerate(audits):
                action_audits.append({"case_id": case["case_id"], "group": case["group"],
                                      "seed_cluster": case["seed"], "event_index": j, **audit})
        if i % 100 == 0:
            print(f"completed {i}/{len(cases)} paired worlds", flush=True)
    by_arm = {arm: {r["case_id"]: r for r in rows if r["arm"] == arm} for arm in modules}
    assert all(set(x) == {c["case_id"] for c in cases} for x in by_arm.values())
    pairs = []
    metrics = ["seconds_per_source", "measure_count", "optical_clear_attempts", "failed_clear_attempts", "movement_distance_m"]
    for case in cases:
        f, c = by_arm["full_C_clear"][case["case_id"]], by_arm["mec_center"][case["case_id"]]
        pair = {"case_id": case["case_id"], "group": case["group"], "seed_cluster": case["seed"],
                "source_count": f["source_count"], "full_complete": f["complete"], "center_complete": c["complete"]}
        for key in metrics:
            pair["full_" + key] = f[key]
            pair["center_" + key] = c[key]
            pair["full_minus_center_" + key] = f[key] - c[key]
        pairs.append(pair)
    time_deltas = [p["full_minus_center_seconds_per_source"] for p in pairs]
    all_complete = all(r["complete"] for r in rows)
    all_certified = all(a["selected_point_certified"] for a in action_audits)
    all_center_exact = all(a["distance_from_mec_center_m"] <= 1e-12 for a in action_audits if a["arm"] == "mec_center")
    max_vertex = max((a["maximum_vertex_distance_m"] for a in action_audits), default=None)
    mean = {arm: statistics.fmean(r["seconds_per_source"] for r in by_arm[arm].values()) for arm in modules}
    ci = cluster_bootstrap(pairs, "full_minus_center_seconds_per_source") if len(cases) == 1200 else None
    per_group = {}
    for group in sorted({p["group"] for p in pairs}):
        part = [p for p in pairs if p["group"] == group]
        per_group[group] = {
            "cases": len(part),
            "full_mean_s_per_source": statistics.fmean(p["full_seconds_per_source"] for p in part),
            "center_mean_s_per_source": statistics.fmean(p["center_seconds_per_source"] for p in part),
            "full_minus_center_mean_s_per_source": statistics.fmean(p["full_minus_center_seconds_per_source"] for p in part),
            "full_slower_cases": sum(p["full_minus_center_seconds_per_source"] > 1e-9 for p in part),
        }
    metric_summary = {}
    for key in metrics:
        metric_summary[key] = {
            "full_total": sum(r[key] for r in by_arm["full_C_clear"].values()),
            "center_total": sum(r[key] for r in by_arm["mec_center"].values()),
            "full_mean_per_case": statistics.fmean(r[key] for r in by_arm["full_C_clear"].values()),
            "center_mean_per_case": statistics.fmean(r[key] for r in by_arm["mec_center"].values()),
            "paired_full_minus_center_mean": statistics.fmean(p["full_minus_center_" + key] for p in pairs),
        }
    summary = {
        "label": "Paired exposed LOCAL-v1 Q3 full-task safe-action ablation; new policy executions; not blind or official",
        "full_preregistered_run": args.limit is None, "worlds": len(cases), "strategy_executions": len(rows),
        "sources_per_arm": sum(r["source_count"] for r in by_arm["full_C_clear"].values()),
        "all_complete": all_complete, "all_error_free": all(r["error"] is None for r in rows),
        "all_accounting_checks": all(r["accounting_error_s"] <= 2e-5 for r in rows),
        "safe_action_events": {arm: sum(r["safe_action_events"] for r in by_arm[arm].values()) for arm in modules},
        "all_selected_points_cover_feasible_polygon_vertices": all_certified,
        "all_center_arm_points_equal_mec_center": all_center_exact,
        "maximum_audited_vertex_distance_m": max_vertex,
        "mean_s_per_source": mean,
        "full_minus_center_mean_s_per_source": mean["full_C_clear"] - mean["mec_center"],
        "full_improvement_s_per_source": mean["mec_center"] - mean["full_C_clear"],
        "full_improvement_fraction": 1.0 - mean["full_C_clear"] / mean["mec_center"],
        "seed_cluster_bootstrap_95pct_full_minus_center_s_per_source": ci,
        "full_faster_cases": sum(x < -1e-9 for x in time_deltas),
        "equal_cases": sum(abs(x) <= 1e-9 for x in time_deltas),
        "full_slower_cases": sum(x > 1e-9 for x in time_deltas),
        "metrics": metric_summary, "per_group": per_group,
        "worst_regressions": sorted(pairs, key=lambda p: p["full_minus_center_seconds_per_source"], reverse=True)[:20],
        "best_improvements": sorted(pairs, key=lambda p: p["full_minus_center_seconds_per_source"])[:20],
        "time_headline_gate_passed": bool(all_complete and all_certified and ci is not None and ci[1] < 0),
        "elapsed_wall_s": time.perf_counter() - started,
    }
    with (out / "rows.jsonl").open("w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    with (out / "pairs.jsonl").open("w") as f:
        for pair in pairs:
            f.write(json.dumps(pair, ensure_ascii=False, separators=(",", ":")) + "\n")
    with (out / "certified_action_audit.jsonl").open("w") as f:
        for audit in action_audits:
            f.write(json.dumps(audit, ensure_ascii=False, separators=(",", ":")) + "\n")
    dump(out / "summary.json", summary)
    # Recheck every sealed input after the run.
    for item in reg["frozen_inputs"]:
        assert sha(ROOT / item["path"]) == item["sha256"], item["path"]
    evaluate.verify()
    dump(out / "postrun_hash_check.json", {
        "registration_sha256": registration_hash,
        "all_registered_hashes_unchanged": True,
        "evaluation_verify_passed": True,
        "completed_unix_s": time.time(),
    })
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
