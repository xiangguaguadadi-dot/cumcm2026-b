"""Freeze the verified non-RL recommendation and its source-backed report."""
from __future__ import annotations

import datetime
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def read(name):
    return json.loads((HERE / name).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind(name):
    return dict(path=name, sha256=sha(HERE / name))


def save(name, value):
    path = HERE / name
    assert not path.exists(), 'Preserve an existing freeze: ' + name
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    assert not (HERE / 'CURRENT_BEST.json').exists()
    assert not (HERE / 'REPORT.md').exists()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    build = read('final_candidates/combined.build.json')
    audit = read('verification/final_saved_rows.json')
    parity = read('verification/final_task_parity.json')
    trace = read('verification/final_trace_parity.json')
    checks = read('verification/final_checks_v3/summary.json')
    quick = read('verification/final_quick/summary.json')
    full = read('verification/final_full/summary.json')
    exposed = read('verification/final_exposed/summary.json')
    a1, a2 = read('A1/iteration_ledger.json'), read('A2/iteration_ledger.json')
    assert a1['best_round'] == 'r11' and 'STOPPED' in a1['decisions']['D3']
    assert a2['best'] == 'R2_rotation_insertion.py'
    candidate = 'final_candidates/combined.py'
    assert sha(HERE / candidate) == build['candidate_sha256'] == audit['candidate_sha256']
    for name in ('q3', 'q4'):
        assert sha(HERE / build[name + '_source']) == build[name + '_sha256']
    assert audit['status'] == 'consistent' and audit['row_count'] == 4800
    assert not audit['failed_candidate_ids']
    assert parity['status'] == 'exact_task_metric_parity' and parity['all_complete']
    assert trace['all_exact'] and trace['all_complete'] and trace['actual_runs'] == 48
    for record in (parity, trace):
        for path, expected in record['hashes'].items():
            path = Path(path)
            if not path.is_absolute():
                path = ROOT / path
            assert sha(path) == expected, str(path)
    assert checks['status'] == 'pass'
    for path, expected in checks['checked_source_sha256'].items():
        assert sha(ROOT / path) == expected
    for record, count in ((quick, 120), (full, 2400)):
        assert record['all_complete'] and record['runs'] == count and record['baseline_cached']
        assert record['candidate_sha256'] == build['candidate_sha256']
    assert exposed['all_complete'] and exposed['new_runs'] == 2400
    assert exposed['candidate_sha256'] == build['candidate_sha256']
    assert sha(HERE / 'verification/final_exposed/case_metrics.json') == audit['candidate_rows_sha256']
    assert sha(ROOT / 'evaluation/manifest_v1.json') == exposed['manifest_sha256']
    for branch, filename in [('A1', 'verification/A1_execution_cost_audit.json'),
                             ('A2', 'verification/A2_execution_cost_audit_v2.json')]:
        cost = read(filename)
        assert cost['status'] == 'reconciled'
        assert cost['ledger_sha256'] == sha(HERE / branch / 'iteration_ledger.json')
    metrics = [r for r in audit['comparisons'] if r['group'] == 'ALL']
    combined = {r['mode']: r for r in metrics if r['suite'] == 'combined'}
    assert all(r['candidate_complete'] == 2400 and r['source_count'] == 30970
               and r['candidate_mean'] < r['baseline_mean'] for r in combined.values())
    assert all(r['candidate_mean'] < r['baseline_mean'] for r in metrics)
    final_batches = []
    for name, summary, role in [('final_quick', quick, 'all candidate rows'),
                                 ('final_full', full, 'all candidate rows'),
                                 ('final_exposed', exposed, 'previous_final only; v1 reused')]:
        rows = read('verification/' + name + '/case_metrics.json')
        rows = [r for r in rows if r.get('variant') == 'candidate']
        if name == 'final_exposed':
            rows = [r for r in rows if r['exposure_suite'] == 'previous_final']
        expected = summary.get('runs', summary.get('new_runs'))
        assert len(rows) == len({r['case_id'] for r in rows}) == expected
        assert all(type(r['requests']) is int for r in rows)
        final_batches.append(dict(batch=name, runs=len(rows),
            recorded_requests=sum(r['requests'] for r in rows), membership=role,
            wall_s=summary.get('wall_seconds', summary.get('wall_seconds_new_runs')),
            source=bind('verification/' + name + '/case_metrics.json')))
    final_batches.append(dict(batch='trace_parity', runs=trace['actual_runs'],
        recorded_requests=trace['requests'], attempts=trace['requests'],
        accepted_requests=trace['accepted_requests'], wall_s=trace['wall_s'],
        source=bind('verification/final_trace_parity.json')))
    final_runs = sum(b['runs'] for b in final_batches)
    final_requests = sum(b['recorded_requests'] for b in final_batches)
    total_runs = a1['totals']['total_policy_runs'] + a2['actual_task_runs'] + final_runs
    total_requests = a1['totals']['total_requests'] + a2['execution_costs']['requests'] + final_requests
    reconstructed = [d for d in a1['diagnostics']
                     if 'reconstructed by deterministic replay' in d['evidence']]
    assert len(reconstructed) == 1 and reconstructed[0]['runs'] == 60
    reconstructed_requests = reconstructed[0]['requests']
    execution = dict(final_batches=final_batches, final_runs=final_runs,
        final_recorded_requests=final_requests,
        nonrl_total_policy_runs=total_runs, nonrl_total_recorded_requests=total_requests,
        a1_diagnostic_reconstructed_requests=reconstructed_requests,
        unique_exposed_regression_worlds=4800, additional_a2_development_worlds=96,
        attempted_request_overhead_unknown=True,
        boundary=f'Recorded v1 counts, including a separately identified {reconstructed_requests}-call deterministic '
                 'reconstruction. Not an exhaustive attempted-call ledger. No RL implementation costs included.')
    save('verification/final_execution_costs.json', execution)
    rl_status = read('RL/implementation/execution_status.json')
    save('verification/rl_status_at_nonrl_freeze.json', dict(as_of=now,
        source='RL/implementation/execution_status.json',
        source_sha256=sha(HERE / 'RL/implementation/execution_status.json'), status=rl_status))
    verification_names = ['verification/final_saved_rows.json', 'verification/final_task_parity.json',
        'verification/final_trace_parity.json', 'verification/final_checks_v3/summary.json',
        'verification/A1_execution_cost_audit.json', 'verification/A2_execution_cost_audit_v2.json',
        'verification/final_execution_costs.json', 'A1/results/r11_all_q3_cover_diagnostic.json',
        'verification/geometry20_round1_exact_counterexamples.json']
    record = dict(schema='cumcm-breakthrough-best-v1', frozen_at_utc=now,
        candidate=candidate, candidate_sha256=build['candidate_sha256'],
        q3_source=build['q3_source'], q3_sha256=build['q3_sha256'],
        q4_source=build['q4_source'], q4_sha256=build['q4_sha256'],
        status='verified_local_exposed_recommendation',
        deployment='Research candidate only; root solver.py and prior C7 unchanged; official execution not performed',
        evaluation_version='v1', evaluation_manifest_sha256=exposed['manifest_sha256'],
        cases_sha256=exposed['cases_sha256'], evidence_role='4800 exposed local regression cases, not new holdout',
        official_runs=0, new_sealed_cases=0, all_complete=True, compared_cases=4800,
        metrics=metrics, build=bind('final_candidates/combined.build.json'),
        results={scope:bind('verification/final_' + scope + '/case_metrics.json')
                 for scope in ('quick', 'full', 'exposed')},
        verification={Path(path).name:bind(path) for path in verification_names},
        branch_ledgers={b:bind(b + '/iteration_ledger.json') for b in ('A1', 'A2')},
        rl_status_at_freeze=bind('verification/rl_status_at_nonrl_freeze.json'),
        rl_scope='G0/G1 implementation separate, no learned policy in this candidate',
        report_generator_sha256=sha(__file__))
    save('CURRENT_BEST.json', record)
    lines = [
        '# 第六阶段非RL研究结果与最终组合', '',
        f'冻结时间：{now}。本报告只覆盖 `20260912_breakthrough` 的 A1/A2 和最终封装；RL 后续执行另记，其他并行目录不计入。', '',
        '## 结论与入口', '',
        '推荐本轮[单文件候选](final_candidates/combined.py)：Q3 使用 A1 R11，Q4 使用 A2 R2。4800 个已暴露本地案例全部清除、正常退出、无异常。主目录 `solver.py`、第一二问、原 C7 与冻结 v1 规则/数据未改；这是研究候选，不是已执行的官方提交。', '',
        '| 题目 | 本轮起点 C7（秒/源） | 最终组合（秒/源） | 相对改善 | 案例 / 实际源 |',
        '|---|---:|---:|---:|---:|',
    ]
    for mode, r in combined.items():
        lines.append(f"| Q{mode} | {r['baseline_mean']:.9f} | {r['candidate_mean']:.9f} | {r['improvement_pct']:.6f}% | 2400 / 30970 |")
    lines += ['', '指标为每局总虚拟时间 / 真实清除数，再对案例算术平均；不混合Q3/Q4、不使用加权综合分。quick 属于 full 子集，两批4800世界早已暴露；没有新盲测或官方结果。Q4仅0.1485%的增量应称边际改善。', '',
        f"候选 SHA256：`{build['candidate_sha256']}`。可机读状态为 [CURRENT_BEST.json](CURRENT_BEST.json)。`.build.json` 的“未执行”是创建时历史状态，后续验证以本冻结记录和下列独立结果为准。", '',
        '## 方法如何改变', '',
        '1. Q3：已知频道在扫描站的补测进入任务费用门控；一次定位轮次后回到全局任务重规划；把已付费服务停点或更短的进站落点纳入发现路线，但仅在连续覆盖充分条件通过时移动尚未扫描站点。未知频道仍实际测量，退出仍依赖真实 no_signal 证据。',
        '2. Q4：保留认证21点构型，在真实原点扫描后、其他站尚未访问时，按已发现源区域中心到未来站的连接距离代理选择共同旋转角。旋转保持覆盖几何，区域中心只作路线代理，不当成真源。',
        '3. 最终组合仅按题号派发到冻结父版本，未新增策略规则或学习网络。', '',
        'Q3证书是外包圆多边形与Voronoi单元的充分条件，数值实现保留安全余量，但不是区间算术认证。R11只对固定下一点的两段路径保证不增，真实新观测会改变后续任务，所以整局收益依靠完整回归检验。详细数学/实现边界见 [A1研究](A1/RESEARCH.md) 和 [A2几何说明](A2/GEOMETRY_PROOF.md)。', '',
        '## 负结果、停止与尾部风险', '',
        '本轮19个算法研究轮：A1 14轮、A2 5轮；R6未执行稿/错误修复不拆成三个独立算法轮。11个算法轮完成4800回归，9次历史保留含明确标注的边际增量。另有3轮几何布局研究；包装、规则和合成测试不算优化轮。', '',
        '- A1：R1、R2、R6b、R7、R9、R10、R11逐步保留；R3–R5三次未晋级停一个方向；最终R12/R13快测退步、R14两批完整回归均退步，三连败停止，冻结R11。R8虽合计略低但两批异号，未晋级。',
        '- A2：R1/R2保留；R3–R5连续三次不及R2而停止。20点搜索只对列出的180布局取得反例，不证明所有20点不可能；新21点布局的有限网格通过，但连续证明仍有未决单元，未部署。',
        '- A1 R6a 有59次 Q3 NameError；失败行与花费原样保留，修复重跑单独计费，未按成功子集排名。', '',
        '| 相对 C7 的逐局变化 | 更快 | 不变 | 更慢 | 最大单局退步（秒/源） | 最差局（秒/源） |',
        '|---|---:|---:|---:|---:|---:|',
    ]
    for mode, r in combined.items():
        lines.append(f"| Q{mode} | {r['faster']} | {r['equal']} | {r['slower']} | {r['largest_regression']:.6f} | {r['worst_candidate']:.6f} |")
    lines += ['', '均值改善不等于逐局、最差局或每类场景都改善。所有场景和两批配对保留在 [独立逐行复算](verification/final_saved_rows.json)；各轮研究路径和逐案结果见 [A1报告](A1/REPORT.md)、[A2报告](A2/REPORT.md)。', '',
        '## 组合实际验证', '',
        '- 冻结规则14项、正常物理79项、精确几何反例6项、RL方案合成合同25项、封装合成检查8项通过，见 [final_checks_v3](verification/final_checks_v3/summary.json)。v2封装测试曾因macOS临时目录别名导致5项夹具失败；只修复夹具路径归一化，旧失败结果保留，未修改候选或物理规则。',
        '- 组合实际执行 quick 120局、full 2400局、另一暴露批次2400局；最后合并4800行，没有把缓存行算成新执行。',
        f"- [4800逐行封装等价](verification/final_task_parity.json)：{len(parity['compared_fields'])}个任务字段无差异，嵌入父源码逐字相同；不要求机器现实耗时相等。",
        '- [24例请求轨迹等价](verification/final_trace_parity.json)：最终组合与父法共48次运行、9856次尝试均接受；除两种机器时钟字段外，请求和响应全等。该抽样不是4800全轨迹证明。',
        '- A1另重放全部2400个Q3世界，949局出现2184次认证移站；每个相应未知频道的新位置measure、每个退出的真实no_signal都在环境日志中有见证，虚拟时间和v1请求数与保存行相同。它复用候选证书代码，不是独立几何实现。', '',
        '## 成本与证据覆盖', '',
        '| 范围 | 实际策略执行 | v1口径记录请求 |', '|---|---:|---:|',
        f"| A1（含诊断重放） | {a1['totals']['total_policy_runs']} | {a1['totals']['total_requests']} |",
        f"| A2（含开发/封装） | {a2['actual_task_runs']} | {a2['execution_costs']['requests']} |",
        f'| 最终组合及轨迹等价 | {final_runs} | {final_requests} |',
        f'| 非RL合计 | {total_runs} | {total_requests} |', '',
        f'请求口径是 measures + clear_attempts + entered + normal_exit，不能排除历史批次未记录的参数/状态拒绝尝试。A1其中{reconstructed_requests}条为首次诊断日志读取失败后的同源确定性重放估算；不能当成第一次完整请求日志。仅24例轨迹样本另有全attempt记录。源码检查、论文阅读、合成几何、规则检查、协调与分析不在这些任务成本内；各轮墙钟存在并发负载，不用于宣称受控CPU加速。独立成本复算与最终批次划分见 [成本账](verification/final_execution_costs.json)。', '',
        '独立回归世界仍为4800，A2另有96个已暴露开发世界；重复执行不增加独立样本数。新增最终密封世界0，官方执行0。RL G0/G1的72个预登记诊断世界和后续费用完全另计。', '',
        '## RL方案与后续执行', '',
        '已交付 [BC-RPI机制方案](RL/PROPOSAL.md)、[实现合同](RL/implementation_spec.md)、[四轮质疑与回应](RL/review_log.md)、[协调者验收](RL_VERIFIER_ACCEPTANCE.md)。方案把学习对象改为有限、可回退的源服务操作；单轮回报监督与后续策略迭代必须分开比较，不把模仿/额外数据收益直接称RL改进。', '',
        f"本报告冻结时，后续执行状态为 `{rl_status.get('status')}`，网络训练运行数为 `{rl_status.get('network_training_runs')}`；这是 [固定时点快照](verification/rl_status_at_nonrl_freeze.json)，不是未来状态承诺。用户已批准原Agent执行G0/G1，350000调用/2000执行上限、零网络训练；具体进度看 [实时执行状态](RL/implementation/execution_status.json)。G0通过并复核后才进入G1，G2训练、发布验证和官方执行均未自动启动。", '',
        '本轮文献分层：A1 3篇核心定向阅读+1篇发现，A2 5篇核心指定段落+1篇扩展，RL 9篇核心指定章节+7篇扩展；这些分支数字不能不去重直接当独立论文总数。RL相对旧41篇有7篇新增、并集48，绝不是本轮48篇全文精读。来源身份、实际读取范围、迁移假设及负结果分别保留在各分支literature与研究报告。', '',
        '## 可复算入口', '',
        '本报告由 `freeze_best.py` 从最终保存行审计和配对结果生成，不重跑求解器。`audit_rows.py` 复算ID、分母、完整性与每批每组；`audit_execution_costs.py` 核对批次实际成员、排除缓存复用，保留失败。重跑策略须新建输出目录，不覆盖本轮结果。', '',
        '只有模拟规则内的全清与本地均值改善已得到支持；官方分布、官方接口时序、Windows演练/正式结果与新盲测泛化尚未验证。', '',
    ]
    (HERE / 'REPORT.md').write_text('\n'.join(lines))
    print(json.dumps(dict(status=record['status'], candidate_sha256=record['candidate_sha256'],
        final_runs=final_runs, final_recorded_requests=final_requests,
        nonrl_total_policy_runs=total_runs, nonrl_total_recorded_requests=total_requests), ensure_ascii=False))


if __name__ == '__main__':
    main()
