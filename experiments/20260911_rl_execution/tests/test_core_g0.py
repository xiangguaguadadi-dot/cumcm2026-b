"""Registered G0 complete-world audit runner, never imported by the actor.

Only the coordinator's g0_core recipes are instantiated. No random or frozen
case generator import, no new world identifiers, and no training occurs here.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

EXEC=Path(__file__).resolve().parents[1]
REPO=EXEC.parents[1]
sys.path[:0]=[str(EXEC),str(REPO)]
from data.worlds import instantiate
from local_env import LocalEnv,InterfaceOnly
from core import run_episode,teacher_selector
from core.engine import load_c7
from core.interface import GuardConfig

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def trace(log):
    return [{'action':e['action'],'request':e['request'],
             'response':{k:v for k,v in e['response'].items() if k not in
                         ('real_timestamp_ms','remaining_real_duration_s')}} for e in log]
def run(recipe,label):
    env=LocalEnv(instantiate(recipe),seed=recipe['seed'],noise=recipe['noise'],keep_log=True)
    interface=InterfaceOnly(env);start=time.perf_counter();exception=None
    try:
        if label=='original_c7':result=load_c7().Solver(interface,mode=recipe['mode']).run()
        else:
            guard=GuardConfig(learning_request_cap=1) if label=='forced_fallback_after_one' else GuardConfig()
            result=run_episode(interface,mode=recipe['mode'],selector=teacher_selector,guard=guard)
    except Exception as exc:
        exception=type(exc).__name__+': '+str(exc);result=None
    wall=time.perf_counter()-start
    stats=env.stats()
    valid=(exception is None and stats['cleared']==stats['n'] and env.finished
           and env.exit_reason=='user_exit' and (label=='original_c7' or result['success']))
    return {'world_id':recipe['world_id'],'recipe':recipe,'label':label,'result':result,
            'stats':stats,'environment_exit_reason':env.exit_reason,'valid_complete':valid,
            'error':exception,'wall_time_s':wall,'business_primitives':len(env.log),
            'primitive_log':env.log,'semantic_trace_sha256':hashlib.sha256(
                json.dumps(trace(env.log),sort_keys=True,separators=(',',':')).encode()).hexdigest()}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--limit',type=int,default=20)
    args=ap.parse_args();out=Path(args.out)
    if out.exists():raise SystemExit('Output must be new; never overwrite actual executions')
    out.mkdir(parents=True)
    registry=EXEC/'data/initial_registry.json';records=json.loads(registry.read_text())['worlds']
    worlds=[r for r in records if r['split']=='g0_core'][:args.limit]
    if not 0<len(worlds)<=20:raise ValueError('G0 core world quota violation')
    hashes={p.name:sha(p) for p in (EXEC/'core').glob('*.py')}
    dump(out/'manifest.json',{'registry_sha256':sha(registry),'core_hashes':hashes,
        'unique_registered_worlds':len(worlds),'planned_execution_count':3*len(worlds),
        'labels':['original_c7','teacher_wrapper','forced_fallback_after_one'],
        'policy_environment_runs_before_this_runner':0,'new_world_generation':False,
        'scope':'G0 correctness; not training, selection, or final performance validation'})
    rows=[];start=time.perf_counter()
    for i,recipe in enumerate(worlds):
        results={}
        for label in ('original_c7','teacher_wrapper','forced_fallback_after_one'):
            entry=run(recipe,label);results[label]=entry
            dump(out/f'{i:02d}_{label}.json',entry)
        b,w,f=(results[k] for k in ('original_c7','teacher_wrapper','forced_fallback_after_one'))
        exact=b['semantic_trace_sha256']==w['semantic_trace_sha256']
        row={'world_id':recipe['world_id'],'mode':recipe['mode'],'group':recipe['group'],
             'all_three_complete':all(r['valid_complete'] for r in results.values()),
             'teacher_exact_event_equality':exact,
             'teacher_wrapper_fallback':w['result'].get('fallback_reason') if w['result'] else None,
             'cost_partition_error_s':w['result'].get('cost_partition_error_s') if w['result'] else None,
             'fallback_cost_partition_error_s':f['result'].get('cost_partition_error_s') if f['result'] else None,
             'baseline_time_s':b['stats']['time_s'],'teacher_time_s':w['stats']['time_s'],
             'fallback_time_s':f['stats']['time_s'],
             'fallback_tail_s':f['result'].get('tail_time_s') if f['result'] else None,
             'business_primitives':{k:r['business_primitives'] for k,r in results.items()},
             'wall_time_s':{k:r['wall_time_s'] for k,r in results.items()},
             'errors':{k:(r['error'] or (r['result'].get('error') if r['result'] else None)) for k,r in results.items()}}
        rows.append(row);dump(out/'rows.json',rows)
        print(json.dumps({'completed_worlds':len(rows),'mode':row['mode'],'valid':row['all_three_complete'],
              'teacher_equal':exact,'errors':row['errors']},ensure_ascii=False),flush=True)
        if not row['all_three_complete'] or not exact:
            print('Stopping after saved correctness failure; remaining registered worlds not executed.',flush=True)
            break
    summary={'unique_worlds_executed':len(rows),'episode_executions':3*len(rows),
        'business_primitives':sum(sum(r['business_primitives'].values()) for r in rows),
        'all_complete':all(r['all_three_complete'] for r in rows),
        'teacher_event_equality_all':all(r['teacher_exact_event_equality'] for r in rows),
        'all_planned_executed':len(rows)==len(worlds),'max_fallback_tail_s':max((r['fallback_tail_s'] or 0.) for r in rows),
        'max_teacher_partition_error_s':max((r['cost_partition_error_s'] or 0.) for r in rows),
        'wall_time_s':time.perf_counter()-start,
        'hashes_unchanged':all(sha(EXEC/'core'/k)==v for k,v in hashes.items())}
    dump(out/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False),flush=True)
    return 0 if summary['all_complete'] and summary['teacher_event_equality_all'] and summary['all_planned_executed'] else 1
if __name__=='__main__':raise SystemExit(main())
