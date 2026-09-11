"""Small, explicitly scoped raw-trajectory diagnosis of saved R1 development."""
from pathlib import Path
import json,math,collections
HERE=Path(__file__).resolve().parent
FOLDER=HERE/'results/r1_development'
report={}
for variant in ['S1','r1_cost_all']:
 files=sorted(FOLDER.glob(variant+'__*_trace.json'));counts=collections.Counter();seconds=collections.Counter();radii=[]
 for path in files:
  j=json.loads(path.read_text());prev=(0.,0.);prevtime=0.;positives=set();failed_points={}
  for row in j['trace']:
   p=(row['x'],row['y']);contexts=row.get('context',[])
   if 'share_observations' in contexts:tag='opportunity'
   elif 'cover_polygon' in contexts:tag='optical_fallback'
   elif 'rescue_bearing' in contexts:tag='rf_recovery'
   elif 'scan_station' in contexts:tag='station_known' if row['channel'] in positives else 'station_discovery'
   else:tag='target_service'
   counts[(tag,row['action'],row['result'])]+=1
   seconds[(tag,'movement')]+=math.dist(prev,p)/5.
   seconds[(tag,'nonmovement')]+=row['virtual_time_s']-prevtime-math.dist(prev,p)/5.
   if row['action']=='measure' and row['result'] in ('direction','near'):positives.add(row['channel'])
   if row['action']=='clear' and row['result']=='no_target_in_range':
    old=failed_points.setdefault(row['channel'],[])
    if any(math.dist(p,q)<1e-6 for q in old):counts[('repeated_failed_clear','clear','same_location')]+=1
    old.append(p)
   prev=p;prevtime=row['virtual_time_s']
 report[variant]=dict(raw_trajectories_read=len(files),paths=[str(p.relative_to(HERE)) for p in files],
  action_counts={'/'.join(k):v for k,v in sorted(counts.items())},
  virtual_seconds={'/'.join(k):v for k,v in sorted(seconds.items())})
(HERE/'results/r1_trace_diagnosis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
for name,r in report.items():
 print(name,'trajectories',r['raw_trajectories_read']);print(r['action_counts']);print(r['virtual_seconds'])
