from pathlib import Path
import importlib.util,random,math,json,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT))
p=HERE/'snapshots/r3.py';spec=importlib.util.spec_from_file_location('candidate',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
r=random.Random(96212345);rows=[]
for i in range(240):
 angle=r.random()*math.tau;length=r.uniform(40.01,79.5);width=r.uniform(.001,19.0);u=(math.cos(angle),math.sin(angle));v=(-u[1],u[0]);origin=(r.uniform(-100,100),r.uniform(-100,100))
 poly=[(origin[0]+x*u[0]+y*v[0],origin[1]+x*u[1]+y*v[1]) for x,y in [(-length/2,-width/2),(length/2,-width/2),(length/2,width/2),(-length/2,width/2)]]
 solver=m.TwoDiskSpatial(None,mode=3,**m.OPTIMIZED_CONFIGS[3]);solver.polygons[1]=poly;solver.position=(origin[0]-length*u[0],origin[1]-length*u[1]);plan=solver._two_disk_plan(1)
 checked=0
 if plan:
  for x in range(51):
   for y in range(11):
    t=(origin[0]+(x/50-.5)*length*u[0]+(y/10-.5)*width*v[0],origin[1]+(x/50-.5)*length*u[1]+(y/10-.5)*width*v[1]);assert min(math.dist(t,q) for q in plan)<=20.+1e-8;checked+=1
 rows.append(dict(case=i,plan_found=plan is not None,grid_checks=checked))
result=dict(synthetic_geometries=len(rows),plans=sum(r['plan_found'] for r in rows),checks=sum(r['grid_checks'] for r in rows),passed=True,note='grid is a diagnostic only; correctness proof is exact convex partition + vertex norm checks in candidate')
(HERE/'results/r3_geometry.json').write_text(json.dumps(result,indent=2));print(result)
