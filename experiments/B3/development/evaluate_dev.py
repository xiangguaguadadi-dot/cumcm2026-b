"""Complete task development, fixed 12 legal scenario families and new seeds.
No learned model; all evaluated configurations and every raw row are saved.
"""
from pathlib import Path
import ast,json,math,random,statistics,sys,time,hashlib,argparse
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import evaluate
from local_env import Source
D=ROOT/'experiments/B3'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def make(seedstart,n):
 tree=ast.parse((ROOT/'evaluation/generate_cases.py').read_text())
 nodes=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='sources' or isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='groups' for t in x.targets)]
 namespace=dict(random=random,math=math,Source=Source);exec(compile(ast.Module(body=nodes,type_ignores=[]),'developer_case_generation','exec'),namespace)
 exposed={x['seed'] for x in json.loads((ROOT/'experiments/20260911_breakthrough/exposed_cases.json').read_text())}
 assert not set(range(seedstart,seedstart+n))&exposed
 cases=[]
 for mode in (3,4):
  for group,scenario,noise in namespace['groups']:
   for seed in range(seedstart,seedstart+n):
    ss=namespace['sources'](seed,mode,scenario)
    assert 10<=len(ss)<=16 and len(set(s.channel for s in ss))==len(ss)
    assert all(1<=s.channel<=20 and 1000<=s.radius<=1500 and math.hypot(s.x,s.y)<=1800+1e-6 for s in ss)
    assert all(s.direction is None for s in ss) if mode==3 else any(s.direction is None for s in ss) and any(s.direction is not None for s in ss)
    cases.append(dict(case_id=f'B3-development-q{mode}-{group}-{seed}',mode=mode,group=group,noise=noise,seed=seed,quick=False,sources=[vars(s) for s in ss]))
 return cases
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--out',required=True);p.add_argument('--start',type=int,default=33001000);p.add_argument('--seeds',type=int,default=12);a=p.parse_args()
 out=Path(a.out);out.mkdir(exist_ok=False,parents=True)
 cases=make(a.start,a.seeds);(out/'cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2));candidate=Path(a.candidate).resolve();before=sha(candidate)
 variants=[('C0',ROOT/'experiments/20260911_breakthrough/baseline/C0.py'),('candidate',candidate)];entries=[]
 for name,path in variants:
  t=time.perf_counter();rows=evaluate.run_cases(cases,path,False);elapsed=time.perf_counter()-t
  (out/(name+'_rows.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2))
  modes=[]
  for mode in (3,4):
   rr=[r for r in rows if r['mode']==mode];modes.append({'mode':mode,'n':len(rr),'complete':sum(r['complete'] and not r.get('error') and r['exit_reason']=='user_exit' and r['cleared_count']==r['source_count'] for r in rr),'mean_s_per_source':statistics.mean(r['average_clear_time_s'] for r in rr)})
  entry={'variant':name,'path':str(path),'sha256':sha(path),'runs':len(rows),'elapsed_s':elapsed,'modes':modes};entries.append(entry);print(json.dumps(entry),flush=True)
 evaluate.verify();assert sha(candidate)==before
 (out/'summary.json').write_text(json.dumps({'role':'development, not holdout','training_runs':0,'development_runs':len(cases)*len(variants),'seed_range':[a.start,a.start+a.seeds-1],'cases_sha256':sha(out/'cases.json'),'variants':entries},ensure_ascii=False,indent=2))
