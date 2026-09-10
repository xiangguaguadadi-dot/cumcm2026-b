"""Independent generated bearings check truth containment and outer-bound refinement."""
import sys,math,random,importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import solver
spec=importlib.util.spec_from_file_location('baseline',ROOT/'evaluation/baseline_solver.py');base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
def inside(x,p):
 for a,b in zip(p,p[1:]+p[:1]):
  if (b[0]-a[0])*(x[1]-a[1])-(b[1]-a[1])*(x[0]-a[0]) < -1e-5:return False
 return True
def area(p):return abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(p,p[1:]+p[:1])))/2
rng=random.Random(931204);checks=[]
for k in range(1000):
 theta=rng.uniform(-math.pi,math.pi);rad=1800 if k%2 else 1800*math.sqrt(rng.random());target=(rad*math.cos(theta),rad*math.sin(theta));d=rng.uniform(5.1,1500);a=rng.uniform(-math.pi,math.pi);p=(target[0]+d*math.cos(a),target[1]+d*math.sin(a));error=[-1,0,1][k%3];bearing=round((math.degrees(a)+180+error)%360,2)%360
 old=base.add_bearing(base.initial_polygon(),p,bearing);new=solver.add_bearing(solver.initial_polygon(),p,bearing)
 assert new and inside(target,new),(k,'removed allowed truth')
 assert all(inside(v,old) for v in new),(k,'not subset')
 assert area(new)<=area(old)+1e-5,(k,'grew')
 checks.append({'index':k,'old_area':area(old),'new_area':area(new)})
print(json.dumps({'passed':len(checks),'seed':931204,'checks':checks},indent=2))
