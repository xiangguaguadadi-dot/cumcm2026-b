"""Isolated Q3 ablation for the information carried by a failed optical clear."""
import argparse, concurrent.futures, hashlib, importlib.util, json, math
import multiprocessing, random, statistics, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PACKAGE = ROOT / "最佳方法/代码"
SOURCE = PACKAGE / "solver.py"
CASES = ROOT / "最佳方法/数据/exposed_cases.json"
EXPECTED = "e6a0666d644ceaa1d7ae69f19042b9ca022379f3e5a57d927e52bcf1a09360bd"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def area(poly):
    return abs(sum(a[0] * b[1] - a[1] * b[0] for a, b in zip(poly, poly[1:] + poly[:1]))) / 2 if poly else 0.0


def contains(poly, point, tol=1e-5):
    signs = []
    for a, b in zip(poly, poly[1:] + poly[:1]):
        edge = math.dist(a, b)
        if edge > 1e-7:
            signs.append(((b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0])) / edge)
    return bool(poly) and (not signs or all(v >= -tol for v in signs) or all(v <= tol for v in signs))


def init_worker():
    global ENV, MOD, OUTSIDE
    if sha(SOURCE) != EXPECTED:
        raise RuntimeError("frozen B3 candidate changed")
    ENV = load("failed_clear_env", PACKAGE / "local_env.py")
    MOD = load("failed_clear_b3", SOURCE)
    dummy = MOD.Solver(None, mode=3)
    OUTSIDE = dummy._exclude_observed_disks.__func__.__globals__["_geo_outside_disk_hull"]


def run_case(task):
    case, arm = task
    env = ENV.LocalEnv([ENV.Source(**s) for s in case["sources"]], case["seed"], case["noise"], keep_log=False)
    config = {**MOD.OPTIMIZED_CONFIGS[3], "geom_failure": arm == "on"}
    solver = MOD.Solver(ENV.InterfaceOnly(env), mode=3, **config)
    truth = {s["channel"]: (s["x"], s["y"]) for s in case["sources"]}
    events, violations = [], []
    original_clear = solver.clear

    def observed_clear(point, channel, certified=False):
        before = list(solver.polygons.get(channel, []))
        result = original_clear(point, channel, certified=certified)
        if not result and before and channel in truth:
            hypothetical = OUTSIDE(before, tuple(point), 20.0 - 1e-6)
            after = list(solver.polygons.get(channel, [])) if arm == "on" else hypothetical
            old_area, new_area = area(before), area(after)
            event = {
                "case_id": case["case_id"], "arm": arm, "channel": channel,
                "attempt": list(point), "source": list(truth[channel]),
                "source_distance_m": math.dist(point, truth[channel]),
                "area_before_m2": old_area, "area_after_m2": new_area,
                "fractional_shrink": max(0.0, old_area - new_area) / old_area if old_area else 0.0,
                "source_inside_before": contains(before, truth[channel]),
                "source_inside_after": contains(after, truth[channel]),
                "actual_update": arm == "on"
            }
            events.append(event)
            if event["source_distance_m"] <= 20.0 - 1e-7 or not event["source_inside_after"]:
                violations.append(event)
        return result

    solver.clear = observed_clear
    started = time.perf_counter()
    error = None
    result = {}
    try:
        result = solver.run()
    except Exception as exc:
        error = type(exc).__name__ + ": " + str(exc)
    if env.started and not env.finished:
        env._finish("strategy_exception" if error else "missing_exit")
    stats = env.stats()
    row = {
        "case_id": case["case_id"], "group": case["group"], "seed": case["seed"],
        "exposure_suite": case.get("exposure_suite"), "arm": arm,
        "complete": stats["cleared"] == stats["n"] and env.exit_reason == "user_exit" and error is None,
        "error": error, "exit_reason": env.exit_reason, "source_count": stats["n"],
        "cleared_count": stats["cleared"], "average_clear_time_s": stats["average_s"],
        "total_virtual_time_s": stats["time_s"], "distance_m": stats["distance_m"],
        "measures": stats["measures"], "clear_attempts": stats["clear_attempts"],
        "clear_failures": stats["clear_failures"], "switches": stats["switches"],
        "runtime_s": time.perf_counter() - started, "failed_clear_events": len(events),
        "effective_shrinks": sum(e["fractional_shrink"] > 1e-12 for e in events),
        "true_source_exclusions": len(violations), "coverage_complete": result.get("coverage_complete", False)
    }
    return row, events, violations


def summarize(rows):
    by = {arm: {r["case_id"]: r for r in rows if r["arm"] == arm} for arm in ("on", "off")}
    assert set(by["on"]) == set(by["off"])
    ids = sorted(by["on"])
    out = {
        "pairs": len(ids), "actual_runs": len(rows), "all_complete": all(r["complete"] for r in rows),
        "sources_per_arm": sum(by["on"][i]["source_count"] for i in ids),
        "true_source_exclusions": sum(r["true_source_exclusions"] for r in rows),
        "failed_clear_events": {arm: sum(r["failed_clear_events"] for r in by[arm].values()) for arm in by},
        "effective_shrinks": {arm: sum(r["effective_shrinks"] for r in by[arm].values()) for arm in by}
    }
    if out["all_complete"]:
        for arm in by:
            part = list(by[arm].values())
            out[arm] = {key: statistics.mean(r[key] for r in part) for key in
                        ("average_clear_time_s", "distance_m", "measures", "clear_attempts", "clear_failures")}
        differences = [by["on"][i]["average_clear_time_s"] - by["off"][i]["average_clear_time_s"] for i in ids]
        out["paired"] = {"mean_on_minus_off_s_per_source": statistics.mean(differences),
                         "faster": sum(d < -1e-9 for d in differences),
                         "tied": sum(abs(d) <= 1e-9 for d in differences),
                         "slower": sum(d > 1e-9 for d in differences)}
        clusters = {}
        for cid in ids:
            row = by["on"][cid]
            clusters.setdefault((row.get("exposure_suite"), row["seed"]), []).append(
                row["average_clear_time_s"] - by["off"][cid]["average_clear_time_s"])
        values = [statistics.mean(v) for v in clusters.values()]
        rng = random.Random(2026091311)
        boots = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(10000))
        out["paired"]["seed_cluster_ci95"] = [boots[249], boots[9749]]
        out["paired"]["seed_clusters"] = len(values)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("quick", "remaining", "all"), default="quick")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = HERE / args.out
    out.mkdir(exist_ok=False)
    cases = [c for c in json.loads(CASES.read_text()) if c["mode"] == 3]
    is_quick = lambda c: c.get("exposure_suite") == "v1" and c.get("quick", False)
    if args.stage == "quick":
        cases = [c for c in cases if is_quick(c)]
    elif args.stage == "remaining":
        cases = [c for c in cases if not is_quick(c)]
    manifest = json.loads((PACKAGE / "evaluation/manifest_v1.json").read_text())
    for rel, expected in manifest["sha256"].items():
        if sha(PACKAGE / rel) != expected:
            raise RuntimeError("frozen file changed: " + rel)
    dump(out / "invocation.json", {"argv": sys.argv, "candidate_sha256": sha(SOURCE),
         "cases_sha256": sha(CASES), "script_sha256": sha(Path(__file__)),
         "case_ids": [c["case_id"] for c in cases], "arms": ["on", "off"]})
    tasks = [(case, arm) for case in cases for arm in ("on", "off")]
    rows = []
    started = time.perf_counter()
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers,
            mp_context=multiprocessing.get_context("spawn"), initializer=init_worker) as pool:
        with (out / "rows.jsonl").open("w") as row_file, (out / "events.jsonl").open("w") as event_file, (out / "violations.jsonl").open("w") as violation_file:
            for row, events, violations in pool.map(run_case, tasks, chunksize=1):
                rows.append(row)
                row_file.write(json.dumps(row, ensure_ascii=False) + "\n")
                for event in events:
                    event_file.write(json.dumps(event, ensure_ascii=False) + "\n")
                for violation in violations:
                    violation_file.write(json.dumps(violation, ensure_ascii=False) + "\n")
                if len(rows) % 20 == 0:
                    print(json.dumps({"runs": len(rows), "total": len(tasks), "elapsed_s": time.perf_counter() - started}), flush=True)
    result = summarize(rows)
    result.update({"status": "complete", "stage": args.stage, "wall_s": time.perf_counter() - started,
                   "label": "Actual exposed local Q3 executions; not blind or official"})
    dump(out / "summary.json", result)
    if sha(SOURCE) != EXPECTED:
        raise RuntimeError("candidate changed during run")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
