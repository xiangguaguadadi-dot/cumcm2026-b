"""Independent saved-row audit. This does not execute a solver or create new worlds."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STAGE4 = ROOT / 'experiments/20260911_stage4'
BASE = STAGE4 / 'combination/results/c7_exposed/case_metrics.json'
CASES = STAGE4 / 'exposed_cases.json'
C7 = STAGE4 / 'combination/geometry_fusions/C7_both.py'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def good(row):
    return (row.get('complete') is True and row.get('exit_reason') == 'user_exit'
            and row.get('error') is None and row.get('source_count', 0) > 0
            and row.get('cleared_count') == row.get('source_count'))


def audit(candidate_rows, baseline_rows, cases):
    assert len(cases) == len(candidate_rows) == len(baseline_rows) == 4800
    ids = {x['case_id']: x for x in cases}
    baseline = {x['case_id']: x for x in baseline_rows}
    candidate = {x['case_id']: x for x in candidate_rows}
    assert len(ids) == len(baseline) == len(candidate) == 4800
    assert set(ids) == set(baseline) == set(candidate)
    formula_errors = []
    metadata_errors = []
    for variant, mapping in [('candidate', candidate), ('baseline', baseline)]:
        for cid, row in mapping.items():
            c = ids[cid]
            if (row['mode'], row['group'], row['source_count'], row['exposure_suite']) != (
                    c['mode'], c['group'], len(c['sources']), c['exposure_suite']):
                metadata_errors.append([variant, cid])
            if row.get('cleared_count', 0) > 0:
                expected = row['total_virtual_time_s'] / row['cleared_count']
                if not math.isclose(row['average_clear_time_s'], expected, abs_tol=1e-9):
                    formula_errors.append([variant, cid, expected, row['average_clear_time_s']])
            elif row.get('average_clear_time_s') is not None:
                formula_errors.append([variant, cid, 'zero denominator must be null'])
    assert not metadata_errors, metadata_errors
    assert not formula_errors, formula_errors
    groups = []
    for suite in ['combined', 'v1', 'previous_final']:
        for mode in [3, 4]:
            for group in ['ALL', *sorted({c['group'] for c in cases})]:
                keys = [cid for cid, c in ids.items() if c['mode'] == mode
                        and (suite == 'combined' or c['exposure_suite'] == suite)
                        and (group == 'ALL' or c['group'] == group)]
                aa = [candidate[k] for k in keys]
                bb = [baseline[k] for k in keys]
                ok = all(good(r) for r in aa + bb)
                entry = dict(suite=suite, mode=mode, group=group, cases=len(keys),
                             candidate_complete=sum(good(r) for r in aa),
                             baseline_complete=sum(good(r) for r in bb),
                             source_count=sum(r['source_count'] for r in aa),
                             candidate_cleared=sum(r.get('cleared_count') or 0 for r in aa),
                             valid_comparison=ok)
                if ok and keys:
                    av = [r['average_clear_time_s'] for r in aa]
                    bv = [r['average_clear_time_s'] for r in bb]
                    delta = [x-y for x, y in zip(av, bv)]
                    mean_a, mean_b = statistics.fmean(av), statistics.fmean(bv)
                    entry.update(candidate_mean=mean_a, baseline_mean=mean_b,
                                 delta=mean_a-mean_b, improvement_pct=100*(mean_b-mean_a)/mean_b,
                                 faster=sum(d < -1e-8 for d in delta),
                                 equal=sum(abs(d) <= 1e-8 for d in delta),
                                 slower=sum(d > 1e-8 for d in delta),
                                 worst_candidate=max(av), largest_regression=max(delta),
                                 largest_improvement=min(delta),
                                 candidate_requests=sum(r['requests'] for r in aa),
                                 candidate_clear_failures=sum(r['clear_failures'] for r in aa),
                                 candidate_mean_move_s_per_source=statistics.fmean(
                                     r['distance_m']/5/r['cleared_count'] for r in aa),
                                 candidate_max_runtime_s=max(r['program_runtime_s'] for r in aa))
                    entry['candidate_mean_nonmove_s_per_source'] = (
                        mean_a - entry['candidate_mean_move_s_per_source'])
                groups.append(entry)
    return dict(status='consistent' if all(good(r) for r in candidate_rows+baseline_rows)
                else 'incomplete_cases_present', row_count=len(candidate_rows),
                unique_case_ids=len(candidate), formula_error_count=len(formula_errors),
                metadata_error_count=len(metadata_errors),
                failed_candidate_ids=[r['case_id'] for r in candidate_rows if not good(r)],
                comparisons=groups)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--rows', type=Path, default=BASE)
    p.add_argument('--baseline-rows', type=Path, default=BASE)
    p.add_argument('--candidate', type=Path, default=C7)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    assert not a.out.exists(), 'Output already exists; preserve earlier evidence'
    manifest = read(STAGE4 / 'exposure_manifest.json')
    assert digest(CASES) == manifest['cases_sha256']
    summary_path = a.rows.parent / 'summary.json'
    if summary_path.exists():
        summary = read(summary_path)
        assert summary['candidate_sha256'] == digest(a.candidate)
    result = audit(read(a.rows), read(a.baseline_rows), read(CASES))
    result.update(evidence='Independent saved-row recomputation; exposed regression, not new inference or holdout',
                  candidate=str(a.candidate), candidate_sha256=digest(a.candidate),
                  candidate_rows=str(a.rows), candidate_rows_sha256=digest(a.rows),
                  baseline_rows=str(a.baseline_rows), baseline_rows_sha256=digest(a.baseline_rows),
                  cases_sha256=digest(CASES), script_sha256=digest(__file__))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'comparisons'}, ensure_ascii=False))
    print(json.dumps([r for r in result['comparisons'] if r['group'] == 'ALL'], ensure_ascii=False))


if __name__ == '__main__':
    main()
