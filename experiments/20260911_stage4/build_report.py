"""Build the final stage-four readout from already completed local runs."""
import hashlib,importlib.util,json,statistics,subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def read(p):return json.loads(p.read_text())
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p):return str(p.relative_to(HERE)) if p.is_relative_to(HERE) else '../'+str(p.relative_to(ROOT/'experiments'))

def main():
    spec=importlib.util.spec_from_file_location('stage4_compare',HERE/'evaluate_exposed.py')
    compare=importlib.util.module_from_spec(spec);spec.loader.exec_module(compare)
    definitions=[
      ('E1_R1','E1_refine/snapshots/r1_posterior.py','E1_refine/results/r1_exposed','条件发现路线'),
      ('E1_R5','E1_refine/snapshots/r5_immediate_block.py','E1_refine/results/r5_exposed','立即服务入口费用'),
      ('E2_R1_all','E2_refine/snapshots/r1_cost_all.py','E2_refine/results/r1_cost_all_exposed','全部补测费用门控'),
      ('E2_R1_station','E2_refine/snapshots/r1_station_only.py','E2_refine/results/r1_station_only_exposed','只对站内已知频道门控'),
      ('E2_R2','E2_refine/snapshots/r2_one_round.py','E2_refine/results/r2_one_round_exposed','持久单轮定位服务'),
      ('E2_R3','E2_refine/snapshots/r3_failure_cells.py','E2_refine/results/r3_failure_cells_exposed','认证删除失败清除网格'),
      ('E3_R1','E3_expand/snapshots/r1.py','E3_expand/results/r1_exposed','付费共享未知源初始化'),
      ('E3_R3','E3_expand/snapshots/r3.py','E3_expand/results/r3_exposed','凸接收域无信号楔约束'),
      ('C1','20260911_stage4/combination/snapshots/C1_combined.py','20260911_stage4/combination/results/c1_exposed','条件路线+站内门控'),
      ('C2','20260911_stage4/combination/service_fusions/C2_conditional_round.py','20260911_stage4/combination/results/c2_exposed','C1+持久单轮服务'),
      ('C7','20260911_stage4/combination/geometry_fusions/C7_both.py','20260911_stage4/combination/results/c7_exposed','C2+两个保守排除组件'),
    ]
    baseline=read(HERE/'baseline/expected_rows.json');baseindex={r['case_id']:r for r in baseline}
    registry=[];raw={};stats={};allcomparisons={}
    for name,source,result,label in definitions:
        source=ROOT/'experiments'/source;result=ROOT/'experiments'/result
        summary=read(result/'summary.json');rows=read(result/'case_metrics.json')
        assert len(rows)==4800 and len({r['case_id']for r in rows})==4800
        assert sha(source)==summary['candidate_sha256']
        comparisons=compare.compare(rows,baseline);allcomparisons[name]=comparisons;raw[name]=rows
        metrics={r['mode']:r for r in comparisons if r['suite']=='combined' and r['group']=='ALL'}
        stats[name]=metrics
        commit=subprocess.check_output(['git','log','-1','--format=%H','--',str(source.relative_to(ROOT))],cwd=ROOT,text=True).strip()
        registry.append(dict(id=name,label=label,candidate=rel(source),candidate_sha256=sha(source),
                             latest_candidate_commit=commit or None,results=rel(result),
                             rows_sha256=sha(result/'case_metrics.json'),all_complete=all(compare.valid(r) for r in rows),
                             mode_metrics=metrics))
    eligible=[r for r in registry if r['all_complete'] and abs(r['mode_metrics'][3]['delta_s_per_source'])<1e-8]
    chosen=min(eligible,key=lambda r:r['mode_metrics'][4]['candidate_mean_s_per_source'])
    winner=chosen['id'];winrows=raw[winner];w4=stats[winner][4]
    allcomparisons['winner_vs_C2']=compare.compare(winrows,raw['C2'])
    allcomparisons['winner_vs_E2_R3']=compare.compare(winrows,raw['E2_R3'])
    save(HERE/'candidate_registry.json',registry);save(HERE/'all_full_comparisons.json',allcomparisons)
    budget1=read(ROOT/'experiments/E1_refine/execution_budget.json')
    budget2=read(ROOT/'experiments/E2_refine/execution_budget.json')
    budget3=read(ROOT/'experiments/E3_expand/execution_budget.json')
    # Root development batches are disjoint by their registered seed sets.
    dev1=read(HERE/'combination/development_r1/summary.json')
    dev2=read(HERE/'combination/development_r2/budget.json');dev3=read(HERE/'combination/development_r3/budget.json')
    rootdev=sum(r['actual_runs']for r in dev1)+dev2['actual_runs']+dev3['actual_runs']
    rootbudget=dict(actual_strategy_executions=rootdev+3*4920,development_actual_runs=rootdev,
                    distinct_new_development_cases=288,full_actual_runs=14400,quick_actual_runs=360,
                    full_candidates=3,full_unique_cases=4800,rule_checks='12 frozen checks for each promoted combination',
                    note='Component off-switch checks are included in development, not additional independent cases. No additional final holdout.')
    save(HERE/'combination/final_execution_budget.json',rootbudget)
    # The research-owned ledgers use different names; report their documented totals.
    e1total=budget1.get('actual_strategy_executions',budget1.get('policy_task_runs'))
    e1unique=budget1.get('distinct_new_development_cases',budget1.get('new_unique_development_cases'))
    assert isinstance(e1total,int) and isinstance(e1unique,int),(budget1.keys(),e1total,e1unique)
    budgets=[('E1',e1total,e1unique),('E2',budget2['actual_strategy_executions'],budget2['distinct_new_development_cases']),
             ('E3',budget3['actual_environment_runs'],budget3['development_distinct_cases']),
             ('主协调融合',rootbudget['actual_strategy_executions'],288)]
    total=sum(r[1]for r in budgets);unique=sum(r[2]for r in budgets)
    save(HERE/'execution_budget.json',dict(total_actual_strategy_executions=total,distinct_new_development_cases=unique,
         completed_full_candidate_deployments=len(registry),full_actual_strategy_executions=4800*len(registry),
         full_distinct_exposed_cases=4800,by_owner=[dict(owner=n,actual_runs=a,new_cases=u)for n,a,u in budgets],
         boundary='All counts include rejected variants and reused-case executions; no cached comparison row is an execution.'))
    current=dict(fixed_baseline='S1',current_best=winner,candidate=chosen['candidate'],
                 candidate_sha256=chosen['candidate_sha256'],dependencies={},
                 modes={str(m):stats[winner][m]['candidate_mean_s_per_source']for m in (3,4)},
                 source_count_each_mode=30970,data_role='4800 exposed local regression',
                 Q3_alternative=dict(candidate='../E1_refine/snapshots/r5_immediate_block.py',mean=stats['E1_R5'][3]['candidate_mean_s_per_source'],
                                     boundary='0.0293% pooled improvement with opposite signs in the two batches; default Q3 retains S1.'))
    save(HERE/'CURRENT_BEST.json',current)
    lines=['# 第四阶段：当前最佳深化与文献扩展', '',
      f'本轮完成E1的5轮、E2的4轮、E3的4轮方法研究和3批组件融合筛选。推荐入口为[{winner}]({chosen["candidate"]})：第三问保持S1的235.876946秒/源；第四问为**{w4["candidate_mean_s_per_source"]:.6f}秒/源**，比本阶段起点473.897493改善**{100*w4["reduction_fraction"]:.4f}%**。', '',
      f'推荐入口在共同4800个本地案例中全部正常退出、全部清除；每题2400局、30970个源。这是已暴露研发回归，不是新留出或官方成绩。本轮{len(registry)}个完整候选部署共实际运行{4800*len(registry)}次任务，全部完整性结果见下表。', '',
      '第三问独立R5的数值最佳为235.807805秒/源，但仅改善0.0293%，v1略好、旧final略差，且6类场景均值退步。它保留为弱证据备选，不把这点不稳定差异并入默认入口。', '',
      '## 所有完整部署', '',
      '| 候选 | 机制 | Q3秒/源 | Q4秒/源 | Q4相对S1 | 全清正常 |',
      '|---|---|---:|---:|---:|---|']
    for r in registry:
        a,b=r['mode_metrics'][3],r['mode_metrics'][4]
        lines.append(f'| [{r["id"]}]({r["results"]}/summary.json) | {r["label"]} | {a["candidate_mean_s_per_source"]:.6f} | {b["candidate_mean_s_per_source"]:.6f} | {-100*b["reduction_fraction"]:+.4f}% | {4800 if r["all_complete"] else "见失败记录"}/4800 |')
    lines+=['', '降低百分比的分母是同题S1的每局“总虚拟时间/成功清除数”算术均值；两题不加权合成分数。只有全部正常、没有错误、清除数等于源数的配对才比较时间。完整分题、分批和分场景表为[all_full_comparisons.json](all_full_comparisons.json)。', '',
      '## 主要收益与不适用方向', '',
      '- E1把“发现16个真实频道后可能取消的覆盖站”纳入路线费用预测，实际覆盖与退出条件保持；独立第四问改善0.512%。把全部未来定位入口当固定服务块会多走路；只修正立即入口虽比S1好，仍弱于条件发现路线。多个已认证清除区域联合选点可用空间很小。',
      '- E2先控制覆盖站已知频道的补测费用，再把单个源服务拆成持久的一轮，返回全局调度。主要收益来自少做低价值测量和减少长期盯住单目标的移动。失败圆外凸包开发负；光学格的完整区域认证剔除仅有微小收益；光学服务分块触发稀少、未扩全量。',
      '- E3核实用户八条论文线索及两个扩展来源，实际尝试付费共享初始化、跨目标第二测点复测、凸接收域负观测约束、条件化观测分支和树深。共享初始化开发小幅正但完整回归负；更深规划未胜单层，成本/可见性门槛也没挽救第二批负结果。只有保守负楔约束单独获得微小完整收益。',
      '- 主协调先融合条件路线与站内门控，再验证单轮服务的组合。立即入口费用与单轮服务存在预测退出位置不匹配，两个入口费用组合开发均未胜当前最佳，未晋级full。最后对两个保守排除组件做2×2对照，有价值的组合才完整回归。', '',
      '安全排除的简短数学依据见[无信号凸性与失败清除格证明](research/no_signal_convexity_lemma.md)。区域缩小不会自动使整局更快，所有性能取自真实执行的接口动作。', '',
      '## 推荐入口的收益构成与退步', '',
      '| 对照 | Q4均值 | 推荐均值差 | 快/同/慢 |', '|---|---:|---:|---|']
    for label,refs in [('S1',baseline),('E2_R3',raw['E2_R3']),('C2',raw['C2'])]:
        cc=compare.compare(winrows,refs)
        r=next(r for r in cc if r['suite']=='combined' and r['mode']==4 and r['group']=='ALL')
        lines.append(f'| {label} | {r["baseline_mean_s_per_source"]:.6f} | {r["delta_s_per_source"]:+.6f} | {r["faster"]}/{r["equal"]}/{r["slower"]} |')
    decomp=[]
    lines+=['', '| 策略 | 总耗时/源 | 移动/源 | 其他动作/源 | 请求/局 |', '|---|---:|---:|---:|---:|']
    for label,rr in [('S1',baseline),('E2_R1_station',raw['E2_R1_station']),('E2_R2',raw['E2_R2']),('C2',raw['C2']),('推荐 '+winner,winrows)]:
        part=[r for r in rr if r['mode']==4];tm=statistics.mean(r['average_clear_time_s']for r in part);mv=statistics.mean(r['distance_m']/5/r['source_count']for r in part);requests=statistics.mean(r['requests']for r in part)
        lines.append(f'| {label} | {tm:.6f} | {mv:.6f} | {tm-mv:.6f} | {requests:.3f} |')
        decomp.append(dict(candidate=label,time_s_per_source=tm,movement_s_per_source=mv,other_s_per_source=tm-mv,requests_per_case=requests))
    save(HERE/'cost_decomposition.json',decomp)
    worse=[r for r in allcomparisons[winner]if r['suite']=='combined' and r['mode']==4 and r['group']!='ALL' and r['delta_s_per_source']>1e-8]
    lines+=['', '相对S1的12类Q4场景均值：'+('；'.join(r['group']+f' +{r["delta_s_per_source"]:.6f}秒/源'for r in worse) if worse else '全部改善。')]
    worst=max((r for r in winrows if r['mode']==4),key=lambda r:r['average_clear_time_s']-baseindex[r['case_id']]['average_clear_time_s'])
    lines+=['',f'仍有{w4["slower"]}个Q4单局慢于S1，最大单局回退{worst["average_clear_time_s"]-baseindex[worst["case_id"]]["average_clear_time_s"]:.6f}秒/源（{worst["case_id"]}）。均值改善不代表逐局占优。所有退步保存在配对表及原始结果。', '',
      '## 来源、版本与方法边界', '',
      '完整[文献阅读账本](../E3_expand/literature.json)与[论文逐条说明](../E3_expand/RESEARCH_BRIEF.md)区分下载、关键章节阅读、完整阅读和未取得的准确版本。八条线索没有按相似题名重复计成新机制。主要更正包括：JFR文件名含2013但正式发表2014；T-RO题名包含静态目标与移动测向传感器；ISRR2015会议稿、IJRR2017扩展与后续书章分别记录；Engin–Isler题名是from Noisy Relative Measurements，WAFR2020与2021书章不同时间；ICRA2013同题2012技术报告不能冒称camera-ready全文，且该报告在R3冻结后才取得，只用于事后理论对照。', '',
      '双机器人通信、动态无标识目标、Gaussian/EKF/CRLB或每步免费观测全部目标的理论保证不能直接搬到本题。概率和未来观测仅用于动作排序；可靠可行集合只接受题设支持的实际信息。', '',
      '## 执行预算与研究收束', '',
      '| 负责部分 | 实际策略任务 | 独特新开发案例 |', '|---|---:|---:|']
    for n,a,u in budgets:lines.append(f'| {n} | {a} | {u} |')
    lines+=['',f'合计{total}次实际策略任务、{unique}个独特新开发案例。完整回归的独特案例为4800个，在不同候选上反复执行；quick是其中子集。开发包含父法/开关/失败对照，同一案例复用不增加独立样本。冻结S1缓存配对不算执行，纯几何夹具不算策略任务。逐项见[执行预算](execution_budget.json)。', '',
      '研究按当前假设的实测收益、反例、触发稀少和控制流程不匹配收束；没有为凑轮数反复扫微小参数。仍未解决全局最优、官方分布适用性与真实通信性能。文献提出的完整PHD/TD3及多机器人方案未实施，不以简化代理冒称论文复现。', '',
      '本轮未新增最终留出、未启动官方Windows模拟器、未重跑全历史。主目录solver.py、前两问和冻结v1规则保留。每个有价值候选完成所需规则检查、quick、full及旧final比较后保存结果；图的更新是本阶段增量。现实运行时间留在逐行数据，存在并行与历史缓存，不用于本机速度排名或充当整个研究用时。', '',
      '## 代码与阅读入口', '',
      f'- [推荐已测试单文件]({chosen["candidate"]})；SHA256 `{chosen["candidate_sha256"]}`。',
      '- [候选与原始结果身份](candidate_registry.json)、[分题默认选择](CURRENT_BEST.json)。',
      '- [E1完整报告](../E1_refine/report.md)、[E2完整报告](../E2_refine/report.md)、[E3完整报告](../E3_expand/report.md)。',
      '- [第四阶段可读方向图](../R1_atlas/STAGE4_PROGRESS.md)、[增量说明](../R1_atlas/stage4_increment/README.md)、[AI增量索引](../R1_atlas/stage4_increment/index.json)、[此前70节点总图](../R1_atlas/DIRECTION_MAP.md)。', '',
      '候选、完整结果和报告保存到既定私有GitHub仓库；来源仅保存链接、阅读范围与研究笔记。']
    (HERE/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(winner=winner,Q4=w4['candidate_mean_s_per_source'],reduction=w4['reduction_fraction'],total_runs=total,new_cases=unique),ensure_ascii=False))

if __name__=='__main__':main()
