"""Independent committed-atlas ID, source, arithmetic, and ancestry audit."""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
import math
import statistics
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def audit(wt, commit):
    def load(name):
        return json.loads(subprocess.check_output(["git", "show", commit + ":experiments/R1_atlas/" + name], cwd=wt))
    graph = load("exploration_graph.json")
    index = load("exploration_index.json")
    nodes = {n["id"]: n for n in graph["nodes"]}
    assert len(nodes) == len(graph["nodes"])
    assert {n["id"] for n in index["nodes"]} == set(nodes)
    for entry in index["nodes"]:
        assert load(entry["details"]) == nodes[entry["id"]]
        assert entry["retained_best_after_round"] == nodes[entry["id"]].get("retained_best_after_round")
    sources = {s["id"]: s for s in graph["sources"]}
    for s in sources.values():
        assert sha(Path(s["absolute_path"]).read_bytes()) == s["sha256"], s["absolute_path"]
    expected = {f"{r['agent']}_R{r['round']}" for r in json.loads((ROOT / "experiments/20260911_agent_campaign/all_rounds.json").read_text())["rounds"]}
    expected |= {k.replace(" ", "_") for k in json.loads((ROOT / "experiments/20260911_breakthrough/stage_registry.json").read_text())["candidates"]}
    assert {n["id"] for n in nodes.values() if n["kind"] == "completed_optimization_round"} == expected
    bases = {
        "R0": json.loads((ROOT / "evaluation/baseline_metrics_v1.json").read_text())["rows"],
        "C0": json.loads((ROOT / "experiments/20260911_breakthrough/baseline/equivalence/case_metrics.json").read_text()),
        "S0": json.loads((ROOT / "experiments/20260911_stage3/baseline/expected_rows.json").read_text()),
    }
    checks = []
    all_cells = 0
    raw_count = 0
    for n in nodes.values():
        assert all(s in sources for s in n["sources"])
        if n["kind"] not in ("completed_optimization_round", "completed_stage3_round"):
            continue
        candidate = Path(n["candidate"]["absolute_path"])
        assert sha(candidate.read_bytes()) == n["candidate"]["sha256"]
        candidate_root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=candidate.parent, text=True).strip())
        blob = subprocess.check_output(["git", "show", n["candidate"]["commit"] + ":" + candidate.relative_to(candidate_root).as_posix()], cwd=candidate_root)
        assert sha(blob) == n["candidate"]["sha256"]
        paths = [Path(sources[s]["absolute_path"]) for s in n["sources"] if Path(sources[s]["absolute_path"]).name == "case_metrics.json"]
        rows = None
        for p in paths:
            rr = json.loads(p.read_text())
            if isinstance(rr, list):
                rr = [r for r in rr if r.get("variant", "candidate") == "candidate"]
                if len(rr) in (2400, 4800):
                    rows = rr
                    break
        assert rows is not None, n["id"]
        assert len({r["case_id"] for r in rows}) == len(rows)
        base = {r["case_id"]: r for r in bases[n["comparison_baseline"]]}
        assert set(base) == {r["case_id"] for r in rows}
        for r in rows:
            assert r["complete"] and not r["error"] and r["exit_reason"] == "user_exit"
            assert r["source_count"] == r["cleared_count"] == base[r["case_id"]]["source_count"]
            assert math.isclose(r["average_clear_time_s"], r["total_virtual_time_s"] / r["source_count"], abs_tol=1e-8)
        for cell in n["effects"]:
            part = [r for r in rows if r["mode"] == cell["mode"] and (cell["group"] == "ALL" or r["group"] == cell["group"])
                    and (cell["suite"] == "combined" or r.get("exposure_suite", "v1") == cell["suite"])]
            assert len(part) == cell["cases"] == cell["complete_cases"]
            assert sum(r["source_count"] for r in part) == cell["source_count"] == cell["cleared_count"]
            cv = statistics.fmean(r["average_clear_time_s"] for r in part)
            bv = statistics.fmean(base[r["case_id"]]["average_clear_time_s"] for r in part)
            assert math.isclose(cv, cell["mean_s_per_source"], abs_tol=1e-8)
            assert math.isclose(bv, cell["baseline_mean_s_per_source"], abs_tol=1e-8)
            assert math.isclose(cv-bv, cell["delta_s_per_source"], abs_tol=1e-8)
            delta = [r["average_clear_time_s"] - base[r["case_id"]]["average_clear_time_s"] for r in part]
            assert [sum(d < -1e-9 for d in delta), sum(abs(d) <= 1e-9 for d in delta), sum(d > 1e-9 for d in delta)] == [cell[k] for k in ("faster", "equal", "slower")]
        checks.append(dict(node=n["id"], raw_rows=len(rows), cells=len(n["effects"]), code_blob_verified=True))
        raw_count += len(rows)
        all_cells += len(n["effects"])
    retention = []
    for direction in (d["id"] for d in graph["directions"] if d["stage"] == 1):
        rr = sorted([n for n in nodes.values() if direction in n.get("direction_tags", [])], key=lambda n: n["round"])
        best = "R0"
        mean = [next(c["baseline_mean_s_per_source"] for c in rr[0]["effects"] if c["mode"] == m and c["group"] == "ALL") for m in (3, 4)]
        for n in rr:
            current = [next(c["mean_s_per_source"] for c in n["effects"] if c["mode"] == m and c["group"] == "ALL") for m in (3, 4)]
            assert n["retained_best_before_round"] == best
            if all(x <= y+1e-9 for x, y in zip(current, mean)) and any(x < y-1e-9 for x, y in zip(current, mean)):
                mean, best = current, n["id"]
            assert n["retained_best_after_round"] == best
            returns = [e["target"] for e in graph["edges"] if e["source"] == n["id"] and e["type"] == "reverts_to"]
            assert returns == ([] if best == n["id"] else [best])
            retention.append(dict(node=n["id"], retained=best))
    degree = {n: 0 for n in nodes}
    adj = collections.defaultdict(list)
    for e in graph["edges"]:
        assert e["source"] in nodes and e["target"] in nodes
        if e["type"] in ("fusion", "derived_from", "iteration"):
            adj[e["source"]].append(e["target"])
            degree[e["target"]] += 1
    queue = [n for n, d in degree.items() if not d]
    seen = []
    while queue:
        n = queue.pop(); seen.append(n)
        for child in adj[n]:
            degree[child] -= 1
            if not degree[child]:
                queue.append(child)
    assert len(seen) == len(nodes)
    return dict(status="pass", commit=commit, graph_nodes=len(nodes), historical_rounds=len(expected),
                total_frozen_rounds=len(checks), source_hashes=len(sources), source_reference_integrity=True,
                candidate_raw_rows_recomputed=raw_count, effect_cells_recomputed=all_cells, retention=retention,
                index_matches=True, implementation_dag_acyclic=True, checks=checks,
                limits="Arithmetic, source identities, ancestry references and historical joint-best rules. No new policy runs, no new geometry proof, no manual replay of every trajectory. Legacy final validation matrices were audited during original delivery and remain separately labeled in the graph.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--worktree", required=True)
    p.add_argument("--commit", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    result = audit(Path(a.worktree).resolve(), a.commit)
    Path(a.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("checks", "retention")}))
