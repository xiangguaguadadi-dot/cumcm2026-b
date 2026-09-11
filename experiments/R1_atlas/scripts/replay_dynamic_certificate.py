"""Read-only proof replay of frozen R3 diagnostic, using frozen B3 exact verifier; writes only R1 research. No policy inference."""
from pathlib import Path
import json,math,sys,hashlib,time
from fractions import Fraction as F
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT.parent/'R3_open/experiments/R3_open'
sys.path.insert(0,str(ROOT/'experiments/B3/research'))
from certify_geometry import hull,exact_verify
base=json.loads((ROOT/'experiments/B3/research/certificate_21_999_1864.json').read_text());P=base['points']
source=OUT/'results/dynamic_coverage_probe_v3.json';data=json.loads(source.read_text());separations=[];positives=[];start=time.perf_counter()
for case in data['rows']:
 extras=case['extra_arrival_coordinates']
 for ck in case['checks']:
  index=ck['station'];w=ck['separation_witness']
  if w:
   q=tuple(map(F,w['source_xy']));assert q[0]**2+q[1]**2<=1800**2
   angle=w['direction_rad'];normal=(F(math.cos(angle)),F(math.sin(angle)))
   assert normal!=(0,0)
   dots=[];outside=[]
   for p in [p for i,p in enumerate(P) if i!=index]+extras:
    dx,dy=F(p[0])-q[0],F(p[1])-q[1]
    if dx*dx+dy*dy<=1000**2:
     dot=normal[0]*dx+normal[1]*dy;assert dot<0;dots.append(float(dot))
    else:outside.append(float(dx*dx+dy*dy-1000**2))
   separations.append(dict(case_id=case['case_id'],station=index,passed=True,exact_rational_source_in_domain=True,exact_rational_no_receiver_in_closed_emission_halfplane=True,eligible_count=len(dots),max_eligible_dot=max(dots) if dots else None,min_squared_range_exclusion_margin=min(outside) if outside else None,source_xy=w['source_xy'],emission_normal=[float(x) for x in normal]))
  if ck['certified']:
   points=P+extras;leaves=[]
   for d,ix,iy,ids in base['leaves']:
    if ids=='outside' or index not in ids:leaves.append([d,ix,iy,ids]);continue
    side=3600/(2**d);x=-1800+ix*side;y=-1800+iy*side;qs=[(x,y),(x+side,y),(x+side,y+side),(x,y+side)]
    safe=[p for j,p in enumerate(points) if j!=index and max((p[0]-q[0])**2+(p[1]-q[1])**2 for q in qs)<(1000-1e-5)**2]
    poly=hull(safe);leaves.append([d,ix,iy,[points.index(p) for p in poly]])
   assert all(ids=='outside' or index not in ids for _,_,_,ids in leaves)
   proof=exact_verify(dict(points=points,leaves=leaves))
   positives.append(dict(case_id=case['case_id'],station=index,passed=True,proof=proof))
result=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),geometry_cases=len(data['rows']),station_case_pairs=21*len(data['rows']),individually_certified=len(positives),exact_separation_witnesses=len(separations),undecided=21*len(data['rows'])-len(positives)-len(separations),separations=separations,positive_certificates=positives,wall_s=time.perf_counter()-start,actual_runs=0,interpretation='Only relative to augmented full future-trajectory receiver sets. Not an impossibility proof for other future routes or global strategy improvements.')
(ROOT/'experiments/R1_atlas/research/dynamic_probe_replay.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print({k:v for k,v in result.items() if k not in ('separations','positive_certificates')})
