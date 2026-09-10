"""A3 development-only evaluation; never uses v1 case numbers or truth in Solver."""
import sys,json,importlib.util,time,statistics,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from local_env import LocalEnv,InterfaceOnly,make_case

def load(path):
 spec=importlib.util.spec_from_file_location('candidate_'+str(hash(path)),path)
 mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--start',type=int,default=62000);p.add_argument('--count',type=int,default=5);p.add_argument('--config',default='{}');a=p.parse_args()
 out=Path(a.out);assert not out.exists()
 config=json.loads(a.config);rows=[];start=time.perf_counter()
 for name,path in [('baseline',ROOT/'evaluation/baseline_solver.py'),('candidate',ROOT/'solver.py')]:
  m=load(path)
  for mode in (3,4):
   for scenario in ('random','min_radius','boundary','cluster'):
    for seed in range(a.start,a.start+a.count):
     env=LocalEnv(make_case(seed,mode,scenario),seed,keep_log=False);sol=m.Solver(InterfaceOnly(env),mode,**config)
     error=None
     try:r=sol.run()
     except Exception as e:error=repr(e)
     stat=env.stats();rows.append(dict(variant=name,mode=mode,scenario=scenario,seed=seed,complete=stat['cleared']==stat['n'] and error is None,error=error,**stat))
 summ={mode:{v:statistics.mean(x['average_s'] for x in rows if x['variant']==v and x['mode']==mode) for v in ('baseline','candidate')} for mode in (3,4)}
 out.write_text(json.dumps(dict(config=config,seed_range=[a.start,a.start+a.count-1],all_complete=all(x['complete'] for x in rows),summary=summ,wall_seconds=time.perf_counter()-start,rows=rows),indent=2));print(json.dumps(summ));print('all complete',all(x['complete'] for x in rows))
if __name__=='__main__':main()
