"""Synthetic geometry validation of R10; no fixed regression cases are read."""
import importlib.util,json,math,random,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('a2_r10',Path(__file__).resolve().parent/'candidates/r10_solver.py')
candidate=importlib.util.module_from_spec(spec);spec.loader.exec_module(candidate)
Solver,add_bearing,initial_polygon,dist,clip,EPS=(getattr(candidate,name) for name in ('Solver','add_bearing','initial_polygon','dist','clip','EPS'))

def inside(p,poly):
    return bool(poly) and all((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])>=-1e-5 for a,b in zip(poly,poly[1:]+poly[:1]))

def wedge(poly,q,deg):
    lo,hi=math.radians(deg)-EPS,math.radians(deg)+EPS
    for a,b in [(math.sin(lo),-math.cos(lo)),(-math.sin(hi),math.cos(hi))]:
        poly=clip(poly,a,b,a*q[0]+b*q[1])
    return poly

rng=random.Random(831150);solver=Solver(None,3);changes=0;max_vertices=0
for k in range(1000):
    angle=rng.uniform(0,2*math.pi);rr=1800*math.sqrt(rng.random())
    target=(rr*math.cos(angle),rr*math.sin(angle))
    def observer():
        aa=rng.uniform(0,2*math.pi);dd=rng.uniform(5.01,1500)
        p=(target[0]+dd*math.cos(aa),target[1]+dd*math.sin(aa))
        deg=math.degrees(math.atan2(target[1]-p[1],target[0]-p[0]))+rng.uniform(-1.005,1.005)
        return p,deg
    p,deg=observer();poly=add_bearing(initial_polygon(),p,deg)
    original=poly[:];q,bearing=observer()
    old=wedge(poly,q,bearing);new=solver.predicted_polygon(poly,q,bearing)
    assert poly==original,'Prediction changed authoritative polygon'
    assert inside(target,new),'A legal hypothetical target was removed'
    assert all(inside(v,old) for v in new),'Prediction expanded old wedge'
    for v in new:
        assert all(math.cos(2*math.pi*i/24)*(v[0]-q[0])+math.sin(2*math.pi*i/24)*(v[1]-q[1])<=1500+1e-6 for i in range(24))
    changes+=new!=old;max_vertices=max(max_vertices,len(new))
print(json.dumps({'seed':831150,'synthetic_legal_targets':1000,'all_targets_retained':True,'authoritative_polygons_unchanged':True,'all_new_vertices_in_old_wedge':True,'changed_predictions':changes,'max_prediction_vertices':max_vertices},indent=2))
