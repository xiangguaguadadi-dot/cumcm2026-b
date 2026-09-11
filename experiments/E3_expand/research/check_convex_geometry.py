"""Synthetic physical checks of the new source exclusion; no candidate tuning."""
from pathlib import Path
import importlib.util,json,random,math
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'experiments/E3_expand'
spec=importlib.util.spec_from_file_location('convex',OUT/'snapshots/r3_development.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
r=random.Random(7193);trials=0;failures=[]
def contains(poly,s):
    if not poly:return False
    cross=[(b[0]-a[0])*(s[1]-a[1])-(b[1]-a[1])*(s[0]-a[0]) for a,b in zip(poly,poly[1:]+poly[:1])]
    return min(cross)>=-1e-6 or max(cross)<=1e-6
for k in range(3000):
    s=(r.uniform(-1600,1600),r.uniform(-1600,1600));radius=r.uniform(1000,1500)
    angle=r.uniform(-math.pi,math.pi);n=(math.cos(angle),math.sin(angle));directional=k%2==1
    def visible(p):return math.dist(s,p)<=radius and (not directional or (p[0]-s[0])*n[0]+(p[1]-s[1])*n[1]>=0)
    def sample(want):
        while True:
            p=(s[0]+r.uniform(-1700,1700),s[1]+r.uniform(-1700,1700))
            if visible(p)==want:return p
    p1,p2,q=sample(True),sample(True),sample(False)
    dx,dy=r.uniform(10,1900),r.uniform(10,1900)
    poly=[(s[0]-dx,s[1]-dy),(s[0]+dx,s[1]-dy),(s[0]+dx,s[1]+dy),(s[0]-dx,s[1]+dy)]
    new=m.exclude_forced_visible_wedge(poly,p1,p2,q);trials+=1
    if not contains(new,s):failures.append(dict(source=s,positive=[p1,p2],negative=q))
assert not failures,failures[:2]
# A deliberately impossible source rectangle is completely deleted.
assert not m.exclude_forced_visible_wedge([(-.2,1.5),(.2,1.5),(.2,2.5),(-.2,2.5)],(-1,0),(1,0),(0,1))
out=dict(random_physical_trials=trials,source_preservation_failures=len(failures),analytic_impossible_rectangle_deleted=True,scope='unit geometry; not 3000 strategy episodes')
(OUT/'research/convex_geometry_checks.json').write_text(json.dumps(out,indent=2));print(out)
