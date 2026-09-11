"""B2 independent legal development, complete parameter and episode ledger."""
import argparse,datetime,hashlib,importlib.util,json,math,random,statistics,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from local_env import Source,LocalEnv,InterfaceOnly

def load(path):
 spec=importlib.util.spec_from_file_location('b2devcandidate',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def make_case(seed,mode,scene,noise):
 rng=random.Random(seed);n=10 if scene=='count10' else 16 if scene=='count16' else rng.randint(10,16)
 chs=rng.sample(range(1,21),n);directional=0 if mode==3 else rng.randint(1,n-1);sources=[]
 for i,ch in enumerate(chs):
  a=rng.uniform(-math.pi,math.pi);r=1800*math.sqrt(rng.random());radius=rng.uniform(1000,1500)
  direction=rng.uniform(-math.pi,math.pi) if i<directional else None
  if scene=='edge':r=rng.uniform(1720,1800);radius=1000
  elif scene=='origin':r=rng.uniform(0,100);radius=1000
  elif scene=='minimum':radius=1000
  x,y=r*math.cos(a),r*math.sin(a)
  if scene=='offcenter':
   x=1180+rng.uniform(-160,160);y=100+rng.uniform(-160,160)
  sources.append(dict(channel=ch,x=x,y=y,radius=radius,direction=direction))
 assert all(math.hypot(s['x'],s['y'])<=1800+1e-8 for s in sources)
 assert mode==3 or 0<sum(s['direction'] is not None for s in sources)<n
 return dict(case_id=f'B2dev-{mode}-{scene}-{noise}-{seed}',seed=seed,mode=mode,scene=scene,noise=noise,sources=sources)

def main():
 p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--out',required=True);p.add_argument('--start',type=int,required=True);p.add_argument('--seeds',type=int,default=8);p.add_argument('--variants',default='parent25,naive28,adaptive');p.add_argument('--modes',default='4');p.add_argument('--configs');a=p.parse_args()
 out=Path(a.out);out.mkdir(parents=True,exist_ok=False);path=Path(a.candidate).resolve();m=load(path)
 sha=lambda q:hashlib.sha256(Path(q).read_bytes()).hexdigest();before=sha(path)
 cases=[];scenes=['area','edge','origin','offcenter','minimum','count10','count16'];noises=['uniform','positive','negative','smooth_shared','cell_50','cell_500']
 # Different seeds per geometry/noise slot, not just a misleading larger row count.
 for mode in map(int,a.modes.split(',')):
  for i,scene in enumerate(scenes):
   for j,noise in enumerate(noises):
    for k in range(a.seeds):cases.append(make_case(a.start+mode*100000+i*1000+j*100+k,mode,scene,noise))
 forbidden={c['seed'] for c in json.loads((ROOT/'experiments/20260911_breakthrough/exposed_cases.json').read_text())}
 assert not forbidden & {c['seed'] for c in cases}
 (out/'cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2))
 variants=json.loads(Path(a.configs).read_text()) if a.configs else {v:dict(optical_partition=v) for v in a.variants.split(',')}
 registration=dict(time_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),candidate=str(path),sha256=before,variants=variants,cases=len(cases),planned_runs=len(cases)*len(variants),cases_sha256=sha(out/'cases.json'),training_runs=0,purpose='independent development selection; not holdout')
 (out/'registration.json').write_text(json.dumps(registration,ensure_ascii=False,indent=2))
 rows=[];t=time.perf_counter()
 with (out/'episodes.jsonl').open('w') as stream:
  for name,config in variants.items():
   for c in cases:
    env=LocalEnv([Source(**s) for s in c['sources']],c['seed'],c['noise'],keep_log=False)
    solver=m.Solver(InterfaceOnly(env),c['mode'],**config);error=None;start=time.perf_counter()
    try:result=solver.run()
    except Exception as ex:error=repr(ex);result={}
    st=env.stats();row=dict(variant=name,config=config,case_id=c['case_id'],mode=c['mode'],scene=c['scene'],noise=c['noise'],seed=c['seed'],complete=st['cleared']==st['n'] and env.exit_reason=='user_exit' and not error,error=error,exit_reason=env.exit_reason,source_count=st['n'],cleared_count=st['cleared'],average=st['average_s'],virtual_s=st['time_s'],distance_m=st['distance_m'],clear_failures=st['clear_failures'],runtime_s=time.perf_counter()-start,counters=solver.counters)
    rows.append(row);stream.write(json.dumps(row,ensure_ascii=False)+'\n');stream.flush()
    if error:(out/(name+'_'+c['case_id']+'_failure.json')).write_text(json.dumps(solver.trace,ensure_ascii=False,indent=2))
   q=[r for r in rows if r['variant']==name];print(name,len(q),sum(bool(r['complete']) for r in q),statistics.mean(r['average'] for r in q),flush=True)
 elapsed=time.perf_counter()-t;assert sha(path)==before
 summaries=[]
 for name in variants:
  for mode in map(int,a.modes.split(',')):
   q=[r for r in rows if r['variant']==name and r['mode']==mode]
   summaries.append(dict(variant=name,mode=mode,cases=len(q),complete=sum(bool(r['complete']) for r in q),mean=statistics.mean(r['average'] for r in q),max_runtime=max(r['runtime_s'] for r in q),partition_calls=sum(r['counters'].get('partition_calls',0) for r in q),parent_points=sum(r['counters'].get('partition_parent_points',0) for r in q),new_points=sum(r['counters'].get('partition_used_points',0) for r in q),mean_failures=statistics.mean(r['clear_failures'] for r in q),mean_distance=statistics.mean(r['distance_m'] for r in q)))
 (out/'summary.json').write_text(json.dumps(dict(registration=registration,actual_runs=len(rows),wall_seconds=elapsed,summaries=summaries),ensure_ascii=False,indent=2));print(json.dumps(summaries,ensure_ascii=False))
if __name__=='__main__':main()
