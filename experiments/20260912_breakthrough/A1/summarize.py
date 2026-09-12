"""Recompute the A1 experiment and call ledger from retained raw rows."""
import hashlib
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = ROOT / 'experiments/20260911_stage4/combination/results/c7_exposed/case_metrics.json'
read = lambda path: json.loads(path.read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()


def candidate_rows(path):
    return [r for r in read(path) if r.get('variant', 'candidate') == 'candidate']


def valid(row):
    return (row['complete'] and row['error'] is None and row['exit_reason'] == 'user_exit'
            and row['cleared_count'] == row['source_count'] and row['cleared_count'] > 0)


def metrics(rows):
    out = {}
    for mode in (3, 4):
        subset = [r for r in rows if r['mode'] == mode]
        good = all(valid(r) for r in subset)
        assert subset
        for r in subset:
            if r['cleared_count']:
                assert abs(r['average_clear_time_s'] - r['total_virtual_time_s'] / r['cleared_count']) < 1e-8
        out[str(mode)] = dict(cases=len(subset), all_complete=good,
            failures=sum(not valid(r) for r in subset), source_count=sum(r['source_count'] for r in subset),
            cleared_count=sum(r['cleared_count'] for r in subset),
            mean_s_per_source=statistics.mean(r['average_clear_time_s'] for r in subset) if good else None,
            worst_s_per_source=max(r['average_clear_time_s'] for r in subset) if good else None,
            total_requests=sum(r['requests'] for r in subset),
            mean_program_runtime_s=statistics.mean(r['program_runtime_s'] for r in subset),
            max_program_runtime_s=max(r['program_runtime_s'] for r in subset))
    return out


def paired(rows, control):
    refs = {r['case_id']: r for r in control}
    assert len(refs) == len(control)
    assert all(r['case_id'] in refs for r in rows)
    result = []
    suites = ['combined'] + sorted(set(r.get('exposure_suite', 'v1') for r in rows))
    for suite in suites:
        for mode in (3, 4):
            for group in ['ALL'] + sorted(set(r['group'] for r in rows if r['mode'] == mode)):
                sub = [r for r in rows if r['mode'] == mode and (suite == 'combined' or r.get('exposure_suite', 'v1') == suite)
                       and (group == 'ALL' or r['group'] == group)]
                if not sub:
                    continue
                for r in sub:
                    ref = refs[r['case_id']]
                    assert r['source_count'] == ref['source_count'] and r['mode'] == ref['mode'] and r['group'] == ref['group']
                good = all(valid(r) and valid(refs[r['case_id']]) for r in sub)
                deltas = [r['average_clear_time_s'] - refs[r['case_id']]['average_clear_time_s'] for r in sub] if good else []
                result.append(dict(suite=suite, mode=mode, group=group, cases=len(sub), valid=good,
                    delta_s_per_source=statistics.mean(deltas) if good else None,
                    faster=sum(x < -1e-8 for x in deltas), equal=sum(abs(x) <= 1e-8 for x in deltas),
                    slower=sum(x > 1e-8 for x in deltas), max_regression=max(deltas) if good else None))
    return result


def main():
    choices = read(HERE / 'round_decisions.json')
    base = candidate_rows(BASE)
    assert len(base) == 4800
    ledger = []
    budgets = []
    all_ids = set()
    for choice in choices['rounds']:
        rid = choice['round']
        snap = HERE / 'snapshots' / (rid + '.py')
        row = {**choice, 'candidate_sha256': sha(snap)}
        all_scopes = {}
        for scope in ('quick', 'full', 'exposed'):
            directory = HERE / 'results' / (rid + '_' + scope)
            if not (directory / 'case_metrics.json').exists():
                continue
            rows = candidate_rows(directory / 'case_metrics.json')
            summary = read(directory / 'summary.json')
            assert sha(snap) == summary['candidate_sha256']
            assert len({r['case_id'] for r in rows}) == len(rows)
            all_ids.update(r['case_id'] for r in rows)
            all_scopes[scope] = metrics(rows)
            all_scopes[scope]['rows_sha256'] = sha(directory / 'case_metrics.json')
            # v1 full rows in exposed outputs are byte/hash-checked reuse, not new runs.
            executed = rows if scope != 'exposed' else [r for r in rows if r['exposure_suite'] != 'v1']
            assert len(executed) == (summary['new_runs'] if scope == 'exposed' else summary['runs'])
            budgets.append(dict(round=rid, scope=scope, actual_policy_runs=len(executed),
                actual_requests=sum(r['requests'] for r in executed),
                failed_runs=sum(not valid(r) for r in executed),
                wall_s=summary['wall_seconds_new_runs'] if scope == 'exposed' else summary['wall_seconds'],
                rows_path=str((directory / 'case_metrics.json').relative_to(HERE))))
        row['scopes'] = all_scopes
        deepest = next((s for s in ('exposed', 'full', 'quick') if s in all_scopes), None)
        if deepest:
            rows = candidate_rows(HERE / 'results' / (rid + '_' + deepest) / 'case_metrics.json')
            row['comparison_to_c7'] = paired(rows, base)
            control_round = choice.get('gate_control')
            if control_round:
                control = candidate_rows(HERE / 'results' / (control_round + '_exposed') / 'case_metrics.json')
                row['comparison_to_gate_control'] = paired(rows, control)
            if rid == 'r8':
                row['comparison_to_r6b'] = paired(rows, candidate_rows(HERE / 'results/r6b_exposed/case_metrics.json'))
        ledger.append(row)
    diagnostic = read(HERE / 'diagnostic_q3_quick/summary.json')
    diagnostic_requests = sum(r['counters']['measure'] + r['counters']['clear_attempts'] + 2 for r in diagnostic['rows'])
    cover = read(HERE / 'results/r6b_cover_diagnostic.json')
    cover_requests = sum(r['counters']['measure'] + r['counters']['clear_attempts'] + 2 for r in cover['rows'])
    failed_diag_count = cover['previous_diagnostic_attempt']['policy_runs']
    failed_diag_requests = sum(r['counters']['measure'] + r['counters']['clear_attempts'] + 2 for r in cover['rows'][:failed_diag_count])
    diagnostics = [dict(label='C7 quick action-cost trace', runs=diagnostic['cases'], requests=diagnostic_requests, evidence='saved counters and actions'),
                   dict(label='R6b first diagnostic reader failure', runs=failed_diag_count, requests=failed_diag_requests,
                        evidence='count reconstructed by deterministic replay of the same immutable candidate and worlds, not an independently saved first-attempt action ledger'),
                   dict(label='R6b repaired diagnostic replay', runs=cover['policy_runs'], requests=cover_requests, evidence='saved counters')]
    for extra in choices.get('additional_diagnostics', []):
        detail = read(HERE / extra['path'])
        diagnostics.append(dict(label=extra['label'], runs=detail['policy_runs'],
            requests=sum(r['counters']['measure'] + r['counters']['clear_attempts'] + 2 for r in detail['rows']), evidence=extra['path']))
    totals = dict(evaluation_runs=sum(b['actual_policy_runs'] for b in budgets),
                  evaluation_requests=sum(b['actual_requests'] for b in budgets),
                  evaluation_failures=sum(b['failed_runs'] for b in budgets),
                  evaluation_wall_s=sum(b['wall_s'] for b in budgets),
                  diagnostic_runs=sum(d['runs'] for d in diagnostics),
                  diagnostic_requests=sum(d['requests'] for d in diagnostics),
                  unique_exposed_case_ids=len(all_ids), new_holdout_worlds=0,
                  official_runs=0, training_runs=0,
                  request_counting='v1 recorded requests = measures + clear_attempts + int(started) + int(user_exit); parameter/state prevalidation rejection attempts are not fully counted',
                  attempt_counts_available=False,
                  rules='Frozen unit/nominal checks are not candidate policy executions; source reading, synthetic geometry CPU, assembly and audit overhead are not inside evaluation_wall_s',
                  timing='Wall and per-case runtimes were gathered under concurrent workloads, not controlled benchmark latency or official runtime')
    totals['total_policy_runs'] = totals['evaluation_runs'] + totals['diagnostic_runs']
    totals['total_requests'] = totals['evaluation_requests'] + totals['diagnostic_requests']
    output = dict(data_role='Exposed local regression, not holdout or official',
        metric='Arithmetic mean across case total_virtual_time_s/cleared_count; no success-only filtering or mixed-Q score',
        request_field_semantics='All requests/actual_requests numeric fields retain the frozen v1 recorded-request convention, not all interface attempts. Diagnostic complete-run counters plus two reproduce the same convention. Rejected-attempt totals are unavailable.',
        best_round=choices['best_round'], decisions=choices['directions'], rows=ledger, budgets=budgets, diagnostics=diagnostics, totals=totals)
    (HERE / 'iteration_ledger.json').write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(json.dumps(totals, ensure_ascii=False, indent=2))
    for row in ledger:
        print(row['round'], row['status'], {s: x['3']['mean_s_per_source'] for s, x in row['scopes'].items()})


if __name__ == '__main__':
    main()
