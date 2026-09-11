"""Independent legal development generation, copied from audited B1 generator. Evaluation only."""
from pathlib import Path
import argparse,random,math,json,hashlib,time,sys,importlib.util,statistics
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from local_env import Source,LocalEnv,InterfaceOnly
OUT=ROOT/"experiments/R2_open"
GROUPS=[('reference_assumed','random','uniform'),('fixed_positive_bias','random','positive'),('fixed_negative_bias','random','negative'),('smooth_shared_field','random','smooth_shared'),('cell50_shared_field','random','cell_50'),('cell500_shared_field','random','cell_500'),('edge_mixed_min_radius','edge','uniform'),('offcenter_cluster','offcenter','uniform'),('origin_cluster','origin','uniform'),('minimum_radius','minimum','uniform'),('exactly10_sources','count10','uniform'),('exactly16_sources','count16','uniform')]

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
 return dict(case_id=f'R2-open-dev-q{mode}-{group}-{seed}',mode=mode,group=group,noise=noise,seed=seed,sources=sources)

def summarize(rows):
 import statistics
 return [dict(mode=m,group=g,cases=len(z),complete=sum(r['complete'] for r in z),mean=statistics.mean(r['average_clear_time_s'] for r in z) if all(r['complete'] for r in z) else None,mean_distance=statistics.mean(r['distance_m'] for r in z),mean_requests=statistics.mean(r['requests'] for r in z),max_runtime=max(r['runtime_s'] for r in z)) for m in (3,4) for g in ('ALL',*[x[0] for x in GROUPS]) if (z:=[r for r in rows if r['mode']==m and (g=='ALL' or r['group']==g)])]


def run_case(module, case, config, audit_geometry=True):
 env=LocalEnv([Source(**s) for s in case['sources']],case['seed'],case['noise'],keep_log=False)
 st=time.perf_counter();error=None;result={};solver=None;check_count=0;max_vertices=0
 truth={s['channel']:(s['x'],s['y']) for s in case['sources']}
 try:
  solver=module.Solver(InterfaceOnly(env),mode=case['mode'],**{**module.OPTIMIZED_CONFIGS[case['mode']],**config})
  if audit_geometry:
   original_measure=solver.measure
   def checked_measure(p,ch):
    nonlocal check_count,max_vertices
    kind=original_measure(p,ch)
    if ch in solver.polygons and ch in truth:
     poly=solver.polygons[ch];max_vertices=max(max_vertices,len(poly));target=truth[ch]
     for a,b in zip(poly,poly[1:]+poly[:1]):
      dx,dy=b[0]-a[0],b[1]-a[1]
      cross=dx*(target[1]-a[1])-dy*(target[0]-a[0])
      assert cross>=-1e-3*max(1,math.hypot(dx,dy)), ('target outside polygon',ch,cross,len(poly))
     check_count+=1
    return kind
   solver.measure=checked_measure
  result=solver.run()
 except Exception as e:error=f'{type(e).__name__}: {e}'
 elapsed=time.perf_counter()-st
 if env.started and not env.finished:env._finish('strategy_exception' if error else 'missing_exit')
 s=env.stats()
 return dict(case_id=case['case_id'],mode=case['mode'],group=case['group'],seed=case['seed'],cleared_count=s['cleared'],source_count=s['n'],complete=s['cleared']==s['n'] and env.exit_reason=='user_exit' and error is None,exit_reason=env.exit_reason,error=error,average_clear_time_s=s['average_s'],total_virtual_time_s=s['time_s'],distance_m=s['distance_m'],requests=s['measures']+s['clear_attempts']+2,clear_failures=s['clear_failures'],runtime_s=elapsed,counters=result.get('counters',{}),sharing_spent_s=getattr(solver,'_sharing_spent_s',0),geometry_checks=check_count,max_vertices=max_vertices)


def main():
 p=argparse.ArgumentParser();p.add_argument('--name',default='r1_development');p.add_argument('--start',type=int,default=42000000);p.add_argument('--seeds',type=int,default=8);p.add_argument('--variants-file');a=p.parse_args()
 folder=OUT/'results'/a.name;folder.mkdir(exist_ok=False)
 forbidden=set(json.loads((OUT/'research/known_seed_audit.json').read_text())['known_seeds'])
 assert not forbidden.intersection(range(a.start,a.start+a.seeds)), 'Seed collision with historical evidence'
 cases=[make_case(seed,m,g,s,n) for m in (3,4) for g,s,n in GROUPS for seed in range(a.start,a.start+a.seeds)]
 (folder/'cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2))
 flags=dict(geom_tangent=False,geom_no_signal=False,geom_failure=False)
 candidate=OUT/'snapshots/r1_development.py'
 variants=[('S0',ROOT/'experiments/20260911_stage3/baseline/S0.py',{}),('embedded_control',candidate,flags),('tangent',candidate,dict(flags,geom_tangent=True)),('no_signal',candidate,dict(flags,geom_no_signal=True)),('failure',candidate,dict(flags,geom_failure=True)),('all_geometry',candidate,dict(geom_tangent=True,geom_no_signal=True,geom_failure=True)),('A2_R8',ROOT/'experiments/20260911_agent_campaign/final_candidates/A2_information_R8.py',{})]
 if a.variants_file:
  variants=[(v['name'],ROOT/v['candidate'],v.get('config',{})) for v in json.loads(Path(a.variants_file).read_text())]
 summary={};t=time.perf_counter();execution=[]
 (folder/'preregistration.json').write_text(json.dumps(dict(seed_range=[a.start,a.start+a.seeds-1],variants=[dict(name=n,path=str(path),sha256=sha(path),config=config) for n,path,config in variants],data_role='development selection; not holdout',q4_legal_mixed=all(0<sum(s['direction'] is not None for s in c['sources'])<len(c['sources']) for c in cases if c['mode']==4),selection='All-complete lowest Q3 mean among S0-derived variants; Q4 must match S0 when intended'),indent=2))
 for name,path,config in variants:
  module=load(path);rows=[];vst=time.perf_counter()
  for case in cases:rows.append(dict(run_case(module,case,config),variant=name))
  (folder/(name+'_rows.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2))
  summary[name]=dict(source=str(path),sha256=sha(path),config=config,runs=len(rows),wall_s=time.perf_counter()-vst,groups=summarize(rows),geometry_checks=sum(r['geometry_checks'] for r in rows),max_vertices=max(r['max_vertices'] for r in rows))
  execution.append(dict(name=name,runs=len(rows),wall_s=summary[name]['wall_s']))
  (folder/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
  (folder/'budget.json').write_text(json.dumps(dict(seed_range=[a.start,a.start+a.seeds-1],variants_completed=len(summary),actual_runs=len(cases)*len(summary),unique_cases=len(cases),wall_s=time.perf_counter()-t,execution=execution),indent=2))
  print(name,[g for g in summary[name]['groups'] if g['group']=='ALL'],flush=True)


if __name__=='__main__':main()
