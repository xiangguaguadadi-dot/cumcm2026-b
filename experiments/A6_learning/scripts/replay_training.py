"""Reproduce a training round in a disposable sandbox without overwriting records."""
import argparse,json,shutil,subprocess,sys,tempfile
from pathlib import Path
B=Path(__file__).resolve().parents[1];R=B.parents[1]
p=argparse.ArgumentParser();p.add_argument('--round',type=int,required=True);p.add_argument('--out',required=True);a=p.parse_args()
output=Path(a.out).resolve()
if output.exists():raise SystemExit('Output already exists; choose a new directory')
budget=json.loads((B/'training'/f'r{a.round}'/'budget.json').read_text())
architecture=B/'snapshots'/('baseline_solver.py' if a.round==1 else f'r{a.round}_training_architecture.py')
trainer=B/'scripts'/('train_policy_r1_r2.py' if a.round<=2 else 'train_policy.py')
with tempfile.TemporaryDirectory(prefix='a6_replay_') as temp:
 root=Path(temp);dest=root/'experiments'/'A6_learning'/'scripts';dest.mkdir(parents=True)
 (dest.parent/'training').mkdir()
 shutil.copy2(R/'local_env.py',root/'local_env.py');shutil.copy2(architecture,root/'solver.py');shutil.copy2(trainer,dest/'train_policy.py')
 cmd=[sys.executable,str(dest/'train_policy.py'),'--round',str(a.round),'--attempts',str(budget['candidates_per_mode']),'--train-cases',str(budget['train_cases_per_mode']),'--dev-cases',str(budget['dev_cases_per_mode']),'--shortlist',str(budget['shortlist'])]
 if a.round>=3:cmd+=['--modes',','.join(map(str,budget['modes_optimized'])),'--minimum-dev-reduction',str(budget['minimum_dev_reduction'])]
 result=subprocess.run(cmd,cwd=root,check=True)
 output.parent.mkdir(parents=True,exist_ok=True)
 shutil.copytree(root/'experiments'/'A6_learning'/'training'/f'r{a.round}',output)
 actual=json.loads((output/'selected.json').read_text());expected=json.loads((B/'training'/f'r{a.round}'/'selected.json').read_text())
 comparison={k:actual[k]['config']==expected[k]['config'] for k in expected}
 (output/'replay_comparison.json').write_text(json.dumps(comparison,indent=2))
 print('Selected configurations match original:',comparison)
 if not all(comparison.values()):raise SystemExit(1)
