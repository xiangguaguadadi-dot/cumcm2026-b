from pathlib import Path
import ast,hashlib,json,random,math,sys,types,time
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'experiments/R3_open';sys.path.insert(0,str(OUT/'research'))
from develop_r5 import load
candidate=OUT/'snapshots/r5_development.py';module=load(candidate)
parent=OUT/'snapshots/r5_parent_R2_component.py'
a=ast.parse(parent.read_text());b=ast.parse(candidate.read_text())
class Map(ast.NodeTransformer):
 def visit_Name(self,node):
  if node.id=='_sp_dist':node.id='_di_dist'
  return node
functions=['_lens_arc_intervals','_lens_route_point'];equal={}
for name in functions:
 x=next(n for n in a.body if isinstance(n,ast.FunctionDef) and n.name==name);y=next(n for n in b.body if isinstance(n,ast.FunctionDef) and n.name==name)
 equal[name]=ast.dump(Map().visit(x),include_attributes=False)==ast.dump(y,include_attributes=False);assert equal[name]
rng=random.Random(9531);stats=[];start=time.perf_counter()
for i in range(1000):
 c0=(rng.uniform(-2000,2000),rng.uniform(-2000,2000));radius=rng.uniform(.001,19.8);count=rng.randrange(3,15)
 ps=[(c0[0]+radius*math.cos(2*math.pi*k/count),c0[1]+radius*math.sin(2*math.pi*k/count)) for k in range(count)]
 c,r=module._di_enclosing_circle(ps);startpoint=(rng.uniform(-2500,2500),rng.uniform(-2500,2500));target=None if i%5==0 else (rng.uniform(-2500,2500),rng.uniform(-2500,2500));dummy=types.SimpleNamespace(position=startpoint,route_successor=target)
 dd=module._di_dist(startpoint,c);margin=max(0,20-r-1e-6);old=startpoint if dd<=margin else (c[0]+margin*(startpoint[0]-c[0])/dd,c[1]+margin*(startpoint[1]-c[1])/dd)
 old=module._di_Solver.route_clear_point(dummy,c,r,old);new=module._lens_route_point(ps,startpoint,target,old);near=module._LensDirectional.nearest_certified_clear(dummy,ps,c,r)
 for q in (old,new,near):assert max(module._di_dist(q,v) for v in ps)<=20+1e-8
 cost=lambda q:module._di_dist(startpoint,q)+(module._di_dist(q,target) if target is not None else 0)
 assert cost(new)<=cost(old)+1e-7
 assert module._di_dist(startpoint,near)<=module._di_dist(startpoint,old)+1e-7
 stats.append(dict(all_vertices_safe=True,proxy_gain_m=cost(old)-cost(new),vertices=count))
result=dict(candidate_sha256=hashlib.sha256(candidate.read_bytes()).hexdigest(),parent_component_sha256=hashlib.sha256(parent.read_bytes()).hexdigest(),mapped_helpers_ast_equal=equal,random_geometry_cases=1000,all_vertices_safe=True,parent_proxy_nonincrease=True,geometry_case_seed=9531,actual_mission_runs=0,wall_s=time.perf_counter()-start,max_proxy_gain_m=max(x['proxy_gain_m'] for x in stats),boundary='Geometric action and fixed-state surrogate checks, not a full online task guarantee.')
(OUT/'results/r5_lens_geometry.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(result)
