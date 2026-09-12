"""Read-only independent batch-cost reconciliation; never executes strategies."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def actual_rows(summary_path):
    """Exclude cached comparison rows and reused v1 rows, but retain failures."""
    summary = read(summary_path)
    directory = summary_path.parent
    if summary.get('suite') in ('quick', 'full'):
        assert summary['baseline_cached'] is True, 'Uncached baseline needs separate accounting'
        rows_path = directory / 'case_metrics.json'
        rows = [r for r in read(rows_path) if r['variant'] == 'candidate']
        return [(directory.name, rows_path, rows, summary['runs'], summary['wall_seconds'])]
    if 'new_runs' in summary:
        rows_path = directory / 'case_metrics.json'
        rows = read(rows_path)
        if summary['v1_reused']:
            # Membership comes from the frozen exposure partition, not the summary total.
            exposed = read(ROOT / 'experiments/20260911_stage4/exposed_cases.json')
            new_ids = {c['case_id'] for c in exposed if c['exposure_suite'] == 'previous_final'}
            rows = [r for r in rows if r['case_id'] in new_ids]
            reused_path = Path(summary['v1_reused']['path']) / 'case_metrics.json'
            assert sha(reused_path) == summary['v1_reused']['rows_sha256']
        return [(directory.name, rows_path, rows, summary['new_runs'], summary['wall_seconds_new_runs'])]
    batches = []
    for key, entry in summary.items():
        if isinstance(entry, dict) and entry.get('runs', 0) > 0:
            rows_path = directory / (key + '_rows.json')
            if rows_path.exists():
                batches.append((directory.name + '/' + key, rows_path, read(rows_path),
                                entry['runs'], entry['wall_s']))
    return batches


def audit(branch):
    batches = []
    for summary_path in sorted((HERE / branch / 'results').glob('*/summary.json')):
        for name, rows_path, rows, expected, wall in actual_rows(summary_path):
            assert len(rows) == len({r['case_id'] for r in rows}) == expected
            missing = sum(type(r.get('requests')) is not int for r in rows)
            count = None if missing else sum(r['requests'] for r in rows)
            batches.append(dict(batch=name, runs=len(rows), recorded_requests=count,
                unknown_request_rows=missing,
                failed_runs=sum(not (r.get('complete') is True and r.get('error') is None
                                    and r.get('exit_reason') == 'user_exit'
                                    and r.get('cleared_count') == r.get('source_count')) for r in rows),
                wall_s=wall, rows_sha256=sha(rows_path), summary_sha256=sha(summary_path)))
    ledger_path = HERE / branch / 'iteration_ledger.json'
    ledger = read(ledger_path)
    reported = {}
    if branch == 'A1':
        for b in ledger['budgets']:
            reported[Path(b['rows_path']).parent.name] = (
                b['actual_policy_runs'], b['actual_requests'], b['failed_runs'], b['wall_s'])
        expected_runs = ledger['totals']['evaluation_runs']
        expected_requests = ledger['totals']['evaluation_requests']
        expected_wall = ledger['totals']['evaluation_wall_s']
    else:
        for b in ledger['execution_costs']['batches']:
            reported[b['batch']] = (b['runs'], b['requests'], 0, b['wall_seconds'])
        expected_runs = ledger['actual_task_runs']
        expected_requests = ledger['execution_costs']['requests']
        expected_wall = ledger['execution_costs']['summed_batch_wall_seconds']
    assert set(reported) == {b['batch'] for b in batches}
    for b in batches:
        target = reported[b['batch']]
        assert (b['runs'], b['recorded_requests'], b['failed_runs']) == target[:3]
        assert math.isclose(b['wall_s'], target[3], abs_tol=1e-8)
    runs = sum(b['runs'] for b in batches)
    unknown = sum(b['unknown_request_rows'] for b in batches)
    requests = None if unknown else sum(b['recorded_requests'] for b in batches)
    wall = sum(b['wall_s'] for b in batches)
    assert (runs, requests) == (expected_runs, expected_requests)
    assert math.isclose(wall, expected_wall, abs_tol=1e-6)
    return dict(branch=branch, status='reconciled', batches=batches,
        runs=runs, recorded_requests=requests, unknown_request_rows=unknown,
        failed_runs=sum(b['failed_runs'] for b in batches), summed_batch_wall_s=wall,
        ledger_sha256=sha(ledger_path),
        scope='Only saved batches listed below; unlisted diagnostics and geometry are excluded',
        cost_boundary='Frozen v1 requests count measures + clear attempts + entered + normal exit. '
                      'They are not a complete attempted-call journal: pre-validation and state '
                      'rejections can be absent. Unknown rejected-attempt overhead is not set to zero.')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--branch', choices=['A1', 'A2'], required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    assert not a.out.exists()
    result = audit(a.branch)
    result['script_sha256'] = sha(__file__)
    result['evidence'] = 'Independent saved-row recomputation; no new policy execution'
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'batches'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
