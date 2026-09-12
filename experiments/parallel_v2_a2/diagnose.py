"""Exact-action replay for diagnostic counters on an already exposed 96-case batch."""
import argparse,importlib.util,json,statistics,sys,time,types
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT))
sp=importlib.util.spec_from_file_location('dev',ROOT/'experiments/E2_refine/develop.py');D=importlib.util.module_from_spec(sp);sp.loader.exec_module(D)
p=argparse.ArgumentParser();p.add_argument('candidate');p.add_argument('out');a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
cases=json.loads((ROOT/'experiments/20260912_breakthrough/A2/results/diagnostic_96/cases.json').read_text())
source=Path(a.candidate);module=D.load(source)
def construct(*args,**kwargs):
 s=module.Solver(*args,**kwargs);original=s.optical_points
 def observe(ch):
  points=original(ch);s.counters['diagnostic_optical_points']=s.counters.get('diagnostic_optical_points',0)+len(points)
  s.counters['diagnostic_optical_cover_calls']=s.counters.get('diagnostic_optical_cover_calls',0)+1
  return points
 s.optical_points=observe
 return s
wrapper=types.SimpleNamespace(Solver=construct,OPTIMIZED_CONFIGS=module.OPTIMIZED_CONFIGS);rows=[];start=time.perf_counter()
for c in cases:
 row,detail=D.run_case(wrapper,c,False);rows.append(row)
D.save(out/'rows.json',rows)
keys=sorted({k for r in rows for k in r['counters']})
summary=dict(data_role='replayed already exposed A2 development cases; not holdout',candidate=str(source),candidate_sha256=D.sha(source),cases=len(rows),all_complete=all(r['complete'] for r in rows),wall_s=time.perf_counter()-start,mean_s_per_source=statistics.mean(r['average_clear_time_s'] for r in rows),counter_totals={k:sum(r['counters'].get(k,0) for r in rows) for k in keys},counter_case_triggers={k:sum(bool(r['counters'].get(k,0)) for r in rows) for k in keys},requests=sum(r['requests'] for r in rows),clear_failures=sum(r['clear_failures'] for r in rows))
D.save(out/'summary.json',summary);print({k:v for k,v in summary.items() if k not in ('counter_totals','counter_case_triggers')})
