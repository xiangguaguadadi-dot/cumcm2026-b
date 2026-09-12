"""Independent raw-row comparisons and truthful execution ledger for this branch."""
import csv,hashlib,json,statistics
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
B=HERE/'reference/results'
refs={'base':{'quick':B/'best_r2_packaging_quick','full':B/'best_r2_packaging_full','exposed':B/'r2_exposed'}}
parents={**{f'route_r{i}':'base' for i in range(1,4)},**{f'visibility_r{i}':'base' for i in range(1,4)},'hex_r1':'base','hex_r2':'base','hex_r3':'hex_r2',**{f'hex_r{i}':'hex_r3' for i in (4,5,6)},**{f'hex_r{i}':'hex_r6' for i in (7,8,9)},**{f'minradius_r{i}':'hex_r3' for i in range(1,4)},**{f'finite_r{i}':'hex_r6' for i in (1,2,3)},'finite_r3_guarded':'finite_r3',**{f'finite_r{i}':'finite_r3_guarded' for i in (4,5,6)},**{f'finite_r{i}':'finite_r6' for i in (7,8,9)}}
parents.update({f'finite_r{i}':'finite_r7' for i in (10,11,12)})
def loadrows(folder):
 rows=read(folder/'case_metrics.json')
 if any(r.get('variant')=='frozen_baseline' for r in rows):rows=[r for r in rows if r['variant']=='candidate']
 assert len(rows)==len({r['case_id'] for r in rows})
 for r in rows:
  if r['complete']:
   assert r['error'] is None and r['exit_reason']=='user_exit' and r['cleared_count']==r['source_count']
   assert abs(r['total_virtual_time_s']/r['cleared_count']-r['average_clear_time_s'])<1e-8
 return rows
records=[];summary=[]
for name,parent in parents.items():
 path=HERE/'snapshots'/f'{name}.py'
 if not path.exists():continue
 item={'candidate':name,'parent':parent,'sha256':sha(path),'stages':{},'ledger_role':'post-execution audit, not claimed preregistration'}
 for stage in ['quick','full','exposed']:
  folder=HERE/'results'/f'{name}_{stage}'
  if name=='route_r1' and stage=='quick':folder=HERE/'results/route_r1_quick312'
  if not (folder/'case_metrics.json').exists():continue
  ref=refs['base'][stage] if parent=='base' else HERE/'results'/f'{parent}_{stage}'
  if not (ref/'case_metrics.json').exists() and parent=='finite_r3_guarded':ref=HERE/'results'/f'finite_r3_{stage}'
  if not (ref/'case_metrics.json').exists():continue
  rows=loadrows(folder);base=loadrows(ref);indexed={r['case_id']:r for r in base}
  assert set(indexed)=={r['case_id'] for r in rows}
  assert all((r['mode'],r['group'],r['source_count'],r.get('exposure_suite'))==(indexed[r['case_id']]['mode'],indexed[r['case_id']]['group'],indexed[r['case_id']]['source_count'],indexed[r['case_id']].get('exposure_suite')) for r in rows)
  outcomes=[]
  for mode in [3,4]:
   scopes=['combined','v1','previous_final'] if stage=='exposed' else [stage]
   for scope in scopes:
    selected=[r for r in rows if r['mode']==mode and (stage!='exposed' or scope=='combined' or r['exposure_suite']==scope)]
    for group in ['ALL']+sorted({r['group'] for r in selected}):
     part=[r for r in selected if group=='ALL' or r['group']==group];br=[indexed[r['case_id']] for r in part]
     valid=all(r['complete'] and b['complete'] for r,b in zip(part,br))
     rec=dict(candidate=name,parent=parent,stage=stage,scope=scope,mode=mode,group=group,cases=len(part),all_complete=valid,cleared=sum(r.get('cleared_count') or 0 for r in part),sources=sum(r['source_count'] for r in part),errors=sum(bool(r['error']) for r in part))
     if valid:
      ds=[r['average_clear_time_s']-b['average_clear_time_s'] for r,b in zip(part,br)];mean=statistics.mean(r['average_clear_time_s'] for r in part);bmean=statistics.mean(r['average_clear_time_s'] for r in br)
      worst=max(range(len(ds)),key=lambda i:ds[i]);best=min(range(len(ds)),key=lambda i:ds[i])
      rec.update(mean_s_per_source=mean,parent_mean_s_per_source=bmean,delta=mean-bmean,reduction_pct=100*(1-mean/bmean),faster=sum(d<-1e-8 for d in ds),equal=sum(abs(d)<=1e-8 for d in ds),slower=sum(d>1e-8 for d in ds),requests=sum(r['requests'] for r in part),clear_failures=sum(r['clear_failures'] for r in part),movement_s_per_source=statistics.mean(r['distance_m']/5/r['source_count'] for r in part),largest_regression_id=part[worst]['case_id'],largest_regression_delta=ds[worst],largest_improvement_id=part[best]['case_id'],largest_improvement_delta=ds[best])
     records.append(rec)
     if group=='ALL':outcomes.append(rec)
  meta=read(folder/'summary.json');item['stages'][stage]=dict(rows_sha256=sha(folder/'case_metrics.json'),candidate_sha256=meta['candidate_sha256'],wall_s=meta.get('wall_seconds',meta.get('wall_seconds_new_runs')),runs=meta.get('runs',meta.get('new_runs')),outcomes=outcomes)
  assert meta['candidate_sha256']==sha(path)
 summary.append(item)
(HERE/'iteration_ledger.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
(HERE/'raw_row_audit.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
small=[r for r in records if r['mode']==4 and r['group']=='ALL']
fields=['candidate','parent','stage','scope','cases','all_complete','mean_s_per_source','parent_mean_s_per_source','delta','faster','equal','slower']
with (HERE/'round_summary.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(small)
print('candidates',len(summary),'comparisons',len(records),'stage_runs',sum(v['runs'] for r in summary for v in r['stages'].values()))
for r in small:
 if r['stage']=='exposed' and r['scope']=='combined':print(r['candidate'],r['mean_s_per_source'],r['delta'])
