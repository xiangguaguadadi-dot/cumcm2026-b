from pathlib import Path
import sys,json,time,hashlib,statistics,importlib.util
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT))
import evaluate
spec=importlib.util.spec_from_file_location('devgen',ROOT/'experiments/R2_open/research/develop.py');dev=importlib.util.module_from_spec(spec);spec.loader.exec_module(dev)
def save(p,x):p.write_text(json.dumps(x,indent=2))
if __name__=='__main__':
 label=sys.argv[1];path=(ROOT/sys.argv[2]).resolve();out=HERE/'results'/label;out.mkdir(exist_ok=False)
 cases=[dev.make_case(seed,3,g,s,n) for g,s,n in dev.GROUPS for seed in range(96212000,96212008)]
 save(out/'registration.json',dict(candidate=str(path),sha256=evaluate.sha(path),cases=96,seeds=[96212000,96212007],role='new development worlds; exposed after execution',frozen_manifest_sha256=evaluate.sha(ROOT/'evaluation/manifest_v1.json')))
 save(out/'cases.json',cases);evaluate.verify();st=time.perf_counter();rows=evaluate.run_cases(cases,path,False);elapsed=time.perf_counter()-st;evaluate.verify();save(out/'case_metrics.json',rows)
 summary=dict(cases=len(rows),all_complete=all(r['complete'] for r in rows),errors=sum(bool(r['error']) for r in rows),mean=statistics.mean(r['average_clear_time_s'] for r in rows),wall_s=elapsed,distance_m=statistics.mean(r['distance_m'] for r in rows),requests=statistics.mean(r['requests'] for r in rows),clear_failures=sum(r['clear_failures'] for r in rows))
 save(out/'summary.json',summary);print(label,summary,flush=True)
