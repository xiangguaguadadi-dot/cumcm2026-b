"""Independent residual containment/coverage checks, no solver environment truth access."""
from pathlib import Path
import importlib.util,json,math,random,time,hashlib,argparse
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--out',required=True);a=p.parse_args();path=Path(a.candidate)
spec=importlib.util.spec_from_file_location('residual_test',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
rng=random.Random(998211234);count=0;maxd=0.;fragment_counts=[];t=time.perf_counter()
def inside(p,poly):
 signs=[]
 for u,v in zip(poly,poly[1:]+poly[:1]):
  z=(v[0]-u[0])*(p[1]-u[1])-(v[1]-u[1])*(p[0]-u[0])
  if abs(z)>1e-6:signs.append(z>0)
 return not signs or all(signs) or not any(signs)
for i in range(200):
 l=rng.uniform(40,260);w=rng.uniform(.1,40);poly=[(0,-w/2),(l,-w/2),(l,w/2),(0,w/2)]
 failures=[(rng.uniform(0,l),rng.uniform(-w/2,w/2)) for _ in range(rng.randint(1,3))]
 s=m.ResidualSolver(None,4);s.polygons[1]=poly;s.observations[1]=[((0,0),0)];s.failed_positions[1]=failures;s.position=(l*.4,0)
 components=s.residual_components(1);assert components is not None
 fragment_counts.append(len(components))
 samples=[(l*j/100,-w/2+w*k/20) for j in range(101) for k in range(21)]
 valid=[q for q in samples if all(m.dist(q,c)>20+1e-6 for c in failures)]
 for q in valid:assert any(inside(q,c) for c in components),(i,q)
 for variant in ('residual12','safe_prune'):
  s.config['residual_variant']=variant;points=s.optical_points(1)
  for q in valid:
   d=min(m.dist(q,c) for c in points);maxd=max(maxd,d);assert d<=20+1e-7,(i,variant,q,d)
   count+=1
out=Path(a.out);assert not out.exists();out.write_text(json.dumps(dict(candidate=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),geometries=200,valid_point_checks=count,max_distance=maxd,max_fragments=max(fragment_counts),all_passed=True,wall_seconds=time.perf_counter()-t,boundary='pointwise geometry checks supplement analytic containment; no official task proof'),indent=2));print(out.read_text())
