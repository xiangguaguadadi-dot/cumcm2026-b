"""Post-selection component ablation on R2 DEV only; never used for selection."""
import json
from pathlib import Path
from train_policy import load_solver,run_config
P=Path(__file__).resolve().parent
mod=load_solver(P/'snapshots/r2_solver.py');baseline=load_solver(P/'snapshots/r0_solver.py')
x=json.loads((P/'training/r2/selected.json').read_text());selected=x['modes']['4']['config'];cases=json.loads((P/'training/r2/cases_m4.json').read_text())['dev']
context=['priority_uncertainty','priority_pending','source_uncertainty_cost']
policies={'static_only':{**selected,**{k:0. for k in context}},'context_only':{**baseline.OPTIMIZED_CONFIGS[4],**{k:selected[k] for k in context}}}
result=dict(note='Post-selection analysis on development data; 2 additional policy evaluations x 144 episodes; no fixed-v1 replay and no candidate selection.',new_evaluations=2,new_task_runs=288,baseline_dev=x['modes']['4']['baseline_dev_mean_s_per_source'],full_policy_dev=x['modes']['4']['dev_mean_s_per_source'],variants={})
for name,config in policies.items():
 result['variants'][name]=dict(config=config,**run_config(mod,4,config,cases));print(name,result['variants'][name]['mean_s_per_source'],flush=True)
(P/'ablation_r2_dev.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
