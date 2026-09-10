"""Diagnostic run with explicit low watchdog; not official-time evaluation."""
import sys,signal,importlib.util,json,time,traceback,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from local_env import LocalEnv,InterfaceOnly,make_case
parser=argparse.ArgumentParser();parser.add_argument('--candidate',default='experiments/A2_information/candidates/r4_solver.py');parser.add_argument('--out',default='experiments/A2_information/dev/r4_watchdog.jsonl');args=parser.parse_args()
spec=importlib.util.spec_from_file_location('diagnostic',ROOT/args.candidate);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
path=ROOT/args.out;out=path.open('x');rows=[]
def alarm(*_):raise TimeoutError('diagnostic five-second wall watchdog; lower than official limit')
signal.signal(signal.SIGALRM,alarm)
for mode in [3,4]:
 for scenario,noise in [('random','uniform'),('random','positive'),('random','smooth_shared'),('boundary','negative'),('cluster','cell_50'),('min_radius','cell_500')]:
  for seed in range(910300,910310):
   env=LocalEnv(make_case(seed,mode,scenario),seed,noise,keep_log=False);solver=mod.Solver(InterfaceOnly(env),mode=mode);start=time.monotonic();error=None;trace=None
   signal.alarm(5)
   try:result=solver.run()
   except Exception as e:error=repr(e);trace=traceback.format_exc()
   finally:signal.alarm(0)
   row=dict(mode=mode,scenario=scenario,noise=noise,seed=seed,error=error,traceback=trace,elapsed=time.monotonic()-start,stats=env.stats(),max_polygon_vertices=max(map(len,solver.polygons.values()),default=0),counters=solver.counters)
   rows.append(row);out.write(json.dumps(row)+'\n');out.flush()
   if error:print(json.dumps({k:row[k] for k in ['mode','scenario','noise','seed','error','max_polygon_vertices']}),flush=True)
out.close();print(json.dumps(dict(cases=len(rows),errors=sum(bool(r['error']) for r in rows))),flush=True)
