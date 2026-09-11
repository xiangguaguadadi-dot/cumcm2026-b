from pathlib import Path
import json,hashlib,time,sys
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'experiments/B1';sys.path.insert(0,str(OUT/'research'))
from develop import load,run_case
p=OUT/'snapshots/r1_development.py';s=p.read_text()
s=s.replace("3:dict(_sp_OPTIMIZED_CONFIGS[3],sharing_style='naive',sharing_gain_m=30.)","3:dict(_sp_OPTIMIZED_CONFIGS[3],sharing_style='visibility',sharing_gain_m=60.)")
s=s.replace("4:dict(_di_OPTIMIZED_CONFIGS[4],sharing_style='visibility',sharing_gain_m=30.)","4:dict(_di_OPTIMIZED_CONFIGS[4],sharing_style='quadrature',sharing_gain_m=60.)")
final=OUT/'snapshots/r1_solver.py';final.write_text(s)
# Exclude introduced namespace errors with actual task replay on balanced legal
# cases. Exact parent rows were already run in the training study.
cases=json.loads((OUT/'results/r1_train/cases.json').read_text());cases=[c for c in cases if c['seed']==3101000]
bases={r['case_id']:r for r in json.loads((OUT/'results/r1_train/C0_rows.json').read_text())}
m=load(final);checks=[];keys=['complete','exit_reason','error','average_clear_time_s','total_virtual_time_s','distance_m','requests','clear_failures']
for c in cases:
 r=run_case(m,c,{'sharing_style':'off'});b=bases[c['case_id']]
 checks.append(dict(case_id=c['case_id'],equal=all(r[k]==b[k] for k in keys),keys=keys,actual=r,reference=b))
assert all(c['equal'] for c in checks)
(OUT/'results/r1_parent_equivalence.json').write_text(json.dumps(dict(actual_runs=len(checks),all_equal=True,checks=checks),ensure_ascii=False,indent=2))
path=OUT/'optimization_path.json';data=json.loads(path.read_text());step=data['steps'][0]
step.update(status='frozen_before_regression',candidate=str(final.relative_to(ROOT)),candidate_sha256=hashlib.sha256(final.read_bytes()).hexdigest(),development_result='2016/2016 complete. Q3 visibility60 selected; Q4 quadrature60 selected by minimum independent-development mean. Three-hypothesis Q3 versions slower; retained as negative results.',frozen_time=time.strftime('%Y-%m-%dT%H:%M:%S%z'),selection={'3':'visibility60','4':'quadrature60'},actual_development_runs=2016,parent_equivalence_runs=24,regression_status='not_started')
path.write_text(json.dumps(data,ensure_ascii=False,indent=2))
with (OUT/'optimization_path.md').open('a') as f:f.write('''\n## R1 · 开发后冻结\n\n训练和开发共2016/2016局全清。独立开发Q3：C0 286.4731、朴素30米门槛251.5779、60米门槛250.8742；Q4：C0 574.0640、朴素566.9913、可见性560.4972、三假说60米门槛560.3975。据开发均值选Q3 visibility60、Q4 quadrature60，保留其余完整负结果；Q4三假说相对visibility60仅快0.0602秒/源，不能夸大稳健性。\n\n[训练全部结果](results/r1_train/summary.json) · [开发全部结果](results/r1_development/summary.json) · [冻结R1](snapshots/r1_solver.py)。关闭补测的命名空间重构在24个平衡合法任务上与精确C0全部任务字段相同，见[parent_equivalence](results/r1_parent_equivalence.json)。冻结后才开始规则、quick、full与4800暴露复核。\n''')
print(final,step['candidate_sha256'])
