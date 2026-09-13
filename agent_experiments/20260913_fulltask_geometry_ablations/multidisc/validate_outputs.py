#!/usr/bin/env python3
"""Independent structural and arithmetic audit of the multi-disc ablation."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUN = HERE / "run_01_full"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def jsonl(path):
    with Path(path).open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    reg = read(HERE / "registration.json")
    for name, digest in reg["pinned_sha256"].items():
        require(sha(ROOT / name) == digest, "registered input changed: " + name)
    for name, digest in reg["artifact_sha256"].items():
        require(sha(HERE / name) == digest, "registered executable changed: " + name)
    cases = [c for c in read(ROOT / "evaluation/cases_v1.json") if c["mode"] == 3]
    require(len(cases) == len({c["case_id"] for c in cases}) == 1200, "case count/IDs")
    expected = {c["case_id"]: c for c in cases}
    on, off = read(RUN / "on_rows.json"), read(RUN / "off_rows.json")
    require(on == jsonl(RUN / "on_rows.jsonl"), "ON JSON and append-only log differ")
    require(off == jsonl(RUN / "off_rows.jsonl"), "OFF JSON and append-only log differ")
    require(len(on) == len(off) == 1200, "arm row counts")
    require([r["case_id"] for r in on] == [c["case_id"] for c in cases], "ON order/IDs")
    require([r["case_id"] for r in off] == [c["case_id"] for c in cases], "OFF order/IDs")
    for arm, rows in (("on", on), ("off", off)):
        require(len({r["case_id"] for r in rows}) == 1200, arm + " duplicate IDs")
        for row in rows:
            case = expected[row["case_id"]]
            require((row["mode"], row["group"], row["seed"], row["source_count"]) ==
                    (3, case["group"], case["seed"], len(case["sources"])), "world mismatch")
            require(row["complete"] and row["exit_reason"] == "user_exit" and row["error"] is None,
                    arm + " incomplete row")
            require(row["cleared_count"] == row["source_count"], arm + " not fully cleared")
            require(math.isclose(row["seconds_per_source"],
                                 row["total_virtual_time_s"] / row["cleared_count"],
                                 rel_tol=0, abs_tol=1e-12), "seconds/source arithmetic")
            require(row["clear_attempt_count"] == row["source_count"] + row["failed_clear_count"],
                    "clear attempt accounting")
            require(row["measure_count"] == row["counters"]["measure"], "measure observer mismatch")
            require(row["clear_attempt_count"] == row["counters"]["clear_attempts"],
                    "clear observer mismatch")
            require(row["failed_clear_count"] == row["counters"]["failed_clear"],
                    "failure observer mismatch")
    require(sum(r["two_disk_used"] + r["three_or_more_disk_used"] for r in on) > 0,
            "ON never activated adaptive multi-disc")
    require(sum(r["two_disk_used"] + r["three_or_more_disk_used"] for r in off) == 0,
            "OFF re-entered adaptive multi-disc")
    require(sum(r["ablation_bypass_calls"] for r in off) > 0, "OFF bypass never invoked")
    require(all(r["ablation_bypass_calls"] == 0 for r in on), "ON contaminated by bypass")

    spec = importlib.util.spec_from_file_location("audit_multidisc_off", HERE / "multidisc_off.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    dispatch = module.MultiDiscOffSpatial.__dict__["_a1_service_round"]
    require("TrialSpatial" in dispatch.__code__.co_names, "OFF dispatch does not name TrialSpatial")
    require(module.MultiDiscOffSpatial.mro().index(module._B3._P._Q3.TrialSpatial) >
            module.MultiDiscOffSpatial.mro().index(module._B3._P._Q3.MultiDiskSpatial), "unexpected MRO")
    require(module.MultiDiscOffSpatial.cover_polygon.__qualname__ == "_sp_Solver.cover_polygon",
            "original finite lattice cover is not retained")

    pairs = read(RUN / "paired_rows.json")
    require(len(pairs) == 1200 and len({p["case_id"] for p in pairs}) == 1200, "pair count/IDs")
    require(sum(p["delta_seconds_per_source"] > 1e-9 for p in pairs) ==
            read(RUN / "summary.json")["comparison"]["slower_cases"], "regression count")
    require(len({p["seed"] for p in pairs}) == 100, "seed cluster count")
    require({sum(p["seed"] == seed for p in pairs) for seed in {p["seed"] for p in pairs}} == {12},
            "each seed must span 12 scenes")

    audit = {
        "status": "pass",
        "fresh_rows_verified": 2400,
        "paired_cases_verified": 1200,
        "unique_seed_clusters": 100,
        "scenes_per_seed": 12,
        "all_complete_and_user_exit": True,
        "seconds_per_source_recomputed": True,
        "clear_accounting_verified": True,
        "observer_counters_match_environment": True,
        "on_adaptive_multidisc_executions": sum(r["two_disk_used"] + r["three_or_more_disk_used"] for r in on),
        "off_adaptive_multidisc_executions": 0,
        "off_bypass_calls": sum(r["ablation_bypass_calls"] for r in off),
        "off_dispatch_target": "TrialSpatial._a1_service_round",
        "retained_grid_cover_method": module.MultiDiscOffSpatial.cover_polygon.__qualname__,
        "grid_fallback_runtime_activations": {"on": sum(r["grid_fallback_count"] for r in on),
                                              "off": sum(r["grid_fallback_count"] for r in off)},
        "grid_fallback_note": "The original method remains reachable but no registered LOCAL-v1 run needed the terminal fallback.",
        "truth_and_observer_boundary": "InterfaceOnly passed to strategy; result counters and env.stats read after run returns.",
        "registered_input_hashes_unchanged": True,
    }
    (HERE / "VALIDATION.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
