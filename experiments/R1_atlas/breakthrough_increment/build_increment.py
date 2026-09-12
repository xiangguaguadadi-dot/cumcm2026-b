#!/usr/bin/env python3
"""Read-only evidence collection; writes ONLY this standalone atlas increment.

No solver/environment imports, policy execution, network, old-atlas edits or Git.
Default is a dry run. --write requires final A1 and coordinator evidence.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
STAGE = REPO / "experiments/20260912_breakthrough"
C7 = REPO / "experiments/20260911_stage4/combination/geometry_fusions/C7_both.py"
C7_SHA = "cf37866829b9c6f376895075e819a732939e6fa8ad6d8d6297a151d7a213dcb3"
SCHEMA = "breakthrough-atlas-increment-v1"
ANCHOR = "S6_C7_ANCHOR"


class EvidenceError(RuntimeError):
    pass


def require(test, message):
    if not test:
        raise EvidenceError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def equivalent(a, b):
    return a is b if a is None or b is None else finite(a) and finite(b) and math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-8)


def valid(row):
    n, cleared = row.get("source_count"), row.get("cleared_count")
    return (row.get("complete") is True and row.get("exit_reason") == "user_exit"
            and not row.get("error") and type(n) is int and n > 0 and cleared == n
            and finite(row.get("total_virtual_time_s")) and finite(row.get("average_clear_time_s")))


def row_effects(rows, *, suite, reference=None):
    """Recompute saved rows, never filtering failures into an efficiency score."""
    ids = [r["case_id"] for r in rows]
    require(len(ids) == len(set(ids)), "Duplicate candidate case IDs")
    ref = None if reference is None else {r["case_id"]: r for r in reference}
    if ref is not None:
        require(len(ref) == len(reference), "Duplicate reference case IDs")
        require(set(ids) <= set(ref), "Candidate/reference ID mismatch")
    for row in rows:
        cleared = row.get("cleared_count")
        if ref is not None:
            baseline = ref[row["case_id"]]
            require(all(row.get(k) == baseline.get(k) for k in ("mode", "group", "source_count")),
                    "Aligned case metadata/denominator mismatch: " + row["case_id"])
        if type(cleared) is int and cleared > 0 and finite(row.get("total_virtual_time_s")):
            require(equivalent(row.get("average_clear_time_s"), row["total_virtual_time_s"] / cleared),
                    "T/cleared formula mismatch: " + row["case_id"])
        if cleared == 0:
            require(row.get("average_clear_time_s") is None, "Zero denominator must remain null: " + row["case_id"])
    result = []
    for mode in sorted({r["mode"] for r in rows}):
        part = [r for r in rows if r["mode"] == mode]
        for group in ["ALL"] + sorted({r["group"] for r in part}):
            selected = part if group == "ALL" else [r for r in part if r["group"] == group]
            complete = all(valid(r) for r in selected)
            known_sources = all(type(r.get("source_count")) is int for r in selected)
            known_cleared = all(type(r.get("cleared_count")) is int for r in selected)
            out = dict(suite=suite, mode=mode, group=group, cases=len(selected),
                       complete_cases=sum(valid(r) for r in selected),
                       error_cases=sum(bool(r.get("error")) for r in selected),
                       all_clear_and_normal=complete,
                       source_count=sum(r["source_count"] for r in selected) if known_sources else None,
                       cleared_count=sum(r["cleared_count"] for r in selected) if known_cleared else None,
                       unknown_clearance_rows=sum(type(r.get("cleared_count")) is not int for r in selected),
                       mean_s_per_source=statistics.mean(r["average_clear_time_s"] for r in selected) if complete else None,
                       failed_case_ids=[r["case_id"] for r in selected if not valid(r)])
            if ref is not None:
                controls = [ref[r["case_id"]] for r in selected]
                gate = complete and all(valid(r) for r in controls)
                out["comparison_valid"] = gate
                if gate:
                    deltas = [r["average_clear_time_s"] - b["average_clear_time_s"] for r, b in zip(selected, controls)]
                    out.update(baseline_mean_s_per_source=statistics.mean(b["average_clear_time_s"] for b in controls),
                               delta_s_per_source=statistics.mean(deltas),
                               faster=sum(d < -1e-8 for d in deltas), equal=sum(abs(d) <= 1e-8 for d in deltas),
                               slower=sum(d > 1e-8 for d in deltas), max_regression=max(deltas))
            result.append(out)
    return result


def all_effects(effects, suite=None):
    return [r for r in effects if r["group"] == "ALL" and (suite is None or r["suite"] == suite)]


def verify_append(parent, candidate, component_sha):
    require(candidate.startswith(parent + b"\n"), "A1 actual parent prefix differs")
    require(sha(candidate[len(parent) + 1:]) == component_sha, "A1 embedded component SHA mismatch")


def execution_journal_counts(records):
    """Count recorded attempts, keeping unresolved calls distinct from zero."""
    started, finished, calls, settled = {}, {}, {}, {}
    for row in records:
        event = row.get("event")
        require(event in ("run_start", "run_finish", "call_start", "call_response", "call_exception"),
                "Unknown accounting journal event")
        if event in ("run_start", "run_finish"):
            rid = row["run_id"]
            target = started if event == "run_start" else finished
            require(rid not in target, "Duplicate journal " + event + ": " + rid)
            if event == "run_finish":
                require(rid in started, "Journal run finished without start")
                require(all(sequence in settled for sequence, call in calls.items() if call["run_id"] == rid),
                        "Journal run finished with unresolved call")
            target[rid] = row
        elif event in ("call_start", "call_response", "call_exception"):
            sequence = row["sequence"]
            require(type(sequence) is int and sequence >= 0, "Invalid journal call sequence")
            if event == "call_start":
                require(sequence not in calls and row["run_id"] in started and row["run_id"] not in finished,
                        "Duplicate call or call outside registered journal run")
                calls[sequence] = row
            else:
                require(sequence in calls and sequence not in settled,
                        "Journal response has no unique attempt")
                require(row["run_id"] == calls[sequence]["run_id"], "Journal call/run mismatch")
                settled[sequence] = row
    require(sorted(calls) == list(range(len(calls))), "Journal call sequence has gaps")
    return dict(executions_started=len(started), executions_completed=len(finished),
                business_calls=len(calls), accepted_calls=sum(r.get("accepted") is True for r in settled.values()),
                failed_calls=sum(r.get("event") == "call_exception" or r.get("accepted") is not True for r in settled.values()),
                unresolved_calls=len(calls) - len(settled), unfinished_runs=len(started) - len(finished))


def collect_strings(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return sum((collect_strings(v) for v in value.values()), [])
    if isinstance(value, list):
        return sum((collect_strings(v) for v in value), [])
    return []


class Builder:
    def __init__(self):
        self.sources = {}
        self.read_hashes = {}
        self.nodes = []
        self.pending = []
        self.rows_cache = {}
        self.a1_best = None
        self.snapshot_outputs = {}
        self.captured_at_utc = datetime.now(timezone.utc).isoformat()
        self.snapshot_id = "rl_g0g1_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")

    def registered_path(self, path):
        """Relocate recorded absolute paths only through their repo experiments suffix."""
        path = Path(path)
        if not path.is_absolute():
            return (REPO / path).resolve()
        if path.resolve().is_relative_to(REPO):
            return path.resolve()
        parts = path.parts
        require("experiments" in parts, "Cannot relocate registered source path: " + str(path))
        return (REPO / Path(*parts[parts.index("experiments"):])).resolve()

    def source(self, path, role, expected=None):
        path = Path(path).resolve()
        require(path.is_relative_to(REPO), "Source outside repository: " + str(path))
        if path in self.snapshot_outputs:
            data = self.snapshot_outputs[path]
        else:
            require(path.is_file(), "Missing source: " + str(path))
            stat = path.stat()
            data = path.read_bytes()
            require((stat.st_size, stat.st_mtime_ns) == (path.stat().st_size, path.stat().st_mtime_ns),
                    "Source changed while reading: " + str(path))
        digest = sha(data)
        if expected is not None:
            require(digest == expected, "Source SHA mismatch: " + str(path))
        rel = str(path.relative_to(REPO))
        key = "s6src_" + sha(rel.encode())[:16]
        previous = self.sources.get(key)
        if previous:
            require(previous["sha256"] == digest, "Source changed during build: " + rel)
            previous["roles"] = sorted(set(previous["roles"] + [role]))
        else:
            self.sources[key] = dict(id=key, repo_relative_path=rel,
                href_from_increment=os.path.relpath(path, HERE), sha256=digest,
                bytes=len(data), roles=[role], processing="read_saved_artifact_and_hash; no policy execution")
        if path not in self.snapshot_outputs:
            self.read_hashes[path] = digest
        return key, data

    def snapshot_json(self, path, role, fields=None, jsonl=False):
        """Archive validated accounting fields, not live mutable source bindings."""
        path = Path(path).resolve()
        require(path.is_relative_to(REPO) and path.is_file(), "Missing/outside snapshot source")
        before = path.stat()
        raw = path.read_bytes()
        after = path.stat()
        require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns),
                "Live accounting source changed during capture; retry after settlement")
        def parse(data):
            return json.loads(data, parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))
        obj = [parse(line) for line in raw.splitlines() if line.strip()] if jsonl else parse(raw)
        if fields is not None:
            obj = [{k: row[k] for k in fields if k in row} for row in obj] if jsonl else {k: obj[k] for k in fields if k in obj}
        if not jsonl and path.name == "execution_status.json" and obj.get("current_run") is not None:
            obj["current_run"] = {k: obj["current_run"].get(k) for k in ("run_id", "kind", "attempted", "accepted", "failed", "pending_call")}
        archived = HERE / "snapshots" / self.snapshot_id / path.name
        payload = b"".join(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8") + b"\n" for row in obj) if jsonl else json_bytes(obj)
        self.snapshot_outputs[archived] = payload
        artifact = self.artifact(archived, role)
        self.sources[artifact["source"]].update(
            original_repo_relative_path=str(path.relative_to(REPO)), original_raw_sha256=sha(raw),
            captured_at_utc=datetime.now(timezone.utc).isoformat(),
            snapshot_transform="Parsed JSON reserialization; selected accounting fields only" if fields else "Parsed JSON reserialization; all fields preserved",
            preserved_top_level_fields=list(fields) if fields else None,
            live_original_is_not_a_current_hash_dependency=True)
        return artifact, obj

    def artifact(self, path, role, expected=None):
        key, _ = self.source(path, role, expected)
        s = self.sources[key]
        return dict(source=key, path=s["repo_relative_path"], sha256=s["sha256"], href=s["href_from_increment"])

    def verify_hash_map(self, mapping, required_paths):
        require(isinstance(mapping, dict), "Missing verifier input hash map")
        normalized = {self.registered_path(path): digest for path, digest in mapping.items()}
        require(len(normalized) == len(mapping), "Verifier hash paths collapse after relocation")
        require(set(required_paths) <= set(normalized), "Verifier does not bind all required inputs")
        for path, digest in normalized.items():
            self.source(path, "independent_verifier_bound_input", digest)

    def read(self, path, role, expected=None):
        key, data = self.source(path, role, expected)
        try:
            obj = json.loads(data, parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))
        except (ValueError, UnicodeError) as exc:
            raise EvidenceError("Invalid saved JSON: " + str(path)) from exc
        return key, obj

    def optional(self, path, role):
        return self.artifact(path, role) if Path(path).is_file() else None

    def rows(self, path, expected=None):
        path = Path(path).resolve()
        key, obj = self.read(path, "saved_case_rows", expected)
        require(isinstance(obj, list), "Expected row array: " + str(path))
        rows = [r for r in obj if r.get("variant", "candidate") == "candidate"]
        self.rows_cache[path] = rows
        return key, rows

    def scope(self, directory, candidate_sha, scope_name, reference=None):
        directory = Path(directory)
        summary_ref, summary = self.read(directory / "summary.json", "saved_execution_summary")
        require(summary.get("candidate_sha256") == candidate_sha, "Execution/candidate SHA mismatch: " + str(directory))
        rows_ref, rows = self.rows(directory / "case_metrics.json")
        effects = row_effects(rows, suite=scope_name, reference=reference)
        require(summary.get("all_complete") == all(valid(r) for r in rows), "Summary completeness differs from saved rows")
        if "runs" in summary:
            require(summary["runs"] == len(rows), "Summary candidate run count differs from rows")
        out = dict(summary_source=summary_ref, rows_source=rows_ref, compared_rows=len(rows),
                   actual_new_runs=summary.get("runs", summary.get("new_runs")), effects=effects,
                   comparison_reference_node=ANCHOR if reference is self.base_rows else None,
                   execution_wall_seconds=summary.get("wall_seconds", summary.get("wall_seconds_new_runs")),
                   data_role="exposed_local_regression_not_holdout_or_official")
        if scope_name == "exposed":
            require(len(rows) == 4800, "Incomplete registered exposed ID set")
            require({r["case_id"] for r in rows} == {r["case_id"] for r in self.base_rows}, "Exposed ID set mismatch")
            for label in sorted({r.get("exposure_suite", "unspecified") for r in rows}):
                part = [r for r in rows if r.get("exposure_suite", "unspecified") == label]
                out["effects"] += row_effects(part, suite=label, reference=reference)
        if summary.get("v1_reused"):
            out["cached_v1_reused"] = summary["v1_reused"]
        return out, rows

    def add(self, node):
        require(node["id"] not in {n["id"] for n in self.nodes}, "Duplicate node ID")
        node.setdefault("stage", 6)
        node.setdefault("official_result", False)
        node.setdefault("new_holdout_result", False)
        node.setdefault("counts_as_algorithm_round", False)
        node.setdefault("counts_as_completed_4800_round", False)
        node.setdefault("parents", [])
        self.nodes.append(node)
        return node

    def common(self):
        self.builder_ref = self.artifact(__file__, "increment_builder")
        self.validator_ref = self.artifact(HERE / "validate_increment.py", "increment_validator")
        self.tests_ref = self.artifact(HERE / "test_increment.py", "synthetic_index_tests_not_policy_tests")
        self.readme_ref = self.artifact(HERE / "README.md", "increment_reading_and_evidence_boundaries")
        self.protocol_ref = self.artifact(STAGE / "PROTOCOL.md", "scope_and_promotion_contract")
        self.legacy = [self.artifact(REPO / "experiments/R1_atlas" / rel, "read_only_legacy_index")
                       for rel in ("exploration_index.json", "stage4_increment/index.json", "rl_increment/index.json")]
        self.frozen = self.artifact(REPO / "evaluation/manifest_v1.json", "unchanged_frozen_v1_manifest")
        c7_art = self.artifact(C7, "frozen_mechanism_anchor", C7_SHA)
        base_ref, self.base_rows = self.rows(REPO / "experiments/20260911_stage4/combination/results/c7_exposed/case_metrics.json")
        self.add(dict(id=ANCHOR, kind="background_anchor", title="原冻结 C7：本轮机制起点", status="historical_exposed_reference",
            candidate=c7_art, rows_source=base_ref, primary_effects=all_effects(row_effects(self.base_rows, suite="exposed")),
            parents=[dict(id="S4_ROOT_C7_both", relationship="same_frozen_candidate_identity")]))

    def a1(self):
        lane = STAGE / "A1"
        ledger_ref, ledger = self.read(lane / "iteration_ledger.json", "author_final_or_current_round_ledger")
        self.a1_best = ledger["best_round"]
        decisions_ref = self.optional(lane / "round_decisions.json", "author_retention_decisions")
        research_artifacts = [a for a in [self.optional(lane / name, "author_research_sources_not_new_literature_review")
                              for name in ("RESEARCH.md", "literature.json")] if a]
        current = {r["round"]: r for r in ledger["rows"]}
        for registration in sorted(lane.glob("r*_registration.json"), key=lambda p: (int(re.search(r"r(\d+)", p.name)[1]), p.name)):
            reg_ref, reg = self.read(registration, "registered_immutable_candidate_lineage")
            round_id = reg["round"]
            row = current.get(round_id)
            if row is None:
                self.pending.append("A1 ledger lacks " + round_id)
                continue
            status = row["status"]
            if status in ("in_progress", "pending"):
                self.pending.append("A1 " + round_id + " is " + status)
            candidate_path = self.registered_path(reg["candidate"])
            parent_path = self.registered_path(reg["parent"])
            candidate = self.artifact(candidate_path, "immutable_candidate_snapshot", reg["candidate_sha256"])
            require(candidate["sha256"] == row["candidate_sha256"], "A1 ledger candidate mismatch")
            parent_art = self.artifact(parent_path, "registered_actual_code_parent", reg["parent_sha256"])
            parent_id = ANCHOR if parent_path == C7 else "S6_A1_" + parent_path.stem.upper()
            gate_id = "S6_A1_" + row["gate_control"].upper() if row.get("gate_control") else ANCHOR
            verify_append(parent_path.read_bytes(), candidate_path.read_bytes(), reg["component_sha256"])
            component_current = self.optional(self.registered_path(reg["component"]), "current_editable_component_not_authoritative_snapshot")
            scopes = {}
            for scope_name, reported in row["scopes"].items():
                output = lane / "results" / (round_id + "_" + scope_name)
                self.source(output / "case_metrics.json", "author_ledger_bound_rows", reported["rows_sha256"])
                scope, rows = self.scope(output, candidate["sha256"], scope_name, self.base_rows)
                for effect in all_effects(scope["effects"]):
                    if effect["suite"] != scope_name:
                        continue
                    claimed = reported[str(effect["mode"])]
                    require(claimed["cases"] == effect["cases"] and claimed["all_complete"] == effect["all_clear_and_normal"], "A1 completeness ledger mismatch")
                    require(equivalent(claimed.get("mean_s_per_source"), effect["mean_s_per_source"]), "A1 mean ledger mismatch")
                scopes[scope_name] = scope
            round_number = int(re.search(r"\d+", round_id)[0])
            revision = round_id in ("r6", "r6a")
            completed = "exposed" in scopes and all(e["all_clear_and_normal"] for e in scopes["exposed"]["effects"])
            node = self.add(dict(id="S6_A1_" + round_id.upper(), kind="unexecuted_draft" if not scopes else "implementation_failure" if round_id == "r6a" else "algorithm_candidate",
                title="A1 " + round_id.upper() + "：" + row["mechanism"], status=status,
                direction_tags=["A1_Q3", row["direction"]], round_key="S6_A1_R" + str(round_number),
                counts_as_algorithm_round=bool(scopes) and not revision,
                counts_as_completed_4800_round=completed and not revision,
                retained=status.startswith("retained"), selected_final_per_task=round_id == self.a1_best,
                retention_semantics="retained records historical promotion; selected_final_per_task marks the final per-task choice",
                candidate=candidate, registration_source=reg_ref,
                ledger_source=ledger_ref, decision_artifact=decisions_ref, actual_code_parent=parent_id,
                retained_parent_at_evaluation=gate_id, parent_artifact=parent_art,
                promotion_comparison_from_author_ledger=[e for e in row.get("comparison_to_gate_control", []) if e.get("group") == "ALL"],
                parent_prefix_and_component_sha_verified=True,
                component_registered_sha256=reg["component_sha256"], current_component=component_current,
                current_component_matches_registered=bool(component_current and component_current["sha256"] == reg["component_sha256"]),
                scopes=scopes, primary_effects=all_effects(scopes.get("exposed", {}).get("effects", []), "exposed"),
                research_artifacts=research_artifacts,
                parents=[dict(id=parent_id, relationship="actual_code_parent", evidence_source=reg_ref),
                         dict(id=gate_id, relationship="retained_promotion_control_not_necessarily_code_parent", evidence_source=ledger_ref)],
                evidence_boundary="Snapshot and registered append-only parent/component hashes are checked. Editable component may have changed after this immutable snapshot. quick is an exposed full subset; failures are retained."))
            if round_id in ("r6a", "r6b"):
                node["revision_of"] = "S6_A1_R6"
                node["revision_reason"] = row["mechanism"]
        self.a1_report = self.optional(lane / "REPORT.md", "author_final_report")
        if self.a1_report is None:
            self.pending.append("A1 final REPORT.md not yet archived")
        self.a1_costs = dict(source=ledger_ref, reported_budgets=ledger.get("budgets"), reported_totals=ledger.get("totals"),
                            not_summed_with_overlapping_node_scopes=True,
                            request_count_semantics="Recorded local requests derived from measure/clear counters plus enter/normal exit. Batch rows.requests omits prevalidation or state-rejected attempts; without a full attempt journal it cannot exclude unrecorded rejected attempts. Diagnostic request counts retain their author's reconstruction caveats.")

    def a2(self):
        lane = STAGE / "A2"
        ledger_ref, ledger = self.read(lane / "iteration_ledger.json", "a2_final_round_and_execution_ledger")
        self.a2_report = self.artifact(lane / "REPORT.md", "a2_final_report")
        research_artifacts = [self.artifact(lane / "LITERATURE.md", "a2_authored_literature_map_not_new_reading")]
        proof = [self.artifact(lane / f, "rotation_proof_or_saved_numerical_check") for f in
                 ("GEOMETRY_PROOF.md", "results/original_certificate_check.json", "results/rotation_certificate_check.json")]
        dev_batches = ["r1_rotation_dev", "r2_rotation_insertion_dev", "r3_deferred_rotation_dev", "r4_commit_rotation_dev", "r5_continuous_rotation_dev"]
        titles = ["开放路径代理选共同相位", "源到未来站连接距离代理选相位", "首次非原点扫描前延迟改相位", "首次站点执行时径向对齐", "连续一维细化插入相位"]
        for entry, dev_batch, title in zip(ledger["rounds"], dev_batches, titles):
            r = entry["round"]
            candidate = self.artifact(lane / (entry["name"] + ".py"), "a2_candidate_wrapper", entry["sha256"])
            code_parent = ANCHOR if r in (1, 3) else "S6_A2_R1"
            gate_parent = ANCHOR if r == 1 else "S6_A2_R1" if r == 2 else "S6_A2_R2"
            dependencies = [self.artifact(C7, "a2_frozen_dependency", C7_SHA)]
            if r != 1:
                dependencies.append(self.artifact(lane / "R1_rotation.py", "a2_imported_support_and_parent_module", ledger["hashes"]["R1_rotation.py"]))
            scopes = {}
            for scope in ("quick", "full", "exposed"):
                out = lane / "results" / ("r" + str(r) + "_" + scope)
                if out.is_dir():
                    scopes[scope], _ = self.scope(out, candidate["sha256"], scope, self.base_rows)
            dev_ref, dev = self.read(lane / "results" / dev_batch / "summary.json", "development_summary")
            dev_rows_ref, dev_rows = self.rows(lane / "results" / dev_batch / (entry["name"] + "_rows.json"))
            require(dev[entry["name"]]["sha256"] == candidate["sha256"], "A2 development SHA mismatch")
            development = dict(summary_source=dev_ref, rows_source=dev_rows_ref, data_role="96_new_but_exposed_development_worlds",
                               effects=row_effects(dev_rows, suite="development"))
            completed = "exposed" in scopes and all(e["all_clear_and_normal"] for e in scopes["exposed"]["effects"])
            self.add(dict(id="S6_A2_R" + str(r), kind="algorithm_candidate", title="A2 R" + str(r) + "：" + title,
                direction_tags=["A2_Q4", "certified_common_rotation"], round_key="S6_A2_R" + str(r),
                counts_as_algorithm_round=True, counts_as_completed_4800_round=completed,
                status=entry["status"], retained=r <= 2, selected_final_per_task=r == 2,
                retention_semantics="retained records historical promotion; selected_final_per_task marks the final per-task choice",
                candidate=candidate, implementation_dependencies=dependencies,
                actual_code_parent=code_parent, retained_parent_at_evaluation=gate_parent,
                parents=[dict(id=code_parent, relationship="class_or_wrapper_code_parent"),
                         dict(id=gate_parent, relationship="retained_promotion_control_not_necessarily_code_parent")],
                code_parent_note="R3 imports R1 utilities but subclasses frozen C7; R4/R5 subclass R1 and carry the retained R2 insertion configuration. The retained control is not falsely labeled the whole code parent.",
                ledger_source=ledger_ref, scopes=scopes, development=development, proof_artifacts=proof,
                primary_effects=all_effects(scopes.get("exposed", {}).get("effects", []), "exposed"),
                research_artifacts=research_artifacts,
                evidence_boundary="Development/quick selection and completed exposed regression are distinct; no new holdout or official result."))
        self.a2_costs = dict(source=ledger_ref, actual_task_runs=ledger["actual_task_runs"],
            execution_costs=ledger["execution_costs"], distinct_new_development_cases=ledger["distinct_new_development_cases"],
            not_summed_with_overlapping_node_scopes=True,
            request_count_semantics="Recorded local requests, not a complete attempt ledger: saved batch rows.requests excludes prevalidation or state-rejected attempts. No full-attempt precision is claimed for these historical batches.")
        self.geometry()
        package = self.artifact(lane / "BEST_R2.py", "mechanical_self_contained_packaging", ledger["hashes"]["BEST_R2.py"])
        package_scope, package_rows = self.scope(lane / "results/best_r2_packaging_exposed", package["sha256"], "exposed", self.base_rows)
        parity = ledger["packaging_parity"]
        require(parity["exact"] and parity["cases"] == 4800 and parity["component_ast_exact"] and parity["embedded_C7_source_exact"], "A2 packaging not verified")
        self.source(lane / "results/best_r2_packaging_exposed/case_metrics.json", "packaging_parity_bound_rows", parity["rows_sha256"])
        _, original_rows = self.rows(lane / "results/r2_exposed/case_metrics.json")
        fields = parity["fields"]
        require([[r.get(k) for k in fields] for r in package_rows] == [[r.get(k) for k in fields] for r in original_rows], "A2 packaging row parity differs")
        self.add(dict(id="S6_A2_PACKAGED_R2", kind="mechanical_packaging", title="A2 R2 单文件等价封装", status="4800_saved_task_fields_exact",
            candidate=package, component=self.artifact(lane / "retained_component.py", "readable_component_for_combination", ledger["hashes"]["retained_component.py"]),
            parents=[dict(id="S6_A2_R2", relationship="mechanical_packaging_no_new_algorithm")],
            parity=parity, ledger_source=ledger_ref, scopes={"exposed": package_scope},
            primary_effects=all_effects(package_scope["effects"], "exposed"),
            evidence_boundary="13 saved task fields equal across 4800 rows; this alone is not per-request trace equality. Packaging repeats are costs, not optimization rounds or independent worlds."))

    def geometry(self):
        lane = STAGE / "A2"
        g1_ref, g1 = self.read(STAGE / "verification/geometry20_round1_exact_counterexamples.json", "independent_exact_finite_layout_counterexamples")
        g1_summary_ref, g1_summary = self.read(lane / "results/geometry20_round1_corrected/summary.json", "corrected_finite_geometry_screen")
        self.source(lane / "results/geometry20_round1_corrected/records.json", "exact_counterexample_input", g1["records_sha256"])
        boundary_revision = self.artifact(lane / "results/geometry20_round1_boundarysafe/summary.json", "later_boundary_safe_probe_revision_not_input_of_exact_audit")
        require(g1["layouts"] == g1["verified_counterexamples"] == 180 and not g1["unresolved"], "G1 finite-layout audit not complete")
        self.add(dict(id="S6_A2_G1", kind="geometry_research", title="G1：180 个20点布局的有限反例搜索", status="listed_layouts_refuted_not_global_lower_bound",
            geometry_round=1, parents=[dict(id=ANCHOR, relationship="search_for_smaller_certified_topology")],
            evidence_sources=[g1_ref, g1_summary_ref], later_boundary_probe=boundary_revision,
            layouts=g1["layouts"], exact_counterexamples=g1["verified_counterexamples"],
            policy_runs=0, evidence_boundary=g1["limitation"], original_probe_corrections="Closed radius / disk-boundary corrections are retained in A2; only the independent exact audit supports the finite counterexample claim."))
        g2_ref, g2 = self.read(lane / "results/geometry21_round2/summary.json", "21_point_finite_geometry_screen")
        c2_ref, c2 = self.read(lane / "results/certificate_7_13/certificate.json", "continuous_certificate_attempt")
        self.add(dict(id="S6_A2_G2", kind="geometry_research", title="G2：21点新拓扑筛选与连续证书尝试", status="grid_passes_but_novel_topology_uncertified",
            geometry_round=2, parents=[dict(id="S6_A2_G1", relationship="next_bounded_geometry_direction_step")],
            evidence_sources=[g2_ref, c2_ref], layouts=g2["configurations"], sample_passes=len(g2["sample_passes"]),
            candidate_continuous_certified=c2["certified"], unresolved_cells=len(c2["failed"]), policy_runs=0,
            evidence_boundary="Uncertified cells are unresolved by this certificate attempt, not proved uncovered positions. Finite grid success is not continuous coverage."))
        g3_ref, g3 = self.read(lane / "results/geometry_phase_round3/records.json", "analytic_phase_variants_and_finite_screen")
        certificates = []
        for row in g3:
            ref, cert = self.read(lane / "results/geometry_phase_round3" / row["certificate"], "phase_variant_continuous_certificate_attempt")
            require(len(cert["failed"]) == row["failed_cells"], "G3 unresolved-cell count mismatch")
            certificates.append(dict(source=ref, sampled_positions=row["sampled"], sample_passed=row["passed"],
                                     continuous_certified=cert["certified"], unresolved_cells=len(cert["failed"])))
        self.add(dict(id="S6_A2_G3", kind="geometry_research", title="G3：7+13 构型相位修订，仍未获连续证书", status="three_uncertified_phase_variants_direction_stopped",
            geometry_round=3, parents=[dict(id="S6_A2_G2", relationship="phase_refinement_of_selected_topology")],
            evidence_sources=[g3_ref], variants=certificates, policy_runs=0,
            evidence_boundary="Three geometry rounds are not task-execution optimization rounds; no new topology was deployed and no global impossibility result was proved."))

    def rl(self):
        lane = STAGE / "RL"
        artifacts = [self.artifact(lane / name, "historical_rl_research_plan_or_review") for name in
                     ("PROPOSAL.md", "implementation_spec.md", "literature.json", "SOURCE_AUDIT.md", "review_log.md")]
        acceptance = self.optional(STAGE / "RL_VERIFIER_ACCEPTANCE.md", "coordinator_acceptance_of_plan_only")
        if acceptance is None:
            self.pending.append("RL coordinator acceptance not yet archived")
        tests = self.optional(lane / "contract_check_results.json", "synthetic_contract_checks_not_policy_or_training_runs")
        self.add(dict(id="S6_RL_BC_RPI_PLAN", kind="research_plan_snapshot", title="BC-RPI：预算化反事实源服务策略迭代方案",
            status="historical_plan_review_accepted_before_execution_authorization" if acceptance else "plan_review_pending",
            parents=[dict(id=ANCHOR, relationship="teacher_mechanism_anchor_not_rl_improvement_result")],
            artifacts=artifacts, coordinator_acceptance=acceptance, synthetic_checks=tests,
            actual_policy_runs=0, actual_training_updates=0, actual_counterfactual_branches=0,
            evidence_boundary="Historical proposal-review phase only: these zeros do not describe later authorized G0/G1 execution. Planned budgets, literature results and prior RL experiments are not new training or gains."))
        impl = lane / "implementation"
        registration_path = impl / "execution_registration.json"
        self.rl_costs = None
        if not registration_path.is_file():
            return
        registration_artifact, registration = self.snapshot_json(registration_path, "subsequently_authorized_g0_g1_registration_as_of")
        registration_ref = registration_artifact["source"]
        fields = ("entered", "full_runs", "suffix_runs", "fixture_runs", "executions_started", "executions_completed",
                  "business_calls", "accepted_calls", "failed_calls", "failed_runs", "network_training_runs", "unknown_cost_runs")
        status_artifact, status = None, {}
        if (impl / "execution_status.json").is_file():
            status_artifact, status = self.snapshot_json(impl / "execution_status.json", "g0_g1_fixed_accounting_status_snapshot_not_final_result",
                fields=fields + ("status", "updated_utc", "current_run", "limits", "reserved_calls", "wall_since_registration_s"))
        for path, digest in registration.get("input_sha256", {}).items():
            self.source(self.registered_path(path), "g0_g1_registered_frozen_input", digest)
        journal_artifact, journal_counts = None, None
        if (impl / "execution_calls.jsonl").is_file():
            journal_artifact, journal = self.snapshot_json(impl / "execution_calls.jsonl", "g0_g1_fixed_actual_call_accounting_snapshot",
                fields=("event", "run_id", "sequence", "accepted", "recorded_utc"), jsonl=True)
            journal_counts = execution_journal_counts(journal)
            # A live status is saved periodically; use the journal's actual as-of counts.
            if status.get("current_run") is None and journal_counts["unfinished_runs"] == 0:
                for field in ("executions_started", "executions_completed", "business_calls", "accepted_calls", "failed_calls"):
                    require(status.get(field) == journal_counts[field], "Settled RL status/journal mismatch: " + field)
        self.rl_costs = dict(registration_source=registration_ref, status_snapshot=status_artifact,
            reported_actual_counters={k: status.get(k) for k in fields}, journal=journal_artifact,
            independently_recounted_journal=journal_counts, as_of_utc=status.get("updated_utc"), captured_at_utc=self.captured_at_utc,
            limits_are_not_actual_execution_costs=True, not_summed_with_algorithm_or_packaging_runs=True)
        self.add(dict(id="S6_RL_G0_G1_EXECUTION", kind="authorized_execution_status_snapshot",
            title="BC-RPI G0/G1：后续获准的零训练执行状态快照",
            status=status.get("status", "registered_status_not_available"), registration_source=registration_ref,
            authorized_scope=registration.get("scope"), execution_snapshot=self.rl_costs,
            parents=[dict(id="S6_RL_BC_RPI_PLAN", relationship="subsequent_user_authorization_not_retroactive_training_result"),
                     dict(id=ANCHOR, relationship="registered_teacher_mechanism_anchor")],
            evidence_boundary="Current saved snapshot, not a claim of completed G0/G1 or a trained improvement. Missing/unreconciled journal counts remain null; status counters are labeled reported. Only G0/G1 was authorized; no promotion result is inferred."))

    def combined(self):
        paths = dict(candidate=STAGE / "final_candidates/combined.py", build=STAGE / "final_candidates/combined.build.json",
            registration=STAGE / "CURRENT_BEST.json", rows_audit=STAGE / "verification/final_saved_rows.json",
            task_parity=STAGE / "verification/final_task_parity.json", trace_parity=STAGE / "verification/final_trace_parity.json")
        missing = [str(p.relative_to(REPO)) for p in paths.values() if not p.is_file()]
        missing += [str((STAGE / "verification" / ("final_" + scope) / "summary.json").relative_to(REPO))
                    for scope in ("quick", "full", "exposed") if not (STAGE / "verification" / ("final_" + scope) / "summary.json").is_file()]
        parents = [dict(id="S6_A1_" + self.a1_best.upper(), relationship="selected_Q3_component"),
                   dict(id="S6_A2_PACKAGED_R2", relationship="selected_Q4_component")]
        if missing:
            self.pending += missing
            self.add(dict(id="S6_FINAL_COMBINED", kind="mechanical_combination", title="最终 Q3/Q4 组合入口", status="pending_coordinator_freeze_and_validation",
                parents=parents, missing_evidence=missing, primary_effects=[],
                evidence_boundary="Placeholder has no claimed results. Building a combined.py file alone is not validation or an optimization round."))
            return
        candidate = self.artifact(paths["candidate"], "final_combined_candidate")
        reg_ref, current = self.read(paths["registration"], "final_coordinator_decision_not_initial_build_status")
        require(current.get("candidate_sha256") == candidate["sha256"], "CURRENT_BEST does not bind current combined candidate SHA")
        require((STAGE / current.get("candidate", "")).resolve() == paths["candidate"], "CURRENT_BEST candidate path differs")
        _, build = self.read(paths["build"], "mechanical_combination_registered_sources")
        q3 = STAGE / "A1/snapshots" / (self.a1_best + ".py")
        q4 = STAGE / "A2/BEST_R2.py"
        for key, source_path in (("q3", q3), ("q4", q4)):
            expected_sha = sha(source_path.read_bytes())
            require(build.get(key + "_sha256") == current.get(key + "_sha256") == expected_sha,
                    "Final selection does not bind current " + key + " source SHA")
            require((STAGE / build.get(key + "_source", "")).resolve() == source_path,
                    "Build source differs from final lane best: " + key)
            require((STAGE / current.get(key + "_source", "")).resolve() == source_path,
                    "CURRENT_BEST source differs from final lane best: " + key)
        require(build.get("candidate_sha256") == candidate["sha256"], "Build/final candidate SHA mismatch")
        artifacts = [self.artifact(paths[k], "coordinator_final_combination_evidence") for k in ("build", "rows_audit", "task_parity", "trace_parity")]
        _, audit = self.read(paths["rows_audit"], "independent_final_saved_row_audit")
        require(audit["status"] == "consistent" and audit["candidate_sha256"] == candidate["sha256"], "Final audit is stale or not consistent")
        self.source(STAGE / "verification/final_exposed/case_metrics.json", "final_audit_bound_rows", audit["candidate_rows_sha256"])
        final_rows = STAGE / "verification/final_exposed/case_metrics.json"
        _, task_parity = self.read(paths["task_parity"], "independent_final_task_parity_status")
        require(task_parity.get("status") == "exact_task_metric_parity" and task_parity.get("rows") == 4800
                and task_parity.get("all_complete") is True and task_parity.get("embedded_parent_sources_exact") is True
                and task_parity.get("differences") == [], "Final task parity is not complete and exact")
        parity_fields = task_parity.get("compared_fields")
        require(isinstance(parity_fields, list) and parity_fields and len(parity_fields) == len(set(parity_fields)),
                "Final parity field list is empty or duplicated")
        self.verify_hash_map(task_parity.get("hashes"), [paths["candidate"], final_rows, q3, q4])
        _, trace_parity = self.read(paths["trace_parity"], "independent_final_trace_parity_status")
        require(trace_parity.get("all_exact") is True and trace_parity.get("all_complete") is True
                and trace_parity.get("cases") == 24 and trace_parity.get("actual_runs") == 48,
                "Final 24-case request parity is incomplete or differs")
        self.verify_hash_map(trace_parity.get("hashes"), [paths["candidate"], q3, q4])
        scopes = {}
        for scope in ("quick", "full", "exposed"):
            scopes[scope], _ = self.scope(STAGE / "verification" / ("final_" + scope), candidate["sha256"], scope, self.base_rows)
        require(all(e["all_clear_and_normal"] for e in scopes["exposed"]["effects"]), "Final combination is not complete")
        self.add(dict(id="S6_FINAL_COMBINED", kind="mechanical_combination", title="最终 Q3/Q4 组合入口", status="completed_4800_combination_with_coordinator_audits",
            parents=parents, candidate=candidate, coordinator_registration_source=reg_ref, coordinator_evidence=artifacts,
            task_metric_fields=parity_fields, task_metric_field_count=len(parity_fields),
            trace_sample_cases=trace_parity["cases"], trace_actual_runs=trace_parity["actual_runs"],
            pre_release_metadata_corrections=current.get("pre_release_metadata_corrections", []),
            scopes=scopes, primary_effects=all_effects(scopes["exposed"]["effects"], "exposed"),
            evidence_boundary="Final combination validation is preserved separately; it does not add an algorithm research round. Task-field and per-request parity are separate coordinator evidence files."))

    def build(self):
        self.common()
        self.a1()
        self.a2()
        self.rl()
        self.combined()
        ids = {n["id"] for n in self.nodes}
        external = {"S4_ROOT_C7_both"}
        for node in self.nodes:
            require(all(p["id"] in ids | external for p in node["parents"]), "Unknown graph parent: " + node["id"])
        counts = dict(new_nodes=len(self.nodes), nodes_by_kind=dict(Counter(n["kind"] for n in self.nodes)),
            algorithm_research_rounds=len({n["round_key"] for n in self.nodes if n["counts_as_algorithm_round"]}),
            algorithm_rounds_with_complete_4800=len({n["round_key"] for n in self.nodes if n["counts_as_completed_4800_round"]}),
            retained_algorithm_rounds=len({n["round_key"] for n in self.nodes if n.get("retained") and n["counts_as_algorithm_round"]}),
            geometry_research_rounds=sum(n["kind"] == "geometry_research" for n in self.nodes),
            mechanical_packaging_or_combination_nodes=sum(n["kind"] in ("mechanical_packaging", "mechanical_combination") for n in self.nodes),
            new_policy_executions_by_this_builder=0, new_training_updates_by_this_builder=0,
            new_official_runs=0, new_sealed_final_worlds=0)
        for path, digest in self.read_hashes.items():
            require(sha(path.read_bytes()) == digest, "Source changed before build finished: " + str(path))
        index = dict(schema_version=SCHEMA, status="ready" if not self.pending else "pending_final_evidence",
            pending_evidence=self.pending, legacy_records_unchanged=True, legacy_indexes=self.legacy,
            frozen_v1_manifest=self.frozen, protocol=self.protocol_ref,
            counts=counts, current_lane_best=dict(A1="S6_A1_" + self.a1_best.upper(), A2="S6_A2_R2"),
            reported_execution_costs=dict(A1=self.a1_costs, A2=self.a2_costs, RL_G0_G1=self.rl_costs),
            evidence_boundary="Saved rows are independently recomputed for IDs, T/cleared, completeness and per-mode/group means; source bytes are SHA256-bound. No strategy/environment execution, old-statistic rewrite, new holdout, official test or new RL training.",
            read_order="Read the legacy indexes, then this standalone S6 increment. Only nodes listed by this index are active; counts exclude packaging, drafts, revision duplicates, geometry and synthetic tests from algorithm full-round totals.",
            nodes=[dict(id=n["id"], kind=n["kind"], title=n["title"], status=n["status"],
                parents=n["parents"], round_key=n.get("round_key"),
                counts_as_algorithm_round=n["counts_as_algorithm_round"],
                counts_as_completed_4800_round=n["counts_as_completed_4800_round"],
                details="nodes/" + n["id"] + ".json", primary_effects=n.get("primary_effects", [])) for n in self.nodes])
        manifest = dict(schema_version=SCHEMA, sources=sorted(self.sources.values(), key=lambda s: s["repo_relative_path"]),
                        builder=self.builder_ref, validator=self.validator_ref, tests=self.tests_ref, reading_instructions=self.readme_ref,
                        generated_index_sha256=sha(json_bytes(index)),
                        generated_node_sha256={"nodes/" + n["id"] + ".json": sha(json_bytes(n)) for n in self.nodes},
                        no_policy_execution=True, writes_restricted_to="experiments/R1_atlas/breakthrough_increment")
        return index, manifest

    def write(self, index, manifest):
        require(not self.pending, "Final evidence not ready; refusing to publish index: " + "; ".join(self.pending))
        require(Path(__file__).resolve().parent == HERE, "Output boundary mismatch")
        (HERE / "nodes").mkdir(exist_ok=True)
        def dump(path, obj):
            require(path.resolve().is_relative_to(HERE), "Output escapes increment")
            path.write_bytes(json_bytes(obj))
        for path, payload in self.snapshot_outputs.items():
            require(path.resolve().is_relative_to(HERE), "Snapshot output escapes increment")
            require(not path.exists(), "Refusing to overwrite archived RL accounting snapshot")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        for node in self.nodes:
            dump(HERE / "nodes" / (node["id"] + ".json"), node)
        dump(HERE / "manifest.json", manifest)
        dump(HERE / "index.json", index)  # Active list is written last; no old nodes are deleted.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Publish only after all final evidence is complete")
    args = parser.parse_args()
    builder = Builder()
    index, manifest = builder.build()
    if args.write:
        builder.write(index, manifest)
    print(json.dumps(dict(status=index["status"], wrote=bool(args.write), counts=index["counts"], pending=index["pending_evidence"]), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
