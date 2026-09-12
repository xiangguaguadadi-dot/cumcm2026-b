"""Generate registered development/confirmation worlds after historical novelty audit.

Only definitions are extracted from the frozen generator: importing its module
would overwrite cases_v1.json. No LocalEnv is instantiated here.
"""
import argparse,ast,hashlib,json,math,secrets,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
CAMPAIGN=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def h(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def filehash(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def identities(d):
    sources=sorted(d['sources'],key=lambda s:s['channel'])
    physical=dict(mode=d['mode'],sources=sources)
    return h(physical),h(dict(**physical,seed=d['seed'],noise=d['noise']))
def scan(value,seeds,geometry,worlds,seed_context=False):
    if isinstance(value,dict):
        if {'mode','noise','seed','sources'}<=set(value) and isinstance(value['sources'],list):
            a,b=identities(value);geometry.add(a);worlds.add(b)
        for k,v in value.items():scan(v,seeds,geometry,worlds,seed_context or 'seed' in k.lower())
    elif isinstance(value,list):
        for v in value:scan(v,seeds,geometry,worlds,seed_context)
    elif seed_context and type(value) is int:seeds.add(value)

def main():
    p=argparse.ArgumentParser();p.add_argument('--role',choices=['development','confirmation'],required=True);p.add_argument('--seed-count',type=int,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    if args.role=='confirmation':
        reg=json.loads((CAMPAIGN/'final_registration.json').read_text())
        assert reg['research_frozen'] is True
        for name,sha in reg['frozen_files'].items():
            path=ROOT/name;assert filehash(path)==sha
            assert subprocess.check_output(['git','show','HEAD:'+name],cwd=ROOT)==path.read_bytes()
    assert not args.out.exists();args.out.mkdir(parents=True)
    paths=subprocess.check_output(['rg','--files','evaluation','experiments','-g','*.json'],cwd=ROOT,text=True).splitlines()
    known,geometry,worlds=set(),set(),set();files=[]
    for name in sorted(paths):
        path=ROOT/name
        if args.out.resolve() in path.resolve().parents:continue
        raw=path.read_bytes()
        if b'seed' not in raw.lower():continue
        try:d=json.loads(raw)
        except (ValueError,UnicodeDecodeError):continue
        before=(len(known),len(geometry),len(worlds));scan(d,known,geometry,worlds)
        files.append(dict(path=name,sha256=hashlib.sha256(raw).hexdigest(),novel_counts=[n-o for n,o in zip((len(known),len(geometry),len(worlds)),before)]))
    chosen=[]
    while len(chosen)<args.seed_count:
        seed=10**12+secrets.randbelow(8*10**12)
        if seed not in known and seed not in chosen:chosen.append(seed)
    src=ROOT/'evaluation/generate_cases.py';tree=ast.parse(src.read_text())
    nodes=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='sources' or isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='groups' for t in x.targets)]
    assert len(nodes)==2
    import random
    from local_env import Source
    ns=dict(random=random,math=math,Source=Source)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(src),'exec'),ns)
    out=[];checks=[]
    for mode in (3,4):
        for group,scenario,noise in ns['groups']:
            for seed in chosen:
                ss=[vars(s) for s in ns['sources'](seed,mode,scenario)]
                case=dict(case_id=f'JOINT-v1-{args.role}-q{mode}-{group}-{seed}',mode=mode,group=group,noise=noise,seed=seed,seed_cluster=seed,sources=ss,quick=False,exposure_suite=args.role)
                a,b=identities(case)
                assert a not in geometry and b not in worlds
                assert 10<=len(ss)<=16 and len({s['channel'] for s in ss})==len(ss)
                assert all(math.hypot(s['x'],s['y'])<=1800+1e-8 and 1000<=s['radius']<=1500 for s in ss)
                nd=sum(s['direction'] is not None for s in ss);assert nd==0 if mode==3 else 0<nd<len(ss)
                out.append(case);checks.append(dict(case_id=case['case_id'],physical_sha256=a,world_sha256=b))
    (args.out/'cases.json').write_text(canonical(out)+'\n')
    manifest=dict(role=args.role,seeds=chosen,worlds=len(out),source_count=sum(len(x['sources']) for x in out),generator_sha256=filehash(src),script_sha256=filehash(__file__),cases_sha256=filehash(args.out/'cases.json'),seed_overlap=[],physical_overlap=[],world_overlap=[],known_seeds=len(known),known_geometries=len(geometry),known_worlds=len(worlds),audit_sources=files,world_identities=checks,scope='All seed-bearing JSON found in inherited coordinator evaluation and experiments, plus current jointplan artifacts; no claims about unrecorded external execution or official stream. Other active sessions are isolated and not inspected.')
    (args.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({k:v for k,v in manifest.items() if k not in ('audit_sources','world_identities','seeds')}))
if __name__=='__main__':main()
