"""Frozen-candidate new-seed runner and paired analysis for stage three.

This module does not generate cases. The CLI requires a committed, frozen
registry and a cases manifest tied to that exact registry. Error rows retain
their failure and only recover known input metadata. Bootstrap samples are
paired seed clusters and never count as new environment executions.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def read(p):
    return json.loads(Path(p).read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(p, value):
    Path(p).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def valid(row):
    return (row.get("complete") is True and not row.get("error")
            and row.get("exit_reason") == "user_exit"
            and row.get("cleared_count") == row.get("source_count")
            and isinstance(row.get("source_count"), int) and row["source_count"] > 0)


def committed_bytes(path):
    rel = Path(path).resolve().relative_to(ROOT)
    return subprocess.check_output(["git", "show", "HEAD:" + rel.as_posix()], cwd=ROOT)


def verify_registry(path):
    path = Path(path).resolve()
    assert committed_bytes(path) == path.read_bytes(), "Registry is not committed"
    registry = read(path)
    assert registry["research_frozen"] is True
    assert set(registry["agents_frozen"]) == {"R2_open", "R3_open"}
    assert registry["candidates"] and registry["seed_exclusion_review_complete"] is True
    for name, digest in registry["evaluation_helpers"].items():
        target = ROOT / name
        assert sha(target) == digest, "Changed review helper: " + name
        assert committed_bytes(target) == target.read_bytes()
    assert len({c["label"] for c in registry["candidates"]}) == len(registry["candidates"])
    exclusion = ROOT / registry["seed_exclusion_path"]
    assert sha(exclusion) == registry["seed_exclusion_sha256"]
    assert committed_bytes(exclusion) == exclusion.read_bytes()
    for c in registry["candidates"]:
        for name, digest in {c["candidate_path"]: c["candidate_sha256"],
                             **c["deployment_dependencies"]}.items():
            target = ROOT / name
            assert sha(target) == digest, "Changed deployment: " + name
            assert committed_bytes(target) == target.read_bytes(), "Uncommitted deployment: " + name
    return registry


def normalize_rows(cases, rows):
    assert len(cases) == len(rows) == len({c["case_id"] for c in cases})
    output = []
    for c, r in zip(cases, rows):
        assert (r["case_id"], r["mode"], r["source_count"]) == (c["case_id"], c["mode"], len(c["sources"]))
        assert r.get("group", c["group"]) == c["group"]
        output.append(dict(r, group=c["group"], seed_cluster=c["seed"]))
    return output


def validate_cases(cases):
    groups = {c["group"] for c in read(HERE / "exposed_cases.json")}
    assert len(groups) == 12
    assert len(cases) == len({c["case_id"] for c in cases}) == 2400
    seeds = {c["seed"] for c in cases}
    assert len(seeds) == 100 and all(type(s) is int for s in seeds)
    assert {(c["mode"], c["group"], c["seed"]) for c in cases} == {
        (m, g, s) for m in (3, 4) for g in groups for s in seeds}
    for c in cases:
        assert 10 <= len(c["sources"]) <= 16
        assert len({s["channel"] for s in c["sources"]}) == len(c["sources"])
        if c["mode"] == 4:
            assert {s["direction"] is not None for s in c["sources"]} == {True, False}
    return seeds


def verify_case_manifest(cases_path, registry_path):
    manifest = read(Path(cases_path).parent / "manifest.json")
    assert manifest["registry_sha256"] == sha(registry_path)
    assert manifest["cases_sha256"] == sha(cases_path)
    assert manifest["cases"] == 2400 and manifest["seed_clusters"] == 100
    cases = read(cases_path)
    assert validate_cases(cases) == set(manifest["seeds"])
    return cases, manifest


def fingerprint(root):
    return {str(p): sha(p) for p in sorted([*root.glob("*.py"), *root.glob("*.json")]) if p.is_file()}


def execute(candidate, dependencies, cases_file, out, label, role, extra_identity=None, data_role="stage3_final_new_seed_local"):
    sys.path.insert(0, str(ROOT))
    import evaluate

    assert Path(evaluate.__file__).resolve() == ROOT / "evaluate.py"
    evaluate.verify()
    files = {str(Path(candidate).resolve()): sha(candidate), str(Path(cases_file).resolve()): sha(cases_file),
             str(Path(__file__).resolve()): sha(__file__), **fingerprint(ROOT)}
    for name, digest in dependencies.items():
        assert sha(name) == digest
        files[str(Path(name).resolve())] = digest
    optional = Path(candidate).parent / "coverage_points.json"
    assert not optional.exists() or str(optional.resolve()) in files, "Undeclared optional coverage file"
    cases = read(cases_file)
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    rows = normalize_rows(cases, evaluate.run_cases(cases, Path(candidate), False))
    wall = time.perf_counter() - start
    # Persist raw failures before any after-run identity assertion, so an
    # interrupted or invalid review does not erase the actual execution record.
    save(out / "case_metrics.json", rows)
    evaluate.verify()
    for name, digest in files.items():
        assert sha(name) == digest, "Identity changed during run: " + name
    assert not optional.exists() or str(optional.resolve()) in files
    modes = []
    for mode in (3, 4):
        part = [r for r in rows if r["mode"] == mode]
        ok = bool(part) and all(valid(r) for r in part)
        modes.append(dict(mode=mode, cases=len(part), valid_completion=sum(valid(r) for r in part),
                          source_count=sum(r["source_count"] for r in part),
                          cleared_count=sum(r["cleared_count"] for r in part) if all(isinstance(r.get("cleared_count"), int) for r in part) else None,
                          observed_cleared_lower_bound=sum(r["cleared_count"] for r in part if isinstance(r.get("cleared_count"), int)),
                          unknown_clearance_rows=sum(not isinstance(r.get("cleared_count"), int) for r in part),
                          errors=sum(bool(r.get("error")) for r in part),
                          mean_s_per_source=statistics.fmean(r["average_clear_time_s"] for r in part) if ok else None))
    summary = dict(label=label, role=role, data_role=data_role, candidate=str(candidate),
                   candidate_sha256=sha(candidate), dependencies=dependencies, cases_sha256=sha(cases_file),
                   runner_sha256=sha(__file__), manifest_sha256=sha(ROOT / "evaluation/manifest_v1.json"),
                   identity_before_and_after=files, python=platform.python_version(), platform=platform.platform(),
                   wall_seconds=wall, actual_runs=len(rows), all_valid_completion=all(valid(r) for r in rows), modes=modes,
                   extra_identity=extra_identity or {})
    save(out / "summary.json", summary)
    fields = ["case_id", "mode", "group", "seed_cluster", "cleared_count", "source_count", "complete", "error",
              "exit_reason", "average_clear_time_s", "total_virtual_time_s", "distance_m", "requests",
              "clear_failures", "program_runtime_s"]
    with (out / "case_metrics.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return summary


def paired(rows, baseline):
    bi = {r["case_id"]: r for r in baseline}
    assert rows and len(rows) == len(baseline) == len(bi) == len({r["case_id"] for r in rows})
    assert {r["case_id"] for r in rows} == set(bi)
    for r in rows:
        assert all(r[k] == bi[r["case_id"]][k] for k in ("mode", "group", "seed_cluster", "source_count"))
        for rr in (r, bi[r["case_id"]]):
            if valid(rr):
                assert math.isfinite(rr["average_clear_time_s"]) and rr["average_clear_time_s"] > 0
                assert math.isclose(rr["average_clear_time_s"], rr["total_virtual_time_s"] / rr["cleared_count"], rel_tol=1e-12, abs_tol=1e-8)
    output = []
    for mode in (3, 4):
        selected = [r for r in rows if r["mode"] == mode]
        assert selected
        for group in ("ALL", *sorted({r["group"] for r in selected})):
            part = [r for r in selected if group == "ALL" or r["group"] == group]
            bases = [bi[r["case_id"]] for r in part]
            ok = all(valid(r) and valid(b) for r, b in zip(part, bases))
            cell = dict(mode=mode, group=group, cases=len(part), valid_comparison=ok,
                        candidate_valid=sum(valid(r) for r in part), baseline_valid=sum(valid(b) for b in bases),
                        source_count=sum(r["source_count"] for r in part),
                        candidate_cleared=sum(r["cleared_count"] for r in part) if all(isinstance(r.get("cleared_count"), int) for r in part) else None,
                        observed_cleared_lower_bound=sum(r["cleared_count"] for r in part if isinstance(r.get("cleared_count"), int)),
                        unknown_clearance_rows=sum(not isinstance(r.get("cleared_count"), int) for r in part),
                        failed_case_ids=[r["case_id"] for r, b in zip(part, bases) if not (valid(r) and valid(b))])
            if not ok:
                output.append(cell)
                continue
            base = statistics.fmean(r["average_clear_time_s"] for r in bases)
            cand = statistics.fmean(r["average_clear_time_s"] for r in part)
            delta = [r["average_clear_time_s"] - b["average_clear_time_s"] for r, b in zip(part, bases)]
            cell.update(baseline_mean_s_per_source=base, candidate_mean_s_per_source=cand,
                        delta_s_per_source=cand-base, reduction_fraction=1-cand/base,
                        faster=sum(d < -1e-8 for d in delta), equal=sum(abs(d) <= 1e-8 for d in delta),
                        slower=sum(d > 1e-8 for d in delta), worst_s_per_source=max(r["average_clear_time_s"] for r in part),
                        max_regression_s_per_source=max(0.0, max(delta)),
                        max_regression_case_id=part[max(range(len(delta)), key=delta.__getitem__)]["case_id"] if max(delta) > 1e-8 else None,
                        candidate_max_virtual_s=max(r["total_virtual_time_s"] for r in part),
                        candidate_mean_runtime_s=statistics.fmean(r["program_runtime_s"] for r in part))
            for metric in ("distance_m", "requests", "clear_failures"):
                cell[metric] = dict(baseline_mean_per_case=statistics.fmean(r[metric] for r in bases),
                                    candidate_mean_per_case=statistics.fmean(r[metric] for r in part))
            if group == "ALL":
                seeds = sorted({r["seed_cluster"] for r in part})
                clusters = [[r for r in part if r["seed_cluster"] == s] for s in seeds]
                assert len({len(c) for c in clusters}) == 1, "Unequal cluster weights require another estimator"
                cv = [statistics.fmean(r["average_clear_time_s"] for r in c) for c in clusters]
                bv = [statistics.fmean(bi[r["case_id"]]["average_clear_time_s"] for r in c) for c in clusters]
                rng = random.Random(110926)
                saved, relative = [], []
                for _ in range(5000):
                    ix = rng.choices(range(len(seeds)), k=len(seeds))
                    b = statistics.fmean(bv[i] for i in ix)
                    c = statistics.fmean(cv[i] for i in ix)
                    saved.append(b-c)
                    relative.append(1-c/b)
                saved.sort(); relative.sort()
                cell.update(seed_clusters=len(seeds), bootstrap_replicates=5000,
                            saved_s_per_source_seed_cluster_95ci=[saved[124], saved[4874]],
                            reduction_fraction_seed_cluster_95ci=[relative[124], relative[4874]])
                bm = statistics.fmean(r["distance_m"] / 5 / r["source_count"] for r in bases)
                cm = statistics.fmean(r["distance_m"] / 5 / r["source_count"] for r in part)
                cell["time_decomposition"] = dict(baseline_movement_s_per_source=bm, candidate_movement_s_per_source=cm,
                                                    baseline_other_s_per_source=base-bm, candidate_other_s_per_source=cand-cm,
                                                    note="Accounting identity, not a component ablation")
            output.append(cell)
    return output


def compare_cohort(baseline, candidates):
    """Suppress each scenario across all candidates if any deployment fails it."""
    cells = [paired(rows, baseline) for rows in candidates]
    failures = {}
    for index, rows in enumerate([baseline, *candidates]):
        for row in rows:
            if not valid(row):
                for group in ("ALL", row["group"]):
                    failures.setdefault((row["mode"], group), []).append(
                        dict(cohort_index=index, case_id=row["case_id"]))
    basic = {"mode", "group", "cases", "candidate_valid", "baseline_valid", "source_count",
             "candidate_cleared", "observed_cleared_lower_bound", "unknown_clearance_rows", "failed_case_ids"}
    for comparisons in cells:
        for i, cell in enumerate(comparisons):
            blocked = failures.get((cell["mode"], cell["group"]))
            if blocked:
                comparisons[i] = {k: v for k, v in cell.items() if k in basic}
                comparisons[i].update(valid_comparison=False, cohort_failure_cases=blocked,
                                      suppression_reason="At least one registered deployment failed this scenario; no cohort ranking")
    return cells


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("run")
    for name in ("registry", "cases", "label", "out"):
        p.add_argument("--" + name, required=True)
    p = commands.add_parser("compare")
    p.add_argument("--registry", required=True)
    p.add_argument("--cases", required=True)
    p.add_argument("--baseline-rows", required=True)
    p.add_argument("--candidate-rows", nargs="+", required=True)
    p.add_argument("--out", required=True)
    args = parser.parse_args()
    registry = verify_registry(args.registry)
    cases, manifest = verify_case_manifest(args.cases, args.registry)
    if args.command == "compare":
        by_label = {c["label"]: c for c in registry["candidates"]}
        labels = []
        for p in [args.baseline_rows, *args.candidate_rows]:
            summary = read(Path(p).parent / "summary.json")
            label = summary["label"]
            assert label in by_label and label not in labels
            labels.append(label)
            assert summary["candidate_sha256"] == by_label[label]["candidate_sha256"]
            assert summary["cases_sha256"] == sha(args.cases)
            assert summary["runner_sha256"] == sha(__file__)
            assert summary["extra_identity"]["registry_sha256"] == sha(args.registry)
        assert labels[0] == "S0" and set(labels) == set(by_label)
        baseline = normalize_rows(cases, read(args.baseline_rows))
        comparisons = compare_cohort(baseline, [normalize_rows(cases, read(p)) for p in args.candidate_rows])
        result = dict(baseline_rows_sha256=sha(args.baseline_rows), runner_sha256=sha(__file__),
                      ci_note="5000 paired seed-cluster bootstrap replicates, seed 110926; exploratory, no multiplicity correction or causal claim.",
                      cohort_failure_policy="Any failed registered deployment suppresses that scenario across all candidates",
                      candidates=[dict(path=str(Path(p).resolve()), rows_sha256=sha(p), comparisons=c) for p, c in zip(args.candidate_rows, comparisons)])
        save(args.out, result)
    else:
        chosen = [c for c in registry["candidates"] if c["label"] == args.label]
        assert len(chosen) == 1
        c = chosen[0]
        result = execute(ROOT / c["candidate_path"], {str(ROOT / k): v for k, v in c["deployment_dependencies"].items()},
                         Path(args.cases).resolve(), args.out, c["label"], c["role"],
                         dict(registry_sha256=sha(args.registry), cases_manifest_sha256=sha(Path(args.cases).parent / "manifest.json")))
        verify_registry(args.registry)
        print(json.dumps({k: result[k] for k in ("label", "actual_runs", "all_valid_completion", "wall_seconds", "modes")}))


if __name__ == "__main__":
    main()
