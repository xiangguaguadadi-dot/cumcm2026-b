"""Paired full-world coverage ablations using unchanged frozen v1 physics."""
import argparse
import gzip
import json
import math
import multiprocessing as mp
import statistics
import sys
import time
from common import HERE, ROOT, dump, sha, load_module, frozen_check


def worker(conn):
    envmod=load_module(ROOT/'local_env.py','coverage_worker_physics')
    modules={}
    while True:
        job=conn.recv()
        if job is None:break
        case,arm,trace=job
        if arm not in modules:
            modules[arm]=load_module(HERE/'snapshots'/f'{arm}.py','coverage_worker_'+arm)
        module=modules[arm]
        env=envmod.LocalEnv([envmod.Source(**s) for s in case['sources']],case['seed'],case['noise'],keep_log=False)
        state=module.Solver(envmod.InterfaceOnly(env),mode=4)
        start=time.perf_counter();error=None;result={}
        try:result=state.run()
        except Exception as exc:error=type(exc).__name__+': '+str(exc)
        elapsed=time.perf_counter()-start
        if env.started and not env.finished:env._finish('strategy_exception' if error else 'missing_exit')
        stats=env.stats()
        pending=[c for c in range(1,21) if state.observations[c] and c not in state.cleared]
        absent=[]
        for ch in range(1,21):
            if ch in state.cleared:continue
            measurements=[v for v in state.trace if v['action']=='measure' and v['channel']==ch]
            actual={(v['x'],v['y']) for v in measurements if v['result']=='no_signal'}
            absent.append(dict(channel=ch,all_sites_physically_measured_no_signal=all(tuple(p) in actual for p in state.points),
                               no_positive_observation=not state.observations[ch],true_absent=ch not in env._sources,
                               scanned_indices=sorted(state.scanned[ch])))
        known=set();cleared=set();known16_pending=False
        for event in state.trace:
            if event['action']=='measure' and event['result'] in ('direction','near'):known.add(event['channel'])
            if event['action']=='clear' and event['result']=='success':known.add(event['channel']);cleared.add(event['channel'])
            if len(known)>=16 and len(cleared)<16:known16_pending=True
        row=dict(case_id=case['case_id'],mode=4,group=case['group'],seed=case['seed'],arm=arm,
                 candidate_sha256=sha(HERE/'snapshots'/f'{arm}.py'),source_count=stats['n'],cleared_count=stats['cleared'],
                 complete=stats['n']==stats['cleared'] and env.exit_reason=='user_exit' and error is None,
                 total_virtual_time_s=stats['time_s'],average_clear_time_s=stats['average_s'],
                 distance_m=stats['distance_m'],measures=stats['measures'],switches=stats['switches'],
                 clear_attempts=stats['clear_attempts'],clear_failures=stats['clear_failures'],
                 requests=stats['measures']+stats['clear_attempts']+int(env.started)+int(env.exit_reason=='user_exit'),
                 accounting_error_s=stats['accounting_error_s'],program_runtime_s=elapsed,
                 exit_reason=env.exit_reason,error=error,coverage_certificate=result.get('coverage_complete',False),
                 certificate_type=result.get('certificate_type'),geometric_certificate=result.get('geometric_coverage_complete',False),
                 station_count=len(state.points),visited_stations=result.get('visited_points',[]),
                 pending_channels_after_run=pending,known16_observed_while_pending=known16_pending,
                 counters=state.counters,absence_channel_checks=absent)
        if arm.startswith('pure'):
            row['pure_geometry_audit']=bool(row['complete'] and row['geometric_certificate']
                 and row['certificate_type']=='complete_geometric_coverage' and not pending
                 and all(a['all_sites_physically_measured_no_signal'] and a['no_positive_observation'] and a['true_absent'] for a in absent))
        conn.send((row,state.trace if trace else None))
    conn.close()


def pressure_cases():
    cases=[]
    for j in range(12):
        for n in (10,16):
            sources=[]
            for k in range(n):
                angle=2*math.pi*(k/n+j/144)
                radius=1800. if k%2==0 else 1799.999
                # One omni plus directional sources: legal mixed Q4, all R=1000.
                direction=None if k==0 else angle+(0. if j%3==0 else math.pi/2+(-1 if j%3==1 else 1)*1e-6)
                sources.append(dict(channel=k+1,x=radius*math.cos(angle),y=radius*math.sin(angle),radius=1000.,direction=direction))
            cases.append(dict(case_id=f'CONSTRUCTED-full-pressure-{j:02d}-n{n}',mode=4,group=['edge_outward','edge_halfplane_inside','edge_halfplane_outside'][j%3],
                              seed=91371000+len(cases),noise=['positive','negative','cell_50'][j%3],sources=sources))
    return cases


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--suite',choices=['quick','full','pressure'],required=True)
    parser.add_argument('--arms',nargs='+',default=['fixed21','fixed22','rotating21']);parser.add_argument('--out',required=True)
    args=parser.parse_args();out=HERE/args.out;out.mkdir(exist_ok=False)
    frozen=frozen_check()
    if args.suite=='pressure':cases=pressure_cases()
    else:
        cases=[c for c in json.loads((ROOT/'evaluation/cases_v1.json').read_text()) if c['mode']==4 and (args.suite=='full' or c['quick'])]
    assert len({c['case_id'] for c in cases})==len(cases)
    dump(out/'cases.json',cases)
    registry=dict(suite=args.suite,arms=args.arms,worlds=len(cases),planned_policy_runs=len(cases)*len(args.arms),
                  seed_role='constructed pressure' if args.suite=='pressure' else 'exposed frozen v1',
                  source=frozen,cases_sha256=sha(out/'cases.json'),runner_sha256=sha(__file__),
                  candidates={a:sha(HERE/'snapshots'/f'{a}.py') for a in args.arms},
                  execution='one worker; per-world arm order cyclically interleaved; complete tails and failures retained')
    dump(out/'registration.json',registry)
    ctx=mp.get_context('spawn');left,right=ctx.Pipe();process=ctx.Process(target=worker,args=(right,));process.start();right.close()
    rows=[];started=time.perf_counter()
    try:
        with (out/'rows.jsonl').open('w') as stream:
            for i,case in enumerate(cases):
                arms=args.arms[i%len(args.arms):]+args.arms[:i%len(args.arms)]
                for arm in arms:
                    left.send((case,arm,args.suite=='pressure'))
                    if not left.poll(1205):raise RuntimeError('worker_timeout; preserve partial rows')
                    row,trace=left.recv();stream.write(json.dumps(row,separators=(',',':'))+'\n');stream.flush();rows.append(row)
                    if trace is not None:
                        target=out/'traces'/f"{case['case_id']}__{arm}.json.gz";target.parent.mkdir(exist_ok=True)
                        with gzip.open(target,'wt') as f:json.dump(trace,f,separators=(',',':'))
                if (i+1)%10==0:print(f'{args.suite}: {i+1}/{len(cases)} worlds, {len(rows)} executions, {time.perf_counter()-started:.2f}s',flush=True)
    finally:
        if process.is_alive():left.send(None)
        process.join(3)
        if process.is_alive():process.terminate();process.join()
        left.close()
    for arm in args.arms:assert sha(HERE/'snapshots'/f'{arm}.py')==registry['candidates'][arm]
    grouped={}
    for arm in args.arms:
        part=[r for r in rows if r['arm']==arm]
        grouped[arm]=dict(cases=len(part),source_count=sum(r['source_count'] for r in part),cleared=sum(r['cleared_count'] for r in part),
                         complete=sum(r['complete'] for r in part),errors=sum(r['error'] is not None for r in part),
                         mean_s_per_source=statistics.mean(r['average_clear_time_s'] for r in part) if all(r['complete'] for r in part) else None,
                         requests=sum(r['requests'] for r in part),known16_pending_worlds=sum(r['known16_observed_while_pending'] for r in part),
                         pure_geometry_pass=sum(r.get('pure_geometry_audit',False) for r in part))
    summary=dict(status='complete',suite=args.suite,worlds=len(cases),executions=len(rows),all_complete=all(r['complete'] for r in rows),
                 groups=grouped,wall_s=time.perf_counter()-started,total_requests=sum(r['requests'] for r in rows),
                 rows_sha256=sha(out/'rows.jsonl'),frozen_after=frozen_check())
    dump(out/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
