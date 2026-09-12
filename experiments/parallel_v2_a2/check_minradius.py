"""Evaluator-only analytic and generated legal half-plane checks."""
import importlib.util,json,math,random
from pathlib import Path
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('mrtest',HERE/'snapshots/minradius_r3.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
r=random.Random(923771);legal=0;cone=0;mincoef=float('inf');maxdistance=0.
# Random legal emitters: a visible p1,p2 and a no-signal q may never rule out s.
for i in range(12000):
 s=(r.uniform(-1800,1800),r.uniform(-1800,1800));theta=r.uniform(-math.pi,math.pi);R=r.uniform(1000,1500)
 def at(a,d):return(s[0]+d*math.cos(a),s[1]+d*math.sin(a))
 p1=at(theta+r.uniform(-math.pi/2,math.pi/2),r.uniform(1,R));p2=at(theta+r.uniform(-math.pi/2,math.pi/2),r.uniform(1,R))
 q=at(theta+math.pi+r.uniform(-math.pi/2+1e-5,math.pi/2-1e-5),r.uniform(0,1600))
 for whole in [False,math.dist(s,q)<999.99]:
  cs=m.minradius_forbidden_constraints(p1,p2,q,whole)
  assert not cs or not all(a*s[0]+b*s[1]<c for a,b,c in cs),(s,p1,p2,q,cs)
  legal+=1
# No signal caused by range alone, even in the emitting half-plane.
range_only=0
for i in range(6000):
 s=(r.uniform(-1800,1800),r.uniform(-1800,1800));theta=r.uniform(-math.pi,math.pi);R=r.uniform(1000,1500)
 def at(a,d):return(s[0]+d*math.cos(a),s[1]+d*math.sin(a))
 p1=at(theta+r.uniform(-math.pi/2,math.pi/2),r.uniform(1,R));p2=at(theta+r.uniform(-math.pi/2,math.pi/2),r.uniform(1,R))
 q=at(theta+r.uniform(-math.pi/2,math.pi/2),R+r.uniform(.001,800))
 cs=m.minradius_forbidden_constraints(p1,p2,q,False)
 assert not cs or not all(a*s[0]+b*s[1]<=c for a,b,c in cs)
 range_only+=1

# Independently check each sampled exclusion point really has q-s in cone(p1-s,p2-s).
for i in range(10000):
 p1=(r.uniform(-1000,1000),r.uniform(-1000,1000));p2=(r.uniform(-1000,1000),r.uniform(-1000,1000));q=(0.,0.);s=(r.uniform(-1000,1000),r.uniform(-1000,1000))
 cs=m.minradius_forbidden_constraints(p1,p2,q,False)
 if not cs or not all(a*s[0]+b*s[1]<=c for a,b,c in cs):continue
 u=(p1[0]-s[0],p1[1]-s[1]);v=(p2[0]-s[0],p2[1]-s[1]);w=(-s[0],-s[1]);det=u[0]*v[1]-u[1]*v[0]
 assert abs(det)>1e-10
 l1=(w[0]*v[1]-w[1]*v[0])/det;l2=(u[0]*w[1]-u[1]*w[0])/det
 assert l1>=0 and l2>=0 and l1+l2>1 and math.hypot(*s)<1000,(l1,l2,s,p1,p2)
 cone+=1;mincoef=min(mincoef,l1,l2);maxdistance=max(maxdistance,math.hypot(*s))
# Necessary boundary caution: source on the positive segment's line survives.
p1,p2,q=(100.,100.),(100.,-100.),(800.,0.)
cs=m.minradius_forbidden_constraints(p1,p2,q,False)
assert all(a*0+b*0<=c for a,b,c in cs)
assert not all(a*100+b*0<=c for a,b,c in cs)
out=dict(legal_halfplane_membership_checks=legal,range_only_no_signal_checks=range_only,random_exclusion_points_with_nonnegative_cone_coefficients=cone,minimum_coefficient=mincoef,max_exclusion_distance=maxdistance,explicit_impossible_example_excluded=True,positive_segment_boundary_preserved=True)
(HERE/'results/minradius_checks.json').write_text(json.dumps(out,indent=2)+'\n');print(out)
