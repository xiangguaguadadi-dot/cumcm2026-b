"""Analytic optical-action cases plus independent feasibility/no-regression checks."""
import sys,math,random,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from solver import Solver,enclosing_circle,dist
s=Solver(None);checks=[]
def check(name,poly,position,expected=None):
 s.position=position;c,r=enclosing_circle(poly);q=s.nearest_certified_clear(poly,c,r)
 assert max(dist(q,v) for v in poly)<=20+1e-8,(name,'containment')
 old=max(0,dist(position,c)-max(0,20-r-1e-6))
 assert dist(q,position)<=old+1e-6,(name,'longer than original standoff')
 if expected:assert dist(q,expected)<2e-6,(name,q,expected)
 checks.append(dict(name=name,position=position,selected=q,radius=r,saved_distance=old-dist(q,position)))
check('single point clear disk',[(0,0)],(100,0),(20,0))
check('segment lens vertical',[(-15,0),(15,0)],(0,100),(0,math.sqrt(175)))
check('segment lens axial',[(-15,0),(15,0)],(-100,0),(-5,0))
check('already feasible',[(-15,0),(15,0)],(0,10),(0,10))
check('almost tangent degenerate',[(-20,0),(20,0)],(100,100),(0,0))
check('dense circular boundary fallback',[(15*math.cos(k*math.pi/64),15*math.sin(k*math.pi/64)) for k in range(128)],(100,0),(5,0))
rng=random.Random(991720)
for k in range(500):
 n=rng.randint(3,10);radius=rng.uniform(.1,19.8);angles=sorted(rng.uniform(-math.pi,math.pi) for _ in range(n))
 poly=[(radius*math.cos(a),radius*math.sin(a)) for a in angles]
 p=(rng.uniform(-100,100),rng.uniform(-100,100));check('random polygon %d'%k,poly,p)
print(json.dumps(dict(passed=len(checks),checks=checks),ensure_ascii=False,indent=2))
