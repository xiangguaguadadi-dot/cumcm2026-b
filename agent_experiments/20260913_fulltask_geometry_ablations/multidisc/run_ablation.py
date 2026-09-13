#!/usr/bin/env python3
"""Fresh paired full-task Q3 execution for B3 multi-disc ON versus OFF."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import multiprocessing as mp
import platform
import random
import statistics
import sys
import time
from pathlib import Path


sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
B3 = ROOT / "最佳方法" / "代码" / "solver.py"
OFF = HERE / "multidisc_off.py"
CASES = ROOT / "evaluation" / "cases_v1.json"
FROZEN = ROOT / "evaluation" / "manifest_v1.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def verify_frozen():
    manifest = load(FROZEN)
    bad = [name for name, digest in manifest["sha256"].items()
           if not (ROOT / name).is_file() or sha(ROOT / name) != digest]
    if bad:
        raise RuntimeError("Frozen LOCAL-v1 input changed: " + repr(bad))
    return manifest


def valid(row):
    return (row["complete"] is True and row["error"] is None
            and row["exit_reason"] == "user_exit"
            and row["cleared_count"] == row["source_count"])


def worker(conn, strategy_path, arm):
    sys.path.insert(0, str(ROOT))
    from local_env import InterfaceOnly, LocalEnv, Source
    spec = importlib.util.spec_from_file_location("fresh_multidisc_" + arm, strategy_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    while True:
        case = conn.recv()
        if case is None:
            break
        # Truth constructs the physical world before the strategy is created.
        # Only InterfaceOnly(env) is passed into the strategy.
        env = LocalEnv([Source(**source) for source in case["sources"]],
                       case["seed"], case["noise"], keep_log=False)
        start = time.perf_counter()
        result = {}
        error = None
        try:
            solver = module.Solver(InterfaceOnly(env), mode=3,
                                   **module.OPTIMIZED_CONFIGS[3])
            result = solver.run()
        except Exception as exc:
            error = type(exc).__name__ + ": " + str(exc)
        elapsed = time.perf_counter() - start
        if env.started and not env.finished:
            env._finish("strategy_exception" if error else "missing_exit")
        # Post-run observer: stats/result are read only after strategy exit.
        stats = env.stats()
        counters = dict(result.get("counters", {}))
        cleared = stats["cleared"]
        row = dict(
            case_id=case["case_id"], arm=arm, mode=3, group=case["group"],
            seed=case["seed"], source_count=stats["n"], cleared_count=cleared,
            seconds_per_source=(stats["time_s"] / cleared if cleared else None),
            total_virtual_time_s=stats["time_s"], measure_count=stats["measures"],
            clear_attempt_count=stats["clear_attempts"],
            failed_clear_count=stats["clear_failures"], distance_m=stats["distance_m"],
            complete=(cleared == stats["n"] and env.exit_reason == "user_exit" and error is None),
            exit_reason=env.exit_reason, error=error,
            coverage_certificate=result.get("coverage_complete", False),
            worker_runtime_s=elapsed,
            two_disk_used=counters.get("two_disk_used", 0),
            three_or_more_disk_used=counters.get("three_disk_used", 0),
            grid_fallback_count=counters.get("fallbacks", 0),
            ablation_bypass_calls=counters.get("multidisc_ablation_bypass_calls", 0),
            counters=counters,
        )
        conn.send(row)
    conn.close()


def run_arm(cases, path, arm, log_path):
    ctx = mp.get_context("spawn")
    parent, child = ctx.Pipe()
    process = ctx.Process(target=worker, args=(child, str(path), arm))
    process.start()
    child.close()
    rows = []
    try:
        with log_path.open("x", encoding="utf-8") as stream:
            for index, case in enumerate(cases, 1):
                parent.send(case)
                if not parent.poll(1205):
                    raise TimeoutError(f"{arm} timed out at {case['case_id']}")
                row = parent.recv()
                if row["case_id"] != case["case_id"]:
                    raise RuntimeError("worker/case ordering mismatch")
                rows.append(row)
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
                if index % 100 == 0:
                    stream.flush()
                    print(json.dumps({"arm": arm, "completed": index,
                                      "failures": sum(not valid(r) for r in rows)},
                                     ensure_ascii=False), flush=True)
    finally:
        if process.is_alive():
            parent.send(None)
        process.join(5)
        if process.is_alive():
            process.terminate()
            process.join()
        parent.close()
    if process.exitcode != 0:
        raise RuntimeError(f"{arm} worker exit code {process.exitcode}")
    return rows


def percentile(values, probability):
    ordered = sorted(values)
    x = probability * (len(ordered) - 1)
    lo = math.floor(x)
    hi = math.ceil(x)
    return ordered[lo] + (x - lo) * (ordered[hi] - ordered[lo])


def seed_cluster_ci(pairs, field, repeats=20000, bootstrap_seed=20260913):
    clusters = {}
    for pair in pairs:
        clusters.setdefault(pair["seed"], []).append(pair)
    if len(clusters) != 100 or set(map(len, clusters.values())) != {12}:
        raise RuntimeError("Expected 100 seed clusters, each spanning 12 scenes")
    seeds = sorted(clusters)
    rng = random.Random(bootstrap_seed)
    draws = []
    for _ in range(repeats):
        selected = [rng.choice(seeds) for _ in seeds]
        differences = [pair[field] for seed in selected for pair in clusters[seed]]
        draws.append(statistics.fmean(differences))
    return dict(method="paired percentile cluster bootstrap by seed across all 12 scenes",
                clusters=len(seeds), cases_per_cluster=12, repeats=repeats,
                bootstrap_seed=bootstrap_seed,
                lower=percentile(draws, 0.025), upper=percentile(draws, 0.975))


def summarize(on_rows, off_rows):
    on = {r["case_id"]: r for r in on_rows}
    off = {r["case_id"]: r for r in off_rows}
    if len(on) != len(off) or set(on) != set(off):
        raise RuntimeError("ON/OFF rows are not ID aligned")
    fields = {
        "delta_seconds_per_source": "seconds_per_source",
        "delta_measure_count": "measure_count",
        "delta_clear_attempt_count": "clear_attempt_count",
        "delta_failed_clear_count": "failed_clear_count",
        "delta_distance_m": "distance_m",
    }
    pairs = []
    for case_id in [r["case_id"] for r in on_rows]:
        a, b = on[case_id], off[case_id]
        if (a["group"], a["seed"], a["source_count"]) != (b["group"], b["seed"], b["source_count"]):
            raise RuntimeError("world identity mismatch: " + case_id)
        pair = dict(case_id=case_id, group=a["group"], seed=a["seed"],
                    source_count=a["source_count"], on_complete=valid(a), off_complete=valid(b))
        for delta_name, raw_name in fields.items():
            pair["on_" + raw_name] = a[raw_name]
            pair["off_" + raw_name] = b[raw_name]
            pair[delta_name] = a[raw_name] - b[raw_name]
        pairs.append(pair)
    all_complete = all(p["on_complete"] and p["off_complete"] for p in pairs)
    comparison = dict(cases=len(pairs), seed_clusters=len({p["seed"] for p in pairs}),
                      all_complete=all_complete,
                      on_complete=sum(p["on_complete"] for p in pairs),
                      off_complete=sum(p["off_complete"] for p in pairs))
    if all_complete:
        for delta_name in fields:
            comparison[delta_name + "_mean"] = statistics.fmean(p[delta_name] for p in pairs)
            comparison[delta_name + "_ci95"] = seed_cluster_ci(pairs, delta_name)
        on_mean = statistics.fmean(r["seconds_per_source"] for r in on_rows)
        off_mean = statistics.fmean(r["seconds_per_source"] for r in off_rows)
        comparison.update(
            on_mean_seconds_per_source=on_mean,
            off_mean_seconds_per_source=off_mean,
            improvement_percent=100 * (off_mean - on_mean) / off_mean,
            faster_cases=sum(p["delta_seconds_per_source"] < -1e-9 for p in pairs),
            equal_cases=sum(abs(p["delta_seconds_per_source"]) <= 1e-9 for p in pairs),
            slower_cases=sum(p["delta_seconds_per_source"] > 1e-9 for p in pairs),
            on_total_measures=sum(r["measure_count"] for r in on_rows),
            off_total_measures=sum(r["measure_count"] for r in off_rows),
            on_total_clear_attempts=sum(r["clear_attempt_count"] for r in on_rows),
            off_total_clear_attempts=sum(r["clear_attempt_count"] for r in off_rows),
            on_total_failed_clears=sum(r["failed_clear_count"] for r in on_rows),
            off_total_failed_clears=sum(r["failed_clear_count"] for r in off_rows),
            on_total_distance_m=sum(r["distance_m"] for r in on_rows),
            off_total_distance_m=sum(r["distance_m"] for r in off_rows),
            on_adaptive_multidisc_executions=sum(r["two_disk_used"] + r["three_or_more_disk_used"] for r in on_rows),
            off_adaptive_multidisc_executions=sum(r["two_disk_used"] + r["three_or_more_disk_used"] for r in off_rows),
            off_bypass_calls=sum(r["ablation_bypass_calls"] for r in off_rows),
        )
    return pairs, comparison


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    verify_frozen()
    registered = load(HERE / "registration.json")
    for name, digest in registered["pinned_sha256"].items():
        if sha(ROOT / name) != digest:
            raise RuntimeError("Registered input changed: " + name)
    if sha(OFF) != registered["artifact_sha256"]["multidisc_off.py"]:
        raise RuntimeError("OFF implementation changed after registration")
    cases = [case for case in load(CASES) if case["mode"] == 3]
    if len(cases) != 1200 or len({c["case_id"] for c in cases}) != 1200:
        raise RuntimeError("Expected exactly 1200 frozen Q3 cases")
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=False)
    execution = dict(label="fresh LOCAL-v1 Q3 full-task paired ablation; exposed local regression",
                     cases=1200, arms=["on", "off"], planned_fresh_runs=2400,
                     case_ids=[c["case_id"] for c in cases], cases_sha256=sha(CASES),
                     b3_sha256=sha(B3), off_sha256=sha(OFF), runner_sha256=sha(__file__),
                     registration_sha256=sha(HERE / "registration.json"),
                     python=platform.python_version(), platform=platform.platform())
    save(output / "execution_registration.json", execution)
    start = time.perf_counter()
    on_rows = run_arm(cases, B3, "on", output / "on_rows.jsonl")
    off_rows = run_arm(cases, OFF, "off", output / "off_rows.jsonl")
    pairs, comparison = summarize(on_rows, off_rows)
    save(output / "paired_rows.json", pairs)
    save(output / "on_rows.json", on_rows)
    save(output / "off_rows.json", off_rows)
    verify_frozen()
    if sha(B3) != execution["b3_sha256"] or sha(OFF) != execution["off_sha256"] or sha(__file__) != execution["runner_sha256"]:
        raise RuntimeError("Executable input changed during run")
    summary = dict(**execution, actual_fresh_runs=len(on_rows) + len(off_rows),
                   wall_seconds=time.perf_counter() - start, comparison=comparison)
    save(output / "summary.json", summary)
    print(json.dumps(comparison, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
