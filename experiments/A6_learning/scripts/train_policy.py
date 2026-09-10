"""Transparent black-box policy search on self-generated train/development cases.

Simulator truths are used ONLY to generate cases and score completed episodes.
Deployment Solver receives InterfaceOnly. No frozen cases/cache are imported.
"""
import argparse,copy,hashlib,importlib.util,json,math,random,statistics,sys,time
from dataclasses import asdict
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]; ROOT=BASE.parents[1]
sys.path.insert(0,str(ROOT))
from local_env import LocalEnv,Source,InterfaceOnly

def load(path):
 spec=importlib.util.spec_from_file_location('training_strategy',path)
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def make_training_case(seed,mode):
 """Independent random mixture; no benchmark file/generator dependency."""
 r=random.Random(seed)
 n=r.randint(10,16);channels=r.sample(range(1,21),n)
 directional=0 if mode==3 else r.randint(1,n-1)
 family=r.choices(['area','rim','compact','central','small_reach'],[4,2,2,1,1])[0]
 phi=r.uniform(-math.pi,math.pi); cc=r.uniform(850,1550)
 center=(cc*math.cos(phi),cc*math.sin(phi));src=[]
 for i,ch in enumerate(channels):
  a=r.uniform(-math.pi,math.pi);rad=1800*math.sqrt(r.random())
  if family=='rim':rad=r.uniform(1680,1800)
  if family=='central':rad=90*math.sqrt(r.random())
  if family=='compact':
   cr=r.uniform(40,180)*math.sqrt(r.random());x=center[0]+cr*math.cos(a);y=center[1]+cr*math.sin(a)
  else:x,y=rad*math.cos(a),rad*math.sin(a)
  reach=1000 if family in ('rim','small_reach') else r.uniform(1000,1500)
  # Outward directions occur in a subset of rim examples; most are unrestricted.
  direction=(a if family=='rim' and r.random()<.5 else r.uniform(-math.pi,math.pi)) if i<directional else None
  src.append(asdict(Source(ch,x,y,reach,direction)))
 noise=r.choice(['uniform','positive','negative','smooth_shared','cell_50','cell_500'])
 return dict(seed=seed,mode=mode,noise=noise,family=family,sources=src)

def episode(mod,case,config):
 env=LocalEnv([Source(**s) for s in case['sources']],case['seed'],case['noise'],keep_log=False)
 started=time.perf_counter();error=None;output={}
 try:output=mod.Solver(InterfaceOnly(env),case['mode'],**config).run()
 except Exception as e:error=f'{type(e).__name__}: {e}'
 stats=env.stats()
 return dict(seed=case['seed'],mode=case['mode'],complete=stats['cleared']==stats['n'] and env.exit_reason=='user_exit' and not error,
  average_s=stats['average_s'],virtual_s=stats['time_s'],cleared=stats['cleared'],n=stats['n'],distance_m=stats['distance_m'],
  measures=stats['measures'],clear_failures=stats['clear_failures'],error=error,runtime_s=time.perf_counter()-started,counters=output.get('counters',{}))

def evaluate(mod,cases,conf):
 rows=[episode(mod,c,conf) for c in cases]
 return dict(complete=sum(r['complete'] for r in rows),n=len(rows),mean_s=statistics.mean(r['average_s'] or 1e9 for r in rows),
  worst_s=max(r['average_s'] or 1e9 for r in rows),rows=rows)

def rank(result):return (result['n']-result['complete'],result['mean_s'])

def main():
 p=argparse.ArgumentParser();p.add_argument('--round',type=int,required=True);p.add_argument('--solver',default=str(ROOT/'solver.py'))
 p.add_argument('--attempts',type=int,default=48);p.add_argument('--train-cases',type=int,default=96);p.add_argument('--dev-cases',type=int,default=192)
 p.add_argument('--shortlist',type=int,default=5);p.add_argument('--modes',default='3,4');p.add_argument('--minimum-dev-reduction',type=float,default=0.0);a=p.parse_args()
 modes=[int(x) for x in a.modes.split(',')];assert set(modes)<=set([3,4])
 out=BASE/'training'/f'r{a.round}';out.mkdir(exist_ok=False)
 mod=load(a.solver);rng=random.Random(660000+a.round)
 r1={'advance_fraction':(.25,.95),'lateral_fraction':(.035,.5),'clear_trial_radius':(20.,210.),'source_priority':(.15,3.5)}
 r2={'schedule_uncertainty':(-.8,1.5),'schedule_density':(-1.2,1.2),'schedule_station_gain':(-1.,1.),'source_priority':(.15,3.5)}
 r3={'advance_fraction':(.25,.95),'lateral_fraction':(.035,.5),'second_range_weight':(-.5,.5),'second_uncertainty_weight':(-.4,.4),'second_route_weight':(0.,1.0)}
 r4={'schedule_missing':(-1.2,1.2),'schedule_repeat':(-1.2,1.2),'schedule_workload':(-1.2,1.2),'source_priority':(.4,2.5)}
 r7={'schedule_boundary':(-2.,2.),'source_priority':(.8,2.5),'schedule_station_gain':(-1.2,.5),'schedule_uncertainty':(.5,2.)}
 bounds=r7 if a.round>=7 else [r1,r2,r3,r4][min(a.round,4)-1]
 # Data ranges fixed before candidate evaluation. No v1 identifier is available here.
 sets={}
 for mode in [3,4]:
  sets[mode]={split:[make_training_case(6600000+a.round*100000+mode*10000+off+i,mode) for i in range(n)] for split,off,n in [('train',0,a.train_cases),('dev',5000,a.dev_cases)]}
 (out/'cases.json').write_text(json.dumps(sets,separators=(',',':')))
 budget=dict(round=a.round,optimizer='two-stage elite random search; NOT an exact implementation of ARS',parameters=bounds,seed=660000+a.round,
  candidates_per_mode=a.attempts,train_cases_per_mode=a.train_cases,dev_cases_per_mode=a.dev_cases,shortlist=a.shortlist,
  modes_optimized_separately=True,modes_optimized=modes,minimum_dev_reduction=a.minimum_dev_reduction,training_truth_usage='post-episode completeness and task-time reward only; no expert action labels',
  deployment_input='four method InterfaceOnly; public observation-derived state',solver_sha256=hashlib.sha256(Path(a.solver).read_bytes()).hexdigest())
 (out/'budget.json').write_text(json.dumps(budget,ensure_ascii=False,indent=2))
 selected={mode:dict(config=dict(mod.OPTIMIZED_CONFIGS[mode]),parameters={},fixed=True,reason='mode fixed before training; no search this round') for mode in [3,4] if mode not in modes};start=time.perf_counter()
 for mode in modes:
  original=dict(mod.OPTIMIZED_CONFIGS[mode]); entries=[];best_vector={k:original.get(k,0.) for k in bounds}
  pop=a.attempts//2
  for j in range(a.attempts):
   if j==0:vector=best_vector.copy()
   elif j<pop:vector={k:rng.uniform(lo,hi) for k,(lo,hi) in bounds.items()}
   else:
    if j==pop:
     elite=sorted(entries,key=lambda q:rank(q['training']))[:max(3,pop//5)]
     center={k:statistics.mean(e['parameters'][k] for e in elite) for k in bounds}
     std={k:max(statistics.pstdev(e['parameters'][k] for e in elite),(bounds[k][1]-bounds[k][0])*.08) for k in bounds}
    vector={k:max(lo,min(hi,rng.gauss(center[k],std[k]))) for k,(lo,hi) in bounds.items()}
   conf={**original,**vector}
   result=evaluate(mod,sets[mode]['train'],conf)
   entry=dict(attempt=j,mode=mode,parameters=vector,config=conf,training=result)
   entries.append(entry)
   with (out/f'q{mode}_attempts.jsonl').open('a') as f:f.write(json.dumps(entry,separators=(',',':'))+'\n')
   print(f'round={a.round} q={mode} attempt={j+1}/{a.attempts} complete={result["complete"]}/{result["n"]} mean={result["mean_s"]:.6f}',flush=True)
  shortlist=sorted(entries,key=lambda q:rank(q['training']))[:a.shortlist]
  # Always carry the input policy into development comparison, even if not shortlisted.
  if entries[0] not in shortlist:shortlist.append(entries[0])
  dev=[]
  for e in shortlist:
   result=evaluate(mod,sets[mode]['dev'],e['config'])
   d=dict(attempt=e['attempt'],parameters=e['parameters'],config=e['config'],development=result);dev.append(d)
   print(f'development q={mode} attempt={e["attempt"]} complete={result["complete"]}/{result["n"]} mean={result["mean_s"]:.6f}',flush=True)
  (out/f'q{mode}_development.json').write_text(json.dumps(dev,separators=(',',':')))
  best=min(dev,key=lambda q:rank(q['development']));input_policy=next(d for d in dev if d['attempt']==0)
  reduction=1-best['development']['mean_s']/input_policy['development']['mean_s']
  if best['development']['complete']==best['development']['n'] and reduction<a.minimum_dev_reduction:best=input_policy
  selected[mode]={k:v for k,v in best.items() if k!='development'}
  selected[mode]['development_summary']={k:v for k,v in best['development'].items() if k!='rows'}
  selected[mode]['input_policy_development']={k:v for k,v in next(d for d in dev if d['attempt']==0)['development'].items() if k!='rows'}
 budget['actual_episodes']=sum(a.attempts*a.train_cases+len(json.loads((out/f'q{m}_development.json').read_text()))*a.dev_cases for m in modes)
 budget['elapsed_seconds']=time.perf_counter()-start
 (out/'budget.json').write_text(json.dumps(budget,ensure_ascii=False,indent=2))
 (out/'selected.json').write_text(json.dumps(selected,ensure_ascii=False,indent=2))
 print(json.dumps(selected,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
