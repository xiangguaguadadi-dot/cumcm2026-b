"""Independently recompute final identity, completeness, and summary arithmetic.

Does not execute a solver or generate a new seed. Reads the registered final
cohort and all raw rows, checking the shared failure policy before efficiency.
"""
from pathlib import Path
import hashlib
import json
import math
import statistics

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def complete(r):
    return r.get('complete') is True and not r.get('error') and r.get('exit_reason') == 'user_exit' and r.get('cleared_count') == r.get('source_count')


def main():
    registry = read(BASE / 'candidate_registry.json')
    cases = read(BASE / 'final_cases/cases.json')
    manifest = read(BASE / 'final_cases/manifest.json')
    exclusion = read(ROOT / registry['seed_exclusion_path'])
    assert len(cases) == len({c['case_id'] for c in cases}) == 2400
    assert len(set(manifest['seeds'])) == 100
    assert manifest['registry_sha256'] == sha(BASE / 'candidate_registry.json')
    assert manifest['cases_sha256'] == sha(BASE / 'final_cases/cases.json')
    assert not set(manifest['seeds']) & set(exclusion['seeds'])
    assert not any(r['start'] <= s < r['stop'] for s in manifest['seeds'] for r in exclusion['ranges'])
    expected = {c['case_id']: c for c in cases}
    data, summaries = {}, {}
    for candidate in registry['candidates']:
        name = candidate['label']
        rows = read(BASE / 'final_validation' / name / 'case_metrics.json')
        sm = read(BASE / 'final_validation' / name / 'summary.json')
        assert len(rows) == len({r['case_id'] for r in rows}) == 2400
        assert set(expected) == {r['case_id'] for r in rows}
        assert sm['candidate_sha256'] == candidate['candidate_sha256'] == sha(ROOT / candidate['candidate_path'])
        assert sm['actual_runs'] == 2400 and sm['cases_sha256'] == manifest['cases_sha256']
        assert sm['extra_identity']['registry_sha256'] == manifest['registry_sha256']
        for path, digest in candidate['deployment_dependencies'].items():
            assert sha(ROOT / path) == digest
        for r in rows:
            c = expected[r['case_id']]
            assert (r['mode'], r['group'], r['seed_cluster'], r['source_count']) == (c['mode'], c['group'], c['seed'], len(c['sources']))
            if complete(r):
                assert r['coverage_certificate'] is True
                assert r['cleared_fraction'] == 1
                assert 0 < r['total_virtual_time_s'] < 360000 and 0 <= r['program_runtime_s'] < 1200
                assert math.isclose(r['average_clear_time_s'], r['total_virtual_time_s'] / len(c['sources']), rel_tol=1e-12, abs_tol=1e-9)
        for cell in sm['modes']:
            part = [r for r in rows if r['mode'] == cell['mode']]
            assert cell['cases'] == len(part) == 1200
            assert cell['source_count'] == sum(r['source_count'] for r in part)
            assert cell['valid_completion'] == sum(complete(r) for r in part)
            if all(complete(r) for r in part):
                assert math.isclose(cell['mean_s_per_source'], statistics.mean(r['average_clear_time_s'] for r in part), rel_tol=1e-12)
        data[name] = {r['case_id']: r for r in rows}
        summaries[name] = sm
    comparison = read(BASE / 'final_validation/comparison.json')
    cells_checked = 0
    for output in comparison['candidates']:
        name = Path(output['path']).parent.name
        assert output['rows_sha256'] == sha(Path(output['path']))
        for cell in output['comparisons']:
            ids = [k for k, r in data[name].items() if r['mode'] == cell['mode'] and (cell['group'] == 'ALL' or r['group'] == cell['group'])]
            valid = all(complete(data[label][k]) for label in data for k in ids)
            assert cell['valid_comparison'] == valid
            if not valid:
                assert all(k not in cell for k in ('reduction_fraction', 'faster', 'candidate_mean_s_per_source'))
                continue
            a = [data[name][k]['average_clear_time_s'] for k in ids]
            b = [data['S0'][k]['average_clear_time_s'] for k in ids]
            ma, mb = statistics.mean(a), statistics.mean(b)
            delta = [x-y for x, y in zip(a, b)]
            for key, value in [('candidate_mean_s_per_source', ma), ('baseline_mean_s_per_source', mb), ('delta_s_per_source', ma-mb), ('reduction_fraction', (mb-ma)/mb)]:
                assert math.isclose(cell[key], value, abs_tol=1e-9, rel_tol=1e-12)
            assert [cell[k] for k in ('faster', 'equal', 'slower')] == [sum(d < -1e-8 for d in delta), sum(abs(d) <= 1e-8 for d in delta), sum(d > 1e-8 for d in delta)]
            assert cell['source_count'] == sum(data[name][k]['source_count'] for k in ids)
            assert math.isclose(cell['max_regression_s_per_source'], max(0, max(delta)), abs_tol=1e-9)
            cells_checked += 1
    fields = ['case_id','mode','group','cleared_count','source_count','cleared_fraction','average_clear_time_s','total_virtual_time_s','complete','exit_reason','error','coverage_certificate','requests','distance_m','clear_failures']
    for k, r in data['Combined'].items():
        parent = data['R2_open_R4' if r['mode'] == 3 else 'R3_open_R5'][k]
        assert all(r[x] == parent[x] for x in fields), (k, 'dispatch mismatch')
    result = dict(status='pass',registered_deployments=len(data),actual_policy_executions=sum(s['actual_runs'] for s in summaries.values()),
                  unique_cases=2400,source_seed_clusters=100,case_seed_exclusion_verified=True,
                  all_complete=all(complete(r) for rows in data.values() for r in rows.values()),
                  failed_cases={k:[r['case_id'] for r in v.values() if not complete(r)] for k,v in data.items()},
                  paired_summary_cells_recomputed=cells_checked,dispatch_task_scalars_equal=2400*len(fields),
                  cases_sha256=manifest['cases_sha256'],registry_sha256=manifest['registry_sha256'],comparison_sha256=sha(BASE/'final_validation/comparison.json'),
                  source_count_by_mode={str(m):sum(len(c['sources']) for c in cases if c['mode']==m) for m in (3,4)},
                  note='Independent raw-row arithmetic and identity recomputation; zero additional policy executions. Bootstrap mechanism was independently fixture-checked before drawing these cases.')
    (BASE/'audit/final_results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
