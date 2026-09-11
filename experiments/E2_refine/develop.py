"""Independent legal development/evaluation layer; truth is never passed to a solver.

This script owns case generation and metrics. Deployed snapshots do not import it.
New source seeds are allocated monotonically inside E2's exclusive range.
"""
import argparse,hashlib,importlib.util,json,math,random,statistics,sys,time,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
HERE=Path(__file__).resolve().parent
from local_env import Source,LocalEnv,InterfaceOnly
GROUPS=[('reference_assumed','random','uniform'),('fixed_positive_bias','random','positive'),
('fixed_negative_bias','random','negative'),('smooth_shared_field','random','smooth_shared'),
('cell50_shared_field','random','cell_50'),('cell500_shared_field','random','cell_500'),
('edge_mixed_min_radius','edge','uniform'),('offcenter_cluster','offcenter','uniform'),
('origin_cluster','origin','uniform'),('minimum_radius','minimum','uniform'),
('exactly10_sources','count10','uniform'),('exactly16_sources','count16','uniform')]

def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):
 spec=importlib.util.spec_from_file_location('e2_dev_'+sha(p)[:12],p)
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

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
 assert 10<=len(sources)<=16 and len({s['channel'] for s in sources})==len(sources)
 assert all(math.hypot(s['x'],s['y'])<=1800+1e-8 and 1000<=s['radius']<=1500 for s in sources)
 assert mode==3 or 0<sum(s['direction'] is not None for s in sources)<len(sources)
 return dict(case_id=f'E2-dev-q{mode}-{group}-{seed}',mode=mode,group=group,noise=noise,seed=seed,sources=sources)

def instrumentation(solver):
 """Read-only diagnostic wrappers: record call contexts, do not rank actions."""
 stack=[];annotations={};events=[]
 for name in ['scan_station','localize','share_observations','rescue_bearing','cover_polygon','measure','clear']:
  original=getattr(solver,name)
  def wrapped(*args,_name=name,_original=original,**kwargs):
   start=len(solver.trace);t0=solver.virtual_time;p0=solver.position
   stack.append(_name);context=tuple(stack)
   try:return _original(*args,**kwargs)
   finally:
    for i in range(start,len(solver.trace)):annotations.setdefault(i,context)
    if _name not in ('measure','clear'):
     events.append(dict(method=_name,args=list(args),start_action=start,end_action=len(solver.trace),
         start_virtual_s=t0,end_virtual_s=solver.virtual_time,position_before=list(p0),position_after=list(solver.position)))
    stack.pop()
  setattr(solver,name,wrapped)
 return annotations,events

def run_case(module,case,trace=False,config=None):
 env=LocalEnv([Source(**s) for s in case['sources']],case['seed'],case['noise'],keep_log=False)
 error=None;result={};solver=None;annotations={};events=[];st=time.perf_counter()
 try:
  conf={**module.OPTIMIZED_CONFIGS[case['mode']],**(config or {})}
  if trace:conf['e2_log_decisions']=True
  solver=module.Solver(InterfaceOnly(env),mode=case['mode'],**conf)
  if trace:annotations,events=instrumentation(solver)
  result=solver.run()
 except Exception as e:error=f'{type(e).__name__}: {e}'
 elapsed=time.perf_counter()-st
 if env.started and not env.finished:env._finish('strategy_exception' if error else 'missing_exit')
 s=env.stats()
 row=dict(case_id=case['case_id'],mode=case['mode'],group=case['group'],seed=case['seed'],
   cleared_count=s['cleared'],source_count=s['n'],complete=s['cleared']==s['n'] and env.exit_reason=='user_exit' and error is None,
   exit_reason=env.exit_reason,error=error,average_clear_time_s=s['average_s'],total_virtual_time_s=s['time_s'],
   distance_m=s['distance_m'],requests=s['measures']+s['clear_attempts']+2,clear_failures=s['clear_failures'],runtime_s=elapsed,
   counters=result.get('counters',{}),sharing_spent_s=getattr(solver,'_sharing_spent_s',0))
 details=None
 if trace and solver:
  details=dict(case_id=case['case_id'],trace=[dict(t,context=list(annotations.get(i,()))) for i,t in enumerate(solver.trace)],
      events=events,gate_decisions=getattr(solver,'e2_decisions',[]),result=result)
 return row,details

def comparisons(rows,base):
 index={r['case_id']:r for r in base};out=[]
 for mode in sorted({r['mode'] for r in rows}):
  for group in ['ALL']+sorted({r['group'] for r in rows if r['mode']==mode}):
   part=[r for r in rows if r['mode']==mode and (group=='ALL' or r['group']==group)]
   refs=[index[r['case_id']] for r in part]
   valid=all(r['complete'] and b['complete'] for r,b in zip(part,refs))
   entry=dict(mode=mode,group=group,cases=len(part),complete=sum(r['complete'] for r in part),valid=valid)
   if valid:
    a=statistics.mean(r['average_clear_time_s'] for r in refs);b=statistics.mean(r['average_clear_time_s'] for r in part)
    ds=[r['average_clear_time_s']-ref['average_clear_time_s'] for r,ref in zip(part,refs)]
    entry.update(mean_s_per_source=b,baseline_mean_s_per_source=a,delta_s_per_source=b-a,
     faster=sum(d < -1e-8 for d in ds),equal=sum(abs(d)<=1e-8 for d in ds),slower=sum(d>1e-8 for d in ds),
     movement_s_per_source=statistics.mean(r['distance_m']/5/r['source_count'] for r in part),
     nonmovement_s_per_source=statistics.mean((r['total_virtual_time_s']-r['distance_m']/5)/r['source_count'] for r in part),
     clear_failures_per_source=statistics.mean(r['clear_failures']/r['source_count'] for r in part),
     sharing_s_per_source=statistics.mean(r['sharing_spent_s']/r['source_count'] for r in part),
     mean_runtime_s=statistics.mean(r['runtime_s'] for r in part),
     largest_regressions=sorted([dict(case_id=r['case_id'],delta_s_per_source=d) for r,d in zip(part,ds)],key=lambda r:r['delta_s_per_source'],reverse=True)[:5])
   out.append(entry)
 return out

def main():
 p=argparse.ArgumentParser();p.add_argument('--batch',required=True);p.add_argument('--per-group',type=int,default=8)
 p.add_argument('--modes',nargs='+',type=int,default=[4]);p.add_argument('--variants',nargs='+',required=True)
 p.add_argument('--reuse-cases');p.add_argument('--reuse-baseline');p.add_argument('--trace-per-group',type=int,default=1)
 a=p.parse_args();folder=HERE/'results'/a.batch;folder.mkdir(exist_ok=False)
 if a.reuse_cases:
  cases=json.loads(Path(a.reuse_cases).read_text());unique=0
 else:
  ledger=json.loads((HERE/'used_seeds.json').read_text());start=ledger['next_seed'];count=len(a.modes)*len(GROUPS)*a.per_group
  assert 45000000<=start and start+count<=46000000
  cases=[];seed=start
  for mode in a.modes:
   for group,scenario,noise in GROUPS:
    for i in range(a.per_group):cases.append(make_case(seed,mode,group,scenario,noise));seed+=1
  ledger['next_seed']=seed;ledger['batches'].append(dict(batch=a.batch,start=start,end_exclusive=seed,seeds=list(range(start,seed)),cases=count))
  save(HERE/'used_seeds.json',ledger);unique=len(cases)
 save(folder/'cases.json',cases)
 seen={};traceids=set()
 for c in cases:
  key=(c['mode'],c['group']);seen[key]=seen.get(key,0)+1
  if seen[key]<=a.trace_per_group:traceids.add(c['case_id'])
 summary={};baseline=None;run_count=0;allstart=time.perf_counter()
 for name in a.variants:
  source=ROOT/'experiments/20260911_stage4/baseline/S1.py' if name=='S1' else HERE/'snapshots'/(name+'.py')
  if name=='S1' and a.reuse_baseline:
   rows=json.loads(Path(a.reuse_baseline).read_text());elapsed=0.;ran=0
  else:
   m=load(source);rows=[];start=time.perf_counter()
   for c in cases:
    row,detail=run_case(m,c,c['case_id'] in traceids);rows.append(dict(row,variant=name))
    if detail:save(folder/(name+'__'+c['case_id']+'_trace.json'),detail)
   elapsed=time.perf_counter()-start;ran=len(rows);run_count+=ran
  save(folder/(name+'_rows.json'),rows)
  if name=='S1':baseline=rows
  if baseline is None:raise ValueError('S1 must come first (possibly reused)')
  summary[name]=dict(source=str(source.relative_to(ROOT)),sha256=sha(source),actual_runs=ran,wall_s=elapsed,comparisons_to_S1=comparisons(rows,baseline))
  save(folder/'summary.json',summary)
  print(name,[g for g in summary[name]['comparisons_to_S1'] if g['group']=='ALL'],flush=True)
 budget=dict(batch=a.batch,actual_runs=run_count,distinct_new_cases=unique,reused_case_executions=run_count-unique,
     wall_s=time.perf_counter()-allstart,variants=a.variants,cases_sha256=sha(folder/'cases.json'),data_role='legal development, not holdout')
 save(folder/'budget.json',budget)
 ledger=json.loads((HERE/'execution_budget.json').read_text());ledger['actual_strategy_executions']+=run_count
 ledger['distinct_new_development_cases']+=unique;ledger['reused_case_executions']+=run_count-unique;ledger['rounds'].append(budget)
 save(HERE/'execution_budget.json',ledger)
if __name__=='__main__':main()
