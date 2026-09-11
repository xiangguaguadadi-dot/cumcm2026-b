"""Trainer/evaluator-only new-world recipes. Never import from a policy module.

The source distribution mirrors frozen evaluation/generate_cases.py's sources()
without importing that script, whose top level rewrites frozen cases_v1.json.
New split namespaces use disjoint deterministic seeds; no final test split exists.
"""
from __future__ import annotations
from dataclasses import asdict
import hashlib
import json
import math
import random
import sys
from pathlib import Path

EXEC_ROOT=Path(__file__).resolve().parents[1]
REPO=EXEC_ROOT.parents[1]
sys.path.insert(0,str(REPO))
from local_env import Source

GENERATOR_VERSION='rl-new-world-recipe-v1'
GROUPS=[
 ('reference_assumed','random','uniform'),
 ('fixed_positive_bias','random','positive'),
 ('fixed_negative_bias','random','negative'),
 ('smooth_shared_field','random','smooth_shared'),
 ('cell50_shared_field','random','cell_50'),
 ('cell500_shared_field','random','cell_500'),
 ('edge_mixed_min_radius','edge_mixed','uniform'),
 ('offcenter_cluster','cluster_offcenter','uniform'),
 ('origin_cluster','cluster_origin','uniform'),
 ('minimum_radius','min_radius','uniform'),
 ('exactly10_sources','count10','uniform'),
 ('exactly16_sources','count16','uniform'),
]

def seed_for(split,mode,index):
    if split.startswith('final'):
        raise ValueError('No final-test generation is authorized in this phase')
    raw=hashlib.sha256(f'{GENERATOR_VERSION}|{split}|{mode}|{index}'.encode()).digest()
    return 10_000_000 + int.from_bytes(raw[:8],'big') % 2_000_000_000

def sources(seed,mode,scenario):
    r=random.Random(seed)
    n=10 if scenario=='count10' else 16 if scenario=='count16' else r.randint(10,16)
    channels=r.sample(range(1,21),n)
    nd=0 if mode==3 else r.randint(1,n-1)
    phi=r.uniform(-math.pi,math.pi)
    center=(1450*math.cos(phi),1450*math.sin(phi))
    out=[]
    for i,ch in enumerate(channels):
        angle=r.uniform(-math.pi,math.pi)
        radius=1800*math.sqrt(r.random())
        reach=r.uniform(1000,1500)
        direction=r.uniform(-math.pi,math.pi) if i<nd else None
        x,y=radius*math.cos(angle),radius*math.sin(angle)
        if scenario=='edge_mixed':
            radius=r.uniform(1700,1800);x,y=radius*math.cos(angle),radius*math.sin(angle)
            reach=1000;direction=angle if i<nd else None
        elif scenario=='cluster_offcenter':
            radius=80*math.sqrt(r.random());x,y=center[0]+radius*math.cos(angle),center[1]+radius*math.sin(angle)
        elif scenario=='cluster_origin':
            radius=60*math.sqrt(r.random());x,y=radius*math.cos(angle),radius*math.sin(angle);reach=1000
        elif scenario=='min_radius':reach=1000
        out.append(Source(ch,x,y,reach,direction))
    assert 10<=len(out)<=16 and len({s.channel for s in out})==len(out)
    assert all(math.hypot(s.x,s.y)<=1800+1e-8 and 1000<=s.radius<=1500 for s in out)
    assert (all(s.direction is None for s in out) if mode==3 else 0<sum(s.direction is not None for s in out)<len(out))
    return out

def recipe(split,mode,index,group_index=None):
    group,scenario,noise=GROUPS[index%len(GROUPS) if group_index is None else group_index%len(GROUPS)]
    return dict(world_id=f'{GENERATOR_VERSION}:{split}:q{mode}:{index:05d}',split=split,
                mode=mode,index=index,group=group,scenario=scenario,noise=noise,seed=seed_for(split,mode,index))

def instantiate(recipe):
    return sources(recipe['seed'],recipe['mode'],recipe['scenario'])

def initial_registry():
    records=[]
    for split,count,offset in [('g0_core',20,0),('g0_audit',20,6),('g1_resource',24,0)]:
        for i in range(count):
            records.append(recipe(split,3+i%2,i//2,group_index=i//2+offset))
    assert len({r['seed'] for r in records})==len(records)
    assert len({r['world_id'] for r in records})==len(records)
    old_paths=[REPO/'evaluation/cases_v1.json',REPO/'experiments/20260911_stage4/exposed_cases.json']
    old_seeds=set()
    references=[]
    for p in old_paths:
        if p.exists():
            raw=p.read_bytes();old_seeds.update(c['seed'] for c in json.loads(raw))
            references.append(dict(path=str(p.relative_to(REPO)),sha256=hashlib.sha256(raw).hexdigest()))
    assert not old_seeds.intersection(r['seed'] for r in records)
    return dict(generator_version=GENERATOR_VERSION,worlds=records,
                old_exposed_seed_overlap=0,old_sources=references,
                final_worlds_generated=0,
                future_splits='demo and training/selection generated only when gates pass; all seeds rechecked then')

if __name__=='__main__':
    destination=Path(__file__).with_name('initial_registry.json')
    value=initial_registry()
    if destination.exists() and json.loads(destination.read_text())!=value:
        raise RuntimeError('Refuse to replace a different world registry')
    destination.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'worlds':len(value['worlds']),'splits':{x:sum(r['split']==x for r in value['worlds']) for x in ('g0_core','g0_audit','g1_resource')},'old_seed_overlap':0,'final_generated':0}))
