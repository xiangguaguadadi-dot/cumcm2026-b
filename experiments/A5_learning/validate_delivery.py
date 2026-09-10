"""Validate delivered hashes, counts, split boundaries, and exact code commits."""
from pathlib import Path
import hashlib,json,subprocess
P=Path(__file__).resolve().parent;ROOT=P.parents[1]
checks=[]
def ck(name,value):
 checks.append(dict(check=name,passed=bool(value)))
 if not value:raise AssertionError(name)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for name in ('report.md','literature.json','plan.md','iteration_log.md','best.json','reproduce.sh'):
 ck('required_'+name,(P/name).is_file())
lit=json.loads((P/'literature.json').read_text());ck('literature_unique',len({x['id'] for x in lit['papers']})==10);ck('core_count',sum(x['layer']=='core' for x in lit['papers'])==5);ck('extended_count',sum(x['layer']=='extended' for x in lit['papers'])==5)
task_runs=0;policy_evals=0;incomplete_trials=0
for n in (1,2,3):
 summary=json.loads((ROOT/f'results/A5_learning_r{n}_full/summary.json').read_text());ck(f'r{n}_full2400',summary['paired_cases']==2400 and summary['all_complete']);ck(f'r{n}_sha',summary['candidate_sha256']==sha(P/f'snapshots/r{n}_solver.py'))
 if n==2:
  paired=json.loads((ROOT/'results/A5_learning_r2_full/case_metrics.json').read_text())
  baseq={x['case_id']:x for x in paired if x['mode']==3 and x['variant']=='frozen_baseline'}
  ck('r2_q3_all_case_virtual_times_identical',all(x['total_virtual_time_s']==baseq[x['case_id']]['total_virtual_time_s'] for x in paired if x['mode']==3 and x['variant']=='candidate'))
 quick=json.loads((ROOT/f'results/A5_learning_r{n}_quick/summary.json').read_text());ck(f'r{n}_quick120',quick['paired_cases']==120 and quick['all_complete'])
 spec=json.loads((P/f'training/r{n}/selected.json').read_text())
 for m in (3,4):
  ds=json.loads((P/f'training/r{n}/cases_m{m}.json').read_text());tr={c['seed'] for c in ds['train']};de={c['seed'] for c in ds['dev']};ck(f'r{n}_m{m}_seed_boundary',not tr&de and min(tr|de)>=700000)
  for case in ds['train']+ds['dev']:
   src=case['sources'];ckname=f'r{n}_m{m}_generated_physics'
   assert 10<=len(src)<=16 and len({s['channel'] for s in src})==len(src)
   assert all(s['x']**2+s['y']**2<=1800**2+1e-7 and 1000<=s['radius']<=1500 for s in src)
   if m==4:assert 1<=sum(s['direction'] is not None for s in src)<len(src)
  rows=[json.loads(x) for x in (P/f'training/r{n}/attempts_m{m}.jsonl').read_text().splitlines()];nr=sum(len(x['rows']) for x in rows);ck(f'r{n}_m{m}_all_attempts_recorded',nr==spec['modes'][str(m)]['total_task_runs']);task_runs+=nr;policy_evals+=len(rows);incomplete_trials+=sum(not x['complete'] for x in rows)
  ck(ckname,True)
best=json.loads((P/'best.json').read_text());ck('root_is_best',sha(ROOT/'solver.py')==best['solver_sha256']);ck('best_round2',best['round']==2 and best['rounds_completed']==3)
for entry in best['non_dominated_candidates']:
 ck(f'r{entry["round"]}_deployment_hash',sha(ROOT/entry['solver_path'])==entry['solver_sha256'])
 if entry.get('code_commit'):
  data=subprocess.check_output(['git','show',entry['code_commit']+':'+entry['solver_path']],cwd=ROOT);ck(f'r{entry["round"]}_exact_commit',hashlib.sha256(data).hexdigest()==entry['solver_sha256'])
 else:ck(f'r{entry["round"]}_exact_commit',False)
result=dict(checks=checks,all_passed=all(x['passed'] for x in checks),training_and_development_policy_evaluations=policy_evals,training_and_development_task_runs=task_runs,additional_timing_runs=12,additional_ablation_runs=288,total_learning_analysis_runs=task_runs+300,incomplete_training_or_dev_policy_evaluations=incomplete_trials,outer_quick_runs=360,outer_full_runs=7200)
(P/'delivery_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False,indent=2))
