"""Seal selection and report from independently audited, completed raw-row runs."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    audit = read(HERE / 'INDEPENDENT_AUDIT.json')
    assert audit['status'] == 'passed' and not audit['pending_experiment_results']
    assert audit['completed_experiment_runs'] == 19800
    results = {r['result']: r for r in audit['results']}
    candidates = {
        'A1': ('A_transfer', 'candidate_A1.py'),
        'A2': ('A_transfer', 'candidate_A2.py'),
        'B1': ('B_improved', 'B1_minimax_costgate.py'),
        'B2': ('B_improved', 'B2_cost_precisiongate.py'),
        'B3': ('B_improved', 'B3_local_refinement.py'),
    }

    def get(version, suite, mode, batch='combined', group='ALL'):
        route, _ = candidates[version]
        r = results[f'{route}/results/{version}_{suite}']
        return next(c for c in r['independent_audit']['comparisons']
                    if (c['mode'], c['suite'], c['group']) == (mode, batch, group))

    selection = {}
    for mode in (3, 4):
        eligible = [v for v in ('A1', 'B1', 'B2', 'B3')
                    if results[f'{candidates[v][0]}/results/{v}_exposed']['independent_audit']['all_complete']
                    and all(get(v, 'exposed', mode, b)['improvement_pct'] > 0
                            for b in ('v1', 'previous_final'))]
        winner = min(eligible, key=lambda v: get(v, 'exposed', mode)['candidate_mean'])
        route, name = candidates[winner]
        candidate = HERE / route / name
        evidence = HERE / route / 'results' / f'{winner}_exposed'
        assert sha(candidate) == read(evidence / 'summary.json')['candidate_sha256']
        selection[mode] = dict(version=winner, candidate=str(candidate.relative_to(HERE)),
                               candidate_sha256=sha(candidate), eligible_versions=eligible,
                               evidence=str(evidence.relative_to(HERE)),
                               exposed_rows_sha256=sha(evidence / 'case_metrics.json'),
                               metrics=get(winner, 'exposed', mode),
                               batches=[get(winner, 'exposed', mode, b) for b in ('v1', 'previous_final')])
    assert all(s['version'] == 'B3' for s in selection.values())
    record = dict(status='completed', data_role='existing exposed local regression; no fresh blind or official test',
                  protocol_sha256=sha(HERE / 'PROTOCOL.md'),
                  registration_sha256=sha(HERE / 'REGISTRATION.json'),
                  independent_audit_sha256=sha(HERE / 'INDEPENDENT_AUDIT.json'),
                  gate='all 4800 complete; both existing batches improve in selected mode; best mean among eligible versions',
                  selected_by_mode=selection, combination_needed=False,
                  main_solver_replaced=False,
                  candidate_regression_runs=19800, baseline_reproduction_runs=120,
                  public_diagnostic_runs=288, total_scene_runs=20208,
                  separate_synthetic_checks=True,
                  note='Same already-executed B3 file wins both modes; no new combination or duplicate confirmation run.')
    (HERE / 'SELECTION.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')

    lines = [
        '# 第二问定位精度向第三、四问迁移：最终结果', '',
        '2026-09-13。两条路线已完成：A直接迁移已有第二问方法；B先改进下一测点设计，再实际运行第三、四问闭环任务。共5个候选，最终两题均推荐已验证的 **B3**。本轮起点是当前工作树的 `fusion_r5`，不是旧README中的C7，也不是主目录 `solver.py`。', '',
        '全部结果来自既有4800个本地暴露案例，Q3/Q4各2400局、各30970个源。先检查全部清除与正常退出，再按每局 `总虚拟时间/实际清除数` 计算，最后对案例取算术平均；改善率为 `100×(父法均值−候选均值)/父法均值`。不将两题混成一个分数。', '',
        '| 题目 | 父法秒/源 | B3秒/源 | 减少秒/源 | 改善 |',
        '|---|---:|---:|---:|---:|',
    ]
    for mode, s in selection.items():
        x = s['metrics']
        lines.append(f'|Q{mode}|{x["baseline_mean"]:.6f}|{x["candidate_mean"]:.6f}|{-x["delta"]:.6f}|{x["improvement_pct"]:.6f}%|')
    lines += ['', 'B3在两个既有批次中均改善，达到本轮预登记保留条件。第三问收益很小，第四问改善更明显；这仍是已暴露数据上的选择结果，不能据此保证未见案例或官方环境收益。两题使用同一份已实际执行的B3文件，无需另造组合或把重复运行记成新证据。', '',
              '## 两条路线分别做了什么', '',
              '**路线A：保持原移动预算，改进测量角度。** 在父法测点之外，加入第二问解析角度和折中角度，用真实可行多边形与未来读数角带的交集比较定位半径。A1同时限制预计后续移动费用；A2去掉这一费用限制，检验单独追求精度的效果。A1对Q4只有0.012%的微小改善；A2虽减少请求与失败试清，却因后续移动增加而让两题都变慢，因此停止扩测。详见 [A报告](A_transfer/REPORT.md)。', '',
              '**路线B：把下一测点与后续清除费用一起设计。** 从真实首测可行多边形和当前位置出发，允许不同前进距离与侧移距离；用扩大角带覆盖连续未来读数区间，计算最坏定位半径的数值上界，同时估计移动、检测及后续清除费用。B1优先减小半径上界，B2优先降低预计费用，B3在B2基础上细化父法测点附近的前进/侧移组合。详见 [B报告](B_improved/REPORT.md)。', '',
              'B3只替换第二测点选择，沿用原可靠可行区域、20米清除条件、全域发现、有限光学覆盖、无信号恢复和退出流程。概率可见性与离散积分仅参与规划，不用于缩小可靠区域或读取隐藏真值。Q4仍可能收到no_signal。', '',
              '## 全部候选与负结果', '',
              '正数表示比配对父法更快。A2只有quick结果，不与其他候选的4800局合并均值直接排名。', '',
              '| 候选 | 集合 | Q3改善 | Q4改善 | 两批同向通过的题目 |',
              '|---|---|---:|---:|---|']
    for version in candidates:
        suite = 'quick' if version == 'A2' else 'exposed'
        values = [get(version, suite, m)['improvement_pct'] for m in (3, 4)]
        passed = [] if version == 'A2' else [f'Q{m}' for m in (3, 4)
                    if all(get(version, suite, m, b)['improvement_pct'] > 0 for b in ('v1', 'previous_final'))]
        lines.append(f'|{version}|{"quick 120" if suite == "quick" else "exposed 4800"}|{values[0]:+.6f}%|{values[1]:+.6f}%|{", ".join(passed) or "无"}|')
    lines += ['', '所有实际执行案例均全清并正常退出，失败行筛除数为0。A1、B1、B2的Q3均未满足两个批次同时改善，未作为Q3推荐。', '',
              '## B3分批结果与不稳定性', '',
              '| 题目 | 批次 | 案例数 | 父法秒/源 | B3秒/源 | 改善 |',
              '|---|---|---:|---:|---:|---:|']
    for mode, s in selection.items():
        for x in s['batches']:
            lines.append(f'|Q{mode}|{x["suite"]}|{x["cases"]}|{x["baseline_mean"]:.6f}|{x["candidate_mean"]:.6f}|{x["improvement_pct"]:.6f}%|')
    lines += ['', '按 `(批次, seed)` 聚类保留共享种子依赖，200个簇、2000次配对bootstrap的“候选−父法”均值差95%区间：', '']
    for mode, s in selection.items():
        x = s['metrics']; low, high = x['paired_seed_cluster_bootstrap_95pct_delta']
        lines.append(f'- Q{mode}：[{low:.6f}, {high:.6f}] 秒/源；{x["faster"]}/{x["equal"]}/{x["slower"]}局更快/相同/更慢，单局最大退步{x["largest_regression"]:.6f}秒/源。')
    lines += ['', 'Q3区间跨0，因此不能称为已证明稳定改善；Q4区间低于0，也只是这些暴露回归数据的描述，未校正多候选选择且不构成泛化证明。完整负例保存在原始行及独立复核报告中。', '',
              'B3合并两批后平均退步的场景（每个场景每题200局；正差为退步）：', '',
              '| 题目 | 场景 | 候选−父法秒/源 |', '|---|---|---:|']
    for mode in (3, 4):
        rows = results['B_improved/results/B3_exposed']['independent_audit']['comparisons']
        for x in rows:
            if x['mode'] == mode and x['suite'] == 'combined' and x['group'] != 'ALL' and x['delta'] > 0:
                lines.append(f'|Q{mode}|{x["group"]}|{x["delta"]:.6f}|')
    lines += ['', '## 几何与费用证据边界', '',
              '连续读数上界采用集合包含构造：把一个读数区间内的角带包在更宽的中点角带中，再取包围圆。自适应细分改善上界精度，但普通浮点和容差不等于区间算术认证；比较两个上界也不能自动证明真实最坏半径变小。费用估计使用9个积分位置、3个误差角及接收假设，预测费用下降不保证闭环实际费用下降。特别是Q4的距离≤5米费用分支未乘方向可见性，是乐观近似；真实后向近场仍可能无信号并触发父法恢复。', '',
              '诊断重放只读取公开轨迹。A1/A2各120局，B1/B3各24局，均逐局核对未插入记录器的虚拟费用等指标，确认记录不改变动作结果；它们是机制诊断，不替代完整回归。详细证据边界以 [数值复核](NUMERICAL_AUDIT.md) 和 [独立审阅](REVIEW.md) 为准。', '',
              '## 验证、执行量与入口', '',
              '- 冻结v1散列、14项单元测试、79项正常规则检查通过。父法quick实际重跑120局，与冻结父法缓存的逐局虚拟指标完全相同。',
              '- 5个候选共13次共同runner调用，实际执行19800局、3880134次请求。4个exposed结果各复用相同SHA的2400个full行，并各实际补跑另外2400局；已复用的9600行不重复计为执行。',
              '- 另有288局公开轨迹诊断及120局父法复现，共20208次场景运行。合成几何检查单列，不充当场景运行；没有新增盲测、官方Windows演练或正式测试。',
              '- `audit_campaign.py`重新按ID核对原始行、T/N分母、全清、分批结果、执行日志与复用SHA；本审计不运行求解器。结果见 [INDEPENDENT_AUDIT.json](INDEPENDENT_AUDIT.json)。',
              '- 各次现实耗时在summary中保留；并行计算与历史缓存不构成受控速度对照。本轮候选没有改动通信接口，无新增HTTP验证。',
              '- Q1/Q2已有成果、主solver与冻结物理/数据/规则保持原状。本轮推荐入口为 [B3_local_refinement.py](B_improved/B3_local_refinement.py)，自包含SHA256：`' + selection[3]['candidate_sha256'] + '`。选择登记见 [SELECTION.json](SELECTION.json)。', '',
              '从代码仓库目录复现（输出路径必须尚不存在；exposed复用刚执行的full）：', '',
              '```bash',
              'python3 experiments/20260913_q2_transfer/evaluate_transfer.py --candidate experiments/20260913_q2_transfer/B_improved/B3_local_refinement.py --suite quick --out results/q2_transfer_replay_quick',
              'python3 experiments/20260913_q2_transfer/evaluate_transfer.py --candidate experiments/20260913_q2_transfer/B_improved/B3_local_refinement.py --suite full --out results/q2_transfer_replay_full',
              'python3 experiments/20260913_q2_transfer/evaluate_transfer.py --candidate experiments/20260913_q2_transfer/B_improved/B3_local_refinement.py --suite exposed --reuse-full results/q2_transfer_replay_full --out results/q2_transfer_replay_exposed',
              '```', '',
              '本轮只提交实验候选、全部正负结果、复核与入口说明；未覆盖默认官方接入入口，亦未把本地成绩填作官方成绩。']
    (HERE / 'REPORT.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({'selection': {m: s['version'] for m, s in selection.items()},
                      'total_scene_runs': record['total_scene_runs']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
