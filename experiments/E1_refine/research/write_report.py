from pathlib import Path
import json,hashlib,statistics
P=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2))
budget=dict(policy_task_runs=0,new_unique_development_cases=0,runs=[],rules=dict(test_rules='12 passed after new route implementation',changes_to_frozen_environment=False))
dev=[]
for folder in sorted((P/'development').iterdir()):
    if not (folder/'summary.json').exists():continue
    s=read(folder/'summary.json');registration=read(folder/'registration.json')
    run=dict(label=folder.name,type='development',actual_runs=sum(x['actual_runs']for x in s),unique_cases=registration['cases'],wall_seconds=sum(x['wall_seconds']for x in s))
    budget['runs'].append(run);budget['policy_task_runs']+=run['actual_runs'];budget['new_unique_development_cases']+=run['unique_cases']
    controls={x['mode']:x for x in s[0]['modes']}
    for cand in s:
        for mode in cand['modes']:
            dev.append(dict(batch=folder.name,candidate=cand['candidate'],mode=mode['mode'],cases=mode['cases'],all_complete=cand['all_complete'],mean_s_per_source=mode['mean_s_per_source'],delta_to_batch_S1=mode['mean_s_per_source']-controls[mode['mode']]['mean_s_per_source'],distance_delta=mode['mean_distance_m']-controls[mode['mode']]['mean_distance_m'],requests_delta=mode['mean_requests']-controls[mode['mode']]['mean_requests']))
for folder in sorted((P/'results').iterdir()):
    if not(folder/'summary.json').exists():continue
    s=read(folder/'summary.json');n=s.get('new_runs',s.get('runs'));wall=s.get('wall_seconds_new_runs',s.get('wall_seconds'))
    run=dict(label=folder.name,type='exposed_regression' if 'new_runs'in s else 'fixed_'+s['suite'],actual_runs=n,unique_new_cases=0,wall_seconds=wall,all_complete=s['all_complete'])
    budget['runs'].append(run);budget['policy_task_runs']+=n
diag=P/'research/joint_diagnostic.json'
if diag.exists():
    s=read(diag);run=dict(label='joint_diagnostic',type='replayed instrumentation',actual_runs=len(s['rows']),unique_new_cases=0,wall_seconds=s['wall_seconds'])
    budget['runs'].append(run);budget['policy_task_runs']+=run['actual_runs']
budget['summed_measured_wall_seconds']=sum(x['wall_seconds']for x in budget['runs'])
budget['wall_time_note']='Per-run wall times summed; some independent tasks overlapped. Excludes editing, reading, tool latency and publication; not elapsed campaign duration.'
save(P/'execution_budget.json',budget);save(P/'development_summary.json',dev)
mechanisms=[
('R1','CONDITIONAL_DISCOVERY_ROUTE_PROPOSED','条件发现路线','真正发现16频道会取消剩余站点，规划却先把站点视为全部必达；用离散几何与源数先验估计取消收益，仅改路线排序。','r1_exposed','保留单独组件；开发排序波动，4800两批均有收益。'),
('R2','R1','仅最后未知源的条件路线','只在15频道已实际发现时启用代理，以减少后续未知服务的影响。',None,'288开发改善仅0.152853秒/源；未追加full，保留完整负/弱证据。'),
('R3','JOINT_CLEAR_ROUTE_PROPOSED','多个认证清除区域联合落点','固定顺序交替优化各20m可清圆交集中的服务点；另比较6条原顺序分别优化后择优。',None,'固定序两题开发仅快0.040621/0.162824；择序反而慢0.020430/0.142569。24重放显示平均每次路由认证区仅0.79/0.29个，未追加full。'),
('R4','R3 diagnosis','完整有向服务块','把一次bearing未收敛源建模为预计入口→中心出口的服务块，完整计有向反转代价。',None,'384开发全清但Q3/Q4慢1.185969/5.180035；请求下降仍被增加的移动抵消。'),
('R5','R4','仅当前第一任务的入口成本','只给立即任务计父second_point的入口与到中心费用；未来任务仍用中心，避免提前固定还将被共享信息改变的入口。','r5_exposed','4800全清，Q4比S1快1.839169但不及R1；Q3均值仅快0.069140且两批反向。保留组件，不夸大小收益。')]
nodes=[dict(id='E1_'+r,parent=parent,mechanism=title,implementation=impl,results=result,status=status)for r,parent,title,impl,result,status in mechanisms]
save(P/'optimization_path.json',dict(fixed_baseline='S1',nodes=nodes,development=dev))
lines=['# E1第四阶段：条件发现、联合服务区域与立即入口费用','',
'研究以固定S1为对照，全部策略只通过四接口取得信息。R1为当前已保留的条件发现组件；R5为从完整服务块失败中修正出的立即入口成本组件。以下完整回归来自同一4800个已暴露本地案例，不是新留出、官方运行或全局最优证明。','',
'外部已实测参照包括协调C1 464.925920210秒/源（R1+E2站内补测费用门控）以及随后E2 one_round 457.721499866秒/源，均优于本路线单独R1与R5。R5基于固定S1，不能把其收益直接相加到其他候选。尤其one_round在首个测点后返调度，R5入口→中心的立即服务代理不再对应其实际控制流，融合需改清代理并另测。按本路线预先指定的分题均值准则，Q3数值最佳为R5，Q4为R1；没有为这两个选择创建或冒称已执行一个统一混合部署。Q3 R5提升只有0.0293%，且旧final小幅退步，应视为不稳定的小差异。','',
'## 完整部署结果','',
'|候选|题|案例/清除源|秒/源|比S1变化|快/同/慢|v1变化|旧final变化|','|---|---:|---:|---:|---:|---:|---:|---:|']
full=[]
for label in ('r1_exposed','r5_exposed'):
    path=P/'results'/label/'summary.json'
    if not path.exists():continue
    s=read(path);groups=s['comparisons_to_S1'];allrows=[x for x in groups if x['suite']=='combined'and x['group']=='ALL']
    if label!='r1_exposed':lines+=['|候选|题|案例/清除源|秒/源|比S1变化|快/同/慢|v1变化|旧final变化|','|---|---:|---:|---:|---:|---:|---:|---:|']
    for x in allrows:
        v1=next(z for z in groups if z['suite']=='v1'and z['group']=='ALL'and z['mode']==x['mode'])
        final=next(z for z in groups if z['suite']=='previous_final'and z['group']=='ALL'and z['mode']==x['mode'])
        lines.append(f"|{label}|Q{x['mode']}|{x['cases']}/{x['candidate_cleared']}|{x['candidate_mean_s_per_source']:.9f}|{x['delta_s_per_source']:+.9f}|{x['faster']}/{x['equal']}/{x['slower']}|{v1['delta_s_per_source']:+.9f}|{final['delta_s_per_source']:+.9f}|")
        full.append(dict(candidate=label,**x))
    lines+=['',f"{label}：候选SHA256 `{s['candidate_sha256']}`，全部完成={s['all_complete']}，复用同候选v1 {s['v1_reused']['cases']}局，实际补跑旧final {s['new_runs']}局。完整逐局与比较为[summary.json](results/{label}/summary.json)及[case_metrics.json](results/{label}/case_metrics.json)。",'']
    regressions=[x for x in groups if x['suite']=='combined'and x['group']!='ALL'and x['delta_s_per_source']>1e-7]
    if regressions:
        lines+=['场景均值退步（仍全部清除）：','']+[f"- Q{x['mode']} {x['group']}：{x['delta_s_per_source']:+.6f}秒/源；{x['slower']}/{x['cases']}局慢于S1。"for x in regressions]+['']
save(P/'full_results_summary.json',full)
lines+=['## 结构路线与失败证据','']
for r,parent,title,impl,result,status in mechanisms:
    lines +=[f'**{r} {title}**（父节点/来源：{parent}）。{impl} {status}','']
lines+=['本路线复用了70节点图中上述未实施节点和现有父策略的几何服务区实现，没有把新论文题名作为已复现算法。R1的离散假说、10..16均匀计数先验与剩余覆盖概率是显式规划近似，不是题设分布事实，也不把模拟概率用于取消实际覆盖。','',
'## 所有开发结果','',
'每个批次都使用本路线新分配种子；同批所有候选共用案例。两题分列，不造跨题总分。负数表示快于同批S1。','',
'|批次|候选|题|案例|秒/源|比同批S1变化|距离变化m/局|请求变化/局|','|---|---|---:|---:|---:|---:|---:|---:|']
for x in dev:
    lines.append(f"|{x['batch']}|{x['candidate']}|Q{x['mode']}|{x['cases']}|{x['mean_s_per_source']:.6f}|{x['delta_to_batch_S1']:+.6f}|{x['distance_delta']:+.3f}|{x['requests_delta']:+.3f}|")
lines+=['','这些开发行全部清除。R1在不同开发批次有正负变化，不能把单批排序当稳定效应；R5全测前不按已有场景挑选。对完整回归的进一步选择仍属于暴露集调试。','',
'## 可执行边界与预算','',
'R3的可行动区是每个保守多边形顶点为圆心的20m圆交集。凸多边形任一点是顶点凸组合，若全部顶点在某20m圆内，则整个区域在该圆内。优化每点时保留原可行动点，因此固定任务序的两邻边费用不增加；但在线顺序、位置与观测会变化，不能推出整局不退步。每次真实clear重新验所有当前顶点；原覆盖站与退出证书不变。','',
'R4有向2-opt反转含内部边方向变化 Σ[d(b,a)−d(a,b)]；R5仅起点的出边带立即服务费，其余任务中心边仍对称。第二测点调用仅用于费用预测，R4会暂存/恢复策略自己的预测position；不调用环境、不修改真实已读观测或多边形。预测可见性缓存只从既有观测计算。父真实动作、50小时保护、完整光学fallback和100小时规则保留。','',
f"已实际执行策略任务 **{budget['policy_task_runs']}** 次，其中开发新独特案例 **{budget['new_unique_development_cases']}** 个，24次既有案例诊断重放另计；完整回归复用v1行不再计为新执行。逐项预算见[execution_budget.json](execution_budget.json)。执行器记录墙钟时长合计{budget['summed_measured_wall_seconds']:.3f}秒，存在并行，且不含研究、写代码、工具等待等，不能冒称整个研究耗时或算法速度排名。",'',
'12项规则检查通过；已完成的quick与被保留候选的full、旧final保存在不同目录。冻结环境、第一二问、根solver未改；未执行官方Windows程序。完整服务块与已认证联合落点在当前实现下的主要假设已被开发反证或显示很小空间；立即入口与条件发现的合并由协调者另行判断和测试，当前范围收束不表示不存在其他路线。','',
'本轮不再追的微调：未对R1先验、几何格点数、R3扫数、R4内部移动权重做大规模参数搜索，因为已有证据指向未来信息/服务流程错配或很小的可行动区联合空间。仍未实施的是在one_round新控制流下重新建立可中断任务块及其后续信息状态；这已经是新的控制模型，交由协调者结合E2结构推进，不能用本轮R5结果替代。','']
(P/'report.md').write_text('\n'.join(lines))
(P/'optimization_path.md').write_text('\n\n'.join([f'{r} {title}（{parent}）：{impl} {status}'for r,parent,title,impl,result,status in mechanisms])+'\n')
