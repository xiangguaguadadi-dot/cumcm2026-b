"""Paired Q2 transfer experiments using the unchanged frozen v1 runner."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import math
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
import evaluate

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

def save(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n")

def verify():
    evaluate.verify()
    reg = read(HERE/'REGISTRATION.json')
    for name, digest in reg['files'].items():
        assert sha(ROOT/name) == digest, 'Changed baseline/input: '+name
    assert sha(HERE/'baseline.py') == reg['baseline_sha256']
    return reg

def load_cases(suite):
    all_cases = read(ROOT/'experiments/20260911_stage4/exposed_cases.json')
    if suite == 'exposed':
        return all_cases
    v1 = read(ROOT/'evaluation/cases_v1.json')
    keys = {c['case_id'] for c in v1 if suite == 'full' or c['quick']}
    chosen = [c for c in all_cases if c['case_id'] in keys]
    assert len(chosen) == len(keys) == (120 if suite == 'quick' else 2400)
    return chosen

def valid(row):
    return (row.get('complete') is True and row.get('exit_reason') == 'user_exit'
            and row.get('error') is None and row.get('cleared_count') == row.get('source_count'))

def compare(rows, reference, cases):
    rr = {r['case_id']:r for r in rows}
    bb = {r['case_id']:r for r in reference}
    cc = {c['case_id']:c for c in cases}
    assert len(rr) == len(rows) == len(cc) and set(rr) == set(bb) == set(cc)
    for cid,c in cc.items():
        for r in (rr[cid],bb[cid]):
            assert (r['mode'],r['group'],r['source_count']) == (c['mode'],c['group'],len(c['sources']))
            if r.get('cleared_count'):
                assert math.isclose(r['average_clear_time_s'],r['total_virtual_time_s']/r['cleared_count'],abs_tol=1e-8,rel_tol=0)
            else:
                assert r.get('average_clear_time_s') is None
    summaries=[]
    for mode in (3,4):
        for batch in ['combined',*sorted({c['exposure_suite'] for c in cases})]:
            selected=[c for c in cases if c['mode']==mode and (batch=='combined' or c['exposure_suite']==batch)]
            for group in ['ALL',*sorted({c['group'] for c in selected})]:
                part=[c for c in selected if group=='ALL' or c['group']==group]
                if not part: continue
                a=[rr[c['case_id']] for c in part]; b=[bb[c['case_id']] for c in part]
                ok=all(valid(r) for r in a+b)
                s=dict(mode=mode,batch=batch,group=group,cases=len(part),source_count=sum(len(c['sources']) for c in part),
                       candidate_complete=sum(valid(r) for r in a),baseline_complete=sum(valid(r) for r in b),valid_comparison=ok)
                if ok:
                    av=[r['total_virtual_time_s']/r['cleared_count'] for r in a]
                    bv=[r['total_virtual_time_s']/r['cleared_count'] for r in b]
                    ds=[x-y for x,y in zip(av,bv)]; am=statistics.fmean(av); bm=statistics.fmean(bv)
                    s.update(candidate_mean=am,baseline_mean=bm,delta=am-bm,improvement_pct=100*(1-am/bm),
                             faster=sum(d < -1e-8 for d in ds),equal=sum(abs(d)<=1e-8 for d in ds),slower=sum(d>1e-8 for d in ds),
                             max_regression=max(ds),max_improvement=min(ds),candidate_worst=max(av),
                             candidate_requests=sum(r['requests'] for r in a),baseline_requests=sum(r['requests'] for r in b),
                             candidate_failed_clear=sum(r['clear_failures'] for r in a),baseline_failed_clear=sum(r['clear_failures'] for r in b),
                             candidate_mean_movement_s_per_source=statistics.fmean(r['distance_m']/5/r['cleared_count'] for r in a),
                             baseline_mean_movement_s_per_source=statistics.fmean(r['distance_m']/5/r['cleared_count'] for r in b),
                             candidate_mean_runtime_s=statistics.fmean(r['program_runtime_s'] for r in a),
                             candidate_max_runtime_s=max(r['program_runtime_s'] for r in a))
                summaries.append(s)
    return summaries

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--suite',choices=['quick','full','exposed'],required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--reuse-full',type=Path)
    p.add_argument('--chunk-size',type=int,default=120)
    args=p.parse_args()
    assert args.chunk_size > 0
    reg=verify(); script_hash=sha(__file__); candidate=args.candidate.resolve(); digest=sha(candidate)
    cases=load_cases(args.suite); out=args.out.resolve(); out.mkdir(parents=True,exist_ok=False)
    # Pin the reviewed parent cache to its executed candidate hash and input.
    ref_summary=read(ROOT/'experiments/parallel_v2_coordinator/fusion_r5_exposed/summary.json')
    assert ref_summary['candidate_sha256']==reg['baseline_sha256']
    assert ref_summary['cases_sha256']==sha(ROOT/'experiments/20260911_stage4/exposed_cases.json')
    refs_all=read(ROOT/'experiments/parallel_v2_coordinator/fusion_r5_exposed/case_metrics.json')
    ref_index={r['case_id']:r for r in refs_all}
    assert len(ref_index)==len(refs_all)==4800
    refs=[ref_index[c['case_id']] for c in cases]
    reused=[]; reuse_info=None
    if args.reuse_full:
        assert args.suite=='exposed'
        previous=read(args.reuse_full/'summary.json')
        assert previous['suite']=='full' and previous['candidate_sha256']==digest and previous['paired_cases']==2400
        assert previous['registration_sha256']==sha(HERE/'REGISTRATION.json')
        reused=read(args.reuse_full/'case_metrics.json')
        assert {r['case_id'] for r in reused}=={c['case_id'] for c in cases if c['exposure_suite']=='v1'}
        reuse_info={'path':str(args.reuse_full.resolve()),'rows_sha256':sha(args.reuse_full/'case_metrics.json'),'rows':len(reused)}
    seen={r['case_id'] for r in reused}; pending=[c for c in cases if c['case_id'] not in seen]
    run_record=dict(candidate=str(candidate),candidate_sha256=digest,script_sha256=script_hash,
                    registration_sha256=sha(HERE/'REGISTRATION.json'),suite=args.suite,
                    cases=len(cases),actual_runs_planned=len(pending),reused=reuse_info,
                    case_ids=[c['case_id'] for c in cases],data_role='existing exposed local regression')
    save(out/'execution_registration.json',run_record)
    start=time.perf_counter(); rows=list(reused)
    with (out/'executed_rows.jsonl').open('w') as log:
        for offset in range(0,len(pending),args.chunk_size):
            assert sha(candidate)==digest and sha(__file__)==script_hash
            batch=pending[offset:offset+args.chunk_size]
            got=evaluate.run_cases(batch,candidate,False)
            assert len(got)==len(batch)
            for row,case in zip(got,batch):
                assert row['case_id']==case['case_id']
                row.update(exposure_suite=case['exposure_suite'],seed_cluster=case['seed'])
                rows.append(row); log.write(json.dumps(row,ensure_ascii=False)+'\n')
            log.flush()
            print(json.dumps({'completed_actual_runs':offset+len(got),'planned':len(pending),'elapsed_s':round(time.perf_counter()-start,3),'failures':sum(not valid(r) for r in rows)},ensure_ascii=False),flush=True)
    idx={r['case_id']:r for r in rows}; rows=[idx[c['case_id']] for c in cases]
    verify(); assert sha(candidate)==digest and sha(__file__)==script_hash
    comparisons=compare(rows,refs,cases)
    summary=dict(label='Q2 transfer / local exposed regression, not official or blind',suite=args.suite,
                 candidate_sha256=digest,baseline_sha256=reg['baseline_sha256'],registration_sha256=sha(HERE/'REGISTRATION.json'),
                 runner_sha256=script_hash,manifest_sha256=sha(ROOT/'evaluation/manifest_v1.json'),paired_cases=len(cases),
                 actual_runs=len(pending),reused_rows=len(reused),wall_seconds=time.perf_counter()-start,
                 actual_requests=sum(r.get('requests',0) or 0 for r in rows if r['case_id'] not in seen),
                 all_complete=all(valid(r) for r in rows),failed_ids=[r['case_id'] for r in rows if not valid(r)],comparisons=comparisons)
    save(out/'case_metrics.json',rows); save(out/'summary.json',summary)
    print(json.dumps({'all_complete':summary['all_complete'],'actual_runs':summary['actual_runs'],'modes':[s for s in comparisons if s['batch']=='combined' and s['group']=='ALL']},ensure_ascii=False),flush=True)

if __name__=='__main__':
    main()
