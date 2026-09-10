"""Independent geometric check for R8's optical failure outer approximation."""
import sys, math, random, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from solver import outside_disk_hull, convex_hull, dist

def inside(x,poly):
    if not poly:return False
    if len(poly)==1:return dist(x,poly[0])<1e-6
    if len(poly)==2:return abs(dist(x,poly[0])+dist(x,poly[1])-dist(*poly))<1e-6
    return all((b[0]-a[0])*(x[1]-a[1])-(b[1]-a[1])*(x[0]-a[0])>=-1e-5 for a,b in zip(poly,poly[1:]+poly[:1]))

rng=random.Random(831148);checks=0;changed=0
for case in range(1000):
    scale=rng.uniform(8,60)
    poly=convex_hull([(rng.uniform(-scale,scale),rng.uniform(-scale,scale)) for _ in range(12)])
    origin=(rng.uniform(-30,30),rng.uniform(-30,30))
    out=outside_disk_hull(poly,origin,20.0-1e-6)
    changed+=out!=poly
    for _ in range(100):
        weights=[rng.random() for _ in poly];total=sum(weights)
        x=tuple(sum(p[d]*w for p,w in zip(poly,weights))/total for d in [0,1])
        if dist(x,origin)>20:
            assert inside(x,out),(case,x,poly,out);checks+=1
    assert all(inside(v,poly) for v in out)
# The outer hull must retain both ends when the actual remainder disconnects.
line=[(-40.,0.),(40.,0.)]
assert outside_disk_hull(line,(0.,0.),20-1e-6)==line
# With the far end already ruled out, the old failed disk now trims the segment.
out=outside_disk_hull([(-40.,0.),(5.,0.)],(0.,0.),20-1e-6)
assert inside((-21.,0.),out) and not inside((-10.,0.),out)
print(json.dumps({'seed':831148,'random_polygons':1000,'verified_exterior_points':checks,'changed_polygons':changed,'disconnected_and_reapplied_examples':True},indent=2))
