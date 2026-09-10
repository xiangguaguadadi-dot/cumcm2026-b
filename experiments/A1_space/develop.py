"""Development-only runs on disjoint seeds; never loads fixed v1 cases."""
import argparse,importlib.util,json,sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from local_env import LocalEnv,InterfaceOnly,make_case

def load(path):
 s=importlib.util.spec_from_file_location('candidate',str(path));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def main():
 p=argparse.ArgumentParser();p.add_argument('--candidate',default='solver.py');p.add_argument('--out',required=True);p.add_argument('--seed',type=int,default=62000);p.add_argument('--n',type=int,default=20);a=p.parse_args();m=load(ROOT/a.candidate)
 rows=[];t=time.perf_counter()
 for mode in (3,4):
  for sc in ('random','boundary','cluster','min_radius'):
   for i in range(a.n):
    seed=a.seed+i
    sources=make_case(seed,mode,sc)
    # The local helper's boundary/cluster stress profiles make every emitter
    # directional in mode 4. Restore the problem's required mixed condition.
    if mode==4 and all(x.direction is not None for x in sources):sources[-1].direction=None
    env=LocalEnv(sources,seed,keep_log=False);e=None;r={} 
    try:r=m.Solver(InterfaceOnly(env),mode=mode).run()
    except Exception as ex:e=repr(ex)
    z=env.stats();rows.append(dict(mode=mode,scenario=sc,seed=seed,complete=z['n']==z['cleared'] and env.exit_reason=='user_exit' and not e,error=e,average_s=z['average_s'],distance_m=z['distance_m'],measures=z['measures']))
 out=dict(seed_start=a.seed,n_per_scenario=a.n,wall_seconds=time.perf_counter()-t,rows=rows)
 for mode in (3,4):
  z=[r for r in rows if r['mode']==mode];print(mode,len(z),sum(x['complete'] for x in z),statistics.mean(x['average_s'] for x in z))
 Path(a.out).write_text(json.dumps(out,indent=2))
if __name__=='__main__':main()
