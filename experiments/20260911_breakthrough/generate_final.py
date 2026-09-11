"""Generate second-campaign final cases ONLY after committed candidate registry.

Registry schema: candidates[{label,candidate_path,candidate_sha256,
deployment_dependencies:{ROOT-relative path:sha}}], excluded_seeds:[int].
The root coordinator creates and audits this registry after all four agents stop.
"""
import argparse
import ast
import hashlib
import json
import math
import random
import subprocess
import sys
import time
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--registry',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--seeds',type=int,default=100)
    a=p.parse_args()
    assert a.seeds>=100,'Pre-registered final cohort requires at least 100 seed clusters'
    regpath=Path(a.registry).resolve()
    rel=regpath.relative_to(ROOT)
    committed=subprocess.check_output(['git','show','HEAD:'+rel.as_posix()],cwd=ROOT)
    assert committed==regpath.read_bytes(),'Registry must be committed before generation'
    reg=json.loads(committed)
    assert reg['all_four_agents_finalized'] is True
    assert len(set(reg['agents_finalized']))==4
    assert reg['candidates'] and reg['excluded_seeds']
    for c in reg['candidates']:
        assert sha(ROOT/c['candidate_path'])==c['candidate_sha256']
        for f,h in c.get('deployment_dependencies',{}).items():
            assert sha(ROOT/f)==h
    sys.path.insert(0,str(ROOT))
    import evaluate
    from local_env import Source
    evaluate.verify()
    source=ROOT/'evaluation/generate_cases.py'
    tree=ast.parse(source.read_text())
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='sources'
        or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='groups' for t in n.targets)]
    assert len(nodes)==2
    namespace=dict(random=random,math=math,Source=Source)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),namespace)
    exposed=json.loads((HERE/'exposed_cases.json').read_text())
    excluded=set(reg['excluded_seeds']) | {c['seed'] for c in exposed}
    seeds=[]
    rng=random.SystemRandom()
    while len(seeds)<a.seeds:
        value=rng.randrange(10**8,2**31)
        if value not in excluded and value not in seeds:
            seeds.append(value)
    cases=[]
    for mode in (3,4):
        for group,scenario,noise in namespace['groups']:
            for seed in seeds:
                sources=[vars(s) for s in namespace['sources'](seed,mode,scenario)]
                assert 10<=len(sources)<=16
                assert len({s['channel'] for s in sources})==len(sources)
                if mode==4:
                    assert {s['direction'] is not None for s in sources}=={True,False}
                cases.append(dict(case_id=f'LOCAL-breakthrough-final-q{mode}-{group}-{seed}',mode=mode,group=group,
                    noise=noise,seed=seed,quick=False,sources=sources))
    out=Path(a.out).resolve()
    out.mkdir(parents=True,exist_ok=False)
    (out/'cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2))
    manifest=dict(role='Second-stage final new-seed validation; same local assumptions, not official',
        generated_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),seed_clusters=len(seeds),cases=len(cases),seeds=seeds,
        excluded_seed_count=len(excluded),excluded_seeds_sha256=hashlib.sha256(json.dumps(sorted(excluded)).encode()).hexdigest(),
        registry_sha256=sha(regpath),registry_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        cases_sha256=sha(out/'cases.json'),generator_script_sha256=sha(__file__),frozen_source_generator_sha256=sha(source),
        frozen_manifest_sha256=sha(ROOT/'evaluation/manifest_v1.json'))
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print(json.dumps(manifest,ensure_ascii=False))

if __name__=='__main__':
    main()
