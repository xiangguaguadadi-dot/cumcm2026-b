#!/usr/bin/env python3
"""Finalize already completed/audited round one; JSON/gzip reads only.

No environment, model, Torch, training module, subprocess or Git is imported or
executed. All eight audit gates and their source hashes must pass. Existing
outputs are never overwritten. The coordinator invokes this only after final
settlement; merely importing the module never writes an artifact.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SEEDS = (912101, 912102, 912103)
ARMS = ('c7', 'q4_r2', *(f'neural_{s}' for s in SEEDS))
EXPECTED_ROLES = {'fit': 24, 'fit_val': 12, 'calibration': 24, 'development': 120}
AUDITS = {
    'development': ('rl_round1_development_v1.json', 'development_saved_rows_verified'),
    'forwards': ('rl_round1_development_forwards_v1.json', 'all_saved_public_online_inputs_and_frozen_forwards_verified'),
    'records': ('rl_round1_final_records_v1.json', 'all_recorded_business_calls_and_saved_outcomes_reconciled'),
    'fit': ('rl_round1_fitted_models_v1.json', 'three_real_fits_and_fit_val_selection_verified'),
    'calibration': ('rl_round1_calibration_v1.json', '24_world_three_model_calibration_verified'),
    'labels': ('rl_round1_labels_v1.json', 'complete_shared_first_round_labels_verified'),
    'public': ('rl_round1_public_export_v3.json', 'all_public_features_labels_and_origins_verified'),
    'pure_tests': ('rl_round1_final_pure_tests_v1.json', 'all_selected_pure_checks_passed'),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value, *, nonnegative=False):
    require(type(value) in (int, float) and math.isfinite(value)
            and (not nonnegative or value >= 0), 'Invalid finite numeric evidence')
    return value


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


class Evidence:
    def __init__(self):
        self.hashes = {}

    def pin(self, path, expected):
        path = str(Path(path).resolve())
        require(type(expected) is str and len(expected) == 64, 'Malformed evidence SHA')
        require(path not in self.hashes or self.hashes[path] == expected,
                'Conflicting audit source SHA: '+path)
        self.hashes[path] = expected

    def read(self, path):
        path = Path(path).resolve()
        self.pin(path, sha256(path))
        opener = gzip.open if path.suffix == '.gz' else open
        with opener(path, 'rt', encoding='utf-8') as stream:
            return json.load(stream)

    def bind(self, audit, path):
        path = str(Path(path).resolve())
        require(path in audit['source_sha256'], 'Required input not bound by its audit: '+path)
        self.pin(path, audit['source_sha256'][path])

    def verify(self):
        for path, expected in self.hashes.items():
            require(sha256(path) == expected, 'Audited evidence changed: '+path)


def check_pure_tests(pure):
    require(pure['schema'] == 'bc-rpi-r1-final-pure-verification-v1'
            and pure['actual_environment_executions'] == 0 and pure['actual_campaign_optimizer_updates'] == 0,
            'Pure tests were not zero-campaign-execution checks')
    groups = pure['groups']
    require(len(groups) == 2 and {r['group'] for r in groups} == {'independent_auditors', 'implementation_contracts'}
            and all(r['success'] is True and type(r['tests']) is int and r['tests'] > 0 for r in groups)
            and pure['unittest_tests'] == sum(r['tests'] for r in groups), 'Incomplete final pure-test groups')
    stats = pure['statistics_self_test']
    require(stats['status'] == 'synthetic_saved_row_self_tests_passed'
            and stats['actual_environment_calls'] == stats['actual_optimizer_updates'] == 0
            and stats['bootstrap_replicates'] == 10000, 'Statistical synthetic self-test failed')
    frozen = pure['original_frozen_evaluation_check']
    require(frozen['exit_code'] == 0 and frozen['stdout'].strip() == 'Frozen v1 hashes verified'
            and frozen['stderr'] == '', 'Original frozen evaluation check failed')


def build(campaign, paths):
    campaign = Path(campaign).resolve()
    evidence = Evidence()
    evidence.pin(__file__, sha256(__file__))
    audits = {name: evidence.read(path) for name, path in paths.items()}
    for name, audit in audits.items():
        require(audit['status'] == AUDITS[name][1], 'Audit not complete: '+name)
        require(type(audit['source_sha256']) is dict and audit['source_sha256'], 'Audit lacks source pins: '+name)
        for path, expected in audit['source_sha256'].items():
            evidence.pin(path, expected)
    check_pure_tests(audits['pure_tests'])
    dev, forwards, records, fit, cal, labels = (audits[k] for k in ('development', 'forwards', 'records', 'fit', 'calibration', 'labels'))
    require(dev['phase'] == 'development' and dev['worlds'] == 120 and dev['actual_executions'] == 600
            and dev['arms'] == list(ARMS), 'Development not complete 120 x 5')
    require([r['arm'] for r in dev['arm_summaries']] == list(ARMS)
            and len(dev['paired_comparisons']) == len(dev['bootstrap']['comparisons']) == 6
            and len(dev['by_group_comparisons']) == 12, 'Missing audited result sections')
    comparisons = []
    for row, interval in zip(dev['paired_comparisons'], dev['bootstrap']['comparisons']):
        require((row['candidate'], row['control']) == (interval['candidate'], interval['control']), 'Misbound comparison interval')
        comparisons.append(dict(row, bootstrap=interval))
    stage = Path(dev['stage_directory']).resolve()
    require(stage.is_relative_to(campaign/'results'), 'Development belongs to another campaign')
    evidence.bind(forwards, stage/'index.json')
    require(forwards['counts']['neural_episodes'] == 360 and len(forwards['episode_checks']) == 360
            and len({r['run_id'] for r in forwards['episode_checks']}) == 360,
            'Online forward audit lacks all 360 neural episodes')
    telemetry = dev['selector_telemetry']
    require(set(telemetry) == set(ARMS[2:])
            and sum(r['scored_decisions'] for r in telemetry.values()) == forwards['counts']['successful_forwards']
            and sum(r['overrides'] for r in telemetry.values()) == forwards['counts']['selected_interventions'],
            'Statistics and actual independent online forwards disagree')
    require(fit['initialization_count'] == 3 and fit['optimizer_updates'] == 180
            and fit['checkpoints_verified'] == 9 and fit['parameters_per_model'] == 61121
            and [r['seed'] for r in fit['results']] == list(SEEDS), 'Incomplete real fitting audit')
    require(cal['world_count'] == 24 and cal['state_count'] == 48 and cal['unique_suffix_executions'] == 87
            and cal['actual_executions'] == 111, 'Incomplete calibration audit')
    role_counts = {role: dict(worlds=len(rows), states=sum(r['states'] for r in rows),
        nonreference_labels=sum(r['candidates']-r['states'] for r in rows)) for role in ('fit', 'fit_val')
        for rows in [[r for r in labels['world_checks'] if r['role'] == role]]}
    require(role_counts == {'fit': dict(worlds=24, states=96, nonreference_labels=702),
                           'fit_val': dict(worlds=12, states=48, nonreference_labels=358)}, 'Label-role denominators changed')
    require(audits['public']['counts']['fit'] == 24 and audits['public']['counts']['fit_val'] == 12
            and audits['public']['counts']['state_bundles'] == 144
            and audits['public']['counts']['nonreference_labels'] == 1060, 'Public export denominator changed')
    registration = evidence.read(campaign/'registration.json')
    worlds = evidence.read(campaign/'world_manifest.json')['worlds']
    require(registration['role_counts'] == EXPECTED_ROLES and registration['neural_seeds'] == list(SEEDS)
            and all(registration[k] is True for k in ('no_further_rounds', 'no_official', 'no_sealed_final'))
            and sha256(campaign/'world_manifest.json') == registration['manifest_sha256']
            and Counter(w['role'] for w in worlds) == EXPECTED_ROLES
            and len({w['world_sha256'] for w in worlds}) == len(worlds) == 180, 'New-world population/scope changed')
    status = evidence.read(campaign/'execution_status.json')
    recorded_statuses = [p for p in records['source_sha256'] if Path(p).name == 'execution_status.json']
    require(len(recorded_statuses) == 1 and records['source_sha256'][recorded_statuses[0]] == sha256(campaign/'execution_status.json'),
            'Live final ledger differs from the independently audited snapshot')
    require(status['status'] == 'development_complete_no_tuning_or_promotion' and status['current_run'] is None
            and status['reserved_calls'] == 0 and status['unknown_cost_calls'] == 0
            and status['stopped_for_unknown_acceptance'] is False
            and status['network_training_runs'] == status['network_training_completed'] == 3
            and status['fit_updates'] == 180, 'Campaign not completely settled')
    counts = records['counts']
    for key in ('business_calls', 'accepted_calls', 'executions_started', 'executions_completed', 'failed_runs', 'full_runs', 'suffix_runs'):
        require(counts.get(key, 0) == status[key], 'Final ledger counter differs from records: '+key)
    require(records['outcomes_checked'] == status['executions_completed'] == status['executions_started'] == 1975
            and counts['unique_worlds_actually_started'] == 192
            and all(counts.get(k, 0) == 0 for k in ('unfinished_runs', 'unresolved_calls', 'unknown_cost_runs', 'unknown_calls')),
            'Incomplete/excess actual execution population')
    require(status['carry_in'] == registration['carry_in'] == {'business_calls': 197456, 'executions_started': 1696},
            'Old carry-in changed')
    summaries = {}
    stage_statuses = {'labels': ('labels_v1', 'labels_complete_no_fit_yet', 36, 1240),
        'calibration': ('calibration_v1', 'calibration_complete_three_frozen_margins', 24, 111),
        'compatibility': ('compatibility_v1', 'compatibility_complete_exact_teacher_equivalence', 12, 24),
        'development': (stage.name, 'development_complete_no_tuning_or_promotion', 120, 600)}
    costs = []
    require(set(records['per_recorded_stage']) == set(stage_statuses), 'Unexpected actual execution stage')
    for phase, (directory, expected_status, nworlds, nruns) in stage_statuses.items():
        path = campaign/'results'/directory/'summary.json'
        summary = evidence.read(path); summaries[phase] = summary
        tally = records['per_recorded_stage'][phase]
        require(summary['status'] == expected_status and summary['completed_worlds'] == summary['registered_worlds'] == nworlds
                and summary['actual_executions'] == tally['executions'] == status['phase_executions'][phase] == nruns
                and summary['actual_calls'] == tally['business_calls'] == status['phase_calls'][phase], 'Incomplete stage: '+phase)
        phase_runs = [r for r in status['runs'] if r['metadata']['stage'] == phase]
        require(len(phase_runs) == nruns, 'Missing paid-run wall-time population')
        costs.append(dict(stage=phase, worlds=nworlds, business_calls=tally['business_calls'], executions=nruns,
            full=tally.get('full', 0), suffix=tally.get('suffix', 0), failed_runs=tally.get('failed_runs', 0),
            sum_recorded_execution_wall_s=math.fsum(finite(r['actual_wall_s'], nonnegative=True) for r in phase_runs)))
    require(sum(r['business_calls'] for r in costs) == status['business_calls']
            and dev['actual_business_calls'] == summaries['development']['actual_calls'], 'Stage costs do not sum to campaign')
    fit_summary = evidence.read(campaign/'results/fit_v1/summary.json')
    evidence.bind(fit, campaign/'results/fit_v1/summary.json')
    require(fit_summary['status'] == 'three_seed_fit_complete_not_calibrated'
            and fit_summary['completed_seeds'] == list(SEEDS) and fit_summary['optimizer_updates'] == 180
            and fit_summary['dataset_manifest_sha256'] == audits['public']['dataset_manifest_sha256'], 'Fit/export chain changed')
    development_registration = evidence.read(stage/'registration.json')
    require(all([r['seed'] for r in rows] == list(SEEDS) for rows in
                (fit_summary['results'], development_registration['models'], cal['margin_checks'])), 'Selected model list is incomplete')
    models = []
    for learned, reported, online, margin in zip(fit['results'], fit_summary['results'], development_registration['models'], cal['margin_checks']):
        chosen = reported['selected']
        require(learned['seed'] == reported['seed'] == online['seed'] == margin['seed']
                and reported['status'] == 'complete' and reported['epochs'] == 20 and reported['updates'] == 60
                and learned['selected_epoch'] == chosen['epoch'] == online['epoch']
                and learned['selected_checkpoint_sha256'] == chosen['sha256'] == online['sha256']
                and online['margin'] == margin['margin'], 'Model/fit_val/calibration/development identity changed')
        checkpoint = next(r for r in learned['checkpoints'] if r['epoch'] == learned['selected_epoch'])
        path = (campaign/online['path']).resolve(); require(path.is_relative_to(campaign), 'Weight outside round')
        evidence.pin(path, online['sha256'])
        models.append(dict(seed=learned['seed'], parameters=61121, training_epochs=20, updates=60,
            selected_epoch=chosen['epoch'], checkpoint_path=str(path), checkpoint_sha256=chosen['sha256'],
            policy_sha256=online['policy_sha256'], fit_val_loss=checkpoint['independently_recomputed_fit_val_loss'],
            margin=margin['margin'], strict_threshold=margin['margin']+.0005,
            fit_wall_s=finite(reported['fit_wall_s'], nonnegative=True), fit_cpu_s=finite(reported['fit_cpu_s'], nonnegative=True)))
    readiness = evidence.read(stage/'worker_readiness.json')
    require(readiness['candidate_ready_wall_s'] is None and readiness['candidate_has_no_readiness_handshake'] is True,
            'Candidate ready-time interpretation changed')
    generated = datetime.now(timezone.utc)
    accounting = dict(stages=costs, new_business_calls=status['business_calls'], new_executions=status['executions_completed'],
        new_full_executions=status['full_runs'], new_suffix_executions=status['suffix_runs'],
        carry_in=status['carry_in'], historical_business_calls=197456+status['business_calls'],
        historical_executions=1696+status['executions_completed'],
        historical_scope='Only the preceding BC-RPI G0/G1 plus this round; excludes older PPO/Q and other repository experiments.',
        fit_wall_s_total=math.fsum(m['fit_wall_s'] for m in models), fit_cpu_s_total=math.fsum(m['fit_cpu_s'] for m in models),
        campaign_registration_to_last_budget_update_s=finite(status['wall_since_registration_s'], nonnegative=True),
        campaign_registration_to_report_generation_s=finite(generated.timestamp()-status['campaign_start_epoch'], nonnegative=True),
        last_budget_update_utc=status['updated_utc'], audit_only_wall_s=None,
        time_scope='Fit timers include checkpoint/validation work; paid-run wall excludes between-run waits. Campaign elapsed includes collection, fit, audits and waiting, not a training-only or exclusive-hardware benchmark.')
    evidence.verify()
    return dict(schema='bc-rpi-r1-final-audited-result-v1', status='complete_first_round_no_deployment_promotion',
        generated_utc=generated.isoformat(), mode=4, method='One counterfactual-supervised round from frozen pi0=C7; three independent seeds, not iterative RL or ensemble',
        unique_new_worlds=180, old_compatibility_worlds=12, role_counts=role_counts,
        calibration=dict(worlds=24, states=48, unique_suffix_executions=87, actual_executions=111),
        development_worlds=120, development_executions=600, models=models,
        arm_summaries=dev['arm_summaries'], paired_comparisons=comparisons, by_group_comparisons=dev['by_group_comparisons'],
        bootstrap=dev['bootstrap'], failure_rows=dev['failure_rows'], selector_telemetry=telemetry,
        online_forward_audit_counts=forwards['counts'], worker_startup=dev['worker_startup'],
        candidate_worker_startup={k: readiness[k] for k in ('candidate_process_launch_wall_s', 'candidate_ready_wall_s', 'candidate_has_no_readiness_handshake')},
        evaluator_capture_scope='Input capture inside selector; prepared-state capture outside selector but inside episode. Raw per-episode measurements remain in source-pinned outcomes.', accounting=accounting,
        pure_tests=dict(unittest_tests=audits['pure_tests']['unittest_tests'], groups=[{k: r[k] for k in ('group', 'tests', 'success')}
            for r in audits['pure_tests']['groups']], statistics_self_test_passed=True, frozen_v1_verified=True),
        retained_candidate='Existing Q3 R11 + Q4 R2; no automatic promotion or additional round authorized',
        audit_paths={k: str(Path(p).resolve()) for k, p in paths.items()}, source_sha256=evidence.hashes,
        finalizer_sha256=sha256(__file__), actual_environment_calls_by_finalizer=0,
        actual_neural_forwards_by_finalizer=0, actual_optimizer_updates_by_finalizer=0,
        evidence_limits=['Local development only; no sealed final or official Windows execution.',
            'G1 prior headroom below 2% remains unchanged; the user explicitly authorized this one training round despite that gate.',
            'Margins are empirical on 24 C7 roll-in worlds and sampled states, not closed-loop or OOD safety probabilities.',
            'No checkpoint/threshold/network tuning from development; three initializations are reported separately.',
            'Latency is observed under instrumented execution with concurrent audit/test workload, not an exclusive-hardware benchmark.',
            'Input capture is inside selector time; prepared-state capture is outside selector but inside wrapper episode; cold startup is separate.',
            'Candidate process launch is not readiness; readiness was not instrumented.',
            'All historical carry-in is prior paid work; it is not re-executed or counted as new worlds.'])


def render(value, out_directory):
    def link(label, path):
        return f'[{label}](<{os.path.relpath(path, out_directory)}>)'
    def number(value, digits=6):
        return '不适用' if value is None else f'{value:.{digits}f}'
    def interval(values):
        return '不适用' if values is None else '['+', '.join(number(v) for v in values)+']'
    def latency(telemetry, population):
        values = telemetry['duration_populations'].get(population, {})
        return '/'.join(number(None if values.get(k) is None else values[k]*1000, 3) for k in ('p95', 'p99'))
    def table(headers, rows):
        return ['|'+'|'.join(headers)+'|', '|'+'|'.join('---' for _ in headers)+'|',
                *('|'+'|'.join(str(v) for v in row)+'|' for row in rows), '']
    lines = ['# BC-RPI 第一轮真实训练与开发验证报告', '', f"生成时间：{value['generated_utc']}。", '',
        '本次授权的一轮训练与完整开发验证已完成；实际效果见下表。当前仍保留 Q3 R11 + Q4 R2，不自动晋级、不启动第二轮。', '',
        '## 方法与证据边界', '',
        '这是从冻结 π0=C7 出发的一次完整反事实监督拟合：同一公开状态下，每个保留动作执行完整“动作+C7续局”，以终局费用差监督网络；不是已经完成多轮策略更新的迭代 RL。三个初始化分别训练、分别校准、分别评估，不是集成模型。', '',
        '旧 G1 的不足 2% 诊断没有改写。本次用户明确要求真实训练，覆盖的是“不足门槛就不训练”的停止条件，授权仅限这一轮。所有结果属于本地开发证据；没有密封最终集、4800 例追加全回归或官方 Windows 执行。', '',
        '## 数据、模型与校准', '',
        '共 180 个独特新 Q4 world，四种角色互不混用。600 是开发执行次数，不是 600 个新 world；另有 12 个旧兼容 probe，不进入新训练/校准/开发角色。', '']
    lines += table(['角色', '独特 world', '公开入口状态', '标签/执行'], [
        ['fit', 24, 96, '702 个非 reference 标签；唯一梯度来源'],
        ['fit_val', 12, 48, '358 个非 reference 标签；仅选 epoch'],
        ['calibration', 24, 48, '24 共有 roll-in + 87 个唯一完整续局'],
        ['development', 120, '闭环实际决策', '五臂全配对，共 600 次 full'],
        ['旧兼容 probe', 12, '真实前向、强制教师动作', '两臂 24 次 full，请求/观测/费用完全一致']])
    lines += ['训练为 3 seed × 20 epochs × 每 epoch 3 个完整 world minibatch，共 180 次实际优化更新；每模型 61,121 个参数。三个初始化共用同一份 36-world 完整标签，不重复计交互。每 seed 仅在 epoch 5/10/20 中由永久 fit_val 的 world→state→非 reference 动作等权 Huber 损失选择，平手取较早 epoch；开发结果不反馈调参。', '',
        '标签尺度为 (T_ref−T_action)/(1000N)，N 仅供终局监督，不进入模型输入。q 取自 24 个 C7 roll-in world 抽样入口：每 world 最大乐观残差的第 22 小值与 0 取 max；这是经验校准，不是完整 πθ 闭环或 OOD 安全概率保证。线上严格 predicted_gain > q+0.0005，每局最多两次干预，其他情况保留教师。', '']
    lines += table(['seed', '选中 epoch', '独立复算 Val loss', 'q', '严格阈值 q+0.0005', '拟合 wall 秒'], [
        [m['seed'], m['selected_epoch'], number(m['fit_val_loss']), number(m['margin'], 12),
         number(m['strict_threshold'], 12), number(m['fit_wall_s'])] for m in value['models']])
    for model in value['models']:
        lines += [f"- {link(str(model['seed'])+' 权重', model['checkpoint_path'])}；SHA256 `{model['checkpoint_sha256']}`；policy SHA256 `{model['policy_sha256']}`。"]
    lines += ['', '## 完整开发结果', '',
        '每臂 120 world。统计量为每局 T/N 的算术平均，不是总 T/总 N；只有相应完整配对全部正常全清，才比较速度。失败保留，未按成功子集重算。', '']
    lines += table(['策略', '正常全清', '失败', 'mean(T/N)，秒/源', '可比较速度'], [
        [r['arm'], f"{r['full_clear_successes']}/120", r['failures'], number(r['raw_world_mean_T_over_N_seconds']),
         '是' if r['mean_eligible_for_speed_comparison'] else '否'] for r in value['arm_summaries']])
    lines += ['Δ=模型−对照，负值更快；改善率=100×(1−模型均值/对照均值)，正值更快。12 组内各重抽 10 个配对 world，10,000 次、seed=912199；六比较共享抽样。95% 区间为线性插值的 percentile 描述性区间，没有最终测试或多重比较校正保证。', '']
    lines += table(['模型', '对照', 'Δ 秒/源', 'Δ 95% 区间', '改善率 %', '改善率 95% 区间', '快/同/慢'], [
        [r['candidate'], r['control'], number(r['mean_paired_delta_seconds_per_source']),
         interval(r['bootstrap']['paired_delta_95_percentile_ci']), number(r['relative_improvement_percent']),
         interval(r['bootstrap']['relative_improvement_95_percentile_ci']),
         '/'.join(str(r[k]) for k in ('faster', 'same', 'slower')) if r['valid_full_clear_comparison'] else '失败不排名']
        for r in value['paired_comparisons']])
    lines += ['## 实际推理与计时范围', '',
        '下表只汇总实际 model-scored、batch=1 决策的延迟；没有用大量教师直通分支稀释模型延迟，也没有平均每局 P95。全部决策、wrapper 与 enter-to-finish 统计另见 JSON。独立前向审计使用真实公开输入复算保存网络，不把复算次数计为开发执行。', '']
    startup = {r['seed']: r['wall_s'] for r in value['worker_startup']}
    lines += table(['模型', '实际 scored/干预', '端到端 P95/P99 毫秒', '模型 forward P95/P99 毫秒', '冷启动秒'], [
        [arm, f"{t['scored_decisions']}/{t['overrides']}",
         latency(t, 'scored_decisions_end_to_end_s'), latency(t, 'model_forward_s'),
         number(startup[int(arm.split('_')[1])])]
        for arm, t in value['selector_telemetry'].items()])
    lines += ['端到端 selector 包含初始 prepare、候选/特征、IPC、forward、选择和输入 capture；prepared-state capture 在 selector 外、wrapper episode 内。模型冷启动另记；candidate 只有进程 launch 时间，ready 时间未知，不能把 launch 当 ready。主审/纯测试与开发存在并行计算，现实 wall 有机器争用，因此这些是本次仪器化运行观测，不是独占硬件延迟 benchmark，更不是因果优化收益。', '',
        '各模型所有拒绝原因、实际 fallback 及不可获得的直接基线 fallback 字段在 JSON 中保留；捕获开销原值见绑定 SHA 的逐局源记录。不可获得不等于零。', '',
        '## 费用与墙钟', '']
    accounting = value['accounting']
    lines += table(['阶段', '本次业务调用', '实际执行', 'full/suffix', '执行 wall 合计秒'], [
        [r['stage'], r['business_calls'], r['executions'], f"{r['full']}/{r['suffix']}", number(r['sum_recorded_execution_wall_s'])]
        for r in accounting['stages']])
    lines += [f"本轮新增 **{accounting['new_business_calls']} 次业务调用、{accounting['new_executions']} 次环境执行**。旧 G0/G1 carry-in 为 197456 次调用、1696 次执行，未重跑；仅 G0/G1 加本轮合计 {accounting['historical_business_calls']} 次调用、{accounting['historical_executions']} 次执行，不含更早 PPO/Q 或仓库其他实验。拟合、独立前向审计和纯张量测试不虚增环境执行计数。", '',
        f"三个拟合计时合计 {number(accounting['fit_wall_s_total'])} wall 秒、{number(accounting['fit_cpu_s_total'])} CPU 秒，包含各自训练循环、Val 与检查点保存。整轮从预算登记到最后账本更新为 {number(accounting['campaign_registration_to_last_budget_update_s'], 3)} 秒，到报告生成时为 {number(accounting['campaign_registration_to_report_generation_s'], 3)} 秒；包含采集、拟合、审核与等待，不是纯训练耗时。审核独占时间未单独计量，不用总墙钟减拟合秒冒充审核时间。", '',
        '## 逐组完整结果', '', '每组固定 10 world；所有 12 组及六比较保留。局部组差异仅作开发描述，不据此挑选模型或修改参数。', '']
    lines += table(['组', '模型', '对照', 'Δ 秒/源', '改善率 %', '快/同/慢'], [
        [group, r['candidate'], r['control'], number(r['mean_paired_delta_seconds_per_source']),
         number(r['relative_improvement_percent']), '/'.join(str(r[k]) for k in ('faster', 'same', 'slower'))
         if r['valid_full_clear_comparison'] else '失败不排名']
        for group, rows in sorted(value['by_group_comparisons'].items()) for r in rows])
    lines += ['## 完整性与交付边界', '',
        f"纯测试 {value['pure_tests']['unittest_tests']} 项全部通过，另有分层统计合成测试及原始冻结 v1 文件校验。纯张量梯度测试不是本轮真实拟合；真实 3 次拟合、180 次更新、9 个检查点由独立记录与参数审计确认。", '',
        f"失败结果行数：{len(value['failure_rows'])}，完整失败行保存在本报告配套 JSON；出现失败的对应完整臂不产加速排名。", '',
        '本汇总只读取已完成的审计及 JSON/gzip 证据：新增环境调用 0、神经前向 0、优化更新 0。所有依赖逐一复核 SHA256 后才生成；不执行 Git、不修改主求解器、Q1/Q2 或当前推荐组合。下一轮或部署需要新的明确授权。', '', '证据入口：', '']
    lines += [f"- {link(name, path)}" for name, path in value['audit_paths'].items()]
    return '\n'.join(lines)+'\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=Path, default=ROOT/'RL/training_round1_20260912')
    parser.add_argument('--out-dir', type=Path, default=ROOT)
    for name, (filename, _) in AUDITS.items():
        parser.add_argument('--'+name.replace('_', '-')+'-audit', type=Path, default=ROOT/'verification'/filename)
    args = parser.parse_args()
    out_dir = args.out_dir.resolve()
    report, result_path = (out_dir/name for name in ('RL_TRAINING_ROUND1_REPORT.md', 'RL_TRAINING_ROUND1_RESULT.json'))
    require(not report.exists() and not result_path.exists(), 'Preserve existing final outputs')
    paths = {name: getattr(args, name+'_audit') for name in AUDITS}
    result = build(args.campaign, paths)
    markdown = render(result, out_dir)
    serialized = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n'
    out_dir.mkdir(parents=True, exist_ok=True)
    with result_path.open('x', encoding='utf-8') as output:
        output.write(serialized)
    with report.open('x', encoding='utf-8') as output:
        output.write(markdown)
    print(json.dumps(dict(status=result['status'], report=str(report), result=str(result_path),
        new_business_calls=result['accounting']['new_business_calls'], new_executions=result['accounting']['new_executions']), ensure_ascii=False))


if __name__ == '__main__':
    main()
