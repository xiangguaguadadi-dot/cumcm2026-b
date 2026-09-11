"""Explicit finite mechanism study on newly generated legal training/development cases."""
from pathlib import Path
import argparse,random,math,json,hashlib,time,sys,importlib.util
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from local_env import Source,LocalEnv,InterfaceOnly
OUT=ROOT/'experiments/B1'
GROUPS=[('reference_assumed','random','uniform'),('fixed_positive_bias','random','positive'),('fixed_negative_bias','random','negative'),('smooth_shared_field','random','smooth_shared'),('cell50_shared_field','random','cell_50'),('cell500_shared_field','random','cell_500'),('edge_mixed_min_radius','edge','uniform'),('offcenter_cluster','offcenter','uniform'),('origin_cluster','origin','uniform'),('minimum_radius','minimum','uniform'),('exactly10_sources','count10','uniform'),('exactly16_sources','count16','uniform')]
VARIANTS=[('C0',None,{}),('A3_R2',None,{}),('naive','naive',{}),('visibility','visibility',{}),('quadrature','quadrature',{}),('visibility60','visibility',{'sharing_gain_m':60.}),('quadrature60','quadrature',{'sharing_gain_m':60.})]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):
 spec=importlib.util.spec_from_file_location('b1_'+sha(p)[:12],p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def make_case(seed,mode,group,scenario,noise):
 r=random.Random(seed);n=10 if scenario=='count10' else 16 if scenario=='count16' else r.randint(10,16)
 chs=r.sample(range(1,21),n);nd=0 if mode==3 else r.randint(1,n-1)
 phi=r.uniform(-math.pi,math.pi);center=(1450*math.cos(phi),1450*math.sin(phi));sources=[]
 for i,ch in enumerate(chs):
  a=r.uniform(-math.pi,math.pi);rad=1800*math.sqrt(r.random());reach=r.uniform(1000,1500)
  direction=r.uniform(-math.pi,math.pi) if i<nd else None
  x,y=rad*math.cos(a),rad*math.sin(a)
  if scenario=='edge':
   rad=r.uniform(1700,1800);x,y=rad*math.cos(a),rad*math.sin(a);reach=1000;direction=a if i<nd else None
  elif scenario=='offcenter':
   rad=80*math.sqrt(r.random());x,y=center[0]+rad*math.cos(a),center[1]+rad*math.sin(a)
  elif scenario=='origin':
   rad=60*math.sqrt(r.random());x,y=rad*math.cos(a),rad*math.sin(a);reach=1000
  elif scenario=='minimum':reach=1000
  sources.append(dict(channel=ch,x=x,y=y,radius=reach,direction=direction))
 assert all(math.hypot(s['x'],s['y'])<=1800+1e-8 and 1000<=s['radius']<=1500 for s in sources)
 assert mode==3 or 0<sum(s['direction'] is not None for s in sources)<len(sources)
 return dict(case_id=f'B1-dev-q{mode}-{group}-{seed}',mode=mode,group=group,noise=noise,seed=seed,sources=sources)
def run_case(module,case,config):
 env=LocalEnv([Source(**s) for s in case['sources']],case['seed'],case['noise'],keep_log=False)
 st=time.perf_counter();error=None;result={};solver=None
 try:
  solver=module.Solver(InterfaceOnly(env),mode=case['mode'],**{**module.OPTIMIZED_CONFIGS[case['mode']],**config});result=solver.run()
 except Exception as e:error=f'{type(e).__name__}: {e}'
 elapsed=time.perf_counter()-st
 if env.started and not env.finished:env._finish('strategy_exception' if error else 'missing_exit')
 s=env.stats()
 return dict(case_id=case['case_id'],mode=case['mode'],group=case['group'],seed=case['seed'],cleared_count=s['cleared'],source_count=s['n'],complete=s['cleared']==s['n'] and env.exit_reason=='user_exit' and error is None,exit_reason=env.exit_reason,error=error,average_clear_time_s=s['average_s'],total_virtual_time_s=s['time_s'],distance_m=s['distance_m'],requests=s['measures']+s['clear_attempts']+2,clear_failures=s['clear_failures'],runtime_s=elapsed,counters=result.get('counters',{}),sharing_spent_s=getattr(solver,'_sharing_spent_s',0))
def summarize(rows):
 import statistics
 return [dict(mode=m,group=g,cases=len(z),complete=sum(r['complete'] for r in z),mean=statistics.mean(r['average_clear_time_s'] for r in z) if all(r['complete'] for r in z) else None,mean_distance=statistics.mean(r['distance_m'] for r in z),mean_requests=statistics.mean(r['requests'] for r in z),max_runtime=max(r['runtime_s'] for r in z)) for m in (3,4) for g in ('ALL',*[x[0] for x in GROUPS]) if (z:=[r for r in rows if r['mode']==m and (g=='ALL' or r['group']==g)])]
def main():
 p=argparse.ArgumentParser();p.add_argument('--split',choices=['train','development'],required=True);a=p.parse_args()
 folder=OUT/'results'/('r1_'+a.split);folder.mkdir(exist_ok=False)
 start=3101000 if a.split=='train' else 3102000
 exposed=json.loads((ROOT/'experiments/20260911_breakthrough/exposed_cases.json').read_text());forbidden={c['seed'] for c in exposed}
 assert not forbidden.intersection(range(start,start+6))
 cases=[make_case(seed,m,g,s,n) for m in (3,4) for g,s,n in GROUPS for seed in range(start,start+6)]
 (folder/'cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2))
 candidate=OUT/'snapshots/r1_development.py';parents={'C0':ROOT/'experiments/20260911_breakthrough/baseline/C0.py','A3_R2':ROOT/'experiments/20260911_agent_campaign/final_candidates/A3_coordination_R2.py'}
 summary={};t=time.perf_counter()
 for name,style,extra in VARIANTS:
  path=parents.get(name,candidate);module=load(path);config={} if style is None else dict(sharing_style=style,**{'sharing_gain_m':30.,**extra})
  # dict duplicate key not allowed when extra overrides; explicit merge below.
  rows=[];vst=time.perf_counter()
  for case in cases:rows.append(dict(run_case(module,case,config),variant=name))
  (folder/(name+'_rows.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2))
  summary[name]=dict(source=str(path),sha256=sha(path),config=config,runs=len(rows),wall_s=time.perf_counter()-vst,groups=summarize(rows))
  print(name,[g for g in summary[name]['groups'] if g['group']=='ALL'],flush=True)
 (folder/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
 (folder/'budget.json').write_text(json.dumps(dict(split=a.split,seed_range=[start,start+5],variants=len(VARIANTS),actual_runs=len(cases)*len(VARIANTS),unique_cases=len(cases),wall_s=time.perf_counter()-t,failures=sum(r['cases']-r['complete'] for v in summary.values() for r in v['groups'] if r['group']=='ALL')),indent=2))
if __name__=='__main__':main()
