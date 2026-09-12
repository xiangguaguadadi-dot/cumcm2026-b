from pathlib import Path
import json,statistics,hashlib
H=Path(__file__).resolve().parent
rows=[];runs=96;unique=4800+96
for reg in sorted(H.glob('r*_registration.json'),key=lambda p:int(p.name.split('_')[0][1:])):
 d=json.loads(reg.read_text());label=d['round'];row=dict(registration=d,role='development and exposed local regression; no holdout or official run');actual=0
 for stage in ('dev','quick','full','exposed'):
  folder=H/'results'/f'{label}_{stage}'
  if label=='r1' and stage=='quick':folder=H/'results/r1_quick_py312'
  if not (folder/'summary.json').exists():continue
  s=json.loads((folder/'summary.json').read_text());metrics=json.loads((folder/'case_metrics.json').read_text());candidate=[r for r in metrics if r.get('variant')=='candidate'];z=[r for r in candidate if r['mode']==3]
  increment=s.get('new_runs',len(candidate));actual+=increment
  row[stage]=dict(policy_runs_executed=increment,rows=len(candidate),all_complete=all(r['complete'] for r in candidate),q3_mean=statistics.mean(r['average_clear_time_s'] for r in z) if all(r['complete'] for r in z) else None,wall_s=s.get('wall_s',s.get('wall_seconds',s.get('wall_seconds_new_runs'))),summary_sha256=hashlib.sha256((folder/'summary.json').read_bytes()).hexdigest())
  if stage=='exposed':
   comparisons=[r for r in s['comparisons_to_previous'] if r['mode']==3 and r['group']=='ALL'];row['comparisons_to_previous']=comparisons;row['promoted']=row[stage]['all_complete'] and all(r['delta_s_per_source']<0 for r in comparisons if r['suite']!='combined')
 decision=H/(label+'_decision.json')
 if decision.exists():
  row['decision']=json.loads(decision.read_text());row['promoted']=False
 row['actual_policy_runs']=actual;runs+=actual;rows.append(row)
out=dict(direction_status='stopped_after_r9_r10_r11_three_consecutive_non_promotions',selected='r8',role='All optimization/test worlds are exposed once used. No new final holdout or official tests.',rows=rows,valid_policy_runs_executed=runs,development_parent_runs=96,distinct_world_ids=unique,bootstrap_failures=dict(wrong_interpreter='Initial Python 3.9 quick attempted 120 workers; importing frozen environment failed before policy/environment entry. Retained in results/r1_quick; 0 valid policy episodes.',site_bootstrap='Initial Python 3.12 calls lacked -S and printed a stale test .pth error; later calls uniformly use -S -B. No system files modified.'),synthetic_diagnostics='Counted separately from policy worlds in r3_geometry.json and r6_dp_checks.json')
(H/'iteration_ledger.json').write_text(json.dumps(out,indent=2));print([(r['registration']['round'],r.get('exposed',{}).get('q3_mean'),r.get('promoted')) for r in rows]);print('actual policy runs',runs)
