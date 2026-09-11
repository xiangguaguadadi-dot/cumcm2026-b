"""Run one registered finite component experiment without extra held-out data."""
import argparse,ast,hashlib,json,math,random,statistics,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
import evaluate
from local_env import Source

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def read(p):return json.loads(p.read_text())
def valid(r):return r.get('complete') and r.get('exit_reason')=='user_exit' and not r.get('error') and r.get('cleared_count')==r.get('source_count')

def main():
    p=argparse.ArgumentParser();p.add_argument('--registry',required=True);p.add_argument('--out',required=True);p.add_argument('--start',type=int,required=True);p.add_argument('--seed-count',type=int,default=8);a=p.parse_args()
    evaluate.verify();manifest=read(HERE/a.registry);out=HERE/a.out;out.mkdir(exist_ok=False)
    seeds=list(range(a.start,a.start+a.seed_count));assert 47000000<=min(seeds)<=max(seeds)<48000000
    ledger=read(HERE/'used_seeds.json');used={s for r in ledger['rounds'] for s in r['seeds']};assert not set(seeds)&used
    old=read(ROOT/'experiments/20260911_stage3/seed_exclusions.json')['seeds'];assert not set(seeds)&set(old)
    generator=ROOT/'evaluation/generate_cases.py';nodes=ast.parse(generator.read_text()).body
    fn=next(n for n in nodes if isinstance(n,ast.FunctionDef) and n.name=='sources')
    groups=ast.literal_eval(next(n.value for n in nodes if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='groups' for t in n.targets)))
    scope=dict(Source=Source,random=random,math=math);exec(compile(ast.Module(body=[fn],type_ignores=[]),'<frozen-generator>','exec'),scope)
    cases=[]
    for group,scenario,noise in groups:
        for seed in seeds:
            ss=scope['sources'](seed,4,scenario)
            assert 10<=len(ss)<=16 and len({s.channel for s in ss})==len(ss)
            assert any(s.direction is None for s in ss) and any(s.direction is not None for s in ss)
            cases.append(dict(case_id=f'DEV-C1-{out.name}-q4-{group}-{seed}',mode=4,group=group,noise=noise,seed=seed,sources=[vars(s) for s in ss]))
    save(out/'registration.json',{**manifest,'seeds':seeds,'case_count':len(cases),'generator_sha256':sha(generator),'role':'new development, not holdout'})
    save(out/'cases.json',cases);ledger['rounds'].append(dict(seeds=seeds,cases=len(cases),label=out.name));save(HERE/'used_seeds.json',ledger)
    raw={};summary=[]
    for name,meta in manifest['candidates'].items():
        file=(HERE/meta['file']).resolve();assert sha(file)==meta['sha256'];start=time.perf_counter()
        rows=evaluate.run_cases(cases,file,False);wall=time.perf_counter()-start;assert sha(file)==meta['sha256']
        raw[name]=rows;save(out/(name+'_rows.json'),rows)
        good=all(valid(r) for r in rows);r=dict(candidate=name,actual_runs=len(rows),complete=sum(bool(valid(r))for r in rows),all_complete=good,wall_seconds=wall)
        if good:r.update(mean_s_per_source=statistics.mean(x['average_clear_time_s'] for x in rows),movement_s_per_source=statistics.mean(x['distance_m']/5/x['source_count'] for x in rows),requests_per_case=statistics.mean(x['requests'] for x in rows))
        summary.append(r);save(out/'summary.json',summary);print(json.dumps(r),flush=True)
    fields=('case_id','complete','exit_reason','error','source_count','cleared_count','total_virtual_time_s','distance_m','requests','clear_failures')
    wiring={}
    for name,parent in manifest.get('wiring_pairs',[]):
        wiring[name]={'parent':parent,'case_count':len(cases),'mismatches':[r['case_id'] for r,s in zip(raw[name],raw[parent])if any(r.get(k)!=s.get(k)for k in fields)]}
    save(out/'wiring_checks.json',wiring)
    save(out/'budget.json',dict(actual_runs=sum(r['actual_runs']for r in summary),unique_cases=len(cases),unique_seeds=len(seeds),wall_seconds=sum(r['wall_seconds']for r in summary),wiring_check_runs_included=len(manifest.get('wiring_pairs',[]))*len(cases)))
    evaluate.verify();assert all(not r['mismatches'] for r in wiring.values())

if __name__=='__main__':main()
