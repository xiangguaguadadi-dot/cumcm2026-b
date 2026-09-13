#!/usr/bin/env python3
"""Isolated audits for open-path scheduling and failed-clear geometry."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODE = HERE.parents[2]
SEED = 2026091303


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def route_length(start, points, route):
    return dist(start, points[route[0]]) + sum(
        dist(points[a], points[b]) for a, b in zip(route, route[1:])
    )


def nearest_route(start, points):
    left = set(range(len(points)))
    route, p = [], start
    while left:
        j = min(left, key=lambda q: (dist(p, points[q]), q))
        route.append(j)
        left.remove(j)
        p = points[j]
    return route


def c7_route(start, points):
    """Literal fixed-state structure of C7 spatial_next_task."""
    n = len(points)
    positions = [start] + points
    ds = [[dist(a, b) for b in positions] for a in positions]
    greedy = [x + 1 for x in nearest_route(start, points)]

    def improve(route):
        route = route[:]
        for _ in range(60):
            best, delta = None, 0.0
            for i in range(n - 1):
                before = 0 if i == 0 else route[i - 1]
                a = route[i]
                for j in range(i + 1, n):
                    b = route[j]
                    change = ds[before][b] - ds[before][a]
                    if j + 1 < n:
                        after = route[j + 1]
                        change += ds[a][after] - ds[b][after]
                    if change < delta - 1e-7:
                        delta, best = change, (i, j)
            if best is None:
                break
            i, j = best
            route[i : j + 1] = reversed(route[i : j + 1])
        return route

    routes = [improve(x) for x in [greedy, list(range(1, n + 1)), list(range(n, 0, -1))]]

    def reinsert(route):
        route = route[:]
        for _ in range(30):
            best, delta = None, 0.0
            for i, x in enumerate(route):
                before = 0 if i == 0 else route[i - 1]
                after = route[i + 1] if i + 1 < n else None
                remove = -ds[before][x]
                if after is not None:
                    remove += ds[before][after] - ds[x][after]
                short = route[:i] + route[i + 1 :]
                for j in range(n):
                    if j == i:
                        continue
                    left = 0 if j == 0 else short[j - 1]
                    right = short[j] if j < len(short) else None
                    change = remove + ds[left][x]
                    if right is not None:
                        change += ds[x][right] - ds[left][right]
                    if change < delta - 1e-7:
                        best, delta = (i, j), change
            if best is None:
                break
            i, j = best
            x = route.pop(i)
            route.insert(j, x)
            route = improve(route)
        return route

    routes += [reinsert(x) for x in routes]
    length = lambda r: ds[0][r[0]] + sum(ds[a][b] for a, b in zip(r, r[1:]))
    best = min(routes, key=lambda r: (length(r), r))
    return [x - 1 for x in best]


def exact_open_path(start, points):
    n = len(points)
    # dp[(mask,j)] is the shortest start-rooted path visiting mask and ending j.
    dp = {(1 << j, j): dist(start, points[j]) for j in range(n)}
    parent = {}
    for mask in range(1, 1 << n):
        for j in range(n):
            if not (mask >> j) & 1 or mask == 1 << j:
                continue
            prev = mask ^ (1 << j)
            choices = [(dp[(prev, k)] + dist(points[k], points[j]), k)
                       for k in range(n) if (prev >> k) & 1]
            cost, k = min(choices)
            dp[(mask, j)] = cost
            parent[(mask, j)] = k
    full = (1 << n) - 1
    cost, j = min((dp[(full, j)], j) for j in range(n))
    route, mask = [], full
    while True:
        route.append(j)
        if mask == 1 << j:
            break
        old = j
        j = parent[(mask, j)]
        mask ^= 1 << old
    return cost, list(reversed(route))


def mst_lower_bound(start, points):
    pts = [start] + points
    used = {0}
    best = [dist(pts[0], p) for p in pts]
    total = 0.0
    while len(used) < len(pts):
        j = min((j for j in range(len(pts)) if j not in used), key=lambda j: best[j])
        total += best[j]
        used.add(j)
        for k in range(len(pts)):
            if k not in used:
                best[k] = min(best[k], dist(pts[j], pts[k]))
    return total


def make_state(rng, family, n):
    start = (rng.uniform(-500, 500), rng.uniform(-500, 500))
    if family == "uniform_disk":
        pts = []
        for _ in range(n):
            r, a = 1800 * math.sqrt(rng.random()), rng.random() * 2 * math.pi
            pts.append((r * math.cos(a), r * math.sin(a)))
    elif family == "annulus":
        pts = []
        for _ in range(n):
            r, a = rng.uniform(1100, 1800), rng.random() * 2 * math.pi
            pts.append((r * math.cos(a), r * math.sin(a)))
    elif family == "two_cluster":
        centers = [(-900, -250), (900, 250)]
        pts = [(centers[i % 2][0] + rng.gauss(0, 180), centers[i % 2][1] + rng.gauss(0, 180))
               for i in range(n)]
        rng.shuffle(pts)
    else:  # alternating comb, intentionally awkward for nearest-neighbor
        xs = [(-1500 + 3000 * i / max(1, n - 1)) for i in range(n)]
        pts = [(x + rng.uniform(-25, 25), (700 if i % 2 else -700) + rng.uniform(-50, 50))
               for i, x in enumerate(xs)]
        rng.shuffle(pts)
    return start, pts


def percentile(values, q):
    a = sorted(values)
    x = (len(a) - 1) * q
    lo, hi = math.floor(x), math.ceil(x)
    return a[lo] if lo == hi else a[lo] * (hi - x) + a[hi] * (x - lo)


def routing_experiment(rows_path):
    rng = random.Random(SEED)
    rows = []
    families = ["uniform_disk", "annulus", "two_cluster", "comb"]
    with rows_path.open("w", encoding="utf-8") as f:
        for family in families:
            for rep in range(120):
                n = 5 + rep % 8
                start, pts = make_state(rng, family, n)
                nn = nearest_route(start, pts)
                h = c7_route(start, pts)
                opt, opt_route = exact_open_path(start, pts)
                mst = mst_lower_bound(start, pts)
                hlen, nnlen = route_length(start, pts, h), route_length(start, pts, nn)
                row = {
                    "state_id": f"{family}-{rep:03d}", "family": family, "n": n,
                    "start": start, "points": pts, "nearest_route": nn, "heuristic_route": h,
                    "exact_route": opt_route, "nearest_length_m": nnlen,
                    "heuristic_length_m": hlen, "exact_length_m": opt, "mst_lower_bound_m": mst,
                    "heuristic_gap_fraction": hlen / opt - 1, "heuristic_over_mst": hlen / mst,
                    "saving_vs_nearest_m": nnlen - hlen,
                    "route_complete": sorted(h) == list(range(n)),
                }
                f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                rows.append(row)
    gaps = [x["heuristic_gap_fraction"] for x in rows]
    by_family = {}
    for family in families:
        part = [x for x in rows if x["family"] == family]
        by_family[family] = {
            "states": len(part),
            "exact_hits": sum(abs(x["heuristic_length_m"] - x["exact_length_m"]) <= 1e-7 for x in part),
            "mean_gap_fraction": statistics.fmean(x["heuristic_gap_fraction"] for x in part),
            "max_gap_fraction": max(x["heuristic_gap_fraction"] for x in part),
            "mean_saving_vs_nearest_m": statistics.fmean(x["saving_vs_nearest_m"] for x in part),
        }
    worst = sorted(rows, key=lambda x: x["heuristic_gap_fraction"], reverse=True)[:10]
    return {
        "states": len(rows), "families": families,
        "route_complete": sum(x["route_complete"] for x in rows),
        "never_worse_than_nearest": sum(x["heuristic_length_m"] <= x["nearest_length_m"] + 1e-7 for x in rows),
        "exact_optimum_hits": sum(abs(x["heuristic_length_m"] - x["exact_length_m"]) <= 1e-7 for x in rows),
        "mean_optimality_gap_fraction": statistics.fmean(gaps),
        "p95_optimality_gap_fraction": percentile(gaps, .95),
        "max_optimality_gap_fraction": max(gaps),
        "mean_saving_vs_nearest_m": statistics.fmean(x["saving_vs_nearest_m"] for x in rows),
        "mean_heuristic_over_mst": statistics.fmean(x["heuristic_over_mst"] for x in rows),
        "max_heuristic_over_mst": max(x["heuristic_over_mst"] for x in rows),
        "by_family": by_family,
        "worst_gap_states": [{k: x[k] for k in ("state_id", "n", "heuristic_gap_fraction",
                              "heuristic_length_m", "exact_length_m", "mst_lower_bound_m")} for x in worst],
    }


def clip(poly, a, b, c):
    if not poly:
        return []
    out, p = [], poly[-1]
    fp = a * p[0] + b * p[1] - c
    for q in poly:
        fq = a * q[0] + b * q[1] - c
        if (fp <= 1e-10) != (fq <= 1e-10):
            t = fp / (fp - fq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
        if fq <= 1e-10:
            out.append(q)
        p, fp = q, fq
    return out


def point_in_convex(poly, q):
    signs = []
    for a, b in zip(poly, poly[1:] + poly[:1]):
        z = (b[0] - a[0]) * (q[1] - a[1]) - (b[1] - a[1]) * (q[0] - a[0])
        if abs(z) > 1e-8:
            signs.append(z > 0)
    return not signs or all(s == signs[0] for s in signs)


def cell_intersection(poly, i, j, spacing=25.0):
    test = poly
    for a, b, c in [(1, 0, (i + .5) * spacing), (-1, 0, (-i + .5) * spacing),
                    (0, 1, (j + .5) * spacing), (0, -1, (-j + .5) * spacing)]:
        test = clip(test, a, b, c)
    return test


def enumerate_cells(poly, failures):
    spacing = 25.0
    lo = [math.floor((min(p[d] for p in poly) - spacing / 2) / spacing) for d in (0, 1)]
    hi = [math.ceil((max(p[d] for p in poly) + spacing / 2) / spacing) for d in (0, 1)]
    all_cells, kept = [], []
    for i in range(lo[0], hi[0] + 1):
        row = range(lo[1], hi[1] + 1) if i % 2 == 0 else range(hi[1], lo[1] - 1, -1)
        for j in row:
            test = cell_intersection(poly, i, j)
            if not test:
                continue
            all_cells.append((i, j, test))
            excluded = any(all(dist(p, q) <= 20 - 1e-6 for q in test) for p in failures)
            if not excluded:
                kept.append((i, j, test))
    return all_cells, kept


def failure_geometry_experiment(rows_path):
    rng = random.Random(SEED + 1)
    rows, false_exclusions, retained_samples = [], 0, 0
    with rows_path.open("w", encoding="utf-8") as f:
        for rep in range(2000):
            cx, cy = rng.uniform(-1400, 1400), rng.uniform(-1400, 1400)
            w, h, a = rng.uniform(70, 260), rng.uniform(35, 180), rng.random() * math.pi
            ca, sa = math.cos(a), math.sin(a)
            poly = [(cx + sx * w / 2 * ca - sy * h / 2 * sa,
                     cy + sx * w / 2 * sa + sy * h / 2 * ca)
                    for sx, sy in [(-1, -1), (1, -1), (1, 1), (-1, 1)]]
            # Draw an admissible true source and failed attempts more than 20 m away.
            u, v = rng.uniform(-.49, .49), rng.uniform(-.49, .49)
            source = (cx + u * w * ca - v * h * sa, cy + u * w * sa + v * h * ca)
            all0, _ = enumerate_cells(poly, [])
            candidates = [(25.0 * i, 25.0 * j) for i, j, _ in all0
                          if dist((25.0 * i, 25.0 * j), source) > 20.00001]
            rng.shuffle(candidates)
            failures = candidates[: min(len(candidates), 1 + rep % 4)]
            all_cells, kept = enumerate_cells(poly, failures)
            excluded_keys = {(i, j) for i, j, _ in all_cells} - {(i, j) for i, j, _ in kept}
            checked = 0
            # Source plus 127 rejection-sampled admissible points.
            samples = [source]
            while len(samples) < 128:
                uu, vv = rng.uniform(-.5, .5), rng.uniform(-.5, .5)
                q = (cx + uu * w * ca - vv * h * sa, cy + uu * w * sa + vv * h * ca)
                if all(dist(q, p) > 20 for p in failures):
                    samples.append(q)
            for q in samples:
                assert point_in_convex(poly, q)
                containing = [(i, j) for i, j, test in all_cells
                              if abs(q[0] - 25 * i) <= 12.5 + 1e-8
                              and abs(q[1] - 25 * j) <= 12.5 + 1e-8
                              and point_in_convex(test, q)]
                # Boundary points may belong to several cells; none may all be excluded.
                if containing and all(key in excluded_keys for key in containing):
                    false_exclusions += 1
                checked += 1
            retained_samples += checked
            row = {"fixture_id": rep, "polygon": poly, "source": source, "failed_points": failures,
                   "all_cells": len(all_cells), "kept_cells": len(kept),
                   "excluded_cells": len(all_cells) - len(kept), "checked_admissible_points": checked}
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            rows.append(row)
    return {"fixtures": len(rows), "admissible_points_checked": retained_samples,
            "false_exclusions": false_exclusions,
            "fixtures_with_reduction": sum(x["excluded_cells"] > 0 for x in rows),
            "total_cells_before": sum(x["all_cells"] for x in rows),
            "total_cells_after": sum(x["kept_cells"] for x in rows),
            "mean_cells_removed": statistics.fmean(x["excluded_cells"] for x in rows),
            "cell_reduction_fraction": 1 - sum(x["kept_cells"] for x in rows) / sum(x["all_cells"] for x in rows)}


def historical_pair_audit(rows_path):
    p0 = CODE / "experiments/E2_refine/results/r2_one_round_exposed/case_metrics.json"
    p1 = CODE / "experiments/E2_refine/results/r3_failure_cells_exposed/case_metrics.json"
    a = {x["case_id"]: x for x in json.loads(p0.read_text()) if x["mode"] == 4}
    b = {x["case_id"]: x for x in json.loads(p1.read_text()) if x["mode"] == 4}
    ids = sorted(a.keys() & b.keys())
    rows = []
    with rows_path.open("w", encoding="utf-8") as f:
        for case_id in ids:
            x, y = a[case_id], b[case_id]
            row = {"case_id": case_id, "suite": y["exposure_suite"], "seed_cluster": y["seed_cluster"],
                   "parent_complete": x["complete"], "feedback_complete": y["complete"],
                   "parent_s_per_source": x["average_clear_time_s"],
                   "feedback_s_per_source": y["average_clear_time_s"],
                   "delta_s_per_source": y["average_clear_time_s"] - x["average_clear_time_s"],
                   "parent_clear_failures": x["clear_failures"], "feedback_clear_failures": y["clear_failures"]}
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            rows.append(row)
    clusters = defaultdict(list)
    for r in rows:
        clusters[(r["suite"], r["seed_cluster"])].append(r["delta_s_per_source"])
    cluster_means = [statistics.fmean(v) for v in clusters.values()]
    rng = random.Random(SEED + 2)
    boots = [statistics.fmean(rng.choices(cluster_means, k=len(cluster_means))) for _ in range(10000)]
    deltas = [r["delta_s_per_source"] for r in rows]
    suite_stats = {}
    for suite in sorted({r["suite"] for r in rows}):
        part = [r for r in rows if r["suite"] == suite]
        suite_stats[suite] = {"cases": len(part),
            "mean_delta_s_per_source": statistics.fmean(r["delta_s_per_source"] for r in part),
            "faster": sum(r["delta_s_per_source"] < -1e-9 for r in part),
            "equal": sum(abs(r["delta_s_per_source"]) <= 1e-9 for r in part),
            "slower": sum(r["delta_s_per_source"] > 1e-9 for r in part)}
    return {"aligned_q4_cases": len(rows), "clusters": len(clusters),
            "parent_complete": sum(r["parent_complete"] for r in rows),
            "feedback_complete": sum(r["feedback_complete"] for r in rows),
            "both_complete": sum(r["parent_complete"] and r["feedback_complete"] for r in rows),
            "mean_parent_s_per_source": statistics.fmean(r["parent_s_per_source"] for r in rows),
            "mean_feedback_s_per_source": statistics.fmean(r["feedback_s_per_source"] for r in rows),
            "mean_delta_s_per_source": statistics.fmean(deltas),
            "relative_reduction_fraction": -statistics.fmean(deltas) / statistics.fmean(r["parent_s_per_source"] for r in rows),
            "cluster_bootstrap_95_ci": [percentile(boots, .025), percentile(boots, .975)],
            "faster": sum(d < -1e-9 for d in deltas), "equal": sum(abs(d) <= 1e-9 for d in deltas),
            "slower": sum(d > 1e-9 for d in deltas),
            "mean_clear_failure_delta": statistics.fmean(
                r["feedback_clear_failures"] - r["parent_clear_failures"] for r in rows),
            "by_suite": suite_stats,
            "evidence_label": "recomputed existing exposed regression rows; no new closed-loop run"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=HERE)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    routing_rows = args.out / "routing_rows.jsonl"
    failure_rows = args.out / "failure_geometry_rows.jsonl"
    pair_rows = args.out / "failure_historical_pairs.jsonl"
    summary = {
        "label": "isolated synthetic mechanism audit plus recomputed exposed-regression audit",
        "seed": SEED,
        "routing": routing_experiment(routing_rows),
        "failure_geometry": failure_geometry_experiment(failure_rows),
        "failure_historical": historical_pair_audit(pair_rows),
        "boundaries": [
            "Routing states and failure polygons are synthetic fixtures, not task worlds.",
            "Routing optimum concerns a frozen Euclidean proxy; online observations and service costs can change.",
            "Historical failure-feedback rows are already exposed local regression data, not new runs, blind data, or official Windows results.",
        ],
    }
    summary["artifacts"] = {p.name: {"sha256": sha(p), "bytes": p.stat().st_size}
                            for p in (routing_rows, failure_rows, pair_rows)}
    (args.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
