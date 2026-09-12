"""Frozen v1 evaluation; standard library, Python >=3.10. No official scores."""
import argparse,csv,hashlib,importlib.util,json,multiprocessing as mp,platform,statistics,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify():
    m=json.loads((ROOT/'evaluation/manifest_v1.json').read_text())
    bad=[p for p,h in m['sha256'].items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
    if bad:raise RuntimeError('Frozen evaluation changed: '+str(bad))
    return m

def worker(conn,path,baseline):
    from local_env import LocalEnv,Source,InterfaceOnly
    spec=importlib.util.spec_from_file_location('strategy',path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    while True:
        case=conn.recv()
        if case is None:break
        env=LocalEnv([Source(**s) for s in case['sources']],case['seed'],case['noise'],keep_log=False)
        conf=mod.OPTIMIZED_CONFIGS[case['mode']]
        start=time.perf_counter();error=None;result={}
        try:result=mod.Solver(InterfaceOnly(env),mode=case['mode'],**conf).run()
        except Exception as e:error=type(e).__name__+': '+str(e)
        elapsed=time.perf_counter()-start
        if env.started and not env.finished:env._finish('strategy_exception' if error else 'missing_exit')
        stats=env.stats()
        conn.send(dict(case_id=case['case_id'],mode=case['mode'],group=case['group'],variant='frozen_baseline' if baseline else 'candidate',
          cleared_count=stats['cleared'],source_count=stats['n'],cleared_fraction=stats['fraction'],
          average_clear_time_s=stats['average_s'],total_virtual_time_s=stats['time_s'],
          program_runtime_s=env.runtime_s,worker_runtime_s=elapsed,
          complete=stats['cleared']==stats['n'] and env.exit_reason=='user_exit' and error is None,
          exit_reason=env.exit_reason,error=error,coverage_certificate=result.get('coverage_complete',False),
          requests=stats['measures']+stats['clear_attempts']+int(env.started)+int(env.exit_reason=='user_exit'),
          distance_m=stats['distance_m'],clear_failures=stats['clear_failures']))
    conn.close()

def run_cases(cases,path,baseline):
    ctx=mp.get_context('spawn');rows=[];parent=None;proc=None
    def start():
        a,b=ctx.Pipe();p=ctx.Process(target=worker,args=(b,str(path),baseline));p.start();b.close();return a,p
    try:
        for case in cases:
            if proc is None:parent,proc=start()
            parent.send(case)
            if not parent.poll(1205):
                proc.terminate();proc.join();parent.close();proc=None
                row=dict(case_id=case['case_id'],mode=case['mode'],group=case['group'],variant='frozen_baseline' if baseline else 'candidate',complete=False,error='worker_timeout',cleared_count=None,source_count=len(case['sources']),cleared_fraction=None,average_clear_time_s=None,total_virtual_time_s=None,program_runtime_s=None)
            else:
                try:row=parent.recv()
                except EOFError:
                    proc.join();parent.close();proc=None
                    row=dict(case_id=case['case_id'],mode=case['mode'],group=case['group'],variant='frozen_baseline' if baseline else 'candidate',complete=False,error='worker_crash',cleared_count=None,source_count=len(case['sources']),cleared_fraction=None,average_clear_time_s=None,total_virtual_time_s=None,program_runtime_s=None)
            rows.append(row)
    finally:
        if proc is not None:
            if proc.is_alive():parent.send(None)
            proc.join(3)
            if proc.is_alive():proc.terminate();proc.join()
            parent.close()
    return rows

def summarize(rows):
    groups=[]
    for mode,group in sorted({(r['mode'],r['group']) for r in rows}):
        z=[r for r in rows if (r['mode'],r['group'])==(mode,group)]
        a=[r for r in z if r['variant']=='frozen_baseline'];b=[r for r in z if r['variant']=='candidate']
        item=dict(mode=mode,group=group,cases=len(b),baseline_complete=sum(r['complete'] for r in a),candidate_complete=sum(r['complete'] for r in b),candidate_errors=sum(bool(r['error']) for r in b))
        # Do not rank a partial-success subset as though the full suite passed.
        comparable=all(r['complete'] for r in z)
        item['time_comparison_valid']=comparable
        if comparable:
            base=statistics.mean(r['average_clear_time_s'] for r in a);cand=statistics.mean(r['average_clear_time_s'] for r in b)
            item.update(baseline_mean_s_per_source=base,candidate_mean_s_per_source=cand,reduction_fraction=1-cand/base,
                        candidate_worst_s_per_source=max(r['average_clear_time_s'] for r in b),
                        candidate_mean_runtime_s=statistics.mean(r['program_runtime_s'] for r in b))
        groups.append(item)
    return groups

def main():
    p=argparse.ArgumentParser();p.add_argument('--suite',choices=['quick','full'],default='quick');p.add_argument('--candidate',default=str(ROOT/'solver.py'));p.add_argument('--out',default=str(ROOT/'results/latest'));p.add_argument('--verify-only',action='store_true');p.add_argument('--rerun-baseline',action='store_true');a=p.parse_args()
    manifest=verify()
    if a.verify_only:print('Frozen v1 hashes verified');return
    candidate=Path(a.candidate).resolve();candidate_hash=sha(candidate)
    cases=json.loads((ROOT/'evaluation/cases_v1.json').read_text())
    if a.suite=='quick':cases=[c for c in cases if c['quick']]
    out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
    t0=time.perf_counter();rows=[]
    for baseline,path in [(True,ROOT/'evaluation/baseline_solver.py'),(False,candidate)]:
        if baseline and not a.rerun_baseline:
            cache=json.loads((ROOT/'evaluation/baseline_metrics_v1.json').read_text())
            if cache['baseline_sha256']!=sha(path) or cache['cases_sha256']!=sha(ROOT/'evaluation/cases_v1.json'):
                raise RuntimeError('Baseline cache provenance mismatch')
            indexed={r['case_id']:r for r in cache['rows']}
            part=[indexed[c['case_id']] for c in cases]
        else:
            part=run_cases(cases,path,baseline)
        rows.extend(part)
        print(('baseline' if baseline else 'candidate'),len(part),'runs',round(time.perf_counter()-t0,3),'seconds',flush=True)
    verify()
    if sha(candidate)!=candidate_hash:raise RuntimeError('Candidate changed during evaluation; discard this run')
    elapsed=time.perf_counter()-t0
    summary=dict(label='LOCAL-v1; official metric definitions, assumed cases; NOT official results',suite=a.suite,
      python=platform.python_version(),platform=platform.platform(),candidate_sha256=candidate_hash,manifest_sha256=sha(ROOT/'evaluation/manifest_v1.json'),
      baseline_cached=not a.rerun_baseline,runs=len(cases)*(2 if a.rerun_baseline else 1),compared_rows=len(rows),paired_cases=len(cases),wall_seconds=elapsed,all_complete=all(r['complete'] for r in rows),groups=summarize(rows))
    (out/'case_metrics.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    fields=['case_id','mode','variant','cleared_count','average_clear_time_s','program_runtime_s','source_count','cleared_fraction','total_virtual_time_s','complete','error']
    with (out/'official_metric_columns_LOCAL.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
    print(json.dumps({k:summary[k] for k in ('runs','paired_cases','wall_seconds','all_complete')},ensure_ascii=False))

if __name__=='__main__':main()
