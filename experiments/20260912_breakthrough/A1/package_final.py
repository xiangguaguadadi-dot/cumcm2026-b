"""Assemble byte-identical BEST and a source-backed final A1 handoff report."""
import hashlib
import json
import statistics
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
read=lambda path:json.loads(path.read_text())
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
ledger=read(HERE/'iteration_ledger.json')
assert not any(r['status']=='in_progress' for r in ledger['rows'])
best_id=ledger['best_round']
best=next(r for r in ledger['rows'] if r['round']==best_id)
assert best['status'].startswith('retained') and 'exposed' in best['scopes']
source=HERE/'snapshots'/(best_id+'.py')
target=HERE/'BEST.py'
if target.exists():
    assert target.read_bytes()==source.read_bytes()
else:
    target.write_bytes(source.read_bytes())
assert sha(target)==best['candidate_sha256']
compile(target.read_text(),str(target),'exec')

c7=ROOT/'experiments/20260911_stage4/combination/geometry_fusions/C7_both.py'
assert source.read_text().startswith(c7.read_text())
tail=source.read_text()[len(c7.read_text()):]
component=HERE/'BEST_Q3_COMPONENT.py'
if component.exists():
    assert component.read_text()==tail
else:
    component.write_text(tail)
# The component expects the same globals produced by evaluating pinned C7,
# including Solver, OPTIMIZED_CONFIGS, math and _Q3. No file lookup is added.
compile(tail,str(component),'exec')
manifest=dict(best_round=best_id,best='BEST.py',best_sha256=sha(target),source=str(source.relative_to(HERE)),
    byte_identical=True,component='BEST_Q3_COMPONENT.py',component_sha256=sha(component),
    component_contract='Execute after pinned C7 in the same globals namespace; final Solver dispatches Q3 to A1 and Q4 to the unchanged C7 parent chain.',
    c7_sha256=sha(c7),external_runtime_dependencies=[],
    identity_verification='Byte equality and SHA256; no extra policy rerun is claimed for this copy. Coordinator verifies final fusion separately.',
    rows='results/'+best_id+'_exposed/case_metrics.json',rows_sha256=sha(HERE/'results'/(best_id+'_exposed')/'case_metrics.json'),
    ledger_sha256=sha(HERE/'iteration_ledger.json'))
(HERE/'BEST_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))

q3=best['scopes']['exposed']['3'];q4=best['scopes']['exposed']['4']
baseline_rows=[r for r in read(ROOT/'experiments/20260911_stage4/combination/results/c7_exposed/case_metrics.json') if r['mode']==3]
c7_mean=statistics.mean(r['average_clear_time_s'] for r in baseline_rows)
savings=100*(1-q3['mean_s_per_source']/c7_mean)
comparison=next(r for r in best['comparison_to_gate_control'] if r['suite']=='combined' and r['mode']==3 and r['group']=='ALL')
totals=ledger['totals']
text=[f'# A1 最终结果：{best_id.upper()} 保留', '',
    f'最终自包含候选 [BEST.py](BEST.py) 与 `snapshots/{best_id}.py` 字节完全相同，SHA256 `{sha(target)}`。它不替换主目录 solver.py。', '',
    f'4800 个已暴露本地案例全部正常退出全清，其中 Q3 {q3["cases"]} 局、{q3["source_count"]} 个源，平均 **{q3["mean_s_per_source"]:.12f} 秒/源**；相对 C7 {c7_mean:.12f} 改善 {savings:.6f}%。Q4 {q4["cases"]} 局仍为 {q4["mean_s_per_source"]:.12f}，任务指标逐行不变。', '',
    '这是固定模拟规则下的实际策略执行/虚拟任务费用，不是官方成绩、生产实测、RL训练结果或新的盲测。指标先逐局 T/真实清除数，再算术平均；不等于所有时间求和除以所有源数。', '',
    '## 1. 逐轮选择与停止', '',
    '| 运行版本 | 结论 | Q3 quick（60局） | Q3 两批合并（2400局） | 对当时保留法 Δ秒/源 | 实际策略运行 |',
    '|---|---|---:|---:|---:|---:|']
for row in ledger['rows']:
    quick=row['scopes'].get('quick',{}).get('3',{}).get('mean_s_per_source')
    combined=row['scopes'].get('exposed',{}).get('3',{}).get('mean_s_per_source')
    delta=next((r['delta_s_per_source'] for r in row.get('comparison_to_gate_control',[]) if r['suite']=='combined' and r['mode']==3 and r['group']=='ALL'),None)
    number=sum(b['actual_policy_runs'] for b in ledger['budgets'] if b['round']==row['round'])
    fmt=lambda x:'—' if x is None else f'{x:.9f}'
    text.append(f'| [{row["round"]}](snapshots/{row["round"]}.py) | {row["status"]} | {fmt(quick)} | {fmt(combined)} | {fmt(delta)} | {number} |')
text += ['', '表中只有 quick 的 Δ 也仅指 quick，不能冒充4800回归。R6是未执行稿；R6a有59次Q3 NameError，其均值不排名；R6b仅修复缺失导入后重跑，不算三个独立算法轮。', '',
    '`retained_marginal` 明确标出两批同向但很小的已接受增量（R7/R9/R10）；其他 `retained` 的实际幅度直接见数值，不另造综合得分或显著性结论。R8设计父是R6b，晋级对照已更新为R7；两批异号，所以即使合计略低也没有晋级。', '',
    '* D1：把已知频道站内补测接入已有任务费用门控，保留R1。',
    '* D2：每个定位轮次后全局重规划，保留R2；R3–R5的服务位置/信息价格变体连续三轮不晋级后停止。',
    '* D3：认证 paid-stop 替站、未来站旋转、有限 minimax 更新，再到只裁短已选扫描站进入段；真实扫描与退出证据都保留。', '',
    '最终方向状态：', '']
for direction,state in ledger['decisions'].items():
    text.append(f'- {direction}：{state}')
text += ['', '## 2. 退步与尾部风险', '',
    f'最终候选相对 {best["gate_control"]}：{comparison["faster"]} 快 / {comparison["equal"]} 同 / {comparison["slower"]} 慢；最大单局退步 {comparison["max_regression"]:.9f} 秒/源；最终最差 Q3 局 {q3["worst_s_per_source"]:.9f} 秒/源。平均改善并不意味逐局或最差局改善。', '',
    '| Q3 场景（每组200局） | 相对当时保留法 Δ秒/源 | 快 / 同 / 慢 |',
    '|---|---:|---:|']
for row in best['comparison_to_gate_control']:
    if row['suite']=='combined' and row['mode']==3 and row['group']!='ALL':
        text.append(f'| {row["group"]} | {row["delta_s_per_source"]:.9f} | {row["faster"]} / {row["equal"]} / {row["slower"]} |')
text += ['', '所有前轮、每批、每组和C7对照都保存在 [iteration_ledger.json](iteration_ledger.json)，没有省略负结果。上述场景是已暴露研发分组；任何读后修正仍属于开发，不可称未见验证。', '',
    '## 3. 正确性与在线权限', '',
    '只通过 enter/measure/clear/exit。源真值、案例ID与源总数只在评测脚本计分，不传给策略。站点只在未扫描状态改变，仍在最终坐标真实扫描未知频道。退出时，除16个真实clear成功达到公开上界外，每个未清频道必须没有正观测，并用自己的真实no_signal位置通过连续覆盖充分条件。Q4不使用该全向无信号证明。', '',
    '证书采用外包目标圆的256边多边形、向外放宽的Voronoi半平面、所有顶点至所属站≤999.999米和范数凸性。离散点只做拒绝；浮点实现带0.001米余量，不伪称区间算术证明。详见 [RESEARCH.md](RESEARCH.md) 和 [R6_RESULT.md](R6_RESULT.md)。', '',
    '进入段裁短只保证给定下一点时两条欧氏边的路长不增；新观测可能改变整个闭环，因此完整运行才决定效率晋级。规则14/14、nominal79/79和冻结manifest检查的原始输出按轮留存，这些规则检查不是14或79次候选游戏。', '',
    '## 4. 成本与样本账本', '',
    f'- 候选评测实际执行 {totals["evaluation_runs"]} 次，v1记录的请求数 {totals["evaluation_requests"]}；含59次运行错误，未丢弃。评测墙钟合计 {totals["evaluation_wall_s"]:.6f} 秒。',
    f'- 另计诊断重放 {totals["diagnostic_runs"]} 次、同口径记录请求 {totals["diagnostic_requests"]} 次；总策略执行 {totals["total_policy_runs"]} 次、v1口径记录请求 {totals["total_requests"]} 次。',
    '- 首次R6b诊断的读日志错误发生在第60局；其请求数按同一冻结候选/世界的确定性重放恢复，不冒充第一次完整保留下来的动作账。',
    f'- 仍只有 {totals["unique_exposed_case_ids"]} 个独立案例ID；quick是full子集，exposed复用full再追加另一批。新增最终盲测0，官方执行0，RL训练0。',
    '- 请求计数严格沿用v1：measures + clear_attempts + int(started) + int(user_exit)。参数或状态预校验拒绝的尝试未完整计入，因未安装独立attempted/accepted计数包装，不能声称这是全部接口调用尝试账。诊断的完整成功局以measure/clear计数加2复现同一口径；规则和纯合成几何另列。',
    '- 墙钟没有包含全部研究阅读、下载、代码编辑、合成几何、汇总与协调审计开销；各轮有并行负载，不用这些时长宣称受控CPU加速。', '',
    '诊断账：', '']
for row in ledger['diagnostics']:
    text.append(f'- {row["label"]}：{row["runs"]} 次、{row["requests"]} 条v1口径记录请求；{row["evidence"]}。')
text += ['', '## 5. 研究与复核入口', '',
    '[RESEARCH.md](RESEARCH.md) 按付费信息、服务调度、发现几何三层机制组织3篇核心定向阅读与1篇引用发现；[literature.json](literature.json) 保存一手来源、版本、实际阅读页节、未读范围、SHA和本题迁移边界。未把文献定理直接套到本题，也未把后读论文追溯为先实现机制的原因。', '',
    '重新核账与封装（不重跑策略）：', '', '```bash',
    'python3.12 -S -B experiments/20260912_breakthrough/A1/summarize.py',
    'python3.12 -S -B experiments/20260912_breakthrough/A1/package_final.py',
    '```', '',
    '最终包见 [BEST_manifest.json](BEST_manifest.json)。BEST_Q3_COMPONENT.py只供协调者在固定C7命名空间内融合；主候选BEST.py本身不依赖外部文件。最终Q3/Q4融合、逐请求等价验证与Git提交由协调者独立负责，本子分支没有提交或推送。']
(HERE/'REPORT.md').write_text('\n'.join(text)+'\n')
print(json.dumps(manifest,ensure_ascii=False,indent=2))
