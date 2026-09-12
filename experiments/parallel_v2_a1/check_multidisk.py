from pathlib import Path
import sys,importlib.util,itertools,random,math,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT))
p=HERE/'snapshots/r6.py';spec=importlib.util.spec_from_file_location('candidate',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);r=random.Random(96212019)
checks=0;maxerr=0.
for i in range(30):
 n=3+i%4;points=[(r.uniform(-100,100),r.uniform(-100,100)) for _ in range(n)];targets=[(q[0]+r.uniform(-10,10),q[1]+r.uniform(-10,10)) for q in points for _ in range(3)];position=(r.uniform(-200,200),r.uniform(-200,200));score,path=m.MultiDiskSpatial._expected_order(position,points,targets)
 brute=min(m.MultiDiskSpatial._sequence_cost(position,perm,targets) for perm in itertools.permutations(points));err=abs(score-brute);maxerr=max(maxerr,err);assert err<1e-9;checks+=1
result=dict(dp_vs_exhaustive_cases=checks,max_absolute_error=maxerr,passed=True)
(HERE/'results/r6_dp_checks.json').write_text(json.dumps(result,indent=2));print(result)
