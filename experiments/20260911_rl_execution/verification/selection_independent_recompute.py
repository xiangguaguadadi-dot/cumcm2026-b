"""Independent saved-row verification: no original statistics-helper import.

Reads only plan, frozen identities, row ledgers, and saved reports. Does not
import or run environments, models, training, fixtures, or new world recipes.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np


def verify(root: Path) -> dict:
    began = time.perf_counter()
    errors, hashes = [], {}
    counts = Counter()
    maximum_numeric_difference = 0.0

    def check(condition, name, detail=None):
        counts[name] += 1
        if not condition:
            errors.append(dict(check=name, detail=detail))

    def load(path, jsonl=False):
        path = root/path
        encoded = path.read_bytes()
        hashes[str(path.relative_to(root))] = hashlib.sha256(encoded).hexdigest()
        return ([json.loads(line) for line in encoded.decode().splitlines()]
                if jsonl else json.loads(encoded))

    def near(actual, saved, name):
        nonlocal maximum_numeric_difference
        valid = type(actual) in (int, float) and type(saved) in (int, float)
        if valid:
            maximum_numeric_difference = max(maximum_numeric_difference, abs(actual-saved))
        check(valid and math.isclose(actual, saved, rel_tol=1e-10, abs_tol=1e-8), name,
              dict(recomputed=actual, saved=saved))

    def mean(values):
        return math.fsum(values)/len(values)

    plan = load(Path('data/g2_plan.json'))
    saved = load(Path('analysis/selection_result/selection_summary.json'))
    freeze = load(Path('data/selection_freeze.json'))
    report_path = root/'analysis/selection_result/REPORT.md'
    report = report_path.read_text()
    hashes[str(report_path.relative_to(root))] = hashlib.sha256(report_path.read_bytes()).hexdigest()
    check(hashes['data/g2_plan.json'] == saved['provenance']['plan_sha256'], 'plan_hash_bound')
    check(hashes['data/g2_plan.json'] == freeze['plan_sha256'], 'freeze_plan_bound')
    check(plan['selection'] == freeze['selection_worlds'], 'freeze_worlds_exact')
    bootstrap = plan['selection_protocol']['bootstrap']
    check(bootstrap['seed'] == 84771 and bootstrap['resamples'] == 10000, 'bootstrap_preregistered')
    seeds = plan['initialization_seeds']
    check(seeds == [81001, 81002, 81003], 'three_registered_initializations')
    worlds = {mode: [w for w in plan['selection'] if w['mode'] == mode] for mode in (3, 4)}
    expected = {w['world_id']: w for w in plan['selection']}
    check(len(expected) == 192, '192_unique_registered_worlds')
    for mode in (3, 4):
        check(len(worlds[mode]) == 96 and sorted(Counter(w['group'] for w in worlds[mode]).values()) == [8]*12,
              '96_worlds_12_groups_each_question', mode)
    specs = [(name, 'baselines') for name in ('original_c7', 'teacher_wrapper', 'same_candidates_greedy')]
    specs += [(f'bc_init{seed}', 'baselines') for seed in seeds]
    specs += [(f'{algorithm}_init{seed}_ep{position:04d}', 'models')
              for algorithm in ('ppo', 'q') for seed in seeds
              for position in plan[algorithm]['checkpoint_episodes']]
    check(len(specs) == 30 and len(freeze['baselines']) == 6 and len(freeze['models']) == 24,
          'six_baselines_24_actual_checkpoints')
    frozen_by_id = {r['model_id']: r for r in freeze['baselines']+freeze['models']}
    check(set(frozen_by_id) == {name for name, _ in specs}, 'all_frozen_model_ids_exact')
    check(set(saved['parts']) == set(frozen_by_id), 'all_reported_model_ids_exact')

    data, part_results = {}, {}
    total_calls, total_seconds, total_rows, total_cleared = 0, 0.0, 0, 0
    for name, category in specs:
        relative = Path('results/g2_selection')/category/name
        ledger = load(relative/'rows.jsonl', jsonl=True)
        metadata = load(relative/'manifest.json')
        completed = load(relative/'summary.json')
        current_sha = hashes[str(relative/'rows.jsonl')]
        check(current_sha == saved['parts'][name]['input']['sha256'] == completed['rows_sha256'],
              'ledger_hash_matches_analysis_and_completed_part', name)
        check(metadata['selection_freeze_sha256'] == hashes['data/selection_freeze.json'], 'part_freeze_bound', name)
        check(all(metadata.get(key) == value for key, value in frozen_by_id[name].items()),
              'part_model_identity_exact', name)
        ids = [row['world_id'] for row in ledger]
        check(len(ledger) == len(set(ids)) == 192 and set(ids) == set(expected), 'part_ID_coverage', name)
        by_id = {row['world_id']: row for row in ledger}
        data[name] = by_id
        for row in ledger:
            registered = expected[row['world_id']]
            check(row['label'] == name, 'row_model_label', name)
            check(row['mode'] == registered['mode'] and row['group'] == registered['group'], 'row_registered_mode_group', name)
            check(type(row['n']) is int and 10 <= row['n'] <= 16, 'row_source_denominator', name)
            check(row['success'] is True and row['cleared'] == row['n'] and not row['error']
                  and not row.get('validation_errors'), 'row_normal_all_clear', name)
            check(all(type(row[k]) in (float, int) and math.isfinite(row[k]) and row[k] >= 0
                      for k in ('average_s', 'virtual_time_s', 'execution_wall_s')), 'row_finite_costs', name)
            near(row['virtual_time_s']/row['cleared'], row['average_s'], 'row_average_denominator_identity')
            check(type(row['business_primitives']) is int and row['business_primitives'] >= 0,
                  'row_actual_call_count', name)
            check(sum(row['actual_calls'].values()) == row['business_primitives'], 'row_call_components', name)
            check(row['n'] == data['original_c7'][row['world_id']]['n'], 'row_paired_N_matches_c7', name)
        summary = dict(rows=len(ledger), unique_world_ids=len(set(ids)), successes=sum(r['success'] for r in ledger),
                       source_denominator=sum(r['n'] for r in ledger), cleared=sum(r['cleared'] for r in ledger),
                       business_primitives=sum(r['business_primitives'] for r in ledger),
                       execution_wall_s=math.fsum(r['execution_wall_s'] for r in ledger), questions={})
        for mode in (3, 4):
            question_rows = [by_id[w['world_id']] for w in worlds[mode]]
            summary['questions'][str(mode)] = dict(rows=len(question_rows),
                source_denominator=sum(r['n'] for r in question_rows), cleared=sum(r['cleared'] for r in question_rows),
                mean_s_per_source=mean([r['average_s'] for r in question_rows]))
            reported = saved['parts'][name]['questions'][str(mode)]
            check(reported['eligible_for_selection'] is True and reported['collection_complete'] is True,
                  'reported_part_complete', [name, mode])
            check(not any(reported[field] for field in ('failed_rows','invalid_rows','duplicate_world_ids','missing_world_ids')),
                  'reported_empty_failure_missing_lists', [name, mode])
            near(summary['questions'][str(mode)]['mean_s_per_source'], reported['mean_seconds_per_source'], 'part_question_mean')
            for group in sorted({w['group'] for w in worlds[mode]}):
                group_rows = [r for r in question_rows if r['group'] == group]
                near(mean([r['average_s'] for r in group_rows]), reported['groups'][group]['mean_seconds_per_source'],
                     'part_group_mean')
        part_results[name] = summary
        total_rows += len(ledger)
        total_calls += summary['business_primitives']
        total_seconds += summary['execution_wall_s']
        total_cleared += summary['cleared']
    check(total_rows == 5760, '5760_actual_evaluation_rows')
    check(saved['recorded_evaluation_cost']['episode_rows'] == total_rows, 'reported_execution_total')
    check(saved['recorded_evaluation_cost']['business_primitives'] == total_calls, 'reported_call_total')
    near(total_seconds, saved['recorded_evaluation_cost']['execution_wall_s'], 'reported_execution_seconds')

    ci_records = []

    def comparison(candidate, baseline, mode, reported, label):
        # Independent implementation: per-group bootstrap means are averaged
        # with their fixed registered population weights. No original helper.
        delta = [c-b for c, b in zip(candidate, baseline)]
        generator = np.random.default_rng(84771)
        simulated = np.zeros(10000)
        for group in sorted({w['group'] for w in worlds[mode]}):
            group_indices = [i for i, w in enumerate(worlds[mode]) if w['group'] == group]
            group_delta = np.asarray([delta[i] for i in group_indices])
            draws = generator.integers(len(group_delta), size=(10000, len(group_delta)))
            simulated += group_delta[draws].mean(axis=1)*(len(group_delta)/len(delta))
            actual_group = reported['groups'][group]
            cm = mean([candidate[i] for i in group_indices])
            bm = mean([baseline[i] for i in group_indices])
            for field, value in (('candidate_mean_s_per_source',cm),('baseline_mean_s_per_source',bm),
                                 ('difference_s_per_source',cm-bm),('improvement_percent',100*(bm-cm)/bm)):
                near(value, actual_group[field], 'paired_group_'+field)
            check(sum(delta[i] > 0 for i in group_indices) == actual_group['candidate_slower_worlds'],
                  'paired_group_slower_count', label)
        interval = np.percentile(simulated, [2.5,97.5], method='linear').tolist()
        cm, bm = mean(candidate), mean(baseline)
        result = dict(label=label, mode=mode, worlds=len(delta), candidate_mean_s_per_source=cm,
                      baseline_mean_s_per_source=bm, improvement_percent=100*(bm-cm)/bm,
                      mean_difference_s_per_source=mean(delta), difference_ci95_s_per_source=interval,
                      candidate_faster_worlds=sum(v < 0 for v in delta), candidate_slower_worlds=sum(v > 0 for v in delta),
                      candidate_equal_worlds=sum(v == 0 for v in delta))
        for key in ('candidate_mean_s_per_source','baseline_mean_s_per_source','improvement_percent','mean_difference_s_per_source'):
            near(result[key],reported[key], 'paired_'+key)
        for i in (0,1):
            near(interval[i],reported['difference_ci95_s_per_source'][i], 'paired_CI_endpoint')
        for key in ('candidate_faster_worlds','candidate_slower_worlds','candidate_equal_worlds'):
            check(result[key] == reported[key], 'paired_world_direction_counts', label)
        ci_records.append(result)
        return result

    choices, combined = {}, {}
    for algorithm in ('ppo','q'):
        for mode in (3,4):
            key = f'{algorithm}_q{mode}'
            reported = saved['algorithms'][algorithm][str(mode)]
            picks, all_candidate_values, all_bc_values, jointly_better = {}, [], [], 0
            original = [data['original_c7'][w['world_id']]['average_s'] for w in worlds[mode]]
            for seed in seeds:
                candidates = []
                for position in plan[algorithm]['checkpoint_episodes']:
                    name = f'{algorithm}_init{seed}_ep{position:04d}'
                    values = [data[name][w['world_id']]['average_s'] for w in worlds[mode]]
                    candidates.append((mean(values), position, name, values))
                # All checkpoints passed the independent completeness checks.
                best_mean, position, name, values = min(candidates, key=lambda x:(x[0],x[1]))
                expected_choice = reported['initialization_choices'][str(seed)]
                check(position == expected_choice['selected_episode_count'] and name == expected_choice['selected_part'],
                      'selected_checkpoint_is_independent_minimum', [algorithm,mode,seed])
                near(best_mean, expected_choice['mean_seconds_per_source'], 'selected_checkpoint_mean')
                bc = [data[f'bc_init{seed}'][w['world_id']]['average_s'] for w in worlds[mode]]
                c7_result = comparison(values, original, mode, expected_choice['comparisons']['original_c7'], name+f'/q{mode}/c7')
                bc_result = comparison(values, bc, mode, expected_choice['comparisons']['corresponding_bc'], name+f'/q{mode}/bc')
                same_direction = c7_result['mean_difference_s_per_source'] < 0 and bc_result['mean_difference_s_per_source'] < 0
                check(same_direction == expected_choice['improves_both_baselines'], 'same_initialization_joint_direction', [algorithm,mode,seed])
                jointly_better += int(same_direction)
                picks[str(seed)] = dict(selected_position=position, selected_part=name, mean_s_per_source=best_mean,
                                       compared_checkpoints=[dict(episodes=x[1],mean_s_per_source=x[0]) for x in candidates],
                                       improves_both=same_direction)
                all_candidate_values.append(values)
                all_bc_values.append(bc)
            # Collapse the initialization axis first. The bootstrap receives 96
            # values, never a flattened 288-row array.
            candidate_mean_by_world = [mean(column) for column in zip(*all_candidate_values)]
            bc_mean_by_world = [mean(column) for column in zip(*all_bc_values)]
            actual_aggregate = reported['aggregate']
            check(actual_aggregate['independent_worlds'] == 96 and actual_aggregate['initialization_evaluations'] == 288,
                  'aggregate_unit_not_288_independent_worlds', key)
            c7_result = comparison(candidate_mean_by_world, original, mode, actual_aggregate['comparisons']['original_c7'], key+'/aggregate/c7')
            bc_result = comparison(candidate_mean_by_world, bc_mean_by_world, mode, actual_aggregate['comparisons']['corresponding_bc'], key+'/aggregate/bc')
            gates = dict(all_three_initializations_have_complete_choices_and_baselines=True,
                         initializations_improving_both_baselines=jointly_better,
                         at_least_two_of_three_improve_both=jointly_better >= 2,
                         original_c7_mean_improvement_at_least_2_percent=c7_result['improvement_percent'] >= 2,
                         corresponding_bc_mean_improvement_at_least_2_percent=bc_result['improvement_percent'] >= 2,
                         original_c7_difference_ci95_upper_below_zero=c7_result['difference_ci95_s_per_source'][1] < 0,
                         corresponding_bc_difference_ci95_upper_below_zero=bc_result['difference_ci95_s_per_source'][1] < 0)
            check(gates == reported['promotion_checks'], 'all_promotion_components', key)
            passes = all(value for name,value in gates.items() if name != 'initializations_improving_both_baselines')
            check(passes == reported['meets_preregistered_selection_gate'], 'final_algorithm_question_gate', key)
            choices[key] = picks
            combined[key] = dict(c7=c7_result, bc=bc_result, checks=gates, meets_selection_gate=passes)
            # Check the visible summary table from independent computed values.
            displayed = f"| {algorithm.upper()} | {mode} | {'是' if passes else '否'} | {jointly_better}/3 | {c7_result['improvement_percent']:.3f}% | {bc_result['improvement_percent']:.3f}% |"
            check(displayed in report, 'markdown_top_result_row', key)
    check(len(ci_records) == 32, 'all_32_selected_and_aggregate_intervals_recomputed')
    check('选择偏差' in report and '不授权默认替换C7' in report, 'visible_evidence_boundary')
    for rel, before in hashes.items():
        check(hashlib.sha256((root/rel).read_bytes()).hexdigest() == before, 'source_unchanged_after_independent_review', rel)
    code_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return dict(version='selection-independent-saved-row-review-v1',
                status='verified_with_selection_caveats' if not errors else 'needs_revision',
                errors=errors, check_counts=dict(counts), maximum_numeric_absolute_difference=maximum_numeric_difference,
                row_totals=dict(parts=30, actual_episode_rows=total_rows, unique_world_ids=len(expected),
                    fully_cleared_rows=total_rows if not errors else None, repeated_clearance_denominator=total_cleared,
                    business_primitives=total_calls, summed_execution_wall_s=total_seconds),
                parts=part_results, selected_checkpoints=choices, aggregate_results=combined, recomputed_intervals=ci_records,
                provenance=dict(execution_root=str(root), source_sha256=hashes, independent_program_sha256=code_sha,
                    imported_original_analysis_helper=False, numpy_version=np.__version__, bootstrap_seed=84771,
                    resamples_per_interval=10000, paired_group_weighting='Fixed 8/96 within each of twelve registered groups',
                    method='Independent math.fsum means and stratified bootstrap group means; average three initializations within world first'),
                work_count=dict(repeated_saved_data_statistical_audit=True, new_worlds=0,
                                new_environment_executions=0, model_evaluations=0, optimizer_steps=0, new_synthetic_fixtures=0),
                elapsed_wall_s=time.perf_counter()-began,
                limitations=['Selection-set evidence after checkpoint choice, with selection bias and no multiple-comparison correction.',
                    'This review reads saved row ledgers, identity manifests and reports; it does not replace the separate full raw-trajectory audit.',
                    'Repeated strategy executions of the same world and repeated cleared-source denominators are not independent new samples.',
                    'No final blind or official Windows validation and no default C7 replacement authorization.'])


def markdown(result):
    totals=result['row_totals']
    lines=['# 选择结果独立复核', '',
           '本复核从保存的逐局账本重新计算，没有调用原统计程序的函数，没有执行环境、模型、训练或新夹具。这是重复统计复算，不是新采样。', '',
           f"状态：**{result['status']}**；发现错误{len(result['errors'])}项。", '',
           f"30个位置合计{totals['actual_episode_rows']:,}行，每个位置192个相同注册world，两题各96个、每题12组且每组8个。全部world ID、mode/group、模型label、分母、全清、异常及费用算式均核对。累计业务调用{totals['business_primitives']:,}次，逐局现实执行耗时之和{totals['summed_execution_wall_s']:.6f}秒。", '',
           f"清除数与重复计入的源分母合计均为{totals['repeated_clearance_denominator']:,}；同一world在30个位置重复执行，这个数不是独立源样本数。", '',
           '## 选点', '', '| 算法/题目 | 初始化81001 | 初始化81002 | 初始化81003 |', '|---|---:|---:|---:|']
    for key,choices in result['selected_checkpoints'].items():
        lines.append(f"| {key} | {choices['81001']['selected_position']} | {choices['81002']['selected_position']} | {choices['81003']['selected_position']} |")
    lines += ['', '所有12个选择均为该题该初始化四个完整检查点的最小平均秒/源；全部60个位置×题均值、720个位置×题×场景均值已复核。', '',
              '## 三初始化按同world合并的比较', '',
              '| 算法/题目 | 候选秒/源 | 相对C7改善% | 相对BC改善% | 候选−C7 95%区间 | 候选−BC 95%区间 | 同时改善两对照初始化 | 晋级 |',
              '|---|---:|---:|---:|---|---|---:|---|']
    for key, record in result['aggregate_results'].items():
        a,b=record['c7'],record['bc']
        ci_a=', '.join(f'{x:.6f}' for x in a['difference_ci95_s_per_source'])
        ci_b=', '.join(f'{x:.6f}' for x in b['difference_ci95_s_per_source'])
        lines.append(f"| {key} | {a['candidate_mean_s_per_source']:.6f} | {a['improvement_percent']:.6f} | {b['improvement_percent']:.6f} | [{ci_a}] | [{ci_b}] | {record['checks']['initializations_improving_both_baselines']}/3 | {'是' if record['meets_selection_gate'] else '否'} |")
    lines += ['', '复算12个已选初始化各两种对照及四个算法/题合并结果各两种对照，共32个95%区间。每个区间按固定12组做10000次配对bootstrap，种子84771；先在同一个world内平均三个初始化，独立单位保持96，不能把288次执行当作288个独立world。', '',
              '四个算法/题均未满足整体晋级门槛。PPO第四问相对BC约改善1.01%，其差值区间上界小于0，但改善未到2%，且仍慢于C7；不把这一局部结果写成晋级。', '',
              f"与原机器可读统计相比，所检查数值的最大绝对差为{result['maximum_numeric_absolute_difference']:.3g}，来自浮点加总顺序。所有输入散列在复核前后保持一致；详见同名JSON的逐项结果与来源散列。", '',
              '该结论仅适用于检查点选择后的本地数据，有选择偏差；区间未校正选择和多重比较。该行级审计不替代另行进行的完整原始轨迹审计，不属于最终盲测或官方Windows验证，不授权默认替换C7。', '',
              '可重复运行`selection_independent_recompute.py`并指定新的输出文件。重复运行仍是统计复算，应记录实际分析耗时，不计作新world、环境执行、模型评估或合成夹具。', '']
    if result['errors']:
        lines += ['## 问题', '', '```json', json.dumps(result['errors'],ensure_ascii=False,indent=2), '```', '']
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out-json',type=Path,required=True)
    parser.add_argument('--out-md',type=Path,required=True)
    args=parser.parse_args()
    if args.out_json.exists() or args.out_md.exists():
        raise RuntimeError('Independent review outputs must be new; do not overwrite prior evidence')
    result=verify(args.root.resolve())
    for path in (args.out_json,args.out_md):path.parent.mkdir(parents=True,exist_ok=True)
    args.out_json.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    args.out_md.write_text(markdown(result))
    print(json.dumps(dict(status=result['status'],errors=result['errors'],rows=result['row_totals'],
        maximum_difference=result['maximum_numeric_absolute_difference'],
        intervals=len(result['recomputed_intervals']),elapsed_wall_s=result['elapsed_wall_s'],
        actual_new_worlds=0),ensure_ascii=False))
    raise SystemExit(0 if not result['errors'] else 1)


if __name__=='__main__':main()
