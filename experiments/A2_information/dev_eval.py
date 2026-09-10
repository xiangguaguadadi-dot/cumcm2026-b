"""Independent LOCAL training/development evaluation; not fixed v1 regression."""
import sys,importlib.util,json,statistics,time,hashlib,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from local_env import LocalEnv,InterfaceOnly,make_case

def load(path):
 spec=importlib.util.spec_from_file_location('trial',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
 p=argparse.ArgumentParser();p.add_argument('--candidate',default='solver.py');p.add_argument('--out',required=True);p.add_argument('--start',type=int,default=910000);p.add_argument('--n',type=int,default=10);a=p.parse_args()
 cand=load(ROOT/a.candidate);base=load(ROOT/'evaluation/baseline_solver.py');rows=[];start=time.perf_counter()
 for mode in [3,4]:
  for scenario,noise in [('random','uniform'),('random','positive'),('random','smooth_shared'),('boundary','negative'),('cluster','cell_50'),('min_radius','cell_500')]:
   for k in range(a.n):
    seed=a.start+k;case=make_case(seed,mode,scenario)
    for label,mod in [('baseline',base),('candidate',cand)]:
     env=LocalEnv(case,seed,noise,keep_log=False);err=None;r={}
     try:r=mod.Solver(InterfaceOnly(env),mode=mode).run()
     except Exception as e:err=repr(e)
     stats=env.stats();rows.append(dict(mode=mode,scenario=scenario,noise=noise,seed=seed,variant=label,error=err,complete=stats['cleared']==stats['n'] and env.exit_reason=='user_exit',average=stats['average_s'],distance=stats['distance_m'],measures=stats['measures'],clear_failures=stats['clear_failures']))
 summary={str(mode):{lab:{'mean':statistics.mean(r['average'] for r in rows if r['mode']==mode and r['variant']==lab),'complete':sum(r['complete'] for r in rows if r['mode']==mode and r['variant']==lab),'n':sum(1 for r in rows if r['mode']==mode and r['variant']==lab)} for lab in ['baseline','candidate']} for mode in [3,4]}
 out=ROOT/a.out;out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps(dict(label='Independent development data; not unseen after use',candidate_sha256=hashlib.sha256((ROOT/a.candidate).read_bytes()).hexdigest(),start_seed=a.start,n=a.n,elapsed=time.perf_counter()-start,summary=summary,rows=rows),ensure_ascii=False,indent=2));print(json.dumps(summary),flush=True)
if __name__=='__main__':main()
