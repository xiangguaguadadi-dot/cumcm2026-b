"""Recompute paired official T/N values from all source rows, write audit/report."""
from pathlib import Path
import json,statistics,math,hashlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE=ROOT/'experiments/parallel_v2_coordinator/fusion_r5_exposed/case_metrics.json'
base=json.loads(BASE.read_text());bb={r['case_id']:r for r in base}
assert len(bb)==len(base)==4800
audit=[];group_audit=[]
for version in ('B1','B2','B3'):
    p=HERE/'results'/f'{version}_exposed'
    rows=json.loads((p/'case_metrics.json').read_text());summary=json.loads((p/'summary.json').read_text())
    rr={r['case_id']:r for r in rows}
    assert len(rr)==len(rows)==4800 and set(rr)==set(bb)
    assert all(r['complete'] and r['cleared_count']==r['source_count'] and r['exit_reason']=='user_exit' and r['error'] is None for r in rows)
    for row in rows:
        assert math.isclose(row['total_virtual_time_s']/row['cleared_count'],row['average_clear_time_s'],abs_tol=1e-8,rel_tol=0)
    for mode in (3,4):
        for batch in ('combined','v1','previous_final'):
            for group in sorted({r['group'] for r in rows if r['mode']==mode}):
                part=[r for r in rows if r['mode']==mode and r['group']==group and (batch=='combined' or r['exposure_suite']==batch)]
                am=statistics.fmean(r['total_virtual_time_s']/r['cleared_count'] for r in part)
                bm=statistics.fmean(bb[r['case_id']]['total_virtual_time_s']/bb[r['case_id']]['cleared_count'] for r in part)
                group_audit.append(dict(version=version,mode=mode,batch=batch,group=group,cases=len(part),candidate=am,baseline=bm,delta=am-bm,improvement_pct=100*(1-am/bm)))
    for mode in (3,4):
        for batch in ('combined','v1','previous_final'):
            part=[r for r in rows if r['mode']==mode and (batch=='combined' or r['exposure_suite']==batch)]
            av=[r['total_virtual_time_s']/r['cleared_count'] for r in part]
            bv=[bb[r['case_id']]['total_virtual_time_s']/bb[r['case_id']]['cleared_count'] for r in part]
            diffs=[a-b for a,b in zip(av,bv)];am=statistics.fmean(av);bm=statistics.fmean(bv)
            audit.append(dict(version=version,candidate_sha256=summary['candidate_sha256'],mode=mode,batch=batch,
                cases=len(part),sources=sum(r['source_count'] for r in part),all_complete=True,
                candidate=am,baseline=bm,improvement_pct=100*(1-am/bm),delta=am-bm,
                faster=sum(d<-1e-8 for d in diffs),equal=sum(abs(d)<=1e-8 for d in diffs),slower=sum(d>1e-8 for d in diffs),
                worst_regression=max(diffs),worst_regression_case=part[max(range(len(part)),key=lambda i:diffs[i])]['case_id'],
                candidate_requests=sum(r['requests'] for r in part),baseline_requests=sum(bb[r['case_id']]['requests'] for r in part),
                candidate_failed_clear=sum(r['clear_failures'] for r in part),baseline_failed_clear=sum(bb[r['case_id']]['clear_failures'] for r in part),
                candidate_movement_s_per_source=statistics.fmean(r['distance_m']/5/r['cleared_count'] for r in part),
                baseline_movement_s_per_source=statistics.fmean(bb[r['case_id']]['distance_m']/5/bb[r['case_id']]['cleared_count'] for r in part),
                mean_runtime_s=statistics.fmean(r['program_runtime_s'] for r in part),max_runtime_s=max(r['program_runtime_s'] for r in part)))
raw=dict(baseline_rows_sha256=hashlib.sha256(BASE.read_bytes()).hexdigest(),paired_id_alignment='4800/4800 unique exact matches for each version',
         denominator='each case total virtual seconds divided by cleared source count, then arithmetic mean across cases; all sources cleared',comparisons=audit,group_comparisons=group_audit)
(HERE/'ROW_AUDIT.json').write_text(json.dumps(raw,ensure_ascii=False,indent=2)+'\n')

def fmt(x):return f'{x:.6f}'
def get(v,m,b='combined'):return next(x for x in audit if (x['version'],x['mode'],x['batch'])==(v,m,b))
kept={m:[v for v in ('B1','B2','B3') if all(get(v,m,b)['improvement_pct']>0 for b in ('v1','previous_final'))] for m in (3,4)}
best={m:min(kept[m],key=lambda v:get(v,m)['candidate']) if kept[m] else None for m in (3,4)}
lines=['# 路线B：真实定位区域上的下一次检测与清除费用优化','',
'2026-09-13。父法为当前 `fusion_r5`，SHA `0bda4f711b9e9716739af8aedf456cb1eeefb47d8ba3ed230ca682c8450a96ea`。本报告所有数据均为既有暴露本地回归，不是盲测，也不是官方Windows结果。',
'','## 结论','',
f'按“完整全清、两个既有批次均改善”的本轮规则，Q3路线B推荐：{best[3] or "保留父法"}；Q4路线B推荐：{best[4] or "保留父法"}。最终与路线A的比较和集成由主线程完成。',
'', 'B3在Q3的合计收益只有0.18329秒/源、0.07974%，属于微弱改善，且仍有1057/2400局变慢，最大单局退步108.89255秒/源。Q4合计改善2.67607秒/源、0.58989%，743/2400局变慢，最大单局退步110.75641秒/源。符合本轮平均指标保留条件，不表示逐局稳定优于父法。',
'','| 版本 | Q3 v1改善% | Q3另一批改善% | Q3合计改善% | Q4 v1改善% | Q4另一批改善% | Q4合计改善% |',
'|---|---:|---:|---:|---:|---:|---:|']
for v in ('B1','B2','B3'):
    nums=[get(v,m,b)['improvement_pct'] for m in (3,4) for b in ('v1','previous_final','combined')]
    lines.append('|'+v+'|'+'|'.join(fmt(n) for n in nums)+'|')
lines += ['', '全部三个版本的4800行均正常全清。每个版本均先跑120例quick，再实际跑2400例full，然后在exposed中复用同SHA的full行并实际补跑另外2400例。每版4920次实际回归，共14760次；B1与B3各24例公开轨迹诊断，另48次，路线B共14808次实际场景运行。合成几何检查不计入场景运行。',
'','## 数学与决策变化','',
'1. 保留父法全部可靠角带、源发现覆盖、有限光学覆盖、清除证书与无信号恢复，只覆盖 `second_point`。当前Q3实际配置 `active_information=False`，所以原父点来自旧的向前加侧移规则；不能把基类中未启用的平均信息选点当作实际基准。',
'2. 从当前首测多边形与实际机器狗位置生成多种移动长度的候选。B1/B2使用0.45、0.75、1.0倍多边形包围圆中心在首测方向的投影距离、60/160米侧移与父点等共至多14点。B3另围绕父点实际前进/侧移各乘0.8、1、1.25细化，去重后至多22点。',
'3. 用所有可能未来示向度的区间上界评价精度。将读数区间中点的角带半宽扩大为原半宽加区间半宽，所得多边形包含该区间内每个实际读数对应的定位多边形。因此其最小包围圆半径是一个上界；优先二分当前最大上界区间，至多32次。达到计算预算时仍保留上界，不拿有限方向样本冒充全角度保证。',
'4. 同时估计“当前点移到第二点+5秒检测+移到后验清除位置+清除及失败修正”的秒数。使用polygon内9个确定性积分位置、3个角误差与未知接收半径/方向的规划模型；这些是假设，不是官方概率分布或隐藏真值。',
'5. 只有预计费用不高于父点、未来最坏半径上界不高于父点的候选才可替换；Q4再要求父法的可见性预测值不下降。B1在通过门控的点中优先半径上界，B2优先预计总费用，B3保留B2优先级并做局部细化。',
'','比较两个保守上界并不自动证明精确最坏半径严格下降，且预测费用不增长也不保证真实任务费用不增长。Q4可见性预测不是定向接收保证，真实no_signal仍走原恢复链。原正式±1度及工程读数舍入半角没有缩窄；20米清除证书从未由预测样本替代。',
'','## 分题实际费用与风险','',
'| 版本/题 | 父法秒/源 | 候选秒/源 | 快/平/慢局数 | 请求数候选/父法 | 失败试清候选/父法 | 最大单局退步秒/源 |',
'|---|---:|---:|---:|---:|---:|---:|']
for v in ('B1','B2','B3'):
    for m in (3,4):
        x=get(v,m)
        lines.append(f'|{v}/Q{m}|{fmt(x["baseline"])}|{fmt(x["candidate"])}|{x["faster"]}/{x["equal"]}/{x["slower"]}|{x["candidate_requests"]}/{x["baseline_requests"]}|{x["candidate_failed_clear"]}/{x["baseline_failed_clear"]}|{fmt(x["worst_regression"])}|')
lines += ['', 'B3分组反例：Q3的偏心聚簇组（offcenter_cluster）平均退步3.00503秒/源、1.68387%；恰10源组平均退步0.46876秒/源、0.16584%。Q4的12个合并场景组均改善，但这并不消除上表的逐局退步。',
'', '分场景退步全部保留在各 `results/*_exposed/summary.json` 的 `comparisons` 中；`ROW_AUDIT.json`独立重算全部216个版本/题目/批次/场景组合，并记录最大退步案例ID、每题移动费用与候选现实耗时。本轮并行运行影响现实耗时，历史父法缓存耗时不用于声称受控加速。',
'','## 公开轨迹核查','',
'采用预定quick集合中每个mode/group的首例，共24例，B1和B3分别完整重跑。日志hook只读公开观测、多边形、位置和动作记录；24例的总虚拟费用、清除数、移动距离、失败试清数逐例与未加hook的quick完全相同。',
'','| 版本/题 | second_point调用/实际改点 | 改点后direction/no_signal/near | 改点的平均上界旧→新/m | 平均规划费用旧→新/s |',
'|---|---:|---:|---:|---:|']
for v in ('B1','B3'):
    d=json.loads((HERE/f'diagnostics/{v}_first_per_group/summary.json').read_text())
    for x in d['summaries']:
        a=x['changed_outcomes']
        lines.append(f'|{v}/Q{x["mode"]}|{x["second_point_calls"]}/{x["executed_changed_points"]}|{a["direction"]}/{a["no_signal"]}/{a["near"]}|{x["changed_mean_old_radius_upper"]:.2f}→{x["changed_mean_new_radius_upper"]:.2f}|{x["changed_mean_old_full_cost_proxy"]:.2f}→{x["changed_mean_new_full_cost_proxy"]:.2f}|')
lines += ['', '上述诊断是机制核查，不用于替代全部4800案例指标。75个实际改点全部满足工程半角1.005001°下的三圆盘全向保守安全域。原日志中名为lower的量采用保守包围圆重检，不能仅凭变量名视为严格下界；独立复核随后从完整公开轨迹重建当时polygon及父点读数，改用同一角带内两个合法顶点的距离/2作为下界见证，75点均高于新点上界，最小间隔1.216500米。此结论仅涉及“保留polygon与未来角带交集”的放宽几何目标，普通浮点未作区间认证，也未纳入near、接收半径等全部物理约束。它不能将Q4的全向距离条件升级成定向可见性保证。原标量记录见 `diagnostics/precision_and_omni_domain_audit.json`；重建的polygon、读数和点对见 [补充数值复核](../NUMERICAL_AUDIT.md) 及 [见证数据](../A_transfer/B_geometry_pair_witnesses.json)。',
'', '日志保留改点后的本频道测量/清除次数，以及到该频道清除完成之间所有全局动作的移动距离与时间；并明确这一时间窗可能包含其他频道任务。',
'','## 验证与复现','',
'- 公共冻结输入、父法quick确定性与79项物理规则检查由主线程执行，见上级 `verification/` 和 `PROTOCOL.md`。',
'- 每个候选均先记录机制与SHA，再执行合成检查、quick及大样本。B1只有一次评测前的角带开角边界修订，旧hash和原因保留在其登记中；未改动正在评测的源码。',
'- `check_mechanism.py` 用1441个读数的密网格交叉检查连续上界，并验证两题合成调用不改变权威polygon；这是合成数值核查，不是整体算法正确性证明。',
'- `verify_builds.py` 从冻结父法与可读 `mechanism.py` 逐字重建三个候选；`BUILD_AUDIT.json` 核对构建与登记SHA。',
'- `summarize_B.py` 独立从原始行重算T/N、配对ID、全清、均值与分批结果，生成本报告及 `ROW_AUDIT.json`。',
'- 场景命令使用上级 `evaluate_transfer.py`，exact执行记录见各结果目录 `execution_registration.json`。没有改主入口、第一二问旧文稿、v1评测数据或其他实验目录。',
'','三个预登记版本已全部完成，未追加第四候选。保留负结果；更小定位区域本身不等于更快完成第三、第四问。']
(HERE/'REPORT.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(dict(recommended=best,rows=len(audit),actual_case_runs=14808),ensure_ascii=False,indent=2))
