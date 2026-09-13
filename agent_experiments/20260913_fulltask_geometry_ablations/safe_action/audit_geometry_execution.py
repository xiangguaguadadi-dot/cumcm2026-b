#!/usr/bin/env python3
"""Replay registered arms and independently retain every certified polygon vertex."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from local_env import InterfaceOnly, LocalEnv, Source
import evaluate


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path): return json.loads(Path(path).read_text())
def dump(path, value): Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def import_arm(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def key(ch, q): return int(ch), round(float(q[0]), 8), round(float(q[1]), 8)


def main():
    reg = load(HERE / "registration.json")
    for item in reg["frozen_inputs"]:
        assert sha(ROOT / item["path"]) == item["sha256"]
    for item in reg["arms"].values():
        assert sha(HERE / item["path"]) == item["sha256"]
    evaluate.verify()
    expected_rows = [json.loads(x) for x in (HERE / "full_1200/rows.jsonl").read_text().splitlines()]
    expected = {(r["arm"], r["case_id"]): r for r in expected_rows}
    cases = [c for c in load(ROOT / "evaluation/cases_v1.json") if c["mode"] == 3]
    assert len(cases) == 1200
    output = HERE / "full_1200/execution_geometry_audit.jsonl"
    assert not output.exists()
    audit_count = 0
    maximum_distance = 0.0
    all_actual_actions_matched = True
    all_replays_exact = True
    started = time.perf_counter()
    with output.open("w") as stream:
        for arm, item in reg["arms"].items():
            module = import_arm(HERE / item["path"], "geometry_execution_audit_" + arm)
            cls = module._B3._G._LensSpatial
            registered_method = cls.route_clear_point

            def observing(self, center, radius, original, _registered=registered_method, _arm=arm):
                q = _registered(self, center, radius, original)
                ch = getattr(self, "_active_target", None)
                poly = self.polygons.get(ch) if ch is not None else None
                if radius <= 20.0 + 1e-9 and poly:
                    self.execution_geometry_audit = getattr(self, "execution_geometry_audit", [])
                    self.execution_geometry_audit.append({
                        "arm": _arm, "channel": ch, "mec_center": list(center),
                        "mec_radius_m": radius, "selected_point": list(q),
                        "feasible_polygon_vertices": [list(v) for v in poly],
                    })
                return q

            cls.route_clear_point = observing
            for i, case in enumerate(cases, 1):
                env = LocalEnv([Source(**s) for s in case["sources"]], case["seed"], case["noise"], keep_log=False)
                solver = module.Solver(InterfaceOnly(env), mode=3, **module.OPTIMIZED_CONFIGS[3])
                error = None
                try: result = solver.run()
                except Exception as exc:
                    error = type(exc).__name__ + ": " + str(exc); result = {}
                stats = env.stats()
                expected_row = expected[(arm, case["case_id"])]
                exact = (error is None and env.exit_reason == "user_exit" and stats["cleared"] == stats["n"]
                         and abs(stats["time_s"] - expected_row["total_virtual_time_s"]) <= 1e-12)
                all_replays_exact &= exact
                actual = Counter(key(t["channel"], (t["x"], t["y"])) for t in solver.trace
                                 if t.get("action") == "clear" and t.get("certified_before_action") is True)
                events = getattr(solver, "execution_geometry_audit", [])
                needed = Counter(key(a["channel"], a["selected_point"]) for a in events)
                matched = all(actual[k] >= n for k, n in needed.items())
                all_actual_actions_matched &= matched
                for event_index, audit in enumerate(events):
                    q = audit["selected_point"]
                    distances = [math.dist(q, v) for v in audit["feasible_polygon_vertices"]]
                    maximum = max(distances)
                    maximum_distance = max(maximum_distance, maximum)
                    center_exact = math.dist(q, audit["mec_center"]) <= 1e-12 if arm == "mec_center" else None
                    row = {"case_id": case["case_id"], "group": case["group"], "seed_cluster": case["seed"],
                           "event_index": event_index, **audit,
                           "maximum_vertex_distance_m_recomputed": maximum,
                           "all_vertices_covered_recomputed": maximum <= 20.0 + 1e-8,
                           "selected_point_was_actual_certified_clear": actual[key(audit["channel"], q)] > 0,
                           "center_point_exact": center_exact, "exact_primary_result_replay": exact}
                    stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                    audit_count += 1
                assert matched and exact
                if i % 200 == 0:
                    print(f"{arm}: {i}/1200", flush=True)
    summary = {
        "purpose": "independent vertex-level audit replay of the exact registered policies; duplicate deterministic worlds, not additional independent evidence",
        "arms": 2, "worlds_per_arm": 1200, "duplicate_audit_replay_executions": 2400,
        "events": audit_count, "all_primary_virtual_times_reproduced_exactly": all_replays_exact,
        "all_selected_points_matched_actual_certified_clear_actions": all_actual_actions_matched,
        "all_vertices_covered": maximum_distance <= 20.0 + 1e-8,
        "maximum_vertex_distance_m": maximum_distance,
        "all_mec_arm_points_exact": all(json.loads(x)["center_point_exact"] is not False
                                        for x in output.read_text().splitlines()),
        "truth_not_passed_to_solver": True,
        "planner_interface": "InterfaceOnly(enter, measure, clear, exit)",
        "elapsed_wall_s": time.perf_counter() - started,
    }
    dump(HERE / "full_1200/execution_geometry_audit_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__": main()
