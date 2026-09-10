"""Build the coordinator report from audited saved rows and the final review."""
from __future__ import annotations

import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent

NAMES = {
    'A1_space': '空间覆盖与移动成本',
    'A2_information': '信息获取与定位不确定性',
    'A3_coordination': '多源与多频道协同',
    'A4_directional': '定向发射与可见性',
    'A5_learning': '学习路线一',
    'A6_learning': '学习路线二',
}

MECHANISMS = {
 'A1_space': (
  '将第三问搜索站的外环半径由1558.85米收缩至1124米，并用连续圆域覆盖证明约束；原点全频道无信号时才切回外环。'
  '对已知目标与未扫站做开放路径排序，使用2-opt和单节点重插；小定位区域可优化可靠清除圆盘中的进入/离开位置。'
  '已观测或已清除的互异频道达到16时，可以结束额外发现扫描，仍必须将全部已知源真正清除。',
  '覆盖与区域访问文献启发了“先保证可发现，再缩短访问路径”；区域TSP、信息路径规划及覆盖路径启发进入spatial_next_task等函数。'
  '没有实施论文中的强化学习、全局最优TSP或原作者完整算法。R2形成两题取舍，R7、R9、R10未刷新；R10虽总体稍慢，消除了R8的一项回归场景退步，作为预登记补充版本验证。'),
 'A2_information': (
  '第三问用多个合法假想目标预测后续测向与清除代价，选择第二测点；已知1800米目标域和1500米接收上界用于保守切面细化。'
  '全向的no_signal可排除1000米圆盘，光学失败对两题均可排除20米圆盘，再取保守凸包；清除位置须落在所有顶点的20米圆交集中。'
  '第四问不能把no_signal直接当成距离排除，主动测点保持基准选择。',
  '双目标主动测向、集合定位、预测观测偏差和信息动作规划文献进入second_point、predicted_polygon及几何约束设计。'
  '这些是机制迁移与本题自推几何，未复现文献完整POMDP/SDP算法。R4在压力开发中出现最高11787顶点和5秒诊断超时，R5加入计算预算后原120例重放无超时；'
  '该诊断不是官方1200秒超时。早期Q4在quick有微小改善而full不支持，失败行及取舍全部保留。'),
 'A3_coordination': (
  '复用单源定位途中已经付过移动成本的停靠点，为其他已发现频道付费补测。根据假想示向度预测多边形收缩，只决定是否测量；'
  '真实多边形只接受接口返回的真实观测。share_observations使用递归保护，保留原搜索覆盖和退出证书。',
  '自适应次模、信息路径规划、多模态资源分配和顺序重规划提供“随观测重算一次补测价值”的启发。'
  'R2把补测延伸到中间定位点，改善两题；R3的新代理退步，故三轮停止。未做门槛、测量顺序与信息代理的完整因子消融。'
  'R1作为各场景均值无基准退步的保留版本一同进入最终复核。'),
 'A4_directional': (
  '保守位置多边形之外，另维护位置、发射方向和接收半径的有限假设，用来估计可见性和排序动作。'
  '小区域可提前进入完整光学格点覆盖；失联时先考虑一次有距离界的镜像，再有限二分折返，最后仍走原救援。'
  '光学格点全部保留，只在两条从中心向两端展开的完整路径间选择。',
  '无线电/视觉无检测似然、多模态成本规划和集合定位启发可见性评分与射频/光学切换。'
  '折返、镜像及中心展开路径是本题自己的推导，不归为论文原算法。R4的面积权重、R7复杂模态成本及R8保证可见的恢复点都失败。'
  'R6只较R5快0.32383秒/源，且三项场景退步；最终相对原基准的12项Q4场景均值仍全部改善。'
  '完整时间余量证明给出277000秒上界，小于360000秒，且显式计入跨阈值的一整条光学路径。'),
 'A5_learning': (
  '以完整任务秒/源为反馈，用平滑高斯交叉熵搜索有限策略参数，再在独立开发数据选择。'
  '学习状态调度与局部测点参数，位置几何、有限覆盖及停止证书由原代码负责。R2只保留第四问的上下文调度，第三问逐局保持原版。',
  'CEM和参数空间搜索提供实际优化机制；DAgger用于检查候选自身诱导的轨迹分布，Shielding用于区分学习动作与可靠性约束，二者未整套复现。'
  'R1失败；R2第四问改善；R3局部测点学习改善Q4但使Q3变差，因此三轮停止，R2和R3分别验证，不拼接。'
  '已暴露开发集上的静态/上下文消融仅帮助解释，不是新的留出证据，也未用于再次选参。'),
 'A6_learning': (
  '独立选择两阶段精英随机搜索：训练集选前列参数与输入策略，开发集选择；不是ARS有限差分更新。'
  '之后搜索可观测状态特征和交互特征，局部测点仍保留解析约束。开发提升必须通过预设0.5%门槛才能启用新增学习参数。',
  '参数空间策略搜索、策略诱导分布偏移、Shielding和任务级路线学习提供原则启发，未训练PPO/DAgger/PILCO等竞争算法。'
  'R1失败；R2取舍；R3恢复Q3原版后成为共同改善；R4、R6及最终R8/R9新增参数未获足够开发支持，参数为零。'
  'R5、R7刷新第四问，R8/R9与R7回归行为持平，连续两轮未刷新后停止。第三轮另有5760局训练重放检查，配置与原记录相同。'),
}


def read(name):
    return json.loads((HERE / name).read_text())


def main():
    registry = read('candidate_registry.json')
    rounds = read('all_rounds.json')
    literature = read('literature_index.json')
    comparison = read('final_validation/comparison.json')
    manifest = read('final_validation/manifest.json')
    final = {Path(r['path']).parent.name: r for r in comparison['candidates']}
    baseline = read('final_validation/baseline/summary.json')
    labels = {r['label']: r for r in registry['candidates']}
    bests = [r for r in registry['candidates'] if r['selection_reason'] == 'route_best']
    assert set(final) == set(labels)
    lines = ['# 六路线研究、迭代与统一新样本复核', '',
     '完成日期：2026-09-11。研究对象为2026数学建模B题第三、四问。第一问定稿与第二问既有结果保持不变。', '',
     '六条路线均已按约定完成实验与经验停止。每条路线保留自己的最佳代码、完整正负结果及中文研究报告；'
     '主协调在候选冻结后生成同一批新案例并直接运行交付快照。本文中的结果全部属于本地模型，未进行Windows官方演练或正式测试。', '',
     '## 1. 统一新样本的主要结果', '',
     f'新样本包含{manifest["distinct_seed_clusters"]}个系统随机种子、12组场景、两道题，共{manifest["cases"]}局；'
     '所有版本使用同一组案例。每题均值是1200局各自“总虚拟耗时÷清除源数”的算术平均，单位为秒/源。'
     '降幅为相对同批原基准的均值降幅；它是等权本地场景汇总，不是官方跨场景总分，也没有合并两题的加权分。', '',
     '|版本|Q3 秒/源|Q3 降幅|Q4 秒/源|Q4 降幅|全清且正常退出|',
     '|---|---:|---:|---:|---:|---:|']
    b3,b4=baseline['modes']
    lines.append(f'|原基准|{b3["mean_s_per_source"]:.5f}|—|{b4["mean_s_per_source"]:.5f}|—|{sum(m["valid_completion"] for m in baseline["modes"])}/2400|')
    for record in bests:
        label=record['label']; m3,m4=final[label]['modes']
        summary=read(f'final_validation/{label}/summary.json')
        if all(m['comparison_valid'] for m in (m3,m4)):
            values=f'{m3["candidate_mean_s_per_source"]:.5f}|{100*m3["reduction_fraction"]:.3f}%|{m4["candidate_mean_s_per_source"]:.5f}|{100*m4["reduction_fraction"]:.3f}%'
        else:
            values='不排名|—|不排名|—'
        lines.append(f'|{label} · {NAMES[record["agent"]]}|{values}|{sum(m["valid_completion"] for m in summary["modes"])}/2400|')
    if all(all(m['comparison_valid'] for m in final[r['label']]['modes']) for r in bests):
        q3=min(bests,key=lambda r: final[r['label']]['modes'][0]['candidate_mean_s_per_source'])
        q4=min(bests,key=lambda r: final[r['label']]['modes'][1]['candidate_mean_s_per_source'])
        lines += ['', f'在六条路线预先保留的最佳版本中，本批Q3均值最低为**{q3["label"]}**，Q4均值最低为**{q4["label"]}**。'
                  '这是本批共同新样本上的描述性结果；不同研究轮数与训练预算不构成等预算的方向优劣试验。'
                  '没有据此混合两份代码或替换主分支solver.py。']
    lines += ['', '### 预登记的补充取舍版本', '',
      '这些版本在新案例生成前登记，理由见[复核计划](FINAL_VALIDATION_PLAN.md)与[候选登记](candidate_registry.json)。'
      '它们不会事后替换各Agent已经完成的选择。', '',
      '|版本|登记理由|Q3 秒/源|Q4 秒/源|全清且正常退出|', '|---|---|---:|---:|---:|']
    for r in registry['candidates']:
        if r in bests: continue
        m3,m4=final[r['label']]['modes'];summary=read(f'final_validation/{r["label"]}/summary.json')
        reason={'route_nondominated_tradeoff':'两题均值非支配取舍','preregistered_scenario_tradeoff':'预登记场景取舍','route_reported_scenario_tradeoff':'路线报告保留的场景取舍'}[r['selection_reason']]
        lines.append(f'|{r["label"]}|{reason}|{m3.get("candidate_mean_s_per_source",float("nan")):.5f}|{m4.get("candidate_mean_s_per_source",float("nan")):.5f}|{sum(m["valid_completion"] for m in summary["modes"])}/2400|')
    lines += ['', '### 配对不确定性与场景退步', '',
      '每个新种子在不同场景和题目复用，因此按100个种子簇做5000次配对自助抽样。下表是“原基准−候选”的秒/源均值差及95%区间，正值表示节省。'
      '区间仅用于探索性描述，未作多候选选择校正，不是因果证明，也不是官方显著性胜负。', '',
      '|版本|Q3 节省及95%区间|Q4 节省及95%区间|', '|---|---:|---:|']
    for r in registry['candidates']:
        cells=[]
        for m in final[r['label']]['modes']:
            if not m['comparison_valid']: cells.append('不比较');continue
            lo,hi=m['paired_saved_seed_cluster_bootstrap_95ci']
            cells.append(f'{m["paired_mean_saved_s_per_source"]:.4f} [{lo:.4f}, {hi:.4f}]')
        lines.append(f'|{r["label"]}|'+ '|'.join(cells)+'|')
    lines += ['', '以下逐个列出相对同批基准的场景均值退步。每组100局；总体改善不表示每场景或每局都更快。'
      '全部24组均值保留在[共同配对数据](final_validation/comparison.json)。', '']
    for r in registry['candidates']:
        regress=[g for g in final[r['label']]['groups'] if g['comparison_valid'] and g['reduction_fraction'] < -1e-12]
        content='；'.join(f'Q{g["mode"]} {g["group"]} 增加{g["candidate_mean_s_per_source"]-g["baseline_mean_s_per_source"]:.4f}秒/源（{-100*g["reduction_fraction"]:.3f}%）' for g in regress)
        lines.append(f'- **{r["label"]}**：'+(content if content else '没有场景均值退步。'))
    lines += ['', '## 2. 六条路线实际做了什么', '',
      f'六份清单合计{literature["engagements"]}条按路线记录的阅读活动，按arXiv编号或标准化题名去重为{literature["distinct_sources_by_arxiv_or_title"]}个来源。'
      '这不是全部全文深读的篇数。每条记录的具体页码/章节、启发、进入的轮次和函数、未采用理由及本题实验证据见'
      '[逐篇文献索引](LITERATURE_MAP.md)。主协调审阅了报告、清单及代码差异，没有把所有原文重新通读一遍。', '']
    origins={o['agent']:o for o in literature['origins']}
    for record in bests:
        identity=record['agent']; source=origins[identity]
        own=[e for e in literature['entries'] if e['agent']==identity]
        core=sum(str(e['tier']).startswith('core') for e in own)
        lines += [f'### {identity} · {NAMES[identity]}', '', *[p+'\n' for p in MECHANISMS[identity]],
          f'实际阅读清单：{len(own)}个来源，其中{core}个标注为关键正文阅读，其余阅读范围按原记录列明。'
          f'[该路线完整中文报告]({source["report_url"]})；'
          f'[本机报告]({Path(record["worktree"])/"experiments"/identity/"report.md"})。', '']
    lines += ['## 3. 全部固定回归轮次与停止依据', '',
      '每轮full实际运行2400次候选，quick运行120次且是full的子集。基准为散列校验后的历史缓存，不算新执行。'
      '固定种子5000–5099已被反复查看，所以本表是研发回归，不能称为未见测试。'
      '共同最佳仅在全部清除、两题均不差且至少一题改善时刷新；取舍保留但不重置停止计数。', '',
      'R2到R3持续改善的路线获授权延长；延长后连续两轮未刷新当前共同最佳即停止。'
      '这只定义本次经验停止，不证明数学收敛、全局最优或穷尽可改进空间。', '',
      '|路线/轮次|Q3 秒/源|Q4 秒/源|相对当时共同最佳|全清|full现实秒|',
      '|---|---:|---:|---|---:|---:|']
    for identity in NAMES:
        best=[306.30043421816345,570.8833714439976]
        selected=0
        for r in [x for x in rounds['rounds'] if x['agent']==identity]:
            values=[m['candidate_mean_s_per_source'] for m in r['modes']]
            diffs=[x-y for x,y in zip(values,best)]
            if max(diffs)<=1e-9 and min(diffs)<-1e-9:
                decision='刷新';best=values;selected=r['round']
            elif max(abs(x) for x in diffs)<=1e-9: decision='持平'
            elif min(diffs)<-1e-9 and max(diffs)>1e-9: decision='两题取舍'
            else: decision='未刷新（退步）'
            lines.append(f'|{identity} R{r["round"]}|{values[0]:.5f}|{values[1]:.5f}|{decision}|{sum(m["complete"] for m in r["modes"])}/2400|{r["full_wall_s"]:.3f}|')
        expected=next(r['round'] for r in bests if r['agent']==identity)
        assert selected==expected,(identity,selected,expected)
    lines += ['', '表中数据由每轮原始case_metrics.json重新配对计算。完整路径、候选SHA256、结果散列和quick/full耗时在[全轮机器记录](all_rounds.json)。'
      '性能退步与压力开发失败均留存，未只保留成功版本。各轮具体改动和逐场景得失见六份完整报告及文献索引。', '',
      '## 4. 计算预算与学习证据', '',
      f'固定回归共**{rounds["full_rounds"]}轮、{rounds["full_candidate_runs"]:,}次full候选执行、{rounds["quick_candidate_runs"]:,}次quick候选执行**。'
      f'full记录的现实执行时间合计{sum(r["full_wall_s"] for r in rounds["rounds"]):.3f}秒。'
      '这些累计次数包含同一案例重复执行，不能称为等量独立样本；也不包含文献阅读、设计、编辑、排队和提交耗时。', '',
      '训练、开发、消融与重放分路线列在[独立交付审计](audit/delivery_independent.md)。'
      'A1有4480次有效开发/验证执行及160次排除的无效批次；A3有360次候选内层执行及360次开发基准执行；'
      'A4有3000次开发/验证执行。A5有33192次训练/开发执行，加12次计时复测与288次开发消融，共33492次学习与分析执行。'
      'A2与A6最终预算由各自报告和审计逐项核对；有中断前未知次数时保留未知，不补造整数。', '',
      f'最终共同复核另运行原版和{len(registry["candidates"])}个预登记候选，共{2400*(1+len(registry["candidates"])):,}次完整任务。'
      '基准在本轮实际重跑，仍需考虑同机并行负载和算法计算量；本地现实时间不能替代正式联网测试时间。', '',
      '## 5. 时间收益来自哪里', '',
      '下表按新样本原始行把虚拟总时间拆为移动距离÷5与其余动作时间，均除以清除数后跨局平均。'
      '“其他”包括检测、换频道、光学动作及微秒舍入残差；这是记账恒等式，不是因果消融。', '',
      '|路线最佳|题目|总节省秒/源|移动节省|其他动作节省|', '|---|---:|---:|---:|---:|']
    for r in bests:
        for m in final[r['label']]['modes']:
            if not m['comparison_valid']: continue
            t=m['time_decomposition']
            lines.append(f'|{r["label"]}|Q{m["mode"]}|{m["paired_mean_saved_s_per_source"]:.4f}|{t["paired_movement_saved_s_per_source"]:.4f}|{t["paired_other_saved_s_per_source"]:.4f}|')
    lines += ['', '## 6. 独立性、可靠性与证据边界', '',
      'A5与A6最初以逐字相同的任务提示、独立上下文启动，没有预先人为拆成两种学习方案。'
      '由于并发上限，部分路线完成当前轮并保存自身状态后暂停，随后接续；这些调度暂停没有计作收敛。', '',
      '中途上下文恢复发生了两次共享协调摘要的信息暴露：原A6与原A2读到了跨路线摘要。'
      'A6的R7架构、训练及参数选择有暴露前时间/散列记录，之后仅完成该轮冻结验证，再由干净上下文接续R8。'
      'A2的R7冻结及R8方向建议有较早文件记录，但R9在暴露后设计，故不能声称该段完全独立；完成已固定R9后由干净上下文接续。'
      '主协调已移开共享摘要并限制接续入口。干净接续不能追溯消除早前暴露，本次不宣称六条路线全程绝对隔离。', '',
      '候选审阅包括完整代码差异、在线四接口边界、覆盖/清除/退出结构、源码与提交对象及full结果散列。'
      '最终交付均为标准库独立文件，学习参数嵌入源码，没有部署权重；快照旁不含coverage_points.json。'
      '最终评测前后检查冻结文件、候选、案例及依赖散列。AST字段清单只是辅助，不能当成反射攻击的安全沙箱。', '',
      '可靠清除依赖题设有界示向度、目标域/接收界、覆盖点几何与有限光学网格。近似概率、有限假想点、训练分数都不作为不存在目标的证书。'
      'A4修改完整光学路径顺序后另给277000秒保守界；其余路线保留或约束在原覆盖与时间保护结构内。'
      '有限样本全部通过不替代全域几何证明，几何证明也不能控制无限网络延迟。', '',
      '新案例仍使用同一套12种本地分布假设，只有随机种子未参与本轮迭代。结果没有返给路线调参。'
      '本次不提供官方Windows验证、新分布鲁棒性证明、跨算法等预算因果结论或全局最优证明。正式第三/四问各三次测试及官方日志仍需另行完成。', '',
      '## 7. 交付与复查入口', '',
      '|候选|交付源码|精确代码提交|', '|---|---|---|']
    for r in registry['candidates']:
        url=f'https://github.com/xiangguaguadadi-dot/cumcm2026-b/blob/{r["code_commit"]}/{r["original_snapshot"]}'
        lines.append(f'|{r["label"]}|[{Path(r["candidate_path"]).name}]({Path(r["candidate_path"]).relative_to(HERE.relative_to(ROOT))})|[{r["code_commit"][:12]}]({url})|')
    lines += ['', f'候选登记时间：{registry["registered_at_utc"]}；案例生成时间：{manifest["generation_time_utc"]}。'
      f'案例SHA256：`{manifest["cases_sha256"]}`。冻结manifest SHA256：`{registry["frozen_manifest_sha256"]}`。', '',
      '每个最终版本目录提供case_metrics.json、CSV与summary.json；[最终比较](final_validation/comparison.json)记录配对区间和全部分组。'
      '[候选登记](candidate_registry.json)保存全部源码SHA256、来源工作树、准确提交、依赖及回归数据散列。'
      '各Agent分支保留历轮开发/训练配置、快照、规则结果、quick/full与完整报告。', '',
      '从代码仓库根目录复跑时使用Python 3.10以上，输出必须换成尚不存在的目录；例如：', '',
      '```sh',
      'python evaluate.py --verify-only',
      'python experiments/20260911_agent_campaign/final_review.py run --root . --candidate experiments/20260911_agent_campaign/final_candidates/A4_directional_R6.py --cases experiments/20260911_agent_campaign/final_validation/cases.json --out results/reproduce_A4_new --label A4_reproduce',
      '```', '',
      '主分支solver.py保持冻结原版。这里交付可独立运行和比较的候选，不把按新结果拼接出的未测试版本冒充已验证改进。', '']
    (HERE/'REPORT.md').write_text('\n'.join(lines))
    print(f'Wrote {HERE / "REPORT.md"}: {len(lines)} blocks')


if __name__ == '__main__':
    main()
