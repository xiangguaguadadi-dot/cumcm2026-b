"""Build the final narrative and inspectable tables from independently audited rows."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(p):
    return json.loads(Path(p).read_text())


def cell(audit, mode, suite='combined', group='ALL'):
    return next(r for r in audit['comparisons'] if (r['mode'], r['suite'], r['group']) == (mode, suite, group))


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |',
                      *['| ' + ' | '.join(str(x) for x in row) + ' |' for row in rows]])


def main():
    selection = read(HERE / 'FINAL_SELECTION.json')
    name = selection['candidate_name']
    old = read(HERE / 'baseline_vs_c7_audit.json')
    current = read(HERE / (name + '_audit.json'))
    fresh = read(HERE / 'confirmation/audit.json')
    c7 = read(HERE / (name + '_vs_c7_audit.json'))
    ablation = read(HERE / (name + '_vs_geometry_audit.json'))
    assert current['all_complete'] and c7['all_complete']
    confirmation_supported = fresh['all_complete'] and all(cell(fresh,m).get('delta',0) < 0 for m in (3,4))
    lines = ['# 隔离并行突破实验：最终交付', '',
        f'最终候选为 **{name}**，单文件 [候选代码]({name}.py)，SHA256 `{selection["candidate_sha256"]}`。', '',
        '本轮由三个独立 Agent 工作树分别开展 Q3、Q4 与学习/跨方法探索，协调者在第四个工作树中复算和组合。原工作区文件未由本轮修改；第一二问、物理规则和冻结评测保持原版本。起点取本轮开始时已有的更好候选，而不是把另一会话的收益计入本轮。', '',
        ('冻结后的新种子确认中，两题均全清并降低平均虚拟耗时。' if confirmation_supported else
         '**新种子确认没有同时满足两题全清且平均耗时改善；不能把暴露集收益直接宣称为已确认泛化。候选没有按本批结果调参。**'), '',
        '## 与“第三问 235 秒、第四问 453 秒”保持同一批次比较', '',
        '下表全部使用 v1 的相同 1200 局/题，指标为每局总虚拟时间除以实际清除数，再对局取算术均值，单位秒/源。', '',
        table(['题目', '用户所指旧 C7', '本轮实际起点', '最终组合', '本轮新增降低'],
            [[f'Q{m}', f'{cell(old,m,"v1")["baseline_mean"]:.6f}',
              f'{cell(current,m,"v1")["baseline_mean"]:.6f}',
              f'{cell(current,m,"v1")["candidate_mean"]:.6f}',
              f'{cell(current,m,"v1")["improvement_pct"]:.4f}%'] for m in (3,4)]), '',
        '## 完整 4800 个已暴露案例', '',
        '两题各 2400 局，均跨两个已暴露历史批次；每题源数分母共 30970。案例 ID、题号、场景、源数及秒/源公式已从原始行独立核对，未剔除慢局。quick 是 v1 的子集，不能另计独立验证。', '',
        table(['题目', '起点', '最终', '新增降低', '更快 / 相同 / 更慢', '最大单局退步'],
            [[f'Q{m}', f'{cell(current,m)["baseline_mean"]:.6f}', f'{cell(current,m)["candidate_mean"]:.6f}',
              f'{cell(current,m)["improvement_pct"]:.4f}%',
              f'{cell(current,m)["faster"]} / {cell(current,m)["equal"]} / {cell(current,m)["slower"]}',
              f'{cell(current,m)["largest_regression"]:.6f}'] for m in (3,4)]), '',
        f'全部 4800 局正常退出且全清。对旧 C7 的合并改善分别为 Q3 {cell(c7,3)["improvement_pct"]:.4f}%、Q4 {cell(c7,4)["improvement_pct"]:.4f}%；这包含本轮之前已有的进展，不能整体记成本轮贡献。', '',
        f'[原始 4800 行]({name}_exposed/case_metrics.json) · [对本轮起点的独立审计]({name}_audit.json) · [对 C7 的审计]({name}_vs_c7_audit.json)', '',
        '## 冻结后的新种子确认', '',
        '只对已经提交冻结的最终候选和本轮起点运行一次配对确认。100 个新种子各用于两题、12 个本地场景，共 2400 个新案例、4800 次实际策略执行；它们与记录中已知的训练、开发及旧评测种子没有交集。选择版本和参数不使用本批结果。', '',
        table(['题目', '正常全清', '源数', '起点', '最终', '降低', '配对变化的 95% 区间'],
            [[f'Q{m}', f'{cell(fresh,m)["candidate_complete"]} / {cell(fresh,m)["cases"]}',
              cell(fresh,m)['source_count'],
              f'{cell(fresh,m).get("baseline_mean",float("nan")):.6f}',
              f'{cell(fresh,m).get("candidate_mean",float("nan")):.6f}',
              f'{cell(fresh,m).get("improvement_pct",float("nan")):.4f}%',
              ', '.join(f'{v:.6f}' for v in cell(fresh,m).get('paired_seed_cluster_bootstrap_95pct_delta',[]))]
             for m in (3,4)]), '',
        '区间针对“最终减起点”的秒/源变化，按同一个种子跨场景形成的簇重采样，未把 1200 局当作 1200 个独立随机种子。本批仍来自原有的 12 类本地分布假设，不代表官方分布或 Windows 官方执行。', '',
        '[确认审计](confirmation/audit.json) · [最终候选原行](confirmation/frozen_candidate/case_metrics.json) · [起点原行](confirmation/start_baseline/case_metrics.json) · [冻结登记](confirmation_registry.json) · [种子排重范围](confirmation_seed_review.json)', '',
        '## 最终方法及实际贡献', '',
        'Q3 保留 A1 R8：把连续定位区域分成可被 20 米清除圆完整覆盖的凸条，用子集动态规划安排首次命中费用最小的访问顺序；在预计费用更低时用多次光学试探替代继续测向。Q4 使用 A2 的最终有限光学几何，并叠加 A3 B4 的在线共享偏差规划。全部失败 clear、移动和换频道费用照常记录。', '',
        f'Q4 在同一 2400 局上，最终几何父版本为 {cell(ablation,4)["baseline_mean"]:.6f} 秒/源，加入 B4 后为 {cell(ablation,4)["candidate_mean"]:.6f}，额外降低 {-cell(ablation,4)["delta"]:.6f} 秒/源。主要收益来自几何与动作选择；组合增益不能把两个独立收益简单相加。', '',
        f'[几何与学习消融审计]({name}_vs_geometry_audit.json) · [方法、费用递推、证明边界与论文依据](METHODS.md)', '',
        '最初融合曾因学习模块改动已证明完整覆盖的清除点而漏清一局，已淘汰并保留原行。修正版通过覆盖执行上下文保护实际点位；最终每份组合重新跑全量，未用“两个父版本单独全清”替代组合验证。', '',
        '[失败及淘汰决定](fusion_r1_decision.json) · [同例干预复核](fusion_r1_causal_check.json) · [组合迭代账本](fusion_ledger.json)', '',
        '## 研究与停止记录', '',
        'A1 完成 11 轮：R8 后 R9/R10/R11 连续三轮不晋级，冻结 R8。A3 完成两个机制方向共 13 轮：残差门控在 R3 后三轮不晋级停止，共享偏差规划在 B4 后三轮不晋级停止。A2 最终保留 finite R7，随后 R8/R9/R10 连续三轮未晋级；R11/R12 在停止口径澄清前已启动的 quick 只归档，没有追加 full。其他已停止路线和实测原行保留在 A2 报告。未通过 quick/开发筛选的候选不虚构 full 结果。', '',
        'A3 针对 15 篇一手来源记录阅读深度，其中 7 篇做了针对性的方法与实验条件阅读，其余为扩展筛选；没有宣称全部全文深读或系统综述。训练实际包括 1296 个不同训练/校准 world，加 96 个复用开发 world。保存账本有 1296 次完整教师执行、9994 次从克隆状态开始的反事实分支及 35688 次完整评估；反事实分支不是新增独立 world。最终选用在线偏差规划，未把训练过程等同于大幅强化学习突破。', '',
        '[三位 Agent 的报告、证明、来源和执行账本索引](AGENT_ARTIFACTS.json)。索引同时给出本地路径及已上传提交的固定链接，未上传项明确标注。', '',
        '## 验证和交付范围', '',
        '冻结物理规则的 14 项单元检查、79 项名义夹具和 manifest 校验通过；几何顶点认证、DP 小例穷举对照、学习实际坐标/保护契约另有专门检查。样本与夹具不代替连续几何论证或完整程序形式证明。最终可见接口仍只有 enter、measure、clear、exit，部署单文件不包含案例真值、测试 ID 分派或缓存得分读取。', '',
        '本地函数模拟器的现实计算耗时发生在共享负载下，不能拿历史缓存时间当受控运行速度对照。Windows HTTP 通信、官方误差场及正式测试均未执行；这里没有官方成绩。', '',
        '在隔离 coordinator 工作树中可复核冻结环境，或用新的输出目录重跑候选：', '',
        '```bash',
        '/opt/homebrew/bin/python3.12 -S -B evaluate.py --verify-only',
        f'/opt/homebrew/bin/python3.12 -S -B evaluate.py --candidate experiments/parallel_v2_coordinator/{name}.py --suite full --out results/review_new',
        '```', '',
        '确认批已有结果，重跑只算复现该批，不能再称新增未见样本。冻结登记及报告文件均留在独立实验分支，未改正式入口或原工作区。分支提交/远端状态见 [交付状态](DELIVERY_STATUS.json)。', '']
    lines += ['## 分场景变化', '', '负数表示最终候选更快。以下是秒/源变化，保留有退步的场景。', '',
        table(['场景','暴露 Q3','暴露 Q4','新确认 Q3','新确认 Q4'],
            [[g, *[f'{cell(a,m,group=g).get("delta",float("nan")):.6f}'
                   for a,m in ((current,3),(current,4),(fresh,3),(fresh,4))]]
             for g in sorted({r['group'] for r in current['comparisons'] if r['group']!='ALL'})]), '']
    (HERE / 'REPORT.md').write_text('\n'.join(lines))
    exposed_ids = {r['case_id'] for r in read(HERE / (name + '_exposed/case_metrics.json'))}
    fresh_ids = {r['case_id'] for r in read(HERE / 'confirmation/frozen_candidate/case_metrics.json')}
    assert len(exposed_ids) == 4800 and len(fresh_ids) == 2400 and not (exposed_ids & fresh_ids)
    summary = dict(selection=selection, exposed=[cell(current,m) for m in (3,4)],
        v1=[cell(current,m,'v1') for m in (3,4)], fresh=[cell(fresh,m) for m in (3,4)],
        comparison_to_c7=[cell(c7,m) for m in (3,4)], learning_increment_q4=cell(ablation,4),
        unique_case_ids=len(exposed_ids | fresh_ids), confirmation_supported=confirmation_supported,
        all_7200_unique_cases_complete=current['all_complete'] and fresh['all_complete'])
    (HERE / 'FINAL_METRICS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'candidate':name,'all_7200_complete':summary['all_7200_unique_cases_complete'],
                      'report_sha256':hashlib.sha256((HERE/'REPORT.md').read_bytes()).hexdigest()},ensure_ascii=False))


if __name__ == '__main__':
    main()
