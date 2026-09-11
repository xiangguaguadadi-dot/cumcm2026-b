"""Optimistic saved-trajectory diagnostic, not a deployable strategy or speed result.
Every extra arrival is hypothetically available for every unknown channel,
without paying for scans. Check one-station deletion at a time on existing
continuous leaves; a failed sufficient certificate is not an impossibility proof.
"""
from pathlib import Path
import json,sys,time,math,hashlib
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'experiments/R3_open'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(OUT/'research'));sys.path.insert(0,str(ROOT/'experiments/B3/research'))
from develop_r3 import load
from local_env import LocalEnv,Source,InterfaceOnly
from certify_geometry import hull
PFILE=ROOT/'experiments/B3/research/certificate_21_999_1864.json'; cert=json.loads(PFILE.read_text());P=cert['points']
leaves=[]
for d,ix,iy,ids in cert['leaves']:
 if ids=='outside':continue
 size=3600/(2**d);x=-1800+ix*size;y=-1800+iy*size
 corners=[(x,y),(x+size,y),(x+size,y+size),(x,y+size)]
 leaves.append((corners,ids))
def inside(poly,qs):
 return len(poly)>=3 and all((b[0]-a[0])*(q[1]-a[1])-(b[1]-a[1])*(q[0]-a[0])>=1e-5 for a,b in zip(poly,poly[1:]+poly[:1]) for q in qs)
def remove_one(index,extras):
 checked=0
 for qs,ids in leaves:
  if index not in ids:continue
  checked+=1
  # Recompute all old eligible stations, including former interior points.
  safe=[p for i,p in enumerate(P) if i!=index and max((p[0]-q[0])**2+(p[1]-q[1])**2 for q in qs)<(1000-1e-5)**2]
  safe += [p for p in extras if max((p[0]-q[0])**2+(p[1]-q[1])**2 for q in qs)<(1000-1e-5)**2]
  if not inside(hull(safe),qs):return dict(certified=False,checked_leaves=checked,failed_square=qs)
 return dict(certified=True,checked_leaves=checked)
def separation_witness(index,extras,square):
 allpoints=[p for i,p in enumerate(P) if i!=index]+extras
 x0,y0=square[0];x1,y1=square[2]
 for ix in range(5):
  for iy in range(5):
   q=(x0+(x1-x0)*ix/4,y0+(y1-y0)*iy/4)
   if math.hypot(*q)>1800-1e-7:continue
   near=[p for p in allpoints if math.hypot(p[0]-q[0],p[1]-q[1])<=1000+1e-7]
   if not near:return dict(source_xy=q,radius_m=1000,direction_rad=0.,receiver_count=0,max_forward_dot=None,min_excluded_distance_m=min(math.hypot(p[0]-q[0],p[1]-q[1]) for p in allpoints))
   angles=sorted(math.atan2(p[1]-q[1],p[0]-q[0]) for p in near)
   gaps=[(angles[(i+1)%len(angles)]+(2*math.pi if i+1==len(angles) else 0)-a,a) for i,a in enumerate(angles)]
   width,left=max(gaps)
   if width<=math.pi+1e-8:continue
   angle=left+width/2;n=(math.cos(angle),math.sin(angle));dot=max(n[0]*(p[0]-q[0])+n[1]*(p[1]-q[1]) for p in near)
   if dot>=-1e-7:continue
   far=[math.hypot(p[0]-q[0],p[1]-q[1]) for p in allpoints if math.hypot(p[0]-q[0],p[1]-q[1])>1000+1e-7]
   return dict(source_xy=q,radius_m=1000,direction_rad=angle,receiver_count=len(near),max_forward_dot=dot,max_angular_gap_rad=width,min_excluded_distance_m=min(far) if far else None)
 return None

cases=json.loads((OUT/'results/r3_development/cases.json').read_text());groups=sorted({c['group'] for c in cases});cases=[next(c for c in cases if c['mode']==4 and c['group']==g) for g in groups]
module=load(OUT/'snapshots/r3.py');rows=[];start=time.perf_counter()
for case in cases:
 env=LocalEnv([Source(**s) for s in case['sources']],case['seed'],case['noise'],keep_log=False); solver=module.Solver(InterfaceOnly(env),mode=4);result=solver.run()
 assert len(solver.cleared)==len(case['sources']) and env.exit_reason=='user_exit'
 extra=sorted({(r['x'],r['y']) for r in solver.trace if all(math.hypot(r['x']-p[0],r['y']-p[1])>1e-5 for p in P)})
 checks=[dict(station=i,radius_m=math.hypot(*P[i]),**remove_one(i,extra)) for i in range(len(P))]
 for ck in checks:
  ck['separation_witness']=None if ck['certified'] else separation_witness(ck['station'],extra,ck['failed_square'])
 rows.append(dict(case_id=case['case_id'],mode=4,group=case['group'],seed=case['seed'],actual_complete=True,extra_arrivals=len(extra),extra_arrival_coordinates=extra,individual_removals_certified=[x['station'] for x in checks if x['certified']],checks=checks))
 print(case['group'],len(extra),rows[-1]['individual_removals_certified'],'witnesses',sum(c['separation_witness'] is not None for c in checks),flush=True)
result=dict(label='optimistic continuous-leaf certificate diagnostic; not efficiency comparison',candidate_sha256=hashlib.sha256((OUT/'snapshots/r3.py').read_bytes()).hexdigest(),certificate_sha256=hashlib.sha256(PFILE.read_bytes()).hexdigest(),data_role='12 reused seen development Q4 cases',actual_runs=len(cases),new_unique_cases=0,assumptions=['Every extra arrival from the completed R3 trajectory can be used for all unknown channels at zero sensing cost.','Future arrival locations and their dependence on the original station are ignored.','Each station deletion is checked separately, never a simultaneous-deletion guarantee.','Floating conservative checks test a sufficient certificate on fixed old leaves; acceptance would still require exact runtime or static proof.'],rows=rows,wall_s=time.perf_counter()-start)
(OUT/'results/dynamic_coverage_probe_v3.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
