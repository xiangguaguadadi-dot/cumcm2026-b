"""Independent metric/identity audit and geometric property probes."""
from pathlib import Path
import ast, hashlib, importlib.util, json, math, random, statistics, sys

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'experiments/R2_open'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2))


def history():
 rounds=read(ROOT/'experiments/20260911_agent_campaign/all_rounds.json')['rounds'];result=[]
 for r in rounds:
  p=Path(r['full_path'])/'case_metrics.json';rows=read(p);c=[x for x in rows if x['variant']=='candidate']
  assert sha(p)==r['full_rows_sha256'];assert len(c)==2400==len({x['case_id'] for x in c})
  z=[]
  for mode in (3,4):
   part=[x for x in c if x['mode']==mode];mean=statistics.mean(x['average_clear_time_s'] for x in part)
   expected=next(x['candidate_mean_s_per_source'] for x in r['modes'] if x['mode']==mode)
   assert abs(mean-expected)<1e-10
   z.append(dict(mode=mode,complete=sum(x['complete'] for x in part),cases=len(part),mean=mean,source_count=sum(x['source_count'] for x in part),cleared_count=sum(x['cleared_count'] for x in part)))
  result.append(dict(label=f"{r['agent']}_R{r['round']}",path=str(p),modes=z,sha256=sha(p)))
 stage=read(ROOT/'experiments/20260911_breakthrough/stage_registry.json')['candidates']
 for name,r in stage.items():
  p=ROOT/r['result_dir']/'case_metrics.json';rows=read(p)
  assert len(rows)==4800==len({x['case_id'] for x in rows}) and sha(p)==r['rows_sha256']
  modes=[]
  for mode in (3,4):
   part=[x for x in rows if x['mode']==mode];mean=statistics.mean(x['average_clear_time_s'] for x in part)
   expected=next(x['candidate_mean_s_per_source'] for x in r['aggregates'] if x['mode']==mode and x['group']=='ALL' and x['suite']=='combined')
   assert abs(mean-expected)<1e-10
   modes.append(dict(mode=mode,cases=len(part),complete=sum(x['complete'] for x in part),mean=mean,source_count=sum(x['source_count'] for x in part),cleared_count=sum(x['cleared_count'] for x in part)))
  result.append(dict(label=name,path=str(p),sha256=sha(p),modes=modes))
 assert len(result)==48
 save(OUT/'research/48_rounds_raw_recomputed.json',dict(rounds=result,count=48,boundary='read/recalculation, no new policy execution; 43 old v1 rounds and five B exposed rounds'))


def properties():
 p=OUT/'snapshots/r1_solver.py';spec=importlib.util.spec_from_file_location('r2_r1',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 rng=random.Random(42000999);assert 42000999 not in read(OUT/'research/known_seed_audit.json')['known_seeds']
 count=0;max_vertices=0
 def contains(poly,s):
  assert poly
  if len(poly)<=2:return min(m._sp_dist(s,q) for q in poly)<1e-3
  return all((b[0]-a[0])*(s[1]-a[1])-(b[1]-a[1])*(s[0]-a[0])>=-1e-4*max(1,m._sp_dist(a,b)) for a,b in zip(poly,poly[1:]+poly[:1]))
 for i in range(2000):
  radius=1800*(1.0 if i%5==0 else math.sqrt(rng.random()));angle=rng.uniform(-math.pi,math.pi);s=(radius*math.cos(angle),radius*math.sin(angle));poly=m._sp_initial_polygon()
  for j in range(3):
   angle=rng.uniform(-math.pi,math.pi);d=1500 if i%7==0 else rng.uniform(5.1,1500);p=(s[0]+d*math.cos(angle),s[1]+d*math.sin(angle));bearing=round((math.degrees(angle)+180+(-1 if i%3==0 else 1 if i%3==1 else rng.uniform(-1,1)))%360,2)
   poly=m._geo_add_bearing(poly,p,bearing);assert contains(poly,s);count+=1
  for radius in (1000-1e-6,20-1e-6):
   angle=rng.uniform(-math.pi,math.pi);d=radius+1e-5 if i%4==0 else radius+rng.uniform(.001,200);q=(s[0]+d*math.cos(angle),s[1]+d*math.sin(angle));poly=m._geo_outside_disk_hull(poly,q,radius);assert contains(poly,s);count+=1
  max_vertices=max(max_vertices,len(poly))
 tree=ast.parse((OUT/'snapshots/r1_solver.py').read_text());env_attrs=sorted({n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute) and isinstance(n.value,ast.Attribute) and n.value.attr=='env'})
 assert env_attrs==['clear','enter','exit','measure']
 identifiers={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
 assert not identifiers.intersection({'LocalEnv','Source','case_id','scenario','seed','seed_cluster'})
 save(OUT/'results/r1_geometry_source_audit.json',dict(candidate_sha256=sha(OUT/'snapshots/r1_solver.py'),geometric_seed=42000999,synthetic_geometries=2000,containment_checks=count,max_vertices=max_vertices,env_attributes=env_attrs,forbidden_identifiers_present=[],q4_definitions_equivalent=read(OUT/'research/r1_build_provenance.json')['q4_normalized_ast_equivalence'],boundary='synthetic geometry probes, not complete source-search episodes; finite tests supplement the analytic proof'))


if __name__=='__main__':
 history();properties();print('48 historical round recalculations and 10000 geometry containment checks passed')
