"""Coordinator-registered G0 nonteacher audit; no new world generation."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import random
import sys
import time

EXEC=Path(__file__).resolve().parents[1];REPO=EXEC.parents[1]
sys.path[:0]=[str(EXEC),str(REPO)]
from data.worlds import instantiate
from local_env import LocalEnv,InterfaceOnly
from core import run_episode,teacher_selector
from core.schema import validate_snapshot

RNG_SEED_BASE=99113000
BANNED_SNAPSHOT_KEYS=frozenset(('seed','scenario','world_id','n','true_n','sources',
    '_sources','env','stats','source_count','true_source_count','source_truth'))

def sha_bytes(b):return hashlib.sha256(b).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def assert_observable_tree(x):
    if isinstance(x,dict):
        bad=set(x)&BANNED_SNAPSHOT_KEYS
        if bad:raise AssertionError('Privileged metadata in snapshot: '+repr(sorted(bad)))
        for v in x.values():assert_observable_tree(v)
    elif isinstance(x,(list,tuple)):
        for v in x:assert_observable_tree(v)

def selector_for(label,index):
    rng=random.Random(RNG_SEED_BASE+index)
    checks={'snapshots':0,'payloads':0,'privileged_key_violations':0}
    def select(snapshot):
        validate_snapshot(snapshot);assert_observable_tree(snapshot)
        checks['snapshots']+=1;checks['payloads']+=len(snapshot['candidates'])
        allowed=[i for i,p in enumerate(snapshot['candidates'])
                 if snapshot['valid_mask'][i] and p['kind']!='fallback']
        if label=='teacher':choice=teacher_selector(snapshot)
        elif label=='greedy_cost':choice=min(allowed,key=lambda i:(snapshot['candidate_features'][i][8],snapshot['candidate_ids'][i]))
        elif label=='random_legal':choice=rng.choice(allowed)
        else:raise ValueError('Unknown selector')
        return {'index':choice,'metadata':{'selector':label}}
    return select,checks

def run(recipe,label,index):
    # Recipes and Source construction stay strictly in this evaluator, before
    # passing only InterfaceOnly to the online controller. Stats read at end.
    env=LocalEnv(instantiate(recipe),seed=recipe['seed'],noise=recipe['noise'],keep_log=True)
    selector,checks=selector_for(label,index);start=time.perf_counter()
    try:result=run_episode(InterfaceOnly(env),mode=recipe['mode'],selector=selector);error=None
    except Exception as e:result=None;error=type(e).__name__+': '+str(e)
    wall=time.perf_counter()-start
    stats=env.stats()  # terminal evaluator only, never used by selector
    valid=(error is None and result['success'] and stats['n']==stats['cleared']
           and env.finished and env.exit_reason=='user_exit')
    return {'world_id':recipe['world_id'],'recipe':recipe,'selector':label,
            'selector_rng_seed':RNG_SEED_BASE+index if label=='random_legal' else None,
            'selector_rng_independent_of_world_seed':True,'result':result,'stats':stats,
            'valid_complete':valid,'error':error,'environment_exit_reason':env.exit_reason,
            'wall_time_s':wall,'business_primitives':len(env.log),'snapshot_checks':checks,
            'primitive_log':env.log}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);args=ap.parse_args()
    out=Path(args.out)
    if out.exists():raise SystemExit('Refusing to overwrite executions')
    out.mkdir(parents=True)
    registry=EXEC/'data/initial_registry.json';worlds=[r for r in json.loads(registry.read_text())['worlds'] if r['split']=='g0_audit']
    if len(worlds)!=20:raise ValueError('Expected exactly 20 allocated registered worlds')
    hashes={p.name:sha_bytes(p.read_bytes()) for p in (EXEC/'core').glob('*.py')}
    manifest={'registry_sha256':sha_bytes(registry.read_bytes()),'core_hashes':hashes,
        'allocated_unique_worlds':20,'planned_episode_executions':60,
        'labels':['teacher','greedy_cost','random_legal'],'rng_seed_base':RNG_SEED_BASE,
        'rng_world_seed_coupling':False,'source_truth_read':'terminal evaluator only',
        'new_world_generation':False,'compressed_records':[]}
    dump(out/'manifest.json',manifest)
    rows=[];start=time.perf_counter()
    for index,recipe in enumerate(worlds):
        for label in manifest['labels']:
            entry=run(recipe,label,index)
            raw=json.dumps(entry,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
            packed=gzip.compress(raw,compresslevel=6,mtime=0)
            fn=f'{index:02d}_{label}.json.gz';(out/fn).write_bytes(packed)
            record={'file':fn,'raw_json_sha256':sha_bytes(raw),'gzip_sha256':sha_bytes(packed),
                    'raw_bytes':len(raw),'gzip_bytes':len(packed)}
            manifest['compressed_records'].append(record)
            r=entry['result']
            rows.append({'world_id':recipe['world_id'],'mode':recipe['mode'],'group':recipe['group'],
                'selector':label,'valid_complete':entry['valid_complete'],
                'source_count':entry['stats']['n'],'cleared':entry['stats']['cleared'],
                'total_time_s':entry['stats']['time_s'],'average_time_s':entry['stats']['average_s'],
                'business_primitives':entry['business_primitives'],'wall_time_s':entry['wall_time_s'],
                'cost_partition_error_s':r['cost_partition_error_s'] if r else None,
                'fallback_reason':r['fallback_reason'] if r else None,
                'controller_recoveries':r['controller_recoveries'] if r else [],
                'decision_count':len(r['decisions']) if r else 0,
                'snapshot_checks':entry['snapshot_checks'],'error':entry['error'] or (r['error'] if r else None),
                'evidence_file':fn})
            dump(out/'rows.json',rows);dump(out/'manifest.json',manifest)
            print(json.dumps({'executions':len(rows),'world_index':index,'mode':recipe['mode'],
                'selector':label,'valid':entry['valid_complete'],'fallback':rows[-1]['fallback_reason'],
                'error':rows[-1]['error']},ensure_ascii=False),flush=True)
        if not all(r['valid_complete'] for r in rows[-3:]):
            print('Stopped after saving all three outcomes for failed world.',flush=True);break
    by={}
    for label in manifest['labels']:
        r=[x for x in rows if x['selector']==label]
        by[label]={'executions':len(r),'all_complete':all(x['valid_complete'] for x in r),
            'source_denominator_sum':sum(x['source_count'] for x in r),'cleared_sum':sum(x['cleared'] for x in r),
            'business_primitives':sum(x['business_primitives'] for x in r),
            'fallback_executions':sum(x['fallback_reason'] is not None for x in r),
            'controller_recovery_executions':sum(bool(x['controller_recoveries']) for x in r)}
    summary={'unique_worlds_executed':len(set(r['world_id'] for r in rows)),'episode_executions':len(rows),
        'business_primitives':sum(r['business_primitives'] for r in rows),'all_complete':all(r['valid_complete'] for r in rows),
        'all_planned_executed':len(rows)==60,'max_partition_error_s':max((r['cost_partition_error_s'] or 0.) for r in rows),
        'by_selector':by,'snapshot_count':sum(r['snapshot_checks']['snapshots'] for r in rows),
        'payload_count':sum(r['snapshot_checks']['payloads'] for r in rows),
        'privileged_key_violations':sum(r['snapshot_checks']['privileged_key_violations'] for r in rows),
        'raw_bytes':sum(r['raw_bytes'] for r in manifest['compressed_records']),
        'gzip_bytes':sum(r['gzip_bytes'] for r in manifest['compressed_records']),
        'wall_time_s':time.perf_counter()-start,
        'core_hashes_unchanged':all(sha_bytes((EXEC/'core'/k).read_bytes())==v for k,v in hashes.items()),
        'interpretation':'G0 correctness/support diversity evidence, not trained-policy performance ranking'}
    dump(out/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False),flush=True)
    return 0 if summary['all_complete'] and summary['all_planned_executed'] else 1
if __name__=='__main__':raise SystemExit(main())
