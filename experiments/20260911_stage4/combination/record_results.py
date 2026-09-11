"""Summarize existing C1 rows; this script executes no policy tasks."""
import importlib.util
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
ROOT = HERE.parents[2]

def read(p):
    return json.loads(p.read_text())

def save(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def main():
    spec = importlib.util.spec_from_file_location('stage4_exposed', STAGE / 'evaluate_exposed.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    rows = read(HERE / 'results/c1_exposed/case_metrics.json')
    parents = {
        'S1': read(STAGE / 'baseline/expected_rows.json'),
        'E1_R1': read(ROOT / 'experiments/E1_refine/results/r1_exposed/case_metrics.json'),
        'E2_station': read(ROOT / 'experiments/E2_refine/results/r1_station_only_exposed/case_metrics.json'),
    }
    comparisons = {name: helper.compare(rows, refs) for name, refs in parents.items()}
    save(HERE / 'results/c1_parent_comparisons.json', comparisons)
    decomposition = []
    for name, rr in {**parents, 'C1_combined': rows}.items():
        part = [r for r in rr if r['mode'] == 4]
        assert all(helper.valid(r) for r in part)
        total = statistics.mean(r['average_clear_time_s'] for r in part)
        movement = statistics.mean(r['distance_m']/5/r['source_count'] for r in part)
        decomposition.append(dict(candidate=name, mean_s_per_source=total,
                                  movement_s_per_source=movement, other_s_per_source=total-movement,
                                  mean_requests=statistics.mean(r['requests'] for r in part)))
    save(HERE / 'results/c1_cost_decomposition.json', decomposition)
    summary = read(HERE / 'results/c1_exposed/summary.json')
    budget = read(HERE / 'execution_budget.json')
    budget.update(regression_actual_runs=4920, regression_unique_cases=4800,
                  regression_breakdown={'quick': 120, 'v1_full': 2400, 'old_final': 2400},
                  total_actual_runs=budget['development_actual_runs']+4920,
                  rule_tests=12, v1_rows_reused_by_exposed=2400,
                  exposed_new_runs_wall_seconds=summary['wall_seconds_new_runs'])
    save(HERE / 'execution_budget.json', budget)
    mode_rows = [r for r in comparisons['S1'] if r['suite']=='combined' and r['group']=='ALL']
    best = dict(fixed_baseline='S1', current_best='C1_combined',
                modes={str(r['mode']):r['candidate_mean_s_per_source'] for r in mode_rows},
                candidate='combination/snapshots/C1_combined.py', candidate_sha256=summary['candidate_sha256'],
                dependencies={}, data_role='4800 exposed local regression',
                source_count_each_mode=30970,
                retained_alternative={'candidate':'../E2_refine/snapshots/r1_station_only.py',
                 'Q4_mean':466.8426814648249,'reason':'Slightly worse mean but fewer single-case regressions than C1.'})
    save(STAGE / 'CURRENT_BEST.json', best)
    lines = ['# C1组合：已完整验证并保留', '',
             'E1条件发现路线与E2站内费用门控在原S1相同几何组件上组合。两个组件关闭开关在同96开发案例分别恢复对应父法的逐局动作指标。开发结果不能代替下表的完整回归。', '',
             '4800已暴露本地案例全部正常退出、全部清除；两题各2400局、30970个源。第三问逐局保持S1，均值235.876945812秒/源。下表是第四问，秒/源按每局指标取算术均值。', '',
             '| 对照 | 对照均值 | C1均值 | C1差值 | 快/同/慢 |',
             '|---|---:|---:|---:|---|']
    for name, compare in comparisons.items():
        r = next(r for r in compare if r['suite']=='combined' and r['group']=='ALL' and r['mode']==4)
        lines.append(f'| {name} | {r["baseline_mean_s_per_source"]:.6f} | {r["candidate_mean_s_per_source"]:.6f} | {r["delta_s_per_source"]:+.6f} | {r["faster"]}/{r["equal"]}/{r["slower"]} |')
    lines += ['', 'C1相对S1改善1.8931%，相对E2单法也有均值收益，但单局退步增多。E2作为较少改变单局表现的备选保留；不宣称C1逐局占优。', '',
              '| 策略 | 总耗时 | 移动 | 其他动作 | 请求/局 |', '|---|---:|---:|---:|---:|']
    for r in decomposition:
        lines.append(f'| {r["candidate"]} | {r["mean_s_per_source"]:.6f} | {r["movement_s_per_source"]:.6f} | {r["other_s_per_source"]:.6f} | {r["mean_requests"]:.3f} |')
    lines += ['', '## 场景退步', '']
    for name, compare in comparisons.items():
        worse=[r for r in compare if r['suite']=='combined' and r['mode']==4 and r['group']!='ALL' and r['delta_s_per_source']>1e-8]
        lines.append(name+'：'+('；'.join(f'{r["group"]} +{r["delta_s_per_source"]:.6f}秒/源' for r in worse) if worse else '12组场景均值均未退步。'))
    q4=[r for r in rows if r['mode']==4]
    bindex={r['case_id']:r for r in parents['S1']}
    worst=max(q4,key=lambda r:r['average_clear_time_s']-bindex[r['case_id']]['average_clear_time_s'])
    lines += ['', f'相对S1最大单局回退：{worst["case_id"]}，+{worst["average_clear_time_s"]-bindex[worst["case_id"]]["average_clear_time_s"]:.6f}秒/源。', '',
              '## 机制与边界', '',
              '组合仅替换下一任务的规划排序与覆盖站已知频道的补测决策。规划概率和未来动作费用都是代理，不裁掉可靠可行区域，不凭估计源数终止。未知频道原覆盖动作、原光学兜底、50小时保护与完整退出条件均继承。未修改HTTP、通信重试、并发或官方环境。', '',
              '开发实际576次任务（96案例×6配置，包含两个关闭开关）；完整回归实际4920次（quick120、v1 2400、旧final2400），共5496次。quick为v1子集；生成4800比较时复用已执行v1行，不重复运行。12项规则测试通过；未新增最终留出。', '',
              '这些都是自建模型上的已暴露研发回归；官方Windows演练尚未运行。本批并发期间的程序运行时间保存在原始行中，不据此做受控速度排名。', '',
              '代码：[C1_combined.py](snapshots/C1_combined.py)；[完整三父法配对表](results/c1_parent_comparisons.json)；[成本分解](results/c1_cost_decomposition.json)；[原始4800行](results/c1_exposed/case_metrics.json)；[执行预算](execution_budget.json)。', '',
              'SHA256：`'+summary['candidate_sha256']+'`。']
    (HERE / 'REPORT.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(best, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
