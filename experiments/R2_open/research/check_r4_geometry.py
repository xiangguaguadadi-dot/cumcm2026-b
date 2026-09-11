from pathlib import Path
import importlib.util,json,random,math,hashlib
OUT=Path(__file__).resolve().parents[1];p=OUT/'snapshots/r4_development.py'
spec=importlib.util.spec_from_file_location('r4dev',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
seed=42001999;assert seed not in json.loads((OUT/'research/known_seed_audit.json').read_text())['known_seeds'];rng=random.Random(seed)
results=[]
for i in range(1000):
 angle=rng.uniform(-math.pi,math.pi);rr=rng.uniform(.01,19.99);origin=(rng.uniform(-1750,1750),rng.uniform(-1750,1750))
 points=[(origin[0]+rr*math.sqrt(rng.random())*math.cos(a),origin[1]+rr*math.sqrt(rng.random())*math.sin(a)) for a in [rng.uniform(-math.pi,math.pi) for _ in range(rng.randint(3,35))]]
 poly=m._geo_convex_hull(points);c,r=m._sp_enclosing_circle(poly);assert r<20
 start=c if i%17==0 else (c[0]+rng.uniform(-300,300),c[1]+rng.uniform(-300,300));target=None if i%7==0 else (c[0]+rng.uniform(-300,300),c[1]+rng.uniform(-300,300))
 d=m._sp_dist(start,c);margin=max(0.,20.-r-1e-6);original=start if d<=margin else (c[0]+margin*(start[0]-c[0])/d,c[1]+margin*(start[1]-c[1])/d)
 parent=object.__new__(m._sp_Solver);parent.position=start;parent.route_successor=target
 fallback=parent.route_clear_point(c,r,original);q=m._lens_route_point(poly,start,target,fallback)
 cost=lambda q:m._sp_dist(start,q)+(m._sp_dist(q,target) if target is not None else 0.)
 assert all(m._sp_dist(q,v)<=20.+1e-8 for v in poly)
 assert cost(q)<=cost(fallback)+1e-7
 # Independently draw convex combinations of true feasible polygon vertices.
 for _ in range(5):
  weights=[rng.random() for _ in poly];total=sum(weights);x=tuple(sum(w*v[d] for w,v in zip(weights,poly))/total for d in (0,1));assert m._sp_dist(q,x)<=20.+1e-8
 results.append(dict(vertices=len(poly),radius=r,margin=20-max(m._sp_dist(q,v) for v in poly),proxy_gain_m=cost(fallback)-cost(q)))
output=dict(seed=seed,synthetic_regions=1000,convex_combination_containment_checks=5000,candidate_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),max_vertices=max(x['vertices'] for x in results),minimum_safety_margin=min(x['margin'] for x in results),mean_proxy_gain_m=sum(x['proxy_gain_m'] for x in results)/len(results),all_contained=True,all_fixed_state_proxy_nonworse=True,boundary='Finite geometry probes support implementation; convexity argument certifies continuous containment. No task episodes or source-placement prior claim.',rows=results)
(OUT/'results/r4_geometry.json').write_text(json.dumps(output,indent=2));print({k:v for k,v in output.items() if k!='rows'})
