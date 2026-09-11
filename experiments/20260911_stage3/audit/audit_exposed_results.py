"""Independent arithmetic/identity audit; no environment or solver execution."""
from pathlib import Path
import argparse,hashlib,json,math,statistics,subprocess

HERE=Path(__file__).resolve().parent
CAMPAIGN=HERE.parent
ROOT=CAMPAIGN.parent.parent

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def good(r):return r.get('complete') is True and not r.get('error') and r.get('exit_reason')=='user_exit' and r.get('cleared_count')==r.get('source_count')

def main():
    p=argparse.ArgumentParser();p.add_argument('--results',required=True);p.add_argument('--out',required=True);p.add_argument('--code-commit');p.add_argument('--worktree');a=p.parse_args()
    folder=Path(a.results).resolve();summary=read(folder/'summary.json');rows=read(folder/'case_metrics.json')
    cases=read(CAMPAIGN/'exposed_cases.json');refs=read(CAMPAIGN/'baseline/expected_rows.json');ri={r['case_id']:r for r in refs}
    assert len(rows)==len(cases)==len(refs)==4800
    assert len({r['case_id'] for r in rows})==4800
    assert summary['script_sha256']==sha(CAMPAIGN/'evaluate_exposed.py')
    assert summary['cases_sha256']==sha(CAMPAIGN/'exposed_cases.json')
    assert summary['control_cache_sha256']==sha(CAMPAIGN/'baseline/expected_rows.json')
    assert summary['manifest_sha256']==sha(ROOT/'evaluation/manifest_v1.json')
    candidate=Path(summary['candidate']);assert sha(candidate)==summary['candidate_sha256']
    for f,h in summary['dependencies'].items():assert sha(f)==h
    identity=[]
    for r,c in zip(rows,cases):
        assert (r['case_id'],r['mode'],r['group'],r['seed_cluster'],r['exposure_suite'],r['source_count'])==(c['case_id'],c['mode'],c['group'],c['seed'],c['exposure_suite'],len(c['sources']))
        assert good(ri[r['case_id']])
        if good(r):
            assert r['coverage_certificate'] is True
            assert 0<=r['total_virtual_time_s']<360000 and 0<=r['program_runtime_s']<1200
            assert math.isclose(r['average_clear_time_s'],r['total_virtual_time_s']/r['cleared_count'],rel_tol=1e-12,abs_tol=1e-9)
    report=[]
    for cell in summary['comparisons_to_S0']:
        part=[r for r in rows if r['mode']==cell['mode'] and (cell['suite']=='combined' or r['exposure_suite']==cell['suite']) and (cell['group']=='ALL' or r['group']==cell['group'])]
        base=[ri[r['case_id']] for r in part]
        valid_part=all(good(r) for r in part)
        assert cell['cases']==len(part) and cell['baseline_complete']==len(base)
        assert cell['candidate_complete']==sum(good(r) for r in part)
        assert cell['valid_comparison']==valid_part
        if not valid_part:
            assert 'candidate_mean_s_per_source' not in cell and 'reduction_fraction' not in cell
            if cell['group']=='ALL': report.append(dict(cell))
            continue
        x=statistics.fmean(r['average_clear_time_s'] for r in part);y=statistics.fmean(r['average_clear_time_s'] for r in base)
        d=[r['average_clear_time_s']-b['average_clear_time_s'] for r,b in zip(part,base)]
        assert cell['cases']==len(part)==cell['candidate_complete']==cell['baseline_complete']
        assert cell['candidate_cleared']==cell['source_count']==sum(r['source_count'] for r in part)
        for k,v in [('candidate_mean_s_per_source',x),('baseline_mean_s_per_source',y),('delta_s_per_source',x-y),('reduction_fraction',1-x/y)]:assert math.isclose(cell[k],v,rel_tol=1e-11,abs_tol=1e-9),(k,cell[k],v)
        counts=[sum(z<-1e-8 for z in d),sum(abs(z)<=1e-8 for z in d),sum(z>1e-8 for z in d)]
        assert [cell[k] for k in ('faster','equal','slower')]==counts
        if cell['group']=='ALL':report.append(dict(cell))
    if summary['v1_reused']:
        v=summary['v1_reused'];vp=Path(v['path']);vs=read(vp/'summary.json')
        assert sha(vp/'case_metrics.json')==v['rows_sha256'] and sha(vp/'summary.json')==v['summary_sha256']
        assert vs['candidate_sha256']==summary['candidate_sha256']
        assert summary['new_runs']==2400
    else:assert summary['new_runs']==4800
    if a.code_commit:
        wt=Path(a.worktree).resolve();relative=candidate.relative_to(wt)
        blob=subprocess.check_output(['git','show',a.code_commit+':'+relative.as_posix()],cwd=wt)
        assert hashlib.sha256(blob).hexdigest()==sha(candidate)
    answer=dict(status='pass',rows=4800,all_clear_valid_exit=all(good(r) for r in rows),failed_case_ids=[r['case_id'] for r in rows if not good(r)],source_denominators_verified=True,comparison_cells=len(summary['comparisons_to_S0']),
        candidate=str(candidate),candidate_sha256=sha(candidate),code_commit=a.code_commit,rows_sha256=sha(folder/'case_metrics.json'),summary_sha256=sha(folder/'summary.json'),
        dependencies=summary['dependencies'],source_count_by_mode={str(m):sum(r['source_count'] for r in rows if r['mode']==m) for m in (3,4)},
        modes=report,limits='Arithmetic and identity audit only; geometry and inference-time access reviewed separately. No candidate or environment was executed.')
    Path(a.out).write_text(json.dumps(answer,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in answer.items() if k!='modes'},ensure_ascii=False))

if __name__=='__main__':main()
