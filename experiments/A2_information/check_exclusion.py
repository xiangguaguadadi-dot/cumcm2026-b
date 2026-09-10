"""Validate convex outer exclusion against independent points of the exact set."""
import sys,math,random,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from solver import outside_disk_hull,convex_hull,dist

def inside(x,p):
 if not p:return False
 if len(p)==1:return dist(x,p[0])<1e-6
 if len(p)==2:return abs(dist(x,p[0])+dist(x,p[1])-dist(*p))<1e-6
 return all((b[0]-a[0])*(x[1]-a[1])-(b[1]-a[1])*(x[0]-a[0])>=-1e-5 for a,b in zip(p,p[1:]+p[:1]))
r=random.Random(831146);tested=0;shrunk=0
for case in range(500):
 poly=convex_hull([(r.uniform(-1800,1800),r.uniform(-1800,1800)) for _ in range(12)])
 origin=(r.uniform(-1500,1500),r.uniform(-1500,1500));out=outside_disk_hull(poly,origin);shrunk+=out!=poly
 for _ in range(100):
  weights=[r.random() for _ in poly];total=sum(weights)
  x=(sum(p[0]*w for p,w in zip(poly,weights))/total,sum(p[1]*w for p,w in zip(poly,weights))/total)
  if dist(x,origin)>=1000:
   assert inside(x,out),(case,x,poly,out);tested+=1
 assert all(inside(v,poly) for v in out)
# A disk strictly inside a square yields a nonconvex remainder whose convex
# outer hull is still the square; never incorrectly clip through the hole.
square=[(-1500.,-1500.),(1500.,-1500.),(1500.,1500.),(-1500.,1500.)]
assert outside_disk_hull(square,(0.,0.))==square
print(json.dumps({'random_polygons':500,'verified_remaining_points':tested,'changed_polygons':shrunk,'nonconvex_hole_case':True},indent=2))
