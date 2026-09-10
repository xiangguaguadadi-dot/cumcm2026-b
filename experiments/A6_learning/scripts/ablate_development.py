"""Post-selection mechanism audit on previously exposed DEVELOPMENT data.

Not a new holdout, not candidate selection, never uses fixed v1 rows.
"""
import json,copy,sys,time
from pathlib import Path
from train_policy import load,evaluate
B=Path(__file__).resolve().parents[1];R=B.parents[1]
best=json.loads((B/'best.json').read_text());mod=load(R/best['solver_path'])
case_round=best['round'];cases=json.loads((B/'training'/f'r{case_round}'/'cases.json').read_text())['4']['dev']
full=dict(mod.OPTIMIZED_CONFIGS[4]);variants={'selected':full}
for key,value in full.items():
 if key.startswith('schedule_') and abs(value)>1e-10:
  conf=dict(full);conf[key]=0.;variants['without_'+key]=conf
# Use the actual baseline module: omitting a learned key from config would
# incorrectly inherit that key again from the selected module's defaults.
baseline=load(B/'snapshots/baseline_solver.py')
variants['original_behavior']=dict(baseline.OPTIMIZED_CONFIGS[4])
out=B/'development_ablation';out.mkdir(exist_ok=False)
budget=dict(purpose='post-selection mechanism audit, no parameter selection',data='exposed development from round '+str(case_round),variants=len(variants),episodes_per_variant=len(cases),planned_episodes=len(variants)*len(cases),solver_sha256=best['solver_sha256'])
(out/'budget.json').write_text(json.dumps(budget,ensure_ascii=False,indent=2))
results={};t=time.perf_counter()
for name,conf in variants.items():
 active_module=baseline if name=='original_behavior' else mod
 result=evaluate(active_module,cases,conf);results[name]=dict(config=conf,solver='baseline_solver.py' if name=='original_behavior' else best['solver_path'],**result)
 print(name,result['mean_s'],result['complete'],result['n'],flush=True)
 (out/(name+'.json')).write_text(json.dumps(results[name],ensure_ascii=False,separators=(',',':')))
budget.update(actual_episodes=budget['planned_episodes'],elapsed_seconds=time.perf_counter()-t)
(out/'budget.json').write_text(json.dumps(budget,ensure_ascii=False,indent=2))
(out/'summary.json').write_text(json.dumps({k:{field:value for field,value in v.items() if field!='rows'} for k,v in results.items()},ensure_ascii=False,indent=2))
