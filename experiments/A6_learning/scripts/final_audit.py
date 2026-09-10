"""Final provenance, integrity, budget, and evidence audit (evaluation-side only)."""
import hashlib,json,statistics,subprocess,sys
from pathlib import Path
B=Path(__file__).resolve().parents[1];R=B.parents[1];sys.path.insert(0,str(R))
from evaluate import verify
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
best=json.loads((B/'best.json').read_text());checks={};details={}
verify();checks['frozen_v1_verified']=True
checks['own_branch']=subprocess.check_output(['git','branch','--show-current'],cwd=R,text=True).strip()=='experiments/20260911/a6_learning'
checks['best_snapshot_hash']=sha(R/best['solver_path'])==best['solver_sha256']
checks['root_solver_is_best']=sha(R/'solver.py')==best['solver_sha256']
committed=subprocess.check_output(['git','show',best['code_commit']+':'+best['code_path_at_commit']],cwd=R)
checks['best_committed_bytes_match']=hashlib.sha256(committed).hexdigest()==best['solver_sha256']
for path,h in best['auxiliary_artifacts'].items():
 if path.startswith('experiments/'):checks['aux:'+path]=sha(R/path)==h
rounds=[];train_episodes=0;all_cases=set();train_attempts=0
for hist in best['history']:
 n=hist['round'];summary=json.loads((R/'results'/f'A6_learning_r{n}_full'/'summary.json').read_text())
 rows=json.loads((R/'results'/f'A6_learning_r{n}_full'/'case_metrics.json').read_text());z=[r for r in rows if r['variant']=='candidate']
 checks[f'r{n}_full_hash']=sha(B/'snapshots'/f'r{n}_solver.py')==summary['candidate_sha256']==hist['solver_sha256']
 checks[f'r{n}_complete']=len(z)==2400 and all(r['complete'] and r['error'] is None and r['exit_reason']=='user_exit' for r in z)
 quickdir=R/'results'/f'A6_learning_r{n}_quick'
 quicksummary=json.loads((quickdir/'summary.json').read_text())
 quickrows=json.loads((quickdir/'case_metrics.json').read_text());quickcandidate=[r for r in quickrows if r['variant']=='candidate']
 checks[f'r{n}_quick_hash']=quicksummary['candidate_sha256']==hist['solver_sha256']
 checks[f'r{n}_quick_complete']=len(quickcandidate)==120 and all(r['complete'] and r['error'] is None and r['exit_reason']=='user_exit' for r in quickcandidate)
 checks[f'r{n}_unique_full_ids']=len({r['case_id'] for r in z})==2400
 checks[f'r{n}_quick_subset_full']={r['case_id'] for r in quickcandidate}<={r['case_id'] for r in z}
 if n>=2:
  boundary=json.loads((B/f'r{n}_boundary_audit.json').read_text())
  checks[f'r{n}_boundary_audit']=boundary['all_passed'] and boundary['sha256']==hist['solver_sha256']

 budget=json.loads((B/'training'/f'r{n}'/'budget.json').read_text());sets=json.loads((B/'training'/f'r{n}'/'cases.json').read_text());episode_count=0
 optimized=budget.get('modes_optimized',[3,4])
 for mode in optimized:
  attempts=[json.loads(line) for line in (B/'training'/f'r{n}'/f'q{mode}_attempts.jsonl').read_text().splitlines()]
  dev=json.loads((B/'training'/f'r{n}'/f'q{mode}_development.json').read_text())
  checks[f'r{n}_q{mode}_attempts']=len(attempts)==budget['candidates_per_mode'] and all(len(a['training']['rows'])==budget['train_cases_per_mode'] for a in attempts)
  checks[f'r{n}_q{mode}_dev']=all(len(d['development']['rows'])==budget['dev_cases_per_mode'] for d in dev)
  episode_count+=sum(len(a['training']['rows']) for a in attempts)+sum(len(d['development']['rows']) for d in dev)
  train_attempts+=len(attempts)
  for split in ['train','dev']:
   seeds={c['seed'] for c in sets[str(mode)][split]}
   checks[f'r{n}_q{mode}_{split}_seed_separation']=not(seeds&set(range(5000,5100))) and not(seeds&all_cases)
   all_cases|=seeds
 checks[f'r{n}_budget_count']=episode_count==budget['actual_episodes'];train_episodes+=episode_count
 rounds.append(dict(round=n,complete=sum(r['complete'] for r in z),means={m:statistics.mean(r['average_clear_time_s'] for r in z if r['mode']==int(m)) for m in ['3','4']},decision=hist['decision']))
rows=json.loads((R/best['full_result_path']/'case_metrics.json').read_text());baserows={r['case_id']:r for r in rows if r['variant']=='frozen_baseline'};cand=[r for r in rows if r['variant']=='candidate']
fields=['cleared_count','average_clear_time_s','total_virtual_time_s','requests','distance_m','clear_failures','exit_reason']
equal=sum(all(r[k]==baserows[r['case_id']][k] for k in fields) for r in cand if r['mode']==3)
checks['q3_per_case_original_equal']=equal==1200
for m in ['3','4']:
 checks['best_mean_q'+m]=abs(statistics.mean(r['average_clear_time_s'] for r in cand if r['mode']==int(m))-best['means_s_per_source'][m])<1e-9
lit=json.loads((B/'literature.json').read_text())
checks['literature_counts']=len(lit['papers'])==len(set(p['id'] for p in lit['papers']))==10 and sum(p['tier']=='core' for p in lit['papers'])==4
checks['literature_mappings_resolved']=all(p.get('empirical_support') and '待实际' not in p['empirical_support'] and 'implementation_functions' in p for p in lit['papers'])
for roundid in [3]:
 p=B/'reproduced'/f'r{roundid}'
 if p.exists():
  actual=[json.loads(l) for l in (p/'q4_attempts.jsonl').read_text().splitlines()];original=[json.loads(l) for l in (B/'training'/f'r{roundid}'/'q4_attempts.jsonl').read_text().splitlines()]
  checks[f'replay_r{roundid}_all_attempts']=all(a['parameters']==b['parameters'] and [v['average_s'] for v in a['training']['rows']]==[v['average_s'] for v in b['training']['rows']] for a,b in zip(actual,original)) and len(actual)==len(original)
  checks[f'replay_r{roundid}_cases']=sha(p/'cases.json')==sha(B/'training'/f'r{roundid}'/'cases.json')
extra={}
for key,path in [('replayed_training',B/'reproduced/r3/budget.json'),('development_ablation',B/'development_ablation/budget.json')]:
 if path.exists():extra[key]=json.loads(path.read_text())['actual_episodes']
summary=dict(rounds=len(rounds),full_candidate_episodes=2400*len(rounds),quick_candidate_episodes=120*len(rounds),training_parameter_attempts=train_attempts,training_development_episodes=train_episodes,extra_episode_counts=extra,q3_exactly_matching_baseline_cases=equal,best_round=best['round'],all_checks_passed=all(checks.values()))
streak=0
for h in reversed(best['history']):
 if h['decision']=='improved':break
 streak+=1
summary['consecutive_rounds_without_improvement']=streak
summary['extended_empirical_stop_met']=len(rounds)>=5 and streak>=2
result=dict(summary=summary,checks=checks,rounds=rounds,best_solver_sha256=best['solver_sha256'],best_code_commit=best['code_commit'])
(B/'final_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
if not all(checks.values()):print([k for k,v in checks.items() if not v]);raise SystemExit(1)
