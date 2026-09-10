"""Audit saved regression rows and their finalized candidate, without rerunning."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import statistics
import subprocess
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def audit(root, snapshot, full, label):
    root, snapshot, full = map(lambda p: Path(p).resolve(), (root, snapshot, full))
    manifest = root / 'evaluation/manifest_v1.json'
    frozen = json.loads(manifest.read_text())['sha256']
    for name, expected in frozen.items():
        assert sha(root / name) == expected, 'Frozen file differs: ' + name
    summary = json.loads((full / 'summary.json').read_text())
    assert summary['candidate_sha256'] == sha(snapshot), 'Snapshot/result mismatch'
    assert summary['manifest_sha256'] == sha(manifest), 'Manifest/result mismatch'
    rows = json.loads((full / 'case_metrics.json').read_text())
    candidate = [r for r in rows if r['variant'] == 'candidate']
    baseline = [r for r in rows if r['variant'] == 'frozen_baseline']
    cases = json.loads((root / 'evaluation/cases_v1.json').read_text())
    expected_ids = {c['case_id'] for c in cases}
    assert len(candidate) == len(baseline) == len(expected_ids) == 2400
    assert {r['case_id'] for r in candidate} == expected_ids
    assert {r['case_id'] for r in baseline} == expected_ids
    base = {r['case_id']: r for r in baseline}
    for row in candidate + baseline:
        assert row['complete'] and not row['error'], 'Incomplete regression case'
        assert row['cleared_count'] == row['source_count']
        assert row['cleared_fraction'] == 1
        assert row['exit_reason'] == 'user_exit'
        assert abs(row['average_clear_time_s'] -
                   row['total_virtual_time_s'] / row['cleared_count']) < 1e-8
    modes, groups = [], []
    for mode in (3, 4):
        part = [r for r in candidate if r['mode'] == mode]
        assert len(part) == 1200
        b = statistics.mean(base[r['case_id']]['average_clear_time_s'] for r in part)
        c = statistics.mean(r['average_clear_time_s'] for r in part)
        modes.append(dict(mode=mode, cases=len(part), complete=len(part), errors=0,
                          source_count=sum(r['source_count'] for r in part),
                          cleared_count=sum(r['cleared_count'] for r in part),
                          baseline_mean_s_per_source=b, candidate_mean_s_per_source=c,
                          reduction_fraction=1-c/b,
                          max_program_runtime_s=max(r['program_runtime_s'] for r in part)))
        for group in sorted({r['group'] for r in part}):
            sub = [r for r in part if r['group'] == group]
            assert len(sub) == 100
            b = statistics.mean(base[r['case_id']]['average_clear_time_s'] for r in sub)
            c = statistics.mean(r['average_clear_time_s'] for r in sub)
            groups.append(dict(mode=mode, group=group, cases=len(sub),
                               baseline_mean_s_per_source=b,
                               candidate_mean_s_per_source=c, reduction_fraction=1-c/b))
    tree = ast.parse(snapshot.read_text())
    imports = sorted({n.module or '' for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} |
                     {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names})
    env_attributes = sorted({n.attr for n in ast.walk(tree)
                             if isinstance(n, ast.Attribute)
                             and isinstance(n.value, ast.Attribute) and n.value.attr == 'env'})
    return dict(label=label, worktree=str(root), head=git(root, 'rev-parse', 'HEAD'),
                branch=git(root, 'branch', '--show-current'),
                working_tree_status=git(root, 'status', '--short'),
                candidate_snapshot=str(snapshot), candidate_sha256=sha(snapshot),
                current_solver_matches_snapshot=sha(root / 'solver.py') == sha(snapshot),
                full_results=str(full), full_rows_sha256=sha(full / 'case_metrics.json'),
                full_summary_sha256=sha(full / 'summary.json'),
                manifest_sha256=sha(manifest), all_frozen_files_match=True,
                all_2400_candidate_cases_complete=True, wall_seconds=summary['wall_seconds'],
                modes=modes, groups=groups,
                regressing_groups=[g for g in groups if g['reduction_fraction'] < -1e-12],
                imports=imports, syntactic_env_attributes=env_attributes,
                inspection_note='AST inventory is not proof of interface-only behavior; '
                                'complete candidate diff requires manual review.')


def main():
    parser = argparse.ArgumentParser()
    for flag in ('root', 'snapshot', 'full', 'label', 'out'):
        parser.add_argument('--' + flag, required=True)
    args = parser.parse_args()
    result = audit(args.root, args.snapshot, args.full, args.label)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(dict(label=result['label'], modes=result['modes'],
                          regression_count=len(result['regressing_groups'])), ensure_ascii=False))


if __name__ == '__main__':
    main()
