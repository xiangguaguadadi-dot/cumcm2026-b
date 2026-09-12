#!/usr/bin/env python3
"""Package completed, independently audited G0/G1 evidence; never runs a policy."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import gzip
import hashlib
import io
import json
from pathlib import Path
import time
import unittest

ROOT = Path(__file__).resolve().parent
IMPL = ROOT / 'RL/implementation'
VERIFY = ROOT / 'verification'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, value):
    if path.exists():
        raise FileExistsError('Preserve the previous final evidence: ' + str(path))
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    g1_audit_path = VERIFY / 'rl_g1_headroom_v1.json'
    record_audit_path = VERIFY / 'rl_g1_records_v1.json'
    g1 = read(g1_audit_path)
    records = read(record_audit_path)
    assert g1['status'] == 'complete_24_world_finite_headroom_audited'
    assert g1['fully_audited_complete_worlds'] == 24 and g1['outcomes_checked'] == 1554
    assert g1['cumulative_counts'] == records['counts']
    assert max(g1['relative_improvement_pct'].values()) < 2
    for source, expected in g1['source_sha256'].items():
        assert sha(Path(source)) == expected, source
    stage = IMPL / 'results/g1_v1'
    rows = read(stage / 'world_results.json')['worlds']
    indexed = read(stage / 'index.json')['runs']
    assert len(rows) == 24 and all(r['status'] == 'complete' for r in rows)
    assert all(r['success'] for r in indexed)
    with gzip.open(VERIFY / 'rl_g0g1_final_ledger_v1/execution_calls.jsonl.gz', 'rt') as stream:
        journal = [json.loads(line) for line in stream]
    stage_journal = [r for r in journal if r['run_id'].startswith('g1_v1_')]
    first, last = stage_journal[0]['recorded_utc'], stage_journal[-1]['recorded_utc']
    elapsed = (datetime.fromisoformat(last) - datetime.fromisoformat(first)).total_seconds()
    suite = unittest.defaultTestLoader.discover(str(ROOT), pattern='test_audit_*.py')
    output = io.StringIO()
    started = time.monotonic()
    tests = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    pure = dict(schema='bc-rpi-independent-audit-pure-tests-v1', tests=tests.testsRun,
                failures=len(tests.failures), errors=len(tests.errors), success=tests.wasSuccessful(),
                wall_s=time.monotonic()-started, actual_environment_calls=0,
                actual_environment_instances=0, log=output.getvalue(),
                test_source_sha256={p.name: sha(p) for p in sorted(ROOT.glob('test_audit_*.py'))})
    assert pure['success'] and pure['tests'] == 140
    write_new(VERIFY / 'rl_final_audit_pure_tests_v1.json', pure)
    result = dict(schema='bc-rpi-g0g1-final-result-v1', status='completed_at_registered_stop_gate',
        decision='stop_current_finite_action_space_without_neural_training',
        basis='Both complete 24-world finite privileged diagnostics are below the preregistered 2 percent headroom threshold.',
        g0_accepted=True, g1_complete=True, g2_started=False, neural_training_runs=0, official_runs=0,
        unique_g1_worlds=24, unique_g1_sources=sum(r['n'] for r in rows),
        means_seconds_per_source=g1['means_seconds_per_source'], relative_improvement_pct=g1['relative_improvement_pct'],
        g1_source_states=dict(o1=sum(r['o1_states'] for r in rows), o2=sum(r['o2_states'] for r in rows)),
        g1_counterfactual_branches=dict(o1=sum(r['o1_branches'] for r in rows), o2=sum(r['o2_branches'] for r in rows)),
        selected_interventions=dict(o1=dict(Counter(len(r['o1_plan']) for r in rows)),
                                    o2=dict(Counter(len(r['o2_plan']) for r in rows))),
        g1_execution_families=dict(Counter(r['family'] for r in indexed)),
        g1_calls_by_action=dict(Counter(r['action'] for r in stage_journal if r['event'] == 'call_start')),
        g1_actual_calls=g1['g1_actual_calls'], g1_actual_executions=g1['g1_actual_executions'],
        cumulative_counts=g1['cumulative_counts'], g1_first_actual_run_utc=first, g1_last_settled_run_utc=last,
        g1_elapsed_research_wall_s=elapsed, worker_cpu_s=None,
        deployment_sha256=read(stage / 'source_freeze.json')['deploy_implementation_sha256'],
        continuation_policy_sha256=read(stage / 'registration.json')['continuation_policy_sha256'],
        evidence={str(p.relative_to(ROOT)):sha(p) for p in (g1_audit_path, record_audit_path,
            VERIFY/'rl_g0_acceptance_v1.json', VERIFY/'rl_g0_final_independent_v3.json',
            VERIFY/'rl_g0g1_final_ledger_v1/snapshot_manifest.json', VERIFY/'rl_final_audit_pure_tests_v1.json',
            stage/'source_freeze.json', stage/'source_archive.json', stage/'input_archive.json', stage/'registration.json')},
        evidence_limits=[
            'O1 is hindsight-optimal only for up to four uniformly sampled C7 source-service boundaries and the retained action set.',
            'O2 is greedy along the actual first-intervention trajectory, not a global two-step optimum; four zero-O1 worlds did not search synergistic pairs.',
            'No observation-only actor was fitted; oracle decisions are not deployable learned-policy performance.',
            'The 24 registered probe worlds are local exposed diagnostics, not blind final or official tests.',
            'Latest non-RL Q4 R2 was not rerun on these G1 worlds; no superiority to that entry is claimed.',
            'Worker CPU decomposition remains unknown; clone_cpu_wall_s is wall time, not CPU time.',
            'An independent agent reviewed G1 before execution; final all-record recomputation was performed by the coordinator. A second final manual all-record review was not completed after agent quota exhaustion.'
        ])
    write_new(ROOT/'RL_EXECUTION_RESULT.json', result)
    m, g = result['means_seconds_per_source'], result['relative_improvement_pct']
    report = f'''# BC-RPI G0/G1 执行结论

2026-09-12。**G0 正确性验收通过，G1 完整执行后停止当前有限动作空间，不进入网络训练。** 原因是两个事后特权诊断的改善率都低于事先登记的 2% 余量门槛。不是预算未决，也不是训练失败；本轮没有拟合网络。

## 结果

24 个登记 Q4 world、12 场景各 2 个、共 319 个独特源。下面先算每个 world 的完整虚拟时间/真实源数，再对 24 个 world 等权平均：

|策略或诊断|平均秒/源|相对同批 C7 改善|
|---|---:|---:|
|C7 教师|{m['c7']:.9f}|—|
|O1：有限单干预事后最优|{m['o1']:.9f}|{g['o1']:.6f}%|
|O2：双干预贪心事后诊断|{m['o2']:.9f}|{g['o2']:.6f}%|

公式为 `(mean(C7 T/N) - mean(O T/N)) / mean(C7 T/N)`，不是把各局改善率平均，也不把不同源数的所有局直接合成一个总 T/总 N。

O1 在完整 C7 轨迹上均匀抽取共 96 个源服务入口，实际执行 806 条完整反事实续局；O2 只在选中第一次干预后完整重放产生的真实轨迹中抽取共 80 个后续入口，实际执行 676 条续局。每个抽中入口都覆盖全部保留动作（含 A0），没有截尾或只挑成功动作。24 次 C7 roll-in、24 次 O1 整局回放、24 次 O2 整局回放，加上 1482 次 suffix，共 1554 次 G1 执行，全部正常全清、无失败分支。

O1 的 20 个 world 选 1 次干预、4 个选 0 次；O2 的 18 个 world 选 2 次、2 个选 1 次、4 个选 0 次。O1 选零时，贪心 O2 不再搜索协同双步，因此本结果不能证明所有双干预计划都低于 2%。O1 也只对所采 4 个边界和有限动作集最优，不对所有时刻/所有动作最优。

## 正确性与独立复核

[G0 验收说明](verification/RL_G0_REVIEW.md) 包含 48 对 C7 等价、12 对最新 Q3 直通等价、21 次额外真实夹具和 117 项断言。部分动作中断不返槽、未知接受禁止盲重试、near 附加 clear 与完整 fallback 尾费均保留。

G1 的[独立逐记录审计](verification/rl_g1_headroom_v1.json)没有导入策略、模拟器或原 evaluator：从实际宏轨迹重新构建所有源入口及均匀抽样，核对 world 身份集合、每个完整动作 bundle、O2 的真实前缀/槽位、全部 A0 续局、整数微秒有限最小值、48 次整局回放及最终等权均值。底层[账本审计](verification/rl_g1_records_v1.json)逐请求重算物理费用并核对宏/前缀/尾段分区。继承前缀进入完整成绩，但不重复虚增实际调用。

独立审计器共 140 项纯合成测试通过（账本/G0 93 项、G1 47 项），见[纯测试记录](verification/rl_final_audit_pure_tests_v1.json)。执行实现 G1 启动前另有 28 项纯测试通过；纯测试均不计作环境样本。G1 启动前由另一子 Agent 只读审查；最后全数据复算由协调者完成，子 Agent 额度耗尽后的第二份最终人工全量复核没有完成，不冒称多方完整最终验收。

## 实际成本

|范围|实际执行|实际业务调用|
|---|---:|---:|
|G0（含历史错误与真实夹具）|142|37,072|
|G1（72 full + 1482 suffix）|1554|160,384|
|累计|1696|197,456|

累计 197,456 = 197,454 接受 + 2 已证拒绝 + 0 未知；全部 1696 次启动均已结算，无活动进程/未决调用。G0 预期失败与输出路径错误后的已付请求仍在账本，未从分母扣除。G1 本身没有拒绝/异常，160,384 次为 enter 72、measure 146,025、clear 12,733、exit 1554。

G1 首次真实执行至最后结算为 {first} 至 {last}，共 {elapsed:.6f} 秒研究墙钟（约 {elapsed/60:.2f} 分钟）。这不是部署延迟；包括串行反事实采样/记录等研究工作。worker CPU 分项尚未采集，保留 `null`；`clone_cpu_wall_s` 实际记录的是墙钟，不能当 CPU，更不能把未知项算零。

全程未达到累计 350,000 调用或 2,000 执行上限；按“完整集合已结束且余量不足”停止，不因剩余额度擅自进入 G2。未训练、未校准、未运行新密封最终集、未操作官方 Windows 接口。

## 结论边界与保留方法

这说明按当前预登记判据，没有足够理由继续训练**这组有限源服务替代动作**；不说明所有 RL 或更大动作空间无效，也不证明公开历史能预测这 1.715% 的事后收益。不能把 O1/O2 写成已部署模型效果。

机制锚是同批 C7。最新非 RL Q4 R2 未在这 24 个 G1 world 上重跑，所以没有宣称超越本轮最新非 RL 方法。部署推荐仍保持已冻结的 [Q3 R11 + Q4 R2](final_candidates/combined.py)，本轮学习实验没有产生新的晋级候选；Q1/Q2、主 solver、C7 与冻结 v1 均未修改。

## 可复查入口

- [机器可读最终结果与证据 hash](RL_EXECUTION_RESULT.json)
- [G1 全部世界结果](RL/implementation/results/g1_v1/world_results.json)、[全部运行索引](RL/implementation/results/g1_v1/index.json)
- [G0/G1 完整压缩日志快照](verification/rl_g0g1_final_ledger_v1/snapshot_manifest.json)：原始 journal 不删除；仓库保存逐字节等价 gzip 与原文 hash，不上传重复未压缩大文件。
- [已归档实现源码](RL/implementation/results/g1_v1/source_archive.json)、[输入归档](RL/implementation/results/g1_v1/input_archive.json)、[预登记](RL/implementation/results/g1_v1/registration.json)
- [独立审计源码](audit_g1_headroom.py)、[逐调用审计源码](audit_rl_execution.py)、[封装脚本](finalize_rl_execution.py)

这些是本地诊断证据，不是官方成绩。数据验证流程促使本报告明确区分实际请求、继承前缀、部分夹具、纯测试、特权余量与可部署学习收益。
'''
    target = ROOT/'RL_EXECUTION_REPORT.md'
    if target.exists():
        raise FileExistsError('Preserve previous report')
    target.write_text(report)
    print(json.dumps(dict(status=result['status'], decision=result['decision'], pure_tests=pure['tests'],
                          means=m, improvements=g, calls=result['cumulative_counts']['business_calls']), indent=2))


if __name__ == '__main__':
    main()
