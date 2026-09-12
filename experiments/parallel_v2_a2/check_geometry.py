"""Synthetic coverage and probability checks, never used by a deployed solver."""
import importlib.util,json,math,random
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('hex_check',HERE/'snapshots/hex_r3.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
r=random.Random(9212);checks=0;max_distance=0.
for k in range(48):
 s=m.HexDirectional(None,mode=4,**m.OPTIMIZED_CONFIGS[4]);ch=1
 a=r.uniform(-math.pi,math.pi);u=(math.cos(a),math.sin(a));v=(-u[1],u[0]);center=(r.uniform(-1200,1200),r.uniform(-1200,1200));long=r.uniform(10,300);short=r.uniform(.001,60)
 def world(x,y):return (center[0]+x*u[0]+y*v[0],center[1]+x*u[1]+y*v[1])
 s.polygons[ch]=[world(-long,-short),world(long,-short),world(long,short),world(-long,short)]
 s.observations[ch]=[((0.,0.),math.degrees(a))]
 if k%2:s._e2_failed_clear[ch]=[center]
 for phase,rot in [('anchor',0.),('center',0.),('center',math.pi/6)]:
  points=s._hex_points(ch,phase,rot)
  samples=[world(r.uniform(-long,long),r.uniform(-short,short)) for _ in range(200)]+s.polygons[ch]
  for p in samples:
   if any(math.dist(p,q)<=20 for q in s._e2_failed_clear[ch]):continue
   distance=min(math.dist(p,q) for q in points);assert distance<=20+1e-8,(k,phase,distance)
   max_distance=max(max_distance,distance);checks+=1
# Geometric hex cell itself: each adjacent pair of its six supports meets at R.
R=19.999;h=math.sqrt(3)*R/2;normals=[(math.cos(math.pi/6+k*math.pi/3),math.sin(math.pi/6+k*math.pi/3)) for k in range(6)]
for (a,b),(c,d) in zip(normals,normals[1:]+normals[:1]):
 det=a*d-b*c;p=(h*(d-b)/det,h*(a-c)/det);assert abs(math.hypot(*p)-R)<1e-10
out={'kind':'synthetic geometry checks, not task evaluation','rectangles':48,'lattice_variants':3,'checked_unexcluded_points':checks,'max_sample_distance_m':max_distance,'hex_vertex_radius_m':R,'six_vertices_check':True}
(HERE/'results/geometry_checks.json').write_text(json.dumps(out,indent=2)+'\n');print(out)
