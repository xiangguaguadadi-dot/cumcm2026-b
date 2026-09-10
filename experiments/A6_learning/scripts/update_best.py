import argparse,hashlib,json
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];ROOT=BASE.parents[1]
p=argparse.ArgumentParser();p.add_argument('--round',type=int,required=True);a=p.parse_args()
bf=BASE/'best.json'
if bf.exists():best=json.loads(bf.read_text())
else:
 best=dict(agent='A6_learning',round=0,rounds_completed=0,solver_path='experiments/A6_learning/snapshots/baseline_solver.py',solver_sha256='36271e5c84cdcd4468b54484d699dce64194f09d78c0c03f3ec1c38f105f6ca9',full_result_path='results/v1_full',means_s_per_source={'3':306.3004342181635,'4':570.8833714439976},complete={'3':1200,'4':1200},code_commit='e7969c3060d134a1a0affdfff41c841040ec810a',code_path_at_commit='solver.py',auxiliary_artifacts={},history=[])
x=json.loads((BASE/f'r{a.round}_full_aggregate.json').read_text())
means={k:v['mean_s'] for k,v in x['modes'].items()}
no_worse=all(means[k]<=best['means_s_per_source'][k]+1e-9 for k in means)
better=any(means[k]<best['means_s_per_source'][k]-1e-9 for k in means)
accepted=x['all_complete'] and no_worse and better
status='improved' if accepted else ('tradeoff' if better and not no_worse else 'not_improved')
history=dict(round=a.round,solver_sha256=x['candidate_sha256'],means_s_per_source=means,all_complete=x['all_complete'],decision=status,previous_best_round=best['round'],previous_best_means=best['means_s_per_source'].copy())
if accepted:
 best.update(round=a.round,solver_path=f'experiments/A6_learning/snapshots/r{a.round}_solver.py',solver_sha256=x['candidate_sha256'],full_result_path=x['result_path'],means_s_per_source=means,complete={k:v['complete'] for k,v in x['modes'].items()},code_commit='PENDING_COMMIT',code_path_at_commit=f'experiments/A6_learning/snapshots/r{a.round}_solver.py')
best['history'].append(history);best['rounds_completed']=a.round
best['auxiliary_artifacts']={'deployment_runtime':'Python standard library only; all learned weights embedded in solver','coverage_points_json':'absent; uses unchanged certified_points','manifest_sha256':hashlib.sha256((ROOT/'evaluation/manifest_v1.json').read_bytes()).hexdigest()}
if best['round']:
 for rel in [f'experiments/A6_learning/training/r{best["round"]}/selected.json',f'experiments/A6_learning/snapshots/r{best["round"]}_metadata.json']:
  best['auxiliary_artifacts'][rel]=hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()
bf.write_text(json.dumps(best,ensure_ascii=False,indent=2)+'\n');print(json.dumps(history,ensure_ascii=False,indent=2))
