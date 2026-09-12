"""Validate Q4 transplant's continuous strip cover and fixed-point DP objective."""
import importlib.util,itertools,json,math,random,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
candidate=Path(sys.argv[1]) if len(sys.argv)>1 else HERE/'snapshots/finite_r3.py'
sp=importlib.util.spec_from_file_location('finite',candidate);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);r=random.Random(926811)
checks=0;maxerror=0.
for i in range(24):
 n=3+i%4;points=[(r.uniform(-100,100),r.uniform(-100,100)) for _ in range(n)];targets=[(q[0]+r.uniform(-10,10),q[1]+r.uniform(-10,10)) for q in points for _ in range(3)];position=(r.uniform(-200,200),r.uniform(-200,200))
 score,path=m.MultiDiskSpatial._expected_order(position,points,targets)
 brute=min(m.MultiDiskSpatial._sequence_cost(position,perm,targets) for perm in itertools.permutations(points));err=abs(score-brute);assert err<1e-9;maxerror=max(maxerror,err);checks+=1
assert math.isinf(m.MultiDiskSpatial._expected_order((0,0),[(0,0)],[(30,0)])[0])
plans=0;covered=0;maxdistance=0.
for i in range(90):
 s=m.MultiDiskSpatial(None,mode=4,**m.OPTIMIZED_CONFIGS[4]);angle=r.uniform(-math.pi,math.pi);u=(math.cos(angle),math.sin(angle));v=(-u[1],u[0]);half=r.uniform(21,140);width=r.uniform(.1,14);center=(r.uniform(-1500,1500),r.uniform(-1500,1500));ch=1
 def world(x,y):return(center[0]+x*u[0]+y*v[0],center[1]+x*u[1]+y*v[1])
 s.polygons[ch]=[world(-half,-width),world(half,-width),world(half,width),world(-half,width)];s.position=world(r.uniform(-100,100),r.uniform(-100,100));s.observations[ch]=[((0.,0.),math.degrees(angle))]
 plan=s._three_disk_plan(ch)
 if plan is None:continue
 plans+=1
 for p in [world(r.uniform(-half,half),r.uniform(-width,width)) for _ in range(300)]+s.polygons[ch]:
  d=min(math.dist(p,q) for q in plan);assert d<=20+1e-8;maxdistance=max(maxdistance,d);covered+=1
out=dict(dp_vs_exhaustive=checks,dp_max_absolute_error=maxerror,missing_hypothesis_guard=True,generated_rectangles=90,selected_full_cover_plans=plans,sample_coverage_checks=covered,max_sample_distance_m=maxdistance,continuous_guarantee='convex strip partition and full vertex certification; samples are diagnostics only')
(HERE/'results'/(candidate.stem+'_geometry_checks.json')).write_text(json.dumps(out,indent=2)+'\n');print(out)
