"""Freeze finalized route candidates before generating any final-review cases."""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

from audit_candidate import audit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def first(record, *keys):
    for key in keys:
        if key in record:
            return record[key]
    raise KeyError(keys)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    assert not (HERE / 'final_validation').exists(), 'Final cases already exist'
    assert not (HERE / 'candidate_registry.json').exists(), 'Registry already frozen'
    destination = HERE / 'final_candidates'
    destination.mkdir(exist_ok=False)
    records = []
    for assignment in json.loads((HERE / 'assignments.json').read_text())['assignments']:
        root, identity = Path(assignment['worktree']), assignment['id']
        assert not subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain']).strip()
        best_path = root / 'experiments' / identity / 'best.json'
        best = json.loads(best_path.read_text())
        selected = [(best, 'route_best')]
        best_round = first(best, 'best_round', 'round')
        for alternative in best.get('non_dominated_candidates', []):
            if alternative['round'] != best_round:
                selected.append((alternative, 'route_nondominated_tradeoff'))
        for alternative in best.get('retained_alternative_rounds', []):
            path = alternative['snapshot']
            commit = subprocess.check_output(['git', '-C', str(root), 'log', '-1', '--format=%H', '--', path], text=True).strip()
            selected.append((dict(round=alternative['round'], snapshot=path, sha256=sha(root/path),
                full_results=f'results/{identity}_r{alternative["round"]}_full', code_commit=commit),
                'route_reported_scenario_tradeoff'))
        if identity == 'A1_space':
            selected.append((dict(round=10, solver_path='experiments/A1_space/snapshots/solver_r10.py',
                solver_sha256='685a43a2729c5d721c16abc4f8281de8557d130bec668747fc6c99124ad8765c',
                full_results_path='results/A1_space_r10_full',
                code_commit='6eb4ac2e24ad2120e1b4c25263509b74fd8cb3af'), 'preregistered_scenario_tradeoff'))
        head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
        for chosen, reason in selected:
            round_number = first(chosen, 'best_round', 'round')
            label = f'{identity}_R{round_number}'
            snapshot = root / first(chosen, 'snapshot', 'solver_path', 'best_solver_relative',
                                    'solver_relative_path')
            full = root / first(chosen, 'full_results_path', 'full_result_path', 'full_results',
                               'full_results_relative', 'full_results_relative_path')
            expected = first(chosen, 'solver_sha256', 'sha256')
            assert sha(snapshot) == expected
            assert not (snapshot.parent / 'coverage_points.json').exists()
            commit = chosen['code_commit']
            rel = str(snapshot.relative_to(root))
            data = subprocess.check_output(['git', '-C', str(root), 'show', commit + ':' + rel])
            assert hashlib.sha256(data).hexdigest() == expected
            review = audit(root, snapshot, full, label)
            out = destination / (label + '.py')
            out.write_bytes(data)
            assert sha(out) == expected
            (HERE / 'audit' / (label + '_rows.json')).write_text(json.dumps(review, ensure_ascii=False, indent=2))
            records.append(dict(label=label, agent=identity, round=round_number, selection_reason=reason,
                worktree=str(root), branch=assignment['branch'], report_commit=head,
                report_url=f'https://github.com/xiangguaguadadi-dot/cumcm2026-b/blob/{head}/experiments/{identity}/report.md',
                best_record_sha256=sha(best_path), original_snapshot=rel, code_commit=commit,
                candidate_path=str(out.relative_to(ROOT)), candidate_sha256=expected,
                deployment_dependencies={}, optional_coverage_sha256=None,
                regression_full=str(full), regression_rows_sha256=sha(full/'case_metrics.json'),
                regression_modes=review['modes']))
    baseline = ROOT / 'evaluation/baseline_solver.py'
    assert sha(baseline) == '36271e5c84cdcd4468b54484d699dce64194f09d78c0c03f3ec1c38f105f6ca9'
    registry = dict(registered_at_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        note='Frozen before final cases. Exact standalone snapshots; no strategy blending or external runtime weights.',
        baseline_path=str(baseline.relative_to(ROOT)), baseline_sha256=sha(baseline),
        frozen_manifest_sha256=sha(ROOT/'evaluation/manifest_v1.json'), candidates=records)
    (HERE/'candidate_registry.json').write_text(json.dumps(registry, ensure_ascii=False, indent=2))
    print(json.dumps(dict(candidates=len(records), labels=[r['label'] for r in records])))


if __name__ == '__main__':
    main()
