#!/usr/bin/env python3
"""Batch=1 local latency check for a post-hoc exact-tail proposal."""
import importlib.util
import json
import math
import random
import statistics
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("q3g_run", HERE / "run_experiments.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def percentile(a, q):
    a = sorted(a)
    x = (len(a) - 1) * q
    lo, hi = math.floor(x), math.ceil(x)
    return a[lo] if lo == hi else a[lo] * (hi - x) + a[hi] * (x - lo)


def main():
    rng = random.Random(mod.SEED + 10)
    rows = []
    # Warm interpreter and allocator before recording.
    for _ in range(5):
        s, p = mod.make_state(rng, "uniform_disk", 10)
        mod.exact_open_path(s, p)
    for n in range(5, 11):
        for rep in range(100):
            family = ["uniform_disk", "annulus", "two_cluster", "comb"][rep % 4]
            start, points = mod.make_state(rng, family, n)
            t0 = time.perf_counter_ns()
            cost, route = mod.exact_open_path(start, points)
            elapsed = time.perf_counter_ns() - t0
            rows.append({"n": n, "rep": rep, "family": family, "elapsed_ns": elapsed,
                         "exact_length_m": cost, "route_complete": sorted(route) == list(range(n))})
    with (HERE / "exact_tail_benchmark_rows.jsonl").open("w") as f:
        for x in rows:
            f.write(json.dumps(x, separators=(",", ":")) + "\n")
    routing = [json.loads(x) for x in (HERE / "routing_rows.jsonl").read_text().splitlines()]
    eligible = [x for x in routing if x["n"] <= 10]
    savings = [x["heuristic_length_m"] - x["exact_length_m"] for x in eligible]
    result = {
        "label": "post-hoc exact-tail feasibility check after observing heuristic outliers",
        "machine_scope": "current macOS/Python process only; not official Windows timing",
        "threshold_n": 10,
        "batch1_calls": len(rows),
        "all_routes_complete": all(x["route_complete"] for x in rows),
        "latency_ms": {str(n): {
            "p50": percentile([x["elapsed_ns"] / 1e6 for x in rows if x["n"] == n], .5),
            "p95": percentile([x["elapsed_ns"] / 1e6 for x in rows if x["n"] == n], .95),
            "max": max(x["elapsed_ns"] / 1e6 for x in rows if x["n"] == n),
        } for n in range(5, 11)},
        "eligible_routing_states": len(eligible),
        "states_strictly_improved": sum(x > 1e-7 for x in savings),
        "total_proxy_distance_saved_m": sum(savings),
        "mean_proxy_distance_saved_per_eligible_state_m": statistics.fmean(savings),
        "max_proxy_distance_saved_m": max(savings),
        "evidence_boundary": "This replaces a frozen-state distance proxy only; repeated online replanning cost and end-to-end task benefit were not tested.",
    }
    (HERE / "exact_tail_summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
