from pathlib import Path
import json,hashlib,statistics
P=Path(__file__).resolve().parent;R=P.parents[1]
def load(p):return json.loads(Path(p).read_text())
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def overall(summary,key='comparisons_to_S1'):
 return [r for r in summary[key] if r['suite']=='combined' and r['group']=='ALL']
name='r3_failure_cells';su=load(P/'results'/f'{name}_exposed/summary.json');ss=overall(su);pv=overall(su,'comparisons_to_previous');assert su['all_complete']
best=dict(current=name,candidate=f'experiments/E2_refine/snapshots/{name}.py',sha256=su['candidate_sha256'],deployment_dependencies={},q3_mean_s_per_source=ss[0]['candidate_mean_s_per_source'],q4_mean_s_per_source=ss[1]['candidate_mean_s_per_source'],all_complete=True,result_path=f'experiments/E2_refine/results/{name}_exposed',data_role='4800 exposed local regression; no new final holdout',comparisons_to_S1=ss,comparisons_to_previous=pv,major_component_candidate='r2_one_round',major_component_q4_s_per_source=457.7214998657269,research_status='locally_saturated_after_bounded_R4_optical_unit_contrast')
assert best['sha256']==sha(P/'snapshots'/f'{name}.py');save(P/'best.json',best)
records=[]
for p in sorted((P/'results').glob('*/summary.json')):
 j=load(p)
 if 'comparisons_to_S1' in j and 'new_runs' in j:count=j['new_runs'];role='exposed previous_final after exact-hash v1 reuse'
 elif 'runs' in j:count=j['runs'];role=j['suite']+' exposed regression'
 else:continue
 records.append(dict(path=str(p.relative_to(P)),actual_runs=count,role=role))
for p in sorted((P/'results').glob('*/budget.json')):
 j=load(p);records.append(dict(path=str(p.relative_to(P)),actual_runs=j['actual_runs'],role=j['data_role']))
actual=sum(r['actual_runs'] for r in records);seed=load(P/'used_seeds.json');unique=sum(b['cases'] for b in seed['batches'])
save(P/'execution_budget.json',dict(actual_strategy_executions=actual,distinct_new_development_cases=unique,reused_case_executions=actual-unique,rounds=records,rule_checks='12 existing frozen rule tests each build; five new targeted cell-certificate cases, zero strategy episodes',note='Quick is a full subset; v1 reuse and historical caches are not execution. No fresh final holdout. All actual runs include weak/rejected controls.'))
choices=[('r1_off','S1','rejected_development_quick'),('r1_cost_opportunity','S1','rejected_development_quick'),('r1_cost_all','S1','full_dominated_by_r1_station_only'),('r1_station_only','S1','accepted_R1_major_component'),('r1_station_uncertified','S1','simpler_control_inferior'),('r2_here','r1_station_only','rejected_development_quick'),('r2_one_round','r1_station_only','accepted_R2_major_component'),('r3_failure_hull','r2_one_round','rejected_development_quick'),('r3_failure_cells','r2_one_round','accepted_R3_small_component'),('r4_optical_1','r2_one_round','bounded_development_only_tiny_gain'),('r4_optical_3','r2_one_round','bounded_development_only_tiny_gain')]
nodes=[];edges=[]
for n,parent,status in choices:
 prov=load(P/'snapshots'/f'{n}.provenance.json');nodes.append(dict(id=n,parent=parent,status=status,candidate=prov['candidate'],sha256=prov['sha256'],config=prov['q4_config'],evidence=[str(p.relative_to(R)) for p in sorted((P/'results').glob(n+'_*')) if p.is_dir()]));edges.append({'from':parent,'to':n,'relation':'controlled_component_contrast'})
path=dict(fixed_parent='S1',current=name,research_status=best['research_status'],nodes=nodes,edges=edges);save(P/'optimization_path.json',path)
rows=load(P/'results'/f'{name}_exposed/case_metrics.json');refs=load(P/'results/r2_one_round_exposed/case_metrics.json');index={r['case_id']:r for r in refs};reg=[]
for row in rows:
 b=index[row['case_id']];d=row['average_clear_time_s']-b['average_clear_time_s']
 if d>1e-8:reg.append(dict(case_id=row['case_id'],mode=row['mode'],group=row['group'],delta_s_per_source=d))
reg.sort(key=lambda r:r['delta_s_per_source'],reverse=True);save(P/'results/r3_failure_cells_regressions_to_R2.json',reg)
# Compact comparisons on actually paired development rows, not cross-batch means.
dev=[]
for batch,parent,names in [('r1_development','S1',['r1_off','r1_cost_opportunity','r1_cost_all']),('r1_ablation','S1',['r1_station_only','r1_station_uncertified']),('r2_development','r1_station_only',['r2_here','r2_one_round']),('r3_development','r2_one_round',['r3_failure_hull','r3_failure_cells']),('r4_development','r2_one_round',['r4_optical_1','r4_optical_3'])]:
 base=load(P/'results'/batch/(parent+'_rows.json'));bi={r['case_id']:r for r in base}
 for n in names:
  rr=load(P/'results'/batch/(n+'_rows.json'));assert all(r['complete'] for r in rr);ds=[r['average_clear_time_s']-bi[r['case_id']]['average_clear_time_s'] for r in rr]
  dev.append(dict(batch=batch,name=n,parent=parent,cases=len(rr),mean=statistics.mean(r['average_clear_time_s'] for r in rr),delta=statistics.mean(ds),faster=sum(d<-1e-8 for d in ds),equal=sum(abs(d)<=1e-8 for d in ds),slower=sum(d>1e-8 for d in ds)))
save(P/'results/compact_development_comparisons.json',dev)
full=[]
for n in ['r1_cost_all','r1_station_only','r2_one_round','r3_failure_cells']:
 j=load(P/'results'/f'{n}_exposed/summary.json');a=overall(j);full.append(dict(candidate=n,q3=a[0]['candidate_mean_s_per_source'],q4=a[1]['candidate_mean_s_per_source'],complete=j['all_complete'],reduction=a[1]['reduction_fraction']))
lines=['# E2：费用门控与有限服务单元研究','',f'本轮已收束。当前单独候选为 [{name}](snapshots/{name}.py)，SHA256 `{best["sha256"]}`，单文件可部署，无外部依赖。4800 个已暴露本地案例全部清除：Q3 **{best["q3_mean_s_per_source"]:.9f}**、Q4 **{best["q4_mean_s_per_source"]:.9f} 秒/源**；每题清除 30970 / 30970 个源。主要收益来自 R1 的已知频道重测费用门控与 R2 的持久单轮定位服务。R3 只有很小增益；R4 的有上限对照未发现足以继续扩展的收益。','', '这些是本地研发结果；没有执行官方 Windows 测试，也没有新增最终留出集。完整回归由既有 v1 2400 例和此前已暴露 final 2400 例组成。下表各候选 Q3 的 2400 行均与固定 S1 原样一致。','', '| 候选 | Q3 秒/源 | Q4 秒/源 | Q4 相对固定 S1 | 完成情况 |','|---|---:|---:|---:|---|','| 固定 S1 | 235.876946 | 473.897493 | — | 4800/4800，历史记录复用 |']
for r in full:lines.append(f'| [{r["candidate"]}](results/{r["candidate"]}_exposed/summary.json) | {r["q3"]:.6f} | {r["q4"]:.6f} | -{100*r["reduction"]:.6f}% | 4800/4800 |')
lines+=['','## 实现及作用','', '**R1：检测费是否能够避免后续动作。** 原 S1 在覆盖站会对所有已知未清除频道重测。候选仍完整扫描未知频道并登记原覆盖证据，仅对已知频道，用一次假想正观测后的后续移动、定位、清除费用下降与实际 5–6 秒测向费用比较，决定是否重测。保持原 S1 机会补测；禁用全部补测、仅改机会停点门控、仅跳过已经可清除区域都做了独立对照。no_signal 的预测分支保留整个真实可行区域，未当作 Q4 的范围排除。开发中主要减少非移动费用。','', '**R2：一次调度只做原定位循环的一轮。** 原 localize 要服务同一源至清除或完整兜底，期间不能全局换目标。`ServiceDirectional(CostDirectional)` 提取原循环的动作逻辑，每次执行一轮后返回原全局规划。每频道迭代计数持久保留，第 9 轮后仍进入有限光学覆盖，避免反复选中重置预算。每一轮可能包含实际付费的失败清除、测向和失联恢复序列；没有把这一轮当成一次 API 调用。仍用原第二测点、原恢复点、原完整未知频道覆盖和退出证明。96 个新开发例中，R2 比 R1 少 6.645225 秒/源，其中移动少 6.763856、非移动多 0.118631。4800 回归进一步比 R1 少 9.121182 秒/源。','', '**R3：失败清除后，删除已能证明没有源的光学网格区域。** 第一种对照把失败 20 米圆盘外区域取凸包，开发退步而未晋级。第二种保留所有实际失败圆盘，只在一个网格与当前多边形的完整交集，被某个失败圆盘严格包含时删去该格。判定全部交集顶点距该失败点均小于等于 `20-1e-6`，凭圆盘凸性证明整个区域被排除；从未仅因格中心落在失败圆内就删格。该规则独立于定向天线。Q4 的 no_signal 不产生 1000 米圆排除。原完整光学覆盖覆盖剩余区域，完整退出条件保持。五项针对性几何检查包括“格中心在圆内但远端顶点在圆外时必须保留”，记录见 [检查](results/r3_cell_certificate_checks.json)。','', f'R3 相对 R2：Q4 仅少 {abs(pv[1]["delta_s_per_source"]):.9f} 秒/源（{100*pv[1]["reduction_fraction"]:.6f}%）；{pv[1]["faster"]} 快、{pv[1]["equal"]} 同、{pv[1]["slower"]} 慢。最大单局退步 {reg[0]["delta_s_per_source"]:.9f} 秒/源，详见[完整退步列表](results/r3_failure_cells_regressions_to_R2.json)。这是小型组件收益，不称为新突破。','', '**R4：光学兜底按 1 / 3 次付费 clear 分块。** 基于冻结 R2，建立每频道持久完整格队列，一项仅在实际 clear 返回失败后消耗，下一实际格点进入原全局路径代理；已有新观测只会收紧原区域，原队列继续覆盖真源。到 180000 秒安全切换点，一次完成全部剩余队列。12 条 R2 已存轨迹只有 15 个光学块、49 次 clear，总计 375.476 秒，最长 14 次 clear / 114.017 秒。96 个新开发例中两种分块均只有 1 局改善、95 局逐行相同，平均仅省约 0.015 秒/源；quick120 全清且近乎相同。按有上限的方法对照要求，未追加 full 或参数搜索。未宣称它已经完整 4800 验证。','', '## 全部开发对照','', '每行与同批同案例父候选配对；不同批次均值不能直接作为提升依据。每批是合法混合 Q4，10–16 个不同频道源，至少一个全向和一个定向。R1 的两个批目录共享同 96 个案例，R2–R4 每轮分别新增 96 个。','', '| 变体 | 同批父候选 | 平均秒/源 | 配对变化 | 快 / 同 / 慢 |','|---|---|---:|---:|---|']
for r in dev:lines.append(f'| {r["name"]} | {r["parent"]} | {r["mean"]:.6f} | {r["delta"]:+.6f} | {r["faster"]} / {r["equal"]} / {r["slower"]} |')
lines+=['','## R3 相对 R2 的分场景结果','', '| 场景 | R2 秒/源 | R3 秒/源 | 变化 | 快 / 同 / 慢 |','|---|---:|---:|---:|---|']
for r in su['comparisons_to_previous']:
 if r['suite']=='combined' and r['mode']==4 and r['group']!='ALL':lines.append(f'| {r["group"]} | {r["baseline_mean_s_per_source"]:.6f} | {r["candidate_mean_s_per_source"]:.6f} | {r["delta_s_per_source"]:+.6f} | {r["faster"]} / {r["equal"]} / {r["slower"]} |')
lines+=['','## 预算、范围与停止理由','', f'实际策略执行 **{actual} 次**，其中 **{unique} 个不同新开发案例**；其余为同案例对照或已暴露回归重用案例执行。11 个 quick 各 120 次，4 个晋级候选各实际 4800 次，共 19200 次完整候选执行；开发共 1728 次。已有精确哈希 v1 结果在4800汇总中复用，不重复计为新执行。种子从 45000000 单调登记至 {seed["next_seed"]-1}，下一可用 {seed["next_seed"]}。全部尝试及实际执行路径保存在[预算](execution_budget.json)、[种子账本](used_seeds.json)、[路径图](optimization_path.json)和 results/。', '', '每轮保留 12 项冻结环境规则检查；它们验证规则而非声称证明新策略对所有环境均成功。R3 另有 5 项与几何删格直接相关的检查。关键候选的完整结果、失败行检查与安全证明已足够，没有重审全部历史或追加无关校验。', '', '阅读范围为既有70节点索引、当前 S1 源码、相关早期费用/几何/服务机制、开发中选定的原始轨迹及动作费用；没有新增外部论文全文阅读，也没有将旧论文启发称为论文算法的严格复现。失败圆外凸包复用了已经部署在 Q3 的保守几何函数思想；本次单独验证它在 Q4 的效果，并保留负面结果。', '', '本轮明确比较了补测费用、源服务拆分、失败信息几何形式、光学服务拆分这四类假设。主要增益已经固定；剩余两个尾部方向开发/完整结果只有很小或负收益，继续扫微小参数缺乏证据，因此在本轮范围收束。并不证明全局最优，也不排除后续新机制。E1 的路线融合由协调者独立实测，E2 没有以未经实际部署的代码叠加宣称组合成绩。']
(P/'report.md').write_text('\n'.join(lines)+'\n')
(P/'optimization_path.md').write_text('# E2 迭代路径与状态\n\n四轮已在本次方法范围内收束。固定父候选S1，当前单独最佳r3_failure_cells；主收益组件r1_station_only、r2_one_round。\n\n'+'\n'.join(f'- {n}: parent={p}; {s}' for n,p,s in choices)+'\n\n完整数值、局限与停止理由见[报告](report.md)。R4仅开发+quick；没有冒称full。\n')
(P/'resume.md').write_text(f'''# E2 final continuation\n\nE2 fourth-stage method exploration is complete within its tested scope, not a global optimum. Only write experiments/E2_refine in{R}; branch experiments/20260911-stage4/e2_refine.\n\nCurrent standalone best{name}; SHA{best['sha256']}; all4800 exposed cases complete, Q3{best['q3_mean_s_per_source']}, Q4{best['q4_mean_s_per_source']},30970sources each. R1major code de3d660 and R2major code ae7e512 already pushed. R3small gain -0.057457625 againstR2; R4quota1/3 each only1/96 newcases change, nofull promoted per bounded-search agreement.\n\nAll experiments finished; no live execution sessions. Budget{actual} realstrategy episodes/{unique} distinctnew cases; nextseed{seed['next_seed']}. report/path/best/budget rebuilt from actual results. Need final commit/push R3/R4 evidence and tellroot exact commit/sha; root may combine matured components, do not restart tests. No official/newfinalholdout.\n''')
print('best',best['sha256'],best['q4_mean_s_per_source'],'budget',actual,unique)
