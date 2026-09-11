"""Independent point-membership checks complement the convex-partition proof."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,math,random,time
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--out',required=True);a=p.parse_args()
path=Path(a.candidate);spec=importlib.util.spec_from_file_location('checked',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
rng=random.Random(92271031);checks=0;max_distance=0.;max_points=0;fallback=0;start=time.perf_counter()
def hull(points):
 points=sorted(set(points));low=[];high=[]
 cross=lambda a,b,c:(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
 for p in points:
  while len(low)>1 and cross(low[-2],low[-1],p)<=0:low.pop()
  low.append(p)
 for p in points[::-1]:
  while len(high)>1 and cross(high[-2],high[-1],p)<=0:high.pop()
  high.append(p)
 return low[:-1]+high[:-1]
for i in range(500):
 length=rng.uniform(.1,590);width=rng.uniform(.0001,53)
 poly=hull([(rng.uniform(0,length),rng.uniform(-width/2,width/2)) for _ in range(10)]+[(0,0),(length,0)])
 angle=rng.uniform(-math.pi,math.pi);origin=(rng.uniform(-900,900),rng.uniform(-900,900));u=(math.cos(angle),math.sin(angle));v=(-u[1],u[0])
 world=lambda p:(origin[0]+u[0]*p[0]+v[0]*p[1],origin[1]+u[1]*p[0]+v[1]*p[1])
 solver=m.DirectionalSolver(None,4);solver.polygons[1]=[world(p) for p in poly];solver.observations[1]=[(origin,math.degrees(angle))];solver.position=world((rng.uniform(-500,1100),rng.uniform(-600,600)))
 points=solver.partition_points(1,'adaptive');assert points
 max_points=max(max_points,len(points));samples=list(solver.polygons[1])
 for t in range(100):
  weights=[rng.random() for _ in poly];total=sum(weights)
  samples.append(world((sum(w*p[0] for p,w in zip(poly,weights))/total,sum(w*p[1] for p,w in zip(poly,weights))/total)))
 for p,q in zip(poly,poly[1:]+poly[:1]):
  for k in range(1,10):samples.append(world((p[0]+(q[0]-p[0])*k/10,p[1]+(q[1]-p[1])*k/10)))
 for sample in samples:
  dd=min(m.dist(sample,p) for p in points);max_distance=max(max_distance,dd);assert dd<=20+1e-7,(i,sample,dd)
  checks+=1
out=Path(a.out);assert not out.exists();out.write_text(json.dumps(dict(candidate=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),polygons=500,point_checks=checks,all_passed=True,max_nearest_clear_m=max_distance,max_points=max_points,wall_seconds=time.perf_counter()-start,boundary='synthetic geometry only, not complete task runs or a replacement for analytical proof'),indent=2));print(out.read_text())
