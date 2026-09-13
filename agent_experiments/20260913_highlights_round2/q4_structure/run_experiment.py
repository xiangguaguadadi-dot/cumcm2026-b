"""Preregistered Q4 count-stop ablation and post-clear heading audit.

Truth is used only after a run to score the heading certificate.  The solver
itself is the frozen C7 candidate and receives only enter/measure/clear/exit.
"""
import argparse, hashlib, importlib.util, json, math, multiprocessing as mp
import platform, random, statistics, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
C7 = ROOT / "experiments/20260911_stage4/combination/geometry_fusions/C7_both.py"
TAU = 2 * math.pi

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path, value): path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")

def frozen_check():
    manifest_path = ROOT / "evaluation/manifest_v1.json"
    manifest = json.loads(manifest_path.read_text())
    bad = [p for p, h in manifest["sha256"].items()
           if not (ROOT / p).is_file() or sha(ROOT / p) != h]
    if bad: raise RuntimeError("frozen evaluation mismatch: " + repr(bad))
    return {"manifest_sha256": sha(manifest_path), "files": len(manifest["sha256"]), "mismatches": bad}

def split_arc(center, halfwidth):
    if halfwidth >= math.pi: return [(0.0, TAU)]
    lo, hi = (center - halfwidth) % TAU, (center + halfwidth) % TAU
    return [(lo, hi)] if lo <= hi else [(0.0, hi), (lo, TAU)]

def intersect(a, b):
    out = []
    for x, y in a:
        for u, v in b:
            lo, hi = max(x, u), min(y, v)
            if lo <= hi + 1e-12: out.append((lo, hi))
    out.sort()
    merged = []
    for lo, hi in out:
        if merged and lo <= merged[-1][1] + 1e-12: merged[-1][1] = max(merged[-1][1], hi)
        else: merged.append([lo, hi])
    return [tuple(x) for x in merged]

def contains(intervals, angle):
    a = angle % TAU
    return any(lo - 1e-10 <= a <= hi + 1e-10 for lo, hi in intervals)

def heading_certificate(source, trace):
    ch = source["channel"]
    positive = [(e["x"], e["y"]) for e in trace
                if e.get("action") == "measure" and e.get("channel") == ch
                and e.get("result") in ("direction", "near")]
    successes = [(e["x"], e["y"]) for e in trace
                 if e.get("action") == "clear" and e.get("channel") == ch
                 and e.get("result") == "success"]
    if not successes: return {"channel": ch, "status": "not_cleared"}
    clear = successes[-1]
    feasible = [(0.0, TAU)]
    informative = 0
    for p in positive:
        dx, dy = p[0] - clear[0], p[1] - clear[1]
        d = math.hypot(dx, dy)
        if d <= 20.000001: continue
        # Successful clear gives |s-clear|<=20 m.  Widen the receive half-plane
        # by the exact tangent angle so the true source heading is retained.
        delta = math.asin(min(1.0, 20.000001 / d)) + 1e-12
        feasible = intersect(feasible, split_arc(math.atan2(dy, dx), math.pi / 2 + delta))
        informative += 1
        if not feasible: break
    width = sum(hi - lo for lo, hi in feasible)
    direction = source.get("direction")
    return {"channel": ch, "true_type": "omni" if direction is None else "directional",
            "positive_sites": len(positive), "informative_sites": informative,
            "clear_point": list(clear), "feasible_intervals_rad": [list(x) for x in feasible],
            "feasible_width_deg": math.degrees(width), "omni_certificate": not feasible,
            "true_heading_retained": None if direction is None else contains(feasible, direction)}

def load_c7(name):
    spec = importlib.util.spec_from_file_location(name, C7)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def worker(conn):
    sys.path.insert(0, str(ROOT))
    from local_env import LocalEnv, Source, InterfaceOnly
    mod = load_c7("q4_structure_c7")
    while True:
        job = conn.recv()
        if job is None: break
        case, arm = job
        env = LocalEnv([Source(**s) for s in case["sources"]], case["seed"], case["noise"], keep_log=False)
        config = dict(mod.OPTIMIZED_CONFIGS[4])
        config["upper_bound_stop"] = arm == "count_stop"
        state = mod.Solver(InterfaceOnly(env), mode=4, **config)
        error = None; result = {}; started = time.perf_counter()
        try: result = state.run()
        except Exception as exc: error = type(exc).__name__ + ": " + str(exc)
        runtime = time.perf_counter() - started
        if env.started and not env.finished: env._finish("strategy_exception" if error else "missing_exit")
        stats = env.stats()
        heading = [heading_certificate(s, state.trace) for s in case["sources"]]
        row = {"case_id": case["case_id"], "group": case["group"], "seed": case["seed"],
               "arm": arm, "source_count": stats["n"], "cleared_count": stats["cleared"],
               "complete": stats["cleared"] == stats["n"] and env.exit_reason == "user_exit" and error is None,
               "total_virtual_time_s": stats["time_s"], "average_clear_time_s": stats["average_s"],
               "distance_m": stats["distance_m"], "measures": stats["measures"], "switches": stats["switches"],
               "clear_attempts": stats["clear_attempts"], "error": error, "exit_reason": env.exit_reason,
               "certificate_type": result.get("certificate_type"), "visited_station_count": len(result.get("visited_points", [])),
               "stations_removed_after_discovery": state.counters.get("stations_removed_after_discovery", 0),
               "program_runtime_s": runtime, "heading_certificates": heading}
        conn.send(row)
    conn.close()

def pressure_cases():
    cases = []
    for j in range(24):
        sources = []
        for k in range(16):
            a = TAU * (k / 16 + j / 384)
            r = 1800.0 if k % 2 == 0 else 1000.0 + 800.0 * ((3 * k + j) % 17) / 16
            direction = None if k == 0 else (a + [0, math.pi/2, math.pi][j % 3]) % TAU
            sources.append({"channel": k + 1, "x": r*math.cos(a), "y": r*math.sin(a),
                            "radius": 1000.0, "direction": direction})
        cases.append({"case_id": f"CONSTRUCTED-count-heading-{j:02d}", "mode": 4,
                      "group": ["outward", "tangent", "inward"][j % 3],
                      "seed": 91420000 + j, "noise": ["positive", "negative", "cell_50"][j % 3],
                      "sources": sources})
    return cases

def ci95(values, seed=20260913):
    rng = random.Random(seed); n = len(values)
    means = [statistics.mean(values[rng.randrange(n)] for _ in range(n)) for _ in range(5000)]
    means.sort(); return [means[124], means[4874]]

def summarize(rows, suite):
    groups = {}
    for arm in ("count_stop", "no_count_stop"):
        z = [r for r in rows if r["arm"] == arm]
        headings = [h for r in z for h in r["heading_certificates"]]
        directional = [h for h in headings if h.get("true_type") == "directional"]
        omni = [h for h in headings if h.get("true_type") == "omni"]
        groups[arm] = {"worlds": len(z), "complete": sum(r["complete"] for r in z),
          "sources": sum(r["source_count"] for r in z), "cleared": sum(r["cleared_count"] for r in z),
          "mean_s_per_source": statistics.mean(r["average_clear_time_s"] for r in z),
          "total_virtual_time_s": sum(r["total_virtual_time_s"] for r in z),
          "distance_m": sum(r["distance_m"] for r in z), "measures": sum(r["measures"] for r in z),
          "switches": sum(r["switches"] for r in z),
          "visited_stations": sum(r["visited_station_count"] for r in z),
          "removed_stations": sum(r["stations_removed_after_discovery"] for r in z),
          "directional_sources": len(directional),
          "directional_true_heading_retained": sum(h.get("true_heading_retained") is True for h in directional),
          "directional_empty_intervals": sum(h.get("omni_certificate") is True for h in directional),
          "omni_sources": len(omni), "omni_certified": sum(h.get("omni_certificate") is True for h in omni),
          "directional_median_width_deg": statistics.median(h["feasible_width_deg"] for h in directional)}
    by_id = {(r["case_id"], r["arm"]): r for r in rows}
    ids = sorted({r["case_id"] for r in rows})
    diffs = [by_id[(i,"count_stop")]["average_clear_time_s"] - by_id[(i,"no_count_stop")]["average_clear_time_s"] for i in ids]
    pairs = [{"case_id": i, "count_stop_minus_no_stop_s_per_source": d} for i,d in zip(ids,diffs)]
    return {"status": "complete", "suite": suite, "worlds": len(ids), "executions": len(rows),
      "all_complete": all(r["complete"] for r in rows), "arms": groups,
      "paired_count_stop_minus_no_stop_mean_s_per_source": statistics.mean(diffs),
      "paired_bootstrap_95_ci_s_per_source": ci95(diffs),
      "count_stop_better_worlds": sum(d < -1e-9 for d in diffs),
      "ties": sum(abs(d) <= 1e-9 for d in diffs), "count_stop_worse_worlds": sum(d > 1e-9 for d in diffs)}, pairs

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--suite", choices=("quick","full","pressure"), required=True)
    ap.add_argument("--out", required=True); args = ap.parse_args()
    out = HERE / args.out; out.mkdir(parents=True, exist_ok=False)
    frozen = frozen_check()
    if args.suite == "pressure": cases = pressure_cases()
    else:
        cases = [c for c in json.loads((ROOT/"evaluation/cases_v1.json").read_text())
                 if c["mode"] == 4 and (args.suite == "full" or c["quick"])]
    dump(out/"cases.json", cases)
    registration = {"suite": args.suite, "worlds": len(cases), "arms": ["count_stop","no_count_stop"],
      "planned_runs": 2*len(cases), "world_role": "constructed pressure" if args.suite == "pressure" else "exposed frozen v1 regression",
      "hypotheses": ["The <=16 cardinality certificate safely removes remaining discovery stations after 16 distinct channels are found.",
                     "Positive receive sites plus a successful clear point yield a continuous conservative heading interval; an empty interval certifies omni emission."],
      "primary_estimand": "paired count_stop minus no_count_stop seconds/source over all worlds",
      "promotion_gate": "all tasks complete; paired mean < 0 and 95% world-bootstrap upper bound < 0",
      "heading_gate": "zero directional exclusions; report omni certificate precision and recall without tuning",
      "c7_sha256": sha(C7), "runner_sha256": sha(Path(__file__)), "cases_sha256": sha(out/"cases.json"),
      "frozen_before": frozen, "python": platform.python_version()}
    dump(out/"registration.json", registration)
    ctx=mp.get_context("spawn"); a,b=ctx.Pipe(); proc=ctx.Process(target=worker,args=(b,));proc.start();b.close()
    rows=[]; start=time.perf_counter()
    try:
        with (out/"rows.jsonl").open("w") as f:
            for i,case in enumerate(cases):
                arms=("count_stop","no_count_stop") if i%2==0 else ("no_count_stop","count_stop")
                for arm in arms:
                    a.send((case,arm))
                    if not a.poll(1205): raise RuntimeError("worker timeout")
                    row=a.recv(); rows.append(row); f.write(json.dumps(row,separators=(",",":"))+"\n");f.flush()
                if (i+1)%25==0: print(args.suite,i+1,"/",len(cases),"worlds",round(time.perf_counter()-start,1),"s",flush=True)
    finally:
        if proc.is_alive(): a.send(None)
        proc.join(3)
        if proc.is_alive(): proc.terminate();proc.join()
        a.close()
    if sha(C7)!=registration["c7_sha256"] or sha(Path(__file__))!=registration["runner_sha256"]: raise RuntimeError("code changed during run")
    summary,pairs=summarize(rows,args.suite); summary["wall_s"]=time.perf_counter()-start
    summary["rows_sha256"]=sha(out/"rows.jsonl");summary["frozen_after"]=frozen_check()
    dump(out/"pairs.json",pairs);dump(out/"summary.json",summary);print(json.dumps(summary,ensure_ascii=False))

if __name__ == "__main__": main()
