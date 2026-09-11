"""Recompute R1 exposed pairing and prepare durable report without rerunning."""
from pathlib import Path
import hashlib,json,statistics
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'experiments/R3_open'
def read(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=read(OUT/'results/r1_exposed/case_metrics.json')
baseline=read(ROOT/'experiments/20260911_stage3/baseline/expected_rows.json')
index={r['case_id']:r for r in baseline}
assert len(rows)==len({r['case_id'] for r in rows})==4800 and set(index)=={r['case_id'] for r in rows}
assert all(r['complete'] and r['exit_reason']=='user_exit' and not r['error'] and r['cleared_count']==r['source_count'] for r in rows)
summary=read(OUT/'results/r1_exposed/summary.json')
cells=summary['comparisons_to_S0']
for c in cells:
    part=[r for r in rows if r['mode']==c['mode'] and (c['suite']=='combined' or r['exposure_suite']==c['suite']) and (c['group']=='ALL' or r['group']==c['group'])]
    assert c['cases']==len(part)
    assert abs(c['candidate_mean_s_per_source']-statistics.mean(r['average_clear_time_s'] for r in part))<1e-10
regressions=[dict(case_id=r['case_id'],mode=r['mode'],suite=r['exposure_suite'],group=r['group'],source_count=r['source_count'],baseline=index[r['case_id']]['average_clear_time_s'],candidate=r['average_clear_time_s'],delta=r['average_clear_time_s']-index[r['case_id']]['average_clear_time_s']) for r in rows if r['average_clear_time_s']>index[r['case_id']]['average_clear_time_s']+1e-8]
regressions.sort(key=lambda x:x['delta'],reverse=True)
save(OUT/'results/r1_case_regressions.json',regressions)
mode_totals=[c for c in cells if c['suite']=='combined' and c['group']=='ALL']
batch=[c for c in cells if c['suite']!='combined' and c['group']=='ALL']
group_regressions=[c for c in cells if c['suite']!='combined' and c['group']!='ALL' and c['delta_s_per_source']>1e-8]
save(OUT/'results/r1_paired_audit.json',dict(cases=4800,unique_ids=4800,all_complete=True,mode_totals=mode_totals,regressed_batch_scenarios=group_regressions,worst_regressions=regressions[:20],all_78_cells_recomputed=True,rows_sha256=sha(OUT/'results/r1_exposed/case_metrics.json')))
best=dict(round=1,status='accepted_exposed_regression',candidate=str((OUT/'snapshots/r1.py').resolve()),candidate_sha256=sha(OUT/'snapshots/r1.py'),dependencies={},control='S0',results=str((OUT/'results/r1_exposed').resolve()),rows_sha256=sha(OUT/'results/r1_exposed/case_metrics.json'),summary_sha256=sha(OUT/'results/r1_exposed/summary.json'),all_complete=True,mode_totals=mode_totals,data_role='4800 exposed development regressions; not new holdout or official',budget_bound_virtual_s=287931)
save(OUT/'best.json',best)
p=read(OUT/'optimization_path.json');p['nodes'][0].update(status='accepted_exposed_regression',mode_totals=mode_totals,regressed_batch_scenarios=group_regressions,max_regression=regressions[0],decision='Q3 identical, Q4 improved 1.8959209367%; continue next evidence-backed idea')
save(OUT/'optimization_path.json',p)
entries=[]
for split in ('train','development'):
    x=read(OUT/f'results/r1_{split}/budget.json');entries.append(dict(kind=split,actual_runs=x['actual_runs'],unique_cases=x['unique_cases'],wall_seconds=x['wall_s'],seed_range=x['seed_range']))
entries.append(dict(kind='finite_parent_equivalence',actual_runs=48,unique_cases=24,reuses='development'))
for stage in ('quick','full'):
    x=read(OUT/f'results/r1_{stage}/summary.json');entries.append(dict(kind=stage,actual_runs=x['runs'],unique_cases=x['paired_cases'],wall_seconds=x['wall_seconds'],baseline_cached=True))
entries.append(dict(kind='previous_final',actual_runs=summary['new_runs'],unique_cases=2400,wall_seconds=summary['wall_seconds_new_runs'],v1_reuse=True))
save(OUT/'execution_budget.json',dict(runtime='Python 3.12.14',unbounded_iterations=True,actual_runs=sum(e['actual_runs'] for e in entries),unique_training_development_cases=576,unique_exposed_cases=4800,entries=entries,checks=dict(unit_rules=14,nominal_rules=79,exact_certificate_leaves=11200),preflight_failures=[dict(kind='seed regex matched prose recommendation',actual_runs=0)]))
table='|批次|题|S0秒/源|R1秒/源|降幅|快/同/慢|清除源数|\n|---|---|---:|---:|---:|---|---|\n'
for c in mode_totals+batch:table+=f"|{c['suite']}|Q{c['mode']}|{c['baseline_mean_s_per_source']:.9f}|{c['candidate_mean_s_per_source']:.9f}|{100*c['reduction_fraction']:.5f}%|{c['faster']}/{c['equal']}/{c['slower']}|{c['candidate_cleared']}/{c['source_count']}|\n"
groups='|批次|题|场景|S0|R1|差值秒/源|快/同/慢|\n|---|---|---|---:|---:|---:|---|\n'
for c in cells:
    if c['suite']!='combined' and c['group']!='ALL':groups+=f"|{c['suite']}|Q{c['mode']}|{c['group']}|{c['baseline_mean_s_per_source']:.6f}|{c['candidate_mean_s_per_source']:.6f}|{c['delta_s_per_source']:+.6f}|{c['faster']}/{c['equal']}/{c['slower']}|\n"
dev='|配置|训练Q3|训练Q4|开发Q3|开发Q4|\n|---|---:|---:|---:|---:|\n'
t,d=(read(OUT/f'results/r1_{s}/summary.json') for s in ('train','development'))
for name in t:
    vals=[next(g['mean'] for g in z[name]['groups'] if g['mode']==m and g['group']=='ALL') for z in (t,d) for m in (3,4)]
    dev+='|'+name+'|'+ '|'.join(f'{v:.9f}' for v in vals)+'|\n'
text=f'''# R3_open 开放研究报告

2026-09-11。R1已通过4800局完整暴露回归并刷新本路线最佳：Q3与S0逐局相同，Q4由524.827143981降至514.876836277秒/源，改善1.89592%。所有4800局全部清除、正常退出、零异常；每题清除30970/30970个源。不是新留出或官方成绩。

## R1做了什么

S0按题选B1 Q3与B3 Q4，是已知对照。R1在Q4把B1沿途补测与B3原样21个连续认证站合在同一轨迹中；训练/开发进一步比较朴素、可见性与三假说门控。最终Q4单中心预测半径减少乘可见概率达到30米才真实measure；Q3保持B1的60米单中心门控。假想观测只排序，不写入真实多边形。没有把两个父算法历史降幅相加。

原始历史940份文件全字节读取、JSON递归聚合与源码AST检查零错误，304958指标行包含重复和缓存，不能当新增运行或逐轨迹人工复演。报告叙述、文献账本和关键函数单独审阅；旧论文PDF未全部重读。阅读身份见reading_coverage.json。新方向的依据来自历史原始实验和源码结构，未声称复现论文系统。

## 独立训练/开发与组件对照

训练43000000–43000011、开发43001000–43001011；每分割288个完整案例，12场景×12种子×2题。历史结构化记录与源码中的候选种子均无冲突；Q4逐例校验同时有全向、定向。六种配置每分割全部288/288全清，合计3456次执行；训练是方案校准，无学习权重，开发参与选择，均不是留出。

{dev}

可见性门控在这两个新分割均优于朴素融合，支持条件性贡献。三假说、30/60米阈值的排名跨分割变化；训练visibility60最优，开发visibility30最优。按开发最低均值冻结visibility30，完整保存这项选择不稳定性，不能把细小参数差声称稳健理论收益。

## 完整暴露比较

{table}

Q4 {len(regressions)}个单局变慢，最大退步{regressions[0]['delta']:.6f}秒/源，案例{regressions[0]['case_id']}。分批场景均值退步{len(group_regressions)}个，完整行见下表与results/r1_case_regressions.json。均值改善不表示逐局更快。

{groups}

## 可靠性、运行和身份

14项规则、79项正常物理核验、quick120与full2400均通过；同SHA复用full后实跑previous_final2400。11200叶整数连续覆盖证书重新验证通过；移除Q4新增补测时，24个平衡新开发案例与S0的10项任务字段一致（48次实际运行），Q3父源码AST一致。这是有限父行为等价验证，完整回归进一步验证两题。

R1只改变B1的_di_certified_points与默认配置。源码env属性严格只有enter/measure/clear/exit，没有测试ID/seed/scenario读取，部署自包含且仅标准库。统一180000秒切换加跨阈值覆盖、16源有限snake、21站扫描和补测费用，保守合成上界287931秒<360000秒；详细推导research/reliability.md。HTTP未改，没有执行Windows测试。

候选snapshots/r1.py，SHA256 `{best['candidate_sha256']}`。完整比较results/r1_exposed、独立复算results/r1_paired_audit.json。执行预算8424次完整任务，5376个不同案例（576新训练开发+4800暴露）；quick与父等价复用案例不增加独立样本量。各批真实时间见execution_budget.json，不能将历史S0现实时间用于机器加速声称。

## 当前决定与后续

接受R1，立即保存提交。没有达到研究饱和，也没有按固定轮数停止。源码发现Q4尚未使用A1的16个互异频道已发现证书停止额外发现扫描，下一步在新的合法开发数据检验这种结构融合；损失补测机会也可能使它变慢。另有实际测点替代冗余覆盖站的证书方向，仍需按频道的证明和开发。
'''
(OUT/'report.md').write_text(text)
(OUT/'iteration_log.md').write_text('# R3_open 实验记录\n\n## R1\n\n'+table+'\n'+groups)
with (OUT/'optimization_path.md').open('a') as f:f.write('\nR1实验后：4800/4800全清，Q3逐局等同S0；Q4=514.876836277，改善1.89592%。最大退步'+str(regressions[0]['delta'])+'秒/源，单局变慢886。接受R1；继续16已发现频道的调度消融。\n')
(OUT/'resume.md').write_text('# R3_open 接续\n\nR1已完整验证并接受，候选snapshots/r1.py，Q3=238.42647061615037，Q4=514.8768362770995。阅读/开发/规则/全部4800结果、预算与最大退步已保存。下一步R2：Q4已发现16频道时停止多余扫描，比较立即停止及就绪门控，使用新种子。R1之后不能以连续未刷新数自动停。\n')
print(json.dumps(dict(best=best,regressed_batch_scenarios=len(group_regressions),max_regression=regressions[0],actual_runs=sum(e['actual_runs'] for e in entries)),ensure_ascii=False))
