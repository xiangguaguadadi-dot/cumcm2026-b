"""Read-only paired review of finalized strategies on new local cases.

The v1 evaluator and case generator are never modified. Case-generation code
is loaded through its function AST to avoid its module-level file write.
This is a new-seed validation under local assumptions, not official replay.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import importlib.util
import json
import math
import platform
import random
import statistics
import sys
import time
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2))


def valid_completion(row):
    return (row['complete'] and not row['error'] and row['exit_reason'] == 'user_exit'
            and row['cleared_count'] == row['source_count'])


def verified_env(root):
    root = Path(root).resolve()
    sys.path.insert(0, str(root))
    import evaluate

    assert Path(evaluate.__file__).resolve() == root / 'evaluate.py'
    evaluate.verify()
    return evaluate


def generate(args):
    root = Path(args.root).resolve()
    verified_env(root)
    from local_env import Source

    source = root / 'evaluation/generate_cases.py'
    tree = ast.parse(source.read_text())
    nodes = [node for node in tree.body
             if isinstance(node, ast.FunctionDef) and node.name == 'sources'
             or isinstance(node, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == 'groups' for t in node.targets)]
    assert len(nodes) == 2
    namespace = dict(random=random, math=math, Source=Source)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), namespace)
    seeds = random.SystemRandom().sample(range(10**8, 2**31), args.seeds)
    cases = []
    for mode in (3, 4):
        for group, scenario, noise in namespace['groups']:
            for index, seed in enumerate(seeds):
                cases.append(dict(
                    case_id=f'LOCAL-final-q{mode}-{group}-{seed}', mode=mode,
                    group=group, noise=noise, seed=seed, quick=False,
                    sources=[vars(s) for s in namespace['sources'](seed, mode, scenario)]))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    save(out / 'cases.json', cases)
    save(out / 'manifest.json', dict(
        label='Final new-seed local validation; not official results',
        generation_time_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        cases=len(cases), distinct_seed_clusters=len(seeds), seeds=seeds,
        cases_sha256=sha(out / 'cases.json'),
        frozen_generator_sha256=sha(source),
        frozen_manifest_sha256=sha(root / 'evaluation/manifest_v1.json'),
        distribution_note='Same 12 local scenario assumptions; fresh random seeds. '
                          'Each seed is reused across groups and modes, so inference clusters by seed.'))
    print(json.dumps(dict(cases=len(cases), sha256=sha(out / 'cases.json'))))


def runtime_fingerprint(root):
    """Record implementation and model/config files, excluding results/corpora."""
    paths = list(root.glob('*.py')) + list(root.glob('*.json'))
    return {str(p.relative_to(root)): sha(p) for p in paths if p.is_file()}


def run(args):
    root = Path(args.root).resolve()
    evaluator = verified_env(root)
    cases_file = Path(args.cases).resolve()
    cases_hash = sha(cases_file)
    cases = json.loads(cases_file.read_text())
    candidate = Path(args.candidate).resolve()
    candidate_sha = sha(candidate)
    optional_coverage = candidate.parent / 'coverage_points.json'
    coverage_before = sha(optional_coverage) if optional_coverage.is_file() else None
    before = runtime_fingerprint(root)
    dependencies = json.loads(Path(args.dependency_manifest).read_text()) if args.dependency_manifest else {}
    for name, expected in dependencies.items():
        assert sha(Path(name)) == expected, 'Selected dependency does not match: ' + name
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    t0 = time.perf_counter()
    rows = evaluator.run_cases(cases, candidate, args.baseline)
    wall_seconds = time.perf_counter() - t0
    evaluator.verify()
    assert sha(candidate) == candidate_sha, 'Candidate changed during review'
    assert sha(cases_file) == cases_hash, 'Case file changed during review'
    assert coverage_before == (sha(optional_coverage) if optional_coverage.is_file() else None), \
        'Optional candidate coverage configuration changed during review'
    assert before == runtime_fingerprint(root), 'Runtime root files changed during review'
    for name, expected in dependencies.items():
        assert sha(Path(name)) == expected, 'Dependency changed during review: ' + name
    assert len(rows) == len(cases) == len({c['case_id'] for c in cases})
    for row, case in zip(rows, cases):
        assert row['case_id'] == case['case_id']
        assert row['mode'] == case['mode'] and row['group'] == case['group']
        row['seed_cluster'] = case['seed']
    save(out / 'case_metrics.json', rows)
    summary = dict(
        label=args.label, role='baseline' if args.baseline else 'candidate',
        root=str(root), candidate=str(candidate), candidate_sha256=candidate_sha,
        root_runtime_fingerprint=before, selected_dependencies=dependencies,
        optional_coverage_path=str(optional_coverage), optional_coverage_sha256=coverage_before,
        cases_sha256=cases_hash,
        manifest_sha256=sha(root / 'evaluation/manifest_v1.json'),
        python=platform.python_version(), platform=platform.platform(),
        wall_seconds=wall_seconds, runs=len(rows),
        all_complete=all(r['complete'] for r in rows),
        all_valid_completion=all(valid_completion(r) for r in rows), modes=[])
    for mode in (3, 4):
        part = [r for r in rows if r['mode'] == mode]
        successful = all(valid_completion(r) for r in part)
        summary['modes'].append(dict(
            mode=mode, cases=len(part), complete=sum(r['complete'] for r in part),
            errors=sum(bool(r['error']) for r in part),
            valid_completion=sum(valid_completion(r) for r in part),
            abnormal_exit=sum(r['exit_reason'] != 'user_exit' for r in part),
            cleared=sum(r['cleared_count'] or 0 for r in part),
            sources=sum(r['source_count'] for r in part),
            mean_s_per_source=statistics.mean(r['average_clear_time_s'] for r in part)
                              if successful else None,
            worst_s_per_source=max(r['average_clear_time_s'] for r in part)
                               if successful else None,
            mean_runtime_s=statistics.mean(r['program_runtime_s'] for r in part)
                           if successful else None))
    save(out / 'summary.json', summary)
    fields = ['case_id', 'mode', 'group', 'seed_cluster', 'cleared_count', 'source_count',
              'cleared_fraction', 'average_clear_time_s', 'total_virtual_time_s',
              'program_runtime_s', 'complete', 'error', 'exit_reason']
    with (out / 'case_metrics.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(summary, ensure_ascii=False))


def compare(args):
    baseline = json.loads(Path(args.baseline_rows).read_text())
    base_index = {r['case_id']: r for r in baseline}
    assert len(base_index) == len(baseline), 'Duplicate baseline case IDs'
    reports = []
    for row_file in args.candidate_rows:
        rows = json.loads(Path(row_file).read_text())
        assert len(rows) == len(base_index), 'Wrong candidate row count'
        assert {r['case_id'] for r in rows} == set(base_index), 'Case sets differ'
        for row in rows:
            base_row = base_index[row['case_id']]
            assert all(row[k] == base_row[k] for k in ('mode', 'group', 'seed_cluster', 'source_count')), \
                'Paired case metadata differ'
        result = dict(path=str(Path(row_file).resolve()), modes=[], groups=[])
        for mode in (3, 4):
            part = [r for r in rows if r['mode'] == mode]
            good = all(valid_completion(r) and valid_completion(base_index[r['case_id']]) for r in part)
            info = dict(mode=mode, complete=sum(r['complete'] for r in part),
                        cases=len(part), comparison_valid=good)
            if good:
                base = statistics.mean(base_index[r['case_id']]['average_clear_time_s'] for r in part)
                cand = statistics.mean(r['average_clear_time_s'] for r in part)
                clustered = {}
                for r in part:
                    clustered.setdefault(r['seed_cluster'], []).append(
                        base_index[r['case_id']]['average_clear_time_s'] - r['average_clear_time_s'])
                units = [statistics.mean(v) for v in clustered.values()]
                rng = random.Random(110926)
                boot = sorted(statistics.mean(rng.choices(units, k=len(units)))
                              for _ in range(5000))
                info.update(baseline_mean_s_per_source=base,
                            candidate_mean_s_per_source=cand,
                            reduction_fraction=1-cand/base,
                            paired_mean_saved_s_per_source=base-cand,
                            paired_saved_seed_cluster_bootstrap_95ci=[boot[124], boot[4874]],
                            seed_clusters=len(units))
                base_movement = statistics.mean(
                    base_index[r['case_id']]['distance_m'] / 5 / r['cleared_count'] for r in part)
                cand_movement = statistics.mean(
                    r['distance_m'] / 5 / r['cleared_count'] for r in part)
                info['time_decomposition'] = dict(
                    baseline_movement_s_per_source=base_movement,
                    candidate_movement_s_per_source=cand_movement,
                    paired_movement_saved_s_per_source=base_movement-cand_movement,
                    baseline_other_s_per_source=base-base_movement,
                    candidate_other_s_per_source=cand-cand_movement,
                    paired_other_saved_s_per_source=(base-cand)-(base_movement-cand_movement),
                    note='Movement is logged distance / 5 m/s. Residual includes sensing, '
                         'channel switching, optical actions and microsecond rounding; '
                         'this accounting identity is not a component ablation.')
            result['modes'].append(info)
            for group in sorted({r['group'] for r in part}):
                sub = [r for r in part if r['group'] == group]
                good = all(valid_completion(r) and valid_completion(base_index[r['case_id']]) for r in sub)
                item = dict(mode=mode, group=group, cases=len(sub),
                            complete=sum(r['complete'] for r in sub), comparison_valid=good)
                if good:
                    base = statistics.mean(base_index[r['case_id']]['average_clear_time_s'] for r in sub)
                    cand = statistics.mean(r['average_clear_time_s'] for r in sub)
                    item.update(baseline_mean_s_per_source=base,
                                candidate_mean_s_per_source=cand,
                                reduction_fraction=1-cand/base)
                result['groups'].append(item)
        reports.append(result)
    save(args.out, dict(
        label='Paired final new-seed comparison; local assumptions, not official',
        ci_note='Exploratory percentile bootstrap of seed-cluster mean paired differences. '
                'Not a proof of causality or a multiplicity-corrected winner test.',
        candidates=reports))
    print(json.dumps([r['modes'] for r in reports], ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('generate')
    p.add_argument('--root', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--seeds', type=int, default=100)
    p.set_defaults(function=generate)
    p = commands.add_parser('run')
    p.add_argument('--root', required=True)
    p.add_argument('--candidate', required=True)
    p.add_argument('--cases', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--label', required=True)
    p.add_argument('--baseline', action='store_true')
    p.add_argument('--dependency-manifest', help='JSON mapping of absolute dependency paths to SHA256')
    p.set_defaults(function=run)
    p = commands.add_parser('compare')
    p.add_argument('--baseline-rows', required=True)
    p.add_argument('--candidate-rows', nargs='+', required=True)
    p.add_argument('--out', required=True)
    p.set_defaults(function=compare)
    args = parser.parse_args()
    args.function(args)


if __name__ == '__main__':
    main()
