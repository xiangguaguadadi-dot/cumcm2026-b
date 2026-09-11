"""Second-campaign exposed regression against task-wise C0; never a holdout.

Example: python experiments/20260911_breakthrough/evaluate_exposed.py \
  --candidate experiments/B1/snapshots/r1.py --out results/B1_r1_exposed \
  --v1-results results/B1_r1_full
Existing v1 rows can be reused only with the exact candidate/manifest hash.
The additional 2400 previous-final cases are actually executed.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def read(p):
    return json.loads(Path(p).read_text())

def save(p, value):
    Path(p).write_text(json.dumps(value, ensure_ascii=False, indent=2))

def valid(row):
    return row.get('complete') and row.get('exit_reason') == 'user_exit' and not row.get('error') and row.get('cleared_count') == row.get('source_count')

def compare(rows, refs):
    index = {r['case_id']: r for r in refs}
    assert len(index) == len(refs) == len(rows) == len({r['case_id'] for r in rows})
    assert set(index) == {r['case_id'] for r in rows}
    output = []
    for suite in ('combined', 'v1', 'previous_final'):
        for mode in (3, 4):
            selected = [r for r in rows if r['mode'] == mode and (suite == 'combined' or r['exposure_suite'] == suite)]
            for group in ('ALL', *sorted({r['group'] for r in selected})):
                part = [r for r in selected if group == 'ALL' or r['group'] == group]
                bases = [index[r['case_id']] for r in part]
                assert all((r['mode'],r['group'],r['source_count']) == (b['mode'],b['group'],b['source_count']) for r,b in zip(part,bases))
                ok = all(valid(r) and valid(b) for r,b in zip(part,bases))
                entry = dict(suite=suite, mode=mode, group=group, cases=len(part), valid_comparison=ok,
                    candidate_complete=sum(bool(valid(r)) for r in part), baseline_complete=sum(bool(valid(b)) for b in bases),
                    candidate_cleared=sum(r.get('cleared_count') or 0 for r in part), source_count=sum(r['source_count'] for r in part),
                    candidate_errors=sum(bool(r.get('error')) for r in part))
                if ok:
                    a=statistics.mean(b['average_clear_time_s'] for b in bases)
                    b=statistics.mean(r['average_clear_time_s'] for r in part)
                    deltas=[r['average_clear_time_s']-base['average_clear_time_s'] for r,base in zip(part,bases)]
                    entry.update(baseline_mean_s_per_source=a,candidate_mean_s_per_source=b,delta_s_per_source=b-a,reduction_fraction=1-b/a,
                        faster=sum(d < -1e-8 for d in deltas),equal=sum(abs(d)<=1e-8 for d in deltas),slower=sum(d>1e-8 for d in deltas),
                        worst_s_per_source=max(r['average_clear_time_s'] for r in part),max_virtual_s=max(r['total_virtual_time_s'] for r in part),
                        mean_runtime_s=statistics.mean(r['program_runtime_s'] for r in part))
                output.append(entry)
    return output

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--candidate', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--v1-results', help='reuse exact-hash candidate full v1 output; do not rerun those cases')
    p.add_argument('--dependency-manifest',help='JSON object of absolute/ROOT-relative dependency filenames and SHA256')
    p.add_argument('--previous-rows',help='also compare with previous best on exactly the same 4800 cases')
    p.add_argument('--verify-only',action='store_true')
    a=p.parse_args()
    sys.path.insert(0,str(ROOT))
    import evaluate
    assert Path(evaluate.__file__).resolve() == ROOT/'evaluate.py'
    evaluate.verify()
    exposed=HERE/'exposed_cases.json'
    assert sha(exposed)==read(HERE/'exposure_manifest.json')['cases_sha256']
    provenance=read(HERE/'baseline/provenance.json')
    for f,h in provenance['files'].items():
        assert sha(HERE/'baseline'/f)==h
    assert sha(HERE/'baseline/expected_rows.json')==provenance['expected_rows_sha256']
    if a.verify_only:
        print('Frozen environment, exposed cases and C0 cache verified')
        return
    candidate=Path(a.candidate).resolve()
    csha=sha(candidate)
    script_hash=sha(__file__)
    shared_hashes={str(HERE/'baseline'/f):h for f,h in provenance['files'].items()}
    shared_hashes[str(HERE/'baseline/expected_rows.json')]=provenance['expected_rows_sha256']
    before={str(f):sha(f) for f in list(ROOT.glob('*.py'))+list(ROOT.glob('*.json')) if f.is_file()}
    deps=read(a.dependency_manifest) if a.dependency_manifest else {}
    deps={str((ROOT/f).resolve()):h for f,h in deps.items()}
    for f,h in deps.items():
        assert sha(f)==h, 'Dependency changed: '+f
    coverage=candidate.parent/'coverage_points.json'
    optional=sha(coverage) if coverage.is_file() else None
    cases=read(exposed)
    v1rows=[]
    reuse=None
    if a.v1_results:
        directory=Path(a.v1_results).resolve()
        summary=read(directory/'summary.json')
        assert summary['suite']=='full' and summary['paired_cases']==2400
        assert summary['candidate_sha256']==csha, 'Cannot reuse v1 with another candidate'
        assert summary['manifest_sha256']==sha(ROOT/'evaluation/manifest_v1.json')
        v1rows=[r for r in read(directory/'case_metrics.json') if r['variant']=='candidate']
        v1cases=[c for c in cases if c['exposure_suite']=='v1']
        assert len(v1rows)==2400 and [r['case_id'] for r in v1rows]==[c['case_id'] for c in v1cases]
        reuse=dict(path=str(directory), rows_sha256=sha(directory/'case_metrics.json'), summary_sha256=sha(directory/'summary.json'), cases=2400)
    run_cases=[c for c in cases if not a.v1_results or c['exposure_suite']!='v1']
    out=Path(a.out).resolve()
    out.mkdir(parents=True,exist_ok=False)
    t=time.perf_counter()
    new_rows=evaluate.run_cases(run_cases,candidate,False)
    elapsed=time.perf_counter()-t
    byid={r['case_id']:r for r in v1rows+new_rows}
    rows=[]
    for c in cases:
        r=byid[c['case_id']]
        # Frozen timeout/crash rows omit group/exit_reason: preserve failure,
        # and restore only known evaluation metadata from the input case.
        assert (r['mode'],r.get('group',c['group']),r['source_count'])==(c['mode'],c['group'],len(c['sources']))
        rows.append(dict(r,group=c['group'],exposure_suite=c['exposure_suite'],seed_cluster=c['seed']))
    evaluate.verify()
    assert sha(candidate)==csha and sha(exposed)==read(HERE/'exposure_manifest.json')['cases_sha256']
    assert before=={str(f):sha(f) for f in list(ROOT.glob('*.py'))+list(ROOT.glob('*.json')) if f.is_file()}
    assert optional==(sha(coverage) if coverage.is_file() else None)
    for f,h in deps.items():
        assert sha(f)==h
    for f,h in shared_hashes.items():
        assert sha(f)==h, 'C0 dependency/cache changed during evaluation'
    assert sha(__file__)==script_hash
    if reuse:
        assert sha(Path(reuse['path'])/'case_metrics.json')==reuse['rows_sha256']
        assert sha(Path(reuse['path'])/'summary.json')==reuse['summary_sha256']
    summary=dict(label='EXPOSED second-campaign regression; not holdout or official',candidate=str(candidate),candidate_sha256=csha,
        script_sha256=sha(__file__),cases_sha256=sha(exposed),manifest_sha256=sha(ROOT/'evaluation/manifest_v1.json'),
        control_cache_sha256=sha(HERE/'baseline/expected_rows.json'),dependencies=deps,optional_coverage_sha256=optional,
        v1_reused=reuse,new_runs=len(new_rows),compared_cases=len(rows),wall_seconds_new_runs=elapsed,
        all_complete=all(valid(r) for r in rows),comparisons_to_C0=compare(rows,read(HERE/'baseline/expected_rows.json')))
    if a.previous_rows:
        previous=Path(a.previous_rows).resolve()
        summary['previous_rows_sha256']=sha(previous)
        summary['comparisons_to_previous']=compare(rows,read(previous))
    save(out/'case_metrics.json',rows)
    save(out/'summary.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('comparisons_to_C0','comparisons_to_previous')},ensure_ascii=False))
    print(json.dumps([r for r in summary['comparisons_to_C0'] if r['group']=='ALL'],ensure_ascii=False))

if __name__=='__main__':
    main()
