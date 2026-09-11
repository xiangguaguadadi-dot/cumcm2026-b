"""Coordinator-only environment validation, durable trajectories and cost ledgers.

Policies never import this module. Source truth is read only after run_episode
returns and is stored beside, never inside, the online decision snapshots.
"""
from __future__ import annotations
import gzip
import hashlib
import json
import math
from pathlib import Path
import resource
import sys
import time

EXEC = Path(__file__).resolve().parents[1]
REPO = EXEC.parents[1]
sys.path[:0] = [str(EXEC), str(REPO)]
from data.worlds import instantiate
from local_env import LocalEnv, InterfaceOnly
from core import run_episode, teacher_selector
from core.engine import load_c7

# Before starting a world we reserve its complete conservative primitive cap.
# 10000 learning measure/clear + 5844 fallback measure/clear + enter/exit.
COMPLETE_EPISODE_RESERVE = 15846

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def dump(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    temp.replace(path)

def append(path, value):
    with Path(path).open('a') as f:
        f.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n')

def save_episode(path, entry):
    path = Path(path).resolve()
    if path.exists():
        raise RuntimeError('Refuse to overwrite an executed episode: ' + str(path))
    start = time.perf_counter()
    encoded = json.dumps(entry, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    encoded_at = time.perf_counter()
    compressed = gzip.compress(encoded, compresslevel=3, mtime=0)
    compressed_at = time.perf_counter()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary=path.with_name(path.name+'.tmp')
    temporary.write_bytes(compressed)
    temporary.replace(path)
    return dict(path=str(path.relative_to(EXEC)), sha256=hashlib.sha256(compressed).hexdigest(),
                content_sha256=hashlib.sha256(encoded).hexdigest(),
                raw_json_bytes=len(encoded), gzip_bytes=len(compressed),
                json_encode_s=encoded_at-start, gzip_s=compressed_at-encoded_at,
                write_s=time.perf_counter()-compressed_at)

def read_episode(path, expected_sha256=None):
    encoded=Path(path).read_bytes()
    if expected_sha256 is not None and hashlib.sha256(encoded).hexdigest()!=expected_sha256:
        raise RuntimeError('Saved trajectory SHA256 changed: '+str(path))
    return json.loads(gzip.decompress(encoded))

def recover_storage(path):
    path=Path(path).resolve();encoded=path.read_bytes();decoded=gzip.decompress(encoded)
    return dict(path=str(path.relative_to(EXEC)),sha256=hashlib.sha256(encoded).hexdigest(),
        content_sha256=hashlib.sha256(decoded).hexdigest(),raw_json_bytes=len(decoded),gzip_bytes=len(encoded),
        json_encode_s=0,gzip_s=0,write_s=0,
        storage_timing_unavailable='Recovered a complete archive after interrupted index append; no environment reexecution')

def peak_mib():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024**2 if sys.platform=='darwin' else 1024)

def percentile(values, percent):
    if not values: return None
    s=sorted(values); i=(len(s)-1)*percent/100; lo=int(i); hi=min(len(s)-1,lo+1)
    return s[lo]*(hi-i)+s[hi]*(i-lo) if hi!=lo else s[lo]

def distribution(values, scale=1.):
    v=[x*scale for x in values]
    return dict(n=len(v), mean=sum(v)/len(v) if v else None,
                p50=percentile(v,50),p95=percentile(v,95),p99=percentile(v,99),max=max(v) if v else None)

def greedy_selector(snapshot):
    eligible=[i for i,(c,v) in enumerate(zip(snapshot['candidates'],snapshot['valid_mask']))
              if v and c['kind']!='fallback']
    index=min(eligible,key=lambda i:(snapshot['candidate_features'][i][8],snapshot['candidate_ids'][i])) if eligible else snapshot['teacher_index']
    return {'index':index,'metadata':{'selector':'same_candidates_immediate_cost_greedy'}}

def execute(recipe, selector, label, *, original_c7=False):
    env=LocalEnv(instantiate(recipe),seed=recipe['seed'],noise=recipe['noise'],keep_log=False)
    calls={'enter':0,'measure':0,'clear':0,'exit':0}
    class Backend:
        def enter(self): calls['enter']+=1; return env.enter()
        def measure(self,x,y,ch): calls['measure']+=1; return env.measure(x,y,ch)
        def clear(self,x,y,ch): calls['clear']+=1; return env.clear(x,y,ch)
        def exit(self): calls['exit']+=1; return env.exit()
    interface=InterfaceOnly(Backend()); begin=time.perf_counter(); error=None
    try:
        raw=(load_c7().Solver(interface,mode=recipe['mode']).run() if original_c7
             else run_episode(interface,mode=recipe['mode'],selector=selector))
    except Exception as e:
        error=type(e).__name__+': '+str(e); raw=None
    elapsed=time.perf_counter()-begin
    # The first truth read occurs here, after the policy has returned.
    stats=env.stats()
    validation_errors=[]
    success=bool(error is None and env.finished and env.exit_reason=='user_exit'
                 and stats['cleared']==stats['n'] and (original_c7 or raw['success']))
    if not original_c7 and raw is not None:
        raw['success']=success; raw['terminal']='success' if success else 'failure'
        raw['true_completeness_checked']=True
        if raw['business_primitive_count']>sum(calls.values()):
            validation_errors.append('Accepted-event count exceeds actual attempted calls')
        if abs(raw['total_time_s']-stats['time_s'])>2e-5 or raw['cost_partition_error_s']>2e-5:
            validation_errors.append('Terminal environment/core cost disagreement')
    if raw is None:validation_errors.append('Policy returned no recoverable raw trajectory')
    if validation_errors:
        success=False
        if raw is not None:
            raw['success']=False;raw['terminal']='failure'
    # Do not throw away an executed failure: the caller must persist this full
    # envelope and add actual calls before stopping on an integrity error.
    entry=dict(world_id=recipe['world_id'],recipe=recipe,label=label,raw=raw,
               terminal_labels=dict(true_n=stats['n'],success=success,stats=stats,
                                    exit_reason=env.exit_reason,error=error,
                                    validation_errors=validation_errors,integrity_valid=not validation_errors),
               actual_calls=calls,business_primitives=sum(calls.values()),
               execution_wall_s=elapsed,peak_process_mib=peak_mib())
    return entry

def row_of(entry, storage=None):
    raw=entry['raw'] or {}; stats=entry['terminal_labels']['stats']
    decisions=raw.get('decisions',[])
    row=dict(world_id=entry['world_id'],label=entry['label'],mode=entry['recipe']['mode'],
             group=entry['recipe']['group'],success=entry['terminal_labels']['success'],
             n=stats['n'],cleared=stats['cleared'],fraction=stats['fraction'],
             virtual_time_s=stats['time_s'],average_s=stats['average_s'],
             business_primitives=entry['business_primitives'],actual_calls=entry['actual_calls'],
             execution_wall_s=entry['execution_wall_s'],peak_process_mib=entry['peak_process_mib'],
             decisions=len(decisions),fallback_reason=raw.get('fallback_reason'),
             tail_time_s=raw.get('tail_time_s',0),controller_recoveries=raw.get('controller_recoveries',[]),
             error=entry['terminal_labels']['error'] or raw.get('error'),
             validation_errors=entry['terminal_labels'].get('validation_errors',[]),
             teacher_matches=sum(d['index']==d['snapshot']['teacher_index'] for d in decisions),
             selector_reasons={})
    for d in decisions:
        reason=d.get('metadata',{}).get('selection_reason','unspecified')
        row['selector_reasons'][reason]=row['selector_reasons'].get(reason,0)+1
    if storage: row['storage']=storage
    return row

def aggregate(rows):
    return dict(unique_worlds=len({r['world_id'] for r in rows}),episode_executions=len(rows),
                business_primitives=sum(r['business_primitives'] for r in rows),
                successes=sum(r['success'] for r in rows),failures=[r for r in rows if not r['success']],
                execution_wall_s=sum(r['execution_wall_s'] for r in rows),
                raw_json_bytes=sum(r.get('storage',{}).get('raw_json_bytes',0) for r in rows),
                gzip_bytes=sum(r.get('storage',{}).get('gzip_bytes',0) for r in rows),
                storage_wall_s=sum(sum(r.get('storage',{}).get(k,0) for k in ('json_encode_s','gzip_s','write_s')) for r in rows),
                storage_timing_unavailable_count=sum(bool(r.get('storage',{}).get('storage_timing_unavailable')) for r in rows),
                peak_process_mib=max((r['peak_process_mib'] for r in rows),default=0))
