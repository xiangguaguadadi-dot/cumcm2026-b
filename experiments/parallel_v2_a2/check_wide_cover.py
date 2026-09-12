"""Exercise 9/10-disk plans beyond the old 145 m gate; samples are diagnostic."""
import importlib.util,json,math,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
candidate=Path(sys.argv[1]);sp=importlib.util.spec_from_file_location('wide',candidate);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
records=[]
for half,width in [(145,1),(160,3),(175,3),(179,5),(184,1)]:
 for angle in [0.,.217,1.18,2.34]:
  u=(math.cos(angle),math.sin(angle));v=(-u[1],u[0]);cx,cy=100.,-120.
  def world(x,y):return cx+x*u[0]+y*v[0],cy+x*u[1]+y*v[1]
  s=m.MultiDiskSpatial(None,mode=4,**m.OPTIMIZED_CONFIGS[4]);s.position=world(-half-1,0)
  s.polygons[1]=[world(-half,-width),world(half,-width),world(half,width),world(-half,width)];s.observations[1]=[(world(-half-1,0),math.degrees(angle))]
  plan=s._three_disk_plan(1)
  if plan is None:records.append(dict(half=half,width=width,angle=angle,selected=False));continue
  points=[world(-half+2*half*i/500,-width+2*width*j/10) for i in range(501) for j in range(11)]
  worst=max(min(math.dist(p,q) for q in plan) for p in points)
  assert worst<=20.+1e-8
  records.append(dict(half=half,width=width,angle=angle,selected=True,plan_length=len(plan),diagnostic_points=len(points),max_distance_m=worst))
assert any(r.get('plan_length')==10 for r in records),records
out=dict(candidate=str(candidate),plan_lengths=sorted({r['plan_length'] for r in records if r['selected']}),records=records,note='Whole strip vertex certification establishes continuous coverage; grids only diagnose implementation beyond old gate.')
(HERE/'results'/f'{candidate.stem}_wide_cover_checks.json').write_text(json.dumps(out,indent=2)+'\n');print(out['plan_lengths'],len(records),'cases')
