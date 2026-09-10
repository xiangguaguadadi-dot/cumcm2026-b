"""Properties supplement the analytic proof; test truth never enters deployment."""
import sys,pathlib,random,math,json,collections,importlib.util
ROOT=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
p=ROOT/'solver.py';spec=importlib.util.spec_from_file_location('candidate',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
r=random.Random(91004);rows=[]
for case in range(400):
 a=r.uniform(0,2*math.pi);rad=1800*math.sqrt(r.random());target=(rad*math.cos(a),rad*math.sin(a));solver=m.Solver(None,4)
 ch=1;solver.polygons[ch]=m.initial_polygon()
 for i in range(r.randint(1,4)):
  b=r.uniform(0,2*math.pi);d=r.uniform(25,1400);p=(target[0]+d*math.cos(b),target[1]+d*math.sin(b))
  deg=math.degrees(math.atan2(target[1]-p[1],target[0]-p[0]))+r.uniform(-1,1)
  solver.observations[ch].append((p,deg));solver.polygons[ch]=m.add_bearing(solver.polygons[ch],p,deg)
 center,radius=m.enclosing_circle(solver.polygons[ch]);solver.position=center
 points=solver.optical_points(ch);route=solver.optical_route(ch,points)
 length=lambda route:sum(m.dist(a,b) for a,b in zip(route,route[1:]))
 cover=min(m.dist(q,target) for q in points)
 assert cover <= 25/math.sqrt(2)+1e-6
 assert collections.Counter(route)==collections.Counter(points)
 assert length(route)<=2*length(points)+1e-6
 solver.virtual_time=180000;fallback=solver.optical_route(ch,points)
 assert length(fallback)<=length(points)+1e-6
 rows.append(dict(case=case,seed=91004,observations=len(solver.observations[ch]),radius=radius,points=len(points),target_grid_distance=cover,snake_length=length(points),selected_length=length(route),reserved_budget_length=length(fallback)))
out=ROOT/'experiments/A4_directional/results/r3_geometry_properties.json'
if out.exists():raise RuntimeError('Do not overwrite')
out.write_text(json.dumps(dict(cases=400,properties_per_case=4,passed=True,note='Finite generated property check supports implementation only; analytic geometric proof is separate.',rows=rows),indent=2))
print('400 generated geometries x 4 properties passed')
