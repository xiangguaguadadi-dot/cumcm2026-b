"""Execute preregistered Q3-only B3 information/control ablations."""
from __future__ import annotations
import argparse, hashlib, json, math, platform, statistics, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
import evaluate

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text())
def save(p, x): Path(p).write_text(json.dumps(x, ensure_ascii=False, indent=2) + "\n")
def valid(r):
    return r.get("complete") is True and r.get("exit_reason") == "user_exit" and r.get("error") is None and r.get("cleared_count") == r.get("source_count")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--candidate",type=Path,required=True)
    ap.add_argument("--suite",choices=("quick","full"),required=True); ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args(); evaluate.verify()
    reg=load(HERE/"registration.json"); parent=ROOT/reg["inputs"]["parent"]["path"]
    for item in reg["inputs"].values():
        assert sha(ROOT/item["path"]) == item["sha256"], item["path"]
    candidate=a.candidate.resolve(); cand_sha=sha(candidate); runner_sha=sha(__file__)
    cases=[c for c in load(ROOT/"evaluation/cases_v1.json") if c["mode"]==3 and (a.suite=="full" or c["quick"])]
    assert len(cases)==(1200 if a.suite=="full" else 60)
    out=a.out.resolve(); out.mkdir(parents=True,exist_ok=False)
    save(out/"invocation.json", {"candidate":str(candidate),"candidate_sha256":cand_sha,"runner_sha256":runner_sha,"suite":a.suite,"planned_runs":len(cases),"case_ids":[c["case_id"] for c in cases]})
    start=time.perf_counter(); rows=evaluate.run_cases(cases,candidate,False)
    assert sha(candidate)==cand_sha and sha(__file__)==runner_sha; evaluate.verify()
    base_all=load(parent.parent/"results/B3_full/case_metrics.json")
    base={r["case_id"]:r for r in base_all}; assert all(c["case_id"] in base for c in cases)
    for r,c in zip(rows,cases): assert r["case_id"]==c["case_id"]
    pairs=[]
    for r in rows:
        b=base[r["case_id"]]
        av=r["total_virtual_time_s"]/r["cleared_count"] if valid(r) else None
        bv=b["total_virtual_time_s"]/b["cleared_count"] if valid(b) else None
        pairs.append({"case_id":r["case_id"],"group":r["group"],"seed_cluster":int(r["case_id"].rsplit("-",1)[1]),
                      "candidate_s_per_source":av,"b3_s_per_source":bv,"delta_s_per_source":None if av is None or bv is None else av-bv,
                      "candidate_complete":valid(r),"b3_complete":valid(b),"candidate_requests":r.get("requests"),"b3_requests":b.get("requests"),
                      "candidate_distance_m":r.get("distance_m"),"b3_distance_m":b.get("distance_m"),
                      "candidate_clear_failures":r.get("clear_failures"),"b3_clear_failures":b.get("clear_failures")})
    ds=[p["delta_s_per_source"] for p in pairs if p["delta_s_per_source"] is not None]
    # Deterministic seed-cluster bootstrap, preserving 12-scenario dependence.
    import random
    clusters=sorted({p["seed_cluster"] for p in pairs}); by={s:[p["delta_s_per_source"] for p in pairs if p["seed_cluster"]==s] for s in clusters}
    rng=random.Random(20260913); boots=[]
    for _ in range(10000):
        chosen=[rng.choice(clusters) for __ in clusters]; boots.append(statistics.fmean(x for s in chosen for x in by[s]))
    boots.sort(); lo=boots[249]; hi=boots[9749]
    summary={"label":"B3 Q3 component ablation on exposed local v1 worlds; not blind or official","suite":a.suite,"candidate_sha256":cand_sha,
             "parent_sha256":sha(parent),"evaluation_manifest_sha256":sha(ROOT/"evaluation/manifest_v1.json"),"python":platform.python_version(),
             "actual_runs":len(rows),"all_candidate_complete":all(valid(r) for r in rows),"all_parent_complete":all(valid(base[r["case_id"]]) for r in rows),
             "cases":len(pairs),"sources":sum(r["source_count"] for r in rows),"candidate_mean_s_per_source":statistics.fmean(p["candidate_s_per_source"] for p in pairs),
             "b3_mean_s_per_source":statistics.fmean(p["b3_s_per_source"] for p in pairs),"candidate_minus_b3_mean_s_per_source":statistics.fmean(ds),
             "b3_improvement_s_per_source":-statistics.fmean(ds),"cluster_bootstrap_95pct_delta":[lo,hi],
             "faster":sum(d < -1e-8 for d in ds),"equal":sum(abs(d)<=1e-8 for d in ds),"slower":sum(d>1e-8 for d in ds),
             "candidate_requests":sum(r.get("requests",0) for r in rows),"b3_requests":sum(base[r["case_id"]].get("requests",0) for r in rows),
             "candidate_distance_m":sum(r.get("distance_m",0) for r in rows),"b3_distance_m":sum(base[r["case_id"]].get("distance_m",0) for r in rows),
             "candidate_clear_failures":sum(r.get("clear_failures",0) for r in rows),"b3_clear_failures":sum(base[r["case_id"]].get("clear_failures",0) for r in rows),
             "wall_seconds":time.perf_counter()-start}
    save(out/"rows.json",rows); save(out/"pairs.json",pairs); save(out/"summary.json",summary); print(json.dumps(summary,ensure_ascii=False))
if __name__=="__main__": main()
