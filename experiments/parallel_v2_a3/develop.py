"""Paired new development episodes. Reads truth only as evaluator."""
import argparse,hashlib,importlib.util,json,statistics,sys,time
from dataclasses import asdict
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT));import evaluate
def main():
    p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--count',type=int,default=96);a=p.parse_args()
    evaluate.verify();path=ROOT/'experiments/20260911_rl_execution/data/worlds.py'
    spec=importlib.util.spec_from_file_location('a3_worlds',path);worlds=importlib.util.module_from_spec(spec);spec.loader.exec_module(worlds)
    recipes=[worlds.recipe('parallel_v2_a3_development',4,i) for i in range(a.count)]
    cases=[dict(case_id=r['world_id'],mode=4,group=r['group'],noise=r['noise'],seed=r['seed'],
        sources=[asdict(x) for x in worlds.instantiate(r)]) for r in recipes]
    out=HERE/'results'/f'{a.name}_development';out.mkdir(exist_ok=False)
    (out/'registry.json').write_text(json.dumps(recipes,indent=2))
    rows={};started=time.monotonic()
    for name in ['baseline',a.name]:
        candidate=HERE/'snapshots'/f'{name}.py'
        rows[name]=evaluate.run_cases(cases,candidate,False)
        print(name,len(rows[name]),'done',flush=True)
    base=rows['baseline'];candidate=rows[a.name]
    valid=all(x['complete'] for part in rows.values() for x in part)
    report=dict(all_complete=valid,cases=a.count,candidate=a.name,wall_s=time.monotonic()-started)
    if valid:
        delta=[r['average_clear_time_s']-b['average_clear_time_s'] for r,b in zip(candidate,base)]
        report.update(baseline_mean=statistics.mean(r['average_clear_time_s'] for r in base),
            candidate_mean=statistics.mean(r['average_clear_time_s'] for r in candidate),
            delta_mean=statistics.mean(delta),faster=sum(d<-1e-8 for d in delta),slower=sum(d>1e-8 for d in delta),
            equal=sum(abs(d)<=1e-8 for d in delta))
    (out/'case_metrics.json').write_text(json.dumps(rows,indent=2));(out/'summary.json').write_text(json.dumps(report,indent=2))
    evaluate.verify();print(json.dumps(report))
if __name__=='__main__':main()
