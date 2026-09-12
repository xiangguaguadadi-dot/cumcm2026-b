#!/usr/bin/env python3
"""Validate only saved S6 graph artifacts and source hashes. No policy imports."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def validate():
    index = json.loads((HERE / "index.json").read_text())
    manifest = json.loads((HERE / "manifest.json").read_text())
    assert hashlib.sha256((HERE / "index.json").read_bytes()).hexdigest() == manifest["generated_index_sha256"]
    assert index["status"] == "ready" and not index["pending_evidence"]
    assert index["legacy_records_unchanged"] is True
    sources = {s["id"]: s for s in manifest["sources"]}
    assert len(sources) == len(manifest["sources"])
    for source in sources.values():
        path = (REPO / source["repo_relative_path"]).resolve()
        assert path.is_relative_to(REPO)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"], str(path)
    nodes = {}
    for item in index["nodes"]:
        path = (HERE / item["details"]).resolve()
        assert path.is_relative_to(HERE)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest["generated_node_sha256"][item["details"]]
        node = json.loads(path.read_text())
        assert node["id"] == item["id"] and node["id"] not in nodes
        for key in ("kind", "title", "status", "parents", "counts_as_algorithm_round", "counts_as_completed_4800_round"):
            assert node[key] == item[key], (node["id"], key)
        assert not node["official_result"] and not node["new_holdout_result"]
        if node["kind"] != "algorithm_candidate":
            assert not node["counts_as_algorithm_round"] and not node["counts_as_completed_4800_round"]
        if node["counts_as_completed_4800_round"]:
            scope = node["scopes"]["exposed"]
            assert scope["compared_rows"] == 4800
            assert all(e["all_clear_and_normal"] for e in scope["effects"])
        nodes[node["id"]] = node
    assert len(nodes) == index["counts"]["new_nodes"]
    assert set(manifest["generated_node_sha256"]) == {item["details"] for item in index["nodes"]}
    seen, active = set(), set()
    def visit(node_id):
        if node_id in seen or node_id == "S4_ROOT_C7_both":
            return
        assert node_id in nodes and node_id not in active, "Unknown/cyclic lineage: " + node_id
        active.add(node_id)
        for parent in nodes[node_id]["parents"]:
            visit(parent["id"])
        active.remove(node_id)
        seen.add(node_id)
    for node_id in nodes:
        visit(node_id)
    def verify_source_references(value):
        if isinstance(value, str) and value.startswith("s6src_"):
            assert value in sources, "Dangling evidence source: " + value
        elif isinstance(value, dict):
            for child in value.values():
                verify_source_references(child)
        elif isinstance(value, list):
            for child in value:
                verify_source_references(child)
    verify_source_references(index)
    verify_source_references(list(nodes.values()))
    algorithm = {n["round_key"] for n in nodes.values() if n["counts_as_algorithm_round"]}
    complete = {n["round_key"] for n in nodes.values() if n["counts_as_completed_4800_round"]}
    assert len(algorithm) == index["counts"]["algorithm_research_rounds"]
    assert len(complete) == index["counts"]["algorithm_rounds_with_complete_4800"]
    assert nodes["S6_RL_BC_RPI_PLAN"]["actual_training_updates"] == 0
    final = nodes["S6_FINAL_COMBINED"]
    assert final["task_metric_field_count"] == len(final["task_metric_fields"]) == len(set(final["task_metric_fields"]))
    assert final["trace_sample_cases"] == 24 and final["trace_actual_runs"] == 48
    if "S6_RL_G0_G1_EXECUTION" in nodes:
        execution = nodes["S6_RL_G0_G1_EXECUTION"]["execution_snapshot"]
        counts = execution["independently_recounted_journal"]
        if counts is not None:
            assert counts["business_calls"] == counts["accepted_calls"] + counts["failed_calls"] + counts["unresolved_calls"]
            assert counts["executions_started"] == counts["executions_completed"] + counts["unfinished_runs"]
    assert nodes["S6_A2_G1"]["exact_counterexamples"] == 180
    assert nodes["S6_A2_G2"]["candidate_continuous_certified"] is False
    assert all(v["continuous_certified"] is False for v in nodes["S6_A2_G3"]["variants"])
    return dict(status="ready_within_checked_scope", nodes=len(nodes), source_hashes=len(sources),
                algorithm_rounds=len(algorithm), complete_4800_rounds=len(complete), policy_executions=0)


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False, indent=2))
