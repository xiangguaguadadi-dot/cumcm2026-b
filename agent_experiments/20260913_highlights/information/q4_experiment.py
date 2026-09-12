"""Read-only evaluator instrumentation of the unchanged B3 candidate.

Truth lives only in this evaluator, never in the decision object or responses.
Run with python3.12 -I -S; only the standard library is used.
"""
import argparse, concurrent.futures, hashlib, importlib.util, json, math
import multiprocessing, random, statistics, sys, time, traceback
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PACKAGE=ROOT/'最佳方法/代码'
SOURCE=PACKAGE/'solver.py'
CASES=ROOT/'最佳方法/数据/exposed_cases.json'
EXPECTED='e6a0666d644ceaa1d7ae69f19042b9ca022379f3e5a57d927e52bcf1a09360bd'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def area(p):return abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(p,p[1:]+p[:1])))/2 if p else 0.
def contains(poly,p,tol=1e-5):
    if not poly:return False
    if len(poly)==1:return math.dist(poly[0],p)<=tol
    signs=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        edge=math.dist(a,b)
        # Clipping can emit consecutive vertices differing by 1e-12 m. Such
        # edges are far below the 1e-5 m containment tolerance; normalizing
        # their cancellation noise invents a spurious half-plane direction.
        if edge>1e-7:signs.append(((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]))/edge)
    return all(s>=-tol for s in signs) or all(s<=tol for s in signs)
def init_worker():
    global ENV,MOD,WEDGE
    if sha(SOURCE)!=EXPECTED:raise RuntimeError('B3 candidate hash changed')
    ENV=load('information_local_env',PACKAGE/'local_env.py')
    MOD=load('information_frozen_b3',SOURCE)
    dummy=MOD.Solver(None,mode=4)
    WEDGE=dummy.refine_no_signal.__func__.__globals__['exclude_forced_visible_wedge']
def refined(poly,positives,negatives):
    p=list(poly)
    for q in negatives[-24:]:
        for i,p1 in enumerate(positives[-8:]):
            for p2 in positives[-8:][i+1:]:p=WEDGE(p,p1,p2,q)
    return p
def run_case(task):
    case,arm,save_snapshots=task
    env=ENV.LocalEnv([ENV.Source(**s) for s in case['sources']],case['seed'],case['noise'],keep_log=False)
    solver=MOD.Solver(ENV.InterfaceOnly(env),mode=4,**{**MOD.OPTIMIZED_CONFIGS[4],'convex_no_signal':arm=='on'})
    truth={s['channel']:(s['x'],s['y']) for s in case['sources']}
    events=[];violations=[];snapshots=[];original=solver.measure
    # The callback inspects public-state geometry only after the actual action.
    # It is an evaluator observer; its results cannot influence any decision.
    def measured(p,ch):
        kind=original(p,ch)
        if ch in solver.polygons and ch not in solver.cleared and ch in truth:
            poly=solver.polygons[ch]
            if not contains(poly,truth[ch]):violations.append(dict(case_id=case['case_id'],arm=arm,channel=ch,kind=kind,polygon=poly,source=truth[ch]))
            pos=[q for q,_ in solver.observations[ch]];neg=solver.no_signal_points[ch]
            if arm=='off' and kind in ('direction','no_signal') and len(pos)>=2 and neg:
                new=refined(poly,pos,neg);before=area(poly);after=area(new)
                inside_before=contains(poly,truth[ch]);inside_after=contains(new,truth[ch])
                event=dict(case_id=case['case_id'],channel=ch,kind=kind,observations=len(pos),negative_observations=len(neg),
                    area_before_m2=before,area_after_m2=after,area_removed_m2=max(0.,before-after),
                    fractional_shrink=max(0.,before-after)/before if before else 0.,
                    source_inside_before=inside_before,source_inside_after=inside_after,
                    measures_so_far=env.measures,clears_so_far=env.clear_attempts,virtual_time_s=env.virtual_time_s)
                events.append(event)
                if not inside_after:violations.append(dict(hypothetical=True,**event,polygon_before=poly,polygon_after=new,source=truth[ch]))
                if save_snapshots and (before-after>1e-6 or len(snapshots)<1):
                    snapshot=dict(**event,polygon_before=poly,polygon_after=new,positive_points=pos[-8:],negative_points=neg[-24:],source=truth[ch])
                    snapshots.append(snapshot);snapshots.sort(key=lambda s:s['fractional_shrink'],reverse=True);del snapshots[3:]
        return kind
    solver.measure=measured
    started=time.perf_counter();error=None;result={}
    try:result=solver.run()
    except Exception as e:error=type(e).__name__+': '+str(e)
    if env.started and not env.finished:env._finish('strategy_exception' if error else 'missing_exit')
    stats=env.stats()
    row=dict(case_id=case['case_id'],mode=4,group=case['group'],seed=case['seed'],exposure_suite=case.get('exposure_suite'),arm=arm,
        complete=stats['cleared']==stats['n'] and env.exit_reason=='user_exit' and error is None,
        error=error,exit_reason=env.exit_reason,source_count=stats['n'],cleared_count=stats['cleared'],
        average_clear_time_s=stats['average_s'],total_virtual_time_s=stats['time_s'],distance_m=stats['distance_m'],
        measures=stats['measures'],clear_attempts=stats['clear_attempts'],clear_failures=stats['clear_failures'],
        switches=stats['switches'],runtime_s=time.perf_counter()-started,accounting_error_s=stats['accounting_error_s'],
        true_source_exclusions=len(violations),eligible_same_state_updates=len(events),
        effective_same_state_shrinks=sum(e['area_removed_m2']>1e-6 for e in events),
        counters=solver.counters,coverage_complete=result.get('coverage_complete',False))
    return row,events,snapshots,violations
def summarize(rows):
    by={arm:{r['case_id']:r for r in rows if r['arm']==arm} for arm in ('on','off')}
    assert set(by['on'])==set(by['off'])
    ids=sorted(by['on']);out=dict(pairs=len(ids),actual_runs=len(rows),all_complete=all(r['complete'] for r in rows),
        true_source_exclusions=sum(r['true_source_exclusions'] for r in rows),
        sources_per_arm=sum(by['on'][i]['source_count'] for i in ids),
        same_state_updates=sum(r['eligible_same_state_updates'] for r in rows),
        same_state_effective_shrinks=sum(r['effective_same_state_shrinks'] for r in rows))
    def group_stats(keys):
        result={}
        for arm in by:
            rr=[by[arm][k] for k in keys]
            result[arm]={f:statistics.mean(r[f] for r in rr) for f in ('average_clear_time_s','measures','clear_attempts','clear_failures','distance_m')}
        delta=[by['on'][k]['average_clear_time_s']-by['off'][k]['average_clear_time_s'] for k in keys]
        result.update(n=len(keys),mean_delta_s_per_source=statistics.mean(delta),
            faster=sum(d< -1e-8 for d in delta),same=sum(abs(d)<=1e-8 for d in delta),slower=sum(d>1e-8 for d in delta))
        return result
    if out['all_complete']:
        out['overall']=group_stats(ids)
        out['groups']={g:group_stats([k for k in ids if by['on'][k]['group']==g]) for g in sorted({r['group'] for r in rows})}
        # Seeds are shared among scenario variants; bootstrap whole seed clusters.
        clusters={}
        for k in ids:
            r=by['on'][k];key=(r.get('exposure_suite'),r['seed'])
            clusters.setdefault(key,[]).append(r['average_clear_time_s']-by['off'][k]['average_clear_time_s'])
        cluster_values=[statistics.mean(v) for v in clusters.values()]
        rng=random.Random(2026091304);boots=sorted(statistics.mean(rng.choices(cluster_values,k=len(cluster_values))) for _ in range(4000))
        out['seed_cluster_bootstrap_95ci_delta_s_per_source']=[boots[100],boots[3899]]
        out['seed_clusters']=len(cluster_values)
    return out
def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['quick','remaining','all'],default='quick');p.add_argument('--workers',type=int,default=2);p.add_argument('--case-id');p.add_argument('--out-name');a=p.parse_args()
    out=HERE/(a.out_name or 'q4_'+a.stage);out.mkdir(exist_ok=False)
    cases=[c for c in json.loads(CASES.read_text()) if c['mode']==4]
    quick=lambda c:c.get('exposure_suite')=='v1' and c.get('quick',False)
    if a.case_id:cases=[c for c in cases if c['case_id']==a.case_id]
    elif a.stage=='quick':cases=[c for c in cases if quick(c)]
    elif a.stage=='remaining':cases=[c for c in cases if not quick(c)]
    manifest=json.loads((PACKAGE/'evaluation/manifest_v1.json').read_text())
    for f,h in manifest['sha256'].items():
        if sha(PACKAGE/f)!=h:raise RuntimeError('Frozen file changed '+f)
    write(out/'invocation.json',dict(argv=sys.argv,candidate_sha256=sha(SOURCE),cases_sha256=sha(CASES),script_sha256=sha(Path(__file__)),
        manifest_sha256=sha(PACKAGE/'evaluation/manifest_v1.json'),case_ids=[c['case_id'] for c in cases],arms=['on','off']))
    started=time.perf_counter();rows=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=multiprocessing.get_context('spawn'),initializer=init_worker) as pool:
        tasks=[(c,arm,a.stage=='quick') for c in cases for arm in ('on','off')]
        with (out/'executed_rows.jsonl').open('w') as rf,(out/'same_state_events.jsonl').open('w') as ef,(out/'snapshots.jsonl').open('w') as sf,(out/'violations.jsonl').open('w') as vf:
            for row,events,snapshots,violations in pool.map(run_case,tasks,chunksize=1):
                rows.append(row);rf.write(json.dumps(row,ensure_ascii=False)+'\n');rf.flush()
                for item in events:ef.write(json.dumps(item,ensure_ascii=False)+'\n')
                for item in snapshots:sf.write(json.dumps(item,ensure_ascii=False)+'\n')
                for item in violations:vf.write(json.dumps(item,ensure_ascii=False)+'\n')
                if len(rows)%20==0:print(json.dumps(dict(stage=a.stage,runs=len(rows),total=len(tasks),elapsed_s=time.perf_counter()-started,errors=sum(bool(r['error']) for r in rows))),flush=True)
    summary=summarize(rows);summary['wall_s']=time.perf_counter()-started;summary['label']='Actual LOCAL exposed-regression executions, not official or blind test'
    write(out/'summary.json',summary)
    if sha(SOURCE)!=EXPECTED:raise RuntimeError('Candidate changed during evaluation')
    print(json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
