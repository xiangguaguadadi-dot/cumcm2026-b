"""Audit and summarize the preregistered G2 checkpoint-selection evaluation.

This module reads saved row ledgers only. It never imports a controller, policy,
environment, world generator, or training runner and cannot execute task worlds.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


ANALYSIS_VERSION = "g2-selection-statistics-v1"
ALGORITHMS = ("ppo", "q")
QUESTIONS = (3, 4)
MIN_IMPROVEMENT_PERCENT = 2.0


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def finite_number(value: Any, *, minimum: float = 0.0) -> bool:
    return (type(value) in (int, float) and math.isfinite(value)
            and value >= minimum)


def integer(value: Any, *, minimum: int = 0, maximum: int | None = None) -> bool:
    return (type(value) is int and value >= minimum
            and (maximum is None or value <= maximum))


def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                   allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def plan_contract(plan: dict) -> tuple[list[int], dict[int, list[dict]], dict]:
    seeds = plan["initialization_seeds"]
    if len(seeds) != 3 or len(set(seeds)) != 3:
        raise ValueError("G2 requires exactly three registered initializations")
    recipes = plan["selection"]
    if len({w["world_id"] for w in recipes}) != len(recipes):
        raise ValueError("Selection plan contains duplicate world IDs")
    by_mode = {mode: [w for w in recipes if w["mode"] == mode]
               for mode in QUESTIONS}
    protocol = plan["selection_protocol"]
    if len(recipes) != protocol["worlds"] or len(recipes) != 192:
        raise ValueError("Selection plan must contain exactly 192 registered worlds")
    for mode, worlds in by_mode.items():
        if len(worlds) != 96 or len(worlds) != protocol["worlds_per_question"]:
            raise ValueError(f"Question {mode} requires exactly 96 registered worlds")
        if len({w["group"] for w in worlds}) != 12:
            raise ValueError("The preregistered bootstrap requires twelve groups per question")
    for algorithm in ALGORITHMS:
        points = plan[algorithm]["checkpoint_episodes"]
        if points != [128, 256, 512, 1024]:
            raise ValueError("Unexpected checkpoint plan; revise the protocol explicitly")
    bootstrap = protocol["bootstrap"]
    if bootstrap["resamples"] != 10000 or bootstrap["seed"] != 84771:
        raise ValueError("Unexpected preregistered bootstrap settings")
    return seeds, by_mode, bootstrap


def part_specs(plan: dict) -> list[dict]:
    specs = [dict(key=name, category="baselines", algorithm=None, seed=None, episodes=None)
             for name in ("original_c7", "teacher_wrapper", "same_candidates_greedy")]
    specs += [dict(key=f"bc_init{seed}", category="baselines", algorithm="bc",
                   seed=seed, episodes=None) for seed in plan["initialization_seeds"]]
    for algorithm in ALGORITHMS:
        for seed in plan["initialization_seeds"]:
            for episodes in plan[algorithm]["checkpoint_episodes"]:
                specs.append(dict(key=f"{algorithm}_init{seed}_ep{episodes:04d}",
                                  category="models", algorithm=algorithm,
                                  seed=seed, episodes=episodes))
    return specs


def read_ledger(path: Path) -> tuple[list[dict], list[dict], dict]:
    if not path.exists():
        return [], [], dict(path=str(path.resolve()), exists=False, sha256=None, bytes=0)
    encoded = path.read_bytes()
    rows, errors = [], []
    try:
        lines = encoded.decode("utf-8").splitlines()
    except UnicodeError as exc:
        return [], [dict(line=None, reason=f"invalid_utf8:{exc}")], dict(
            path=str(path.resolve()), exists=True, sha256=sha_bytes(encoded), bytes=len(encoded))
    for line_number, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError("row is not an object")
            rows.append(row)
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(dict(line=line_number, reason=f"invalid_json_row:{exc}"))
    return rows, errors, dict(path=str(path.resolve()), exists=True,
                              sha256=sha_bytes(encoded), bytes=len(encoded))


def row_problems(row: dict, recipe: dict, reference_n: int | None) -> list[str]:
    problems = []
    if row.get("mode") != recipe["mode"]:
        problems.append("mode_disagrees_with_registered_world")
    if row.get("group") != recipe["group"]:
        problems.append("group_disagrees_with_registered_world")
    n, cleared = row.get("n"), row.get("cleared")
    if not integer(n, minimum=10, maximum=16):
        problems.append("invalid_true_source_count")
    if not integer(cleared, maximum=n if integer(n) else None):
        problems.append("invalid_cleared_count")
    if reference_n is not None and n != reference_n:
        problems.append("source_count_disagrees_with_original_c7")
    if type(row.get("success")) is not bool:
        problems.append("success_is_not_explicit_boolean")
    for key in ("virtual_time_s", "execution_wall_s"):
        if not finite_number(row.get(key)):
            problems.append(f"invalid_{key}")
    if not integer(row.get("business_primitives")):
        problems.append("invalid_business_primitives")
    if cleared == 0:
        if row.get("average_s") is not None:
            problems.append("zero_clear_requires_null_average")
    elif integer(cleared, minimum=1):
        average = row.get("average_s")
        if not finite_number(average):
            problems.append("invalid_average_seconds_per_cleared_source")
        elif finite_number(row.get("virtual_time_s")):
            expected = row["virtual_time_s"] / cleared
            if not math.isclose(average, expected, rel_tol=1e-9, abs_tol=2e-5):
                problems.append("average_disagrees_with_virtual_time_over_cleared")
    if "error" not in row:
        problems.append("missing_error_field")
    if "fallback_reason" not in row:
        problems.append("missing_fallback_reason_field")
    return problems


def audit_part(spec: dict, rows: list[dict], parse_errors: list[dict], source: dict,
               by_mode: dict[int, list[dict]], reference_n: dict[str, int]) -> dict:
    expected_all = {w["world_id"]: w for worlds in by_mode.values() for w in worlds}
    indexed = defaultdict(list)
    unexpected = []
    for index, row in enumerate(rows):
        world_id = row.get("world_id")
        if not isinstance(world_id, str) or world_id not in expected_all:
            unexpected.append(dict(row_index=index, world_id=world_id, mode=row.get("mode")))
        else:
            indexed[world_id].append(row)
    result = dict(**spec, input=source, rows_recorded=len(rows), parse_errors=parse_errors,
                  unexpected_rows=unexpected, questions={})
    result["recorded_cost"] = dict(
        business_primitives=sum(r["business_primitives"] for r in rows
                                if integer(r.get("business_primitives"))),
        execution_wall_s=sum(r["execution_wall_s"] for r in rows
                             if finite_number(r.get("execution_wall_s"))),
        cost_rows_invalid=sum(not integer(r.get("business_primitives"))
                              or not finite_number(r.get("execution_wall_s")) for r in rows),
        note="Counts every recorded row, including failures and duplicates; absent or malformed rows have unknown cost.")
    for mode, worlds in by_mode.items():
        wanted = [w["world_id"] for w in worlds]
        missing = [wid for wid in wanted if not indexed[wid]]
        duplicates = [dict(world_id=wid, rows=len(indexed[wid]))
                      for wid in wanted if len(indexed[wid]) > 1]
        relevant_unexpected = [r for r in unexpected if r["mode"] not in QUESTIONS or r["mode"] == mode]
        errors, failures = [], []
        kept = []
        for recipe in worlds:
            matching = indexed[recipe["world_id"]]
            for row in matching:
                problems = row_problems(row, recipe, reference_n.get(recipe["world_id"]))
                if problems:
                    errors.append(dict(world_id=recipe["world_id"], reasons=problems))
                if row.get("success") is not True or row.get("cleared") != row.get("n") or row.get("error"):
                    failures.append(dict(world_id=recipe["world_id"], success=row.get("success"),
                                         n=row.get("n"), cleared=row.get("cleared"), error=row.get("error"),
                                         fallback_reason=row.get("fallback_reason")))
            if len(matching) == 1:
                kept.append(matching[0])
        structural = not (missing or duplicates or relevant_unexpected or errors or parse_errors)
        eligible = structural and not failures
        q = dict(expected_rows=len(worlds), recorded_expected_rows=sum(len(indexed[wid]) for wid in wanted),
                 unique_expected_worlds=sum(bool(indexed[wid]) for wid in wanted),
                 missing_world_ids=missing, duplicate_world_ids=duplicates,
                 unexpected_rows=relevant_unexpected, invalid_rows=errors, failed_rows=failures,
                 collection_complete=structural, eligible_for_selection=eligible,
                 status=("complete_success" if eligible else "complete_with_failures" if structural
                         else "not_executed_or_result_missing" if not source["exists"] else "incomplete_or_invalid"),
                 mean_seconds_per_source=(float(np.mean([r["average_s"] for r in kept])) if eligible else None),
                 clear_fraction=(sum(r["cleared"] for r in kept)/sum(r["n"] for r in kept)
                                 if kept and all(integer(r.get("n"), minimum=1)
                                                 and integer(r.get("cleared")) for r in kept) else None),
                 successful_worlds=sum(r.get("success") is True and r.get("cleared") == r.get("n")
                                       and not r.get("error") for r in kept),
                 fallback_worlds=sum(bool(r.get("fallback_reason")) for r in kept), groups={})
        for group in sorted({w["group"] for w in worlds}):
            group_ids = {w["world_id"] for w in worlds if w["group"] == group}
            group_rows = [r for r in kept if r["world_id"] in group_ids]
            group_ok = (len(group_rows) == len(group_ids)
                        and not parse_errors and not relevant_unexpected
                        and not any(e["world_id"] in group_ids for e in errors+failures)
                        and not any(e["world_id"] in group_ids for e in duplicates))
            q["groups"][group] = dict(expected_worlds=len(group_ids), recorded_unique_worlds=len(group_rows),
                                      complete_success=group_ok,
                                      mean_seconds_per_source=(float(np.mean([r["average_s"] for r in group_rows]))
                                                               if group_ok else None))
        result["questions"][str(mode)] = q
    return result


def paired_statistics(candidate: list[float], baseline: list[float], worlds: list[dict],
                      bootstrap: dict) -> dict:
    """Stratified paired percentile CI; no initialization resampling."""
    c, b = np.asarray(candidate, dtype=float), np.asarray(baseline, dtype=float)
    if c.shape != b.shape or c.shape != (len(worlds),) or not len(worlds):
        raise ValueError("Paired arrays must align exactly with registered world IDs")
    if not np.isfinite(c).all() or not np.isfinite(b).all() or np.any(c < 0) or np.any(b < 0):
        raise ValueError("Paired times must be finite and nonnegative")
    delta = c-b
    rng = np.random.default_rng(bootstrap["seed"])
    resamples = np.zeros(bootstrap["resamples"], dtype=float)
    groups = {}
    for group in sorted({w["group"] for w in worlds}):
        ids = [i for i, w in enumerate(worlds) if w["group"] == group]
        sampled = rng.integers(0, len(ids), size=(bootstrap["resamples"], len(ids)))
        # Keep the observed group count in every resample, preserving plan weights.
        resamples += delta[np.asarray(ids)][sampled].sum(axis=1)/len(worlds)
        cg, bg = float(c[ids].mean()), float(b[ids].mean())
        groups[group] = dict(worlds=len(ids), candidate_mean_s_per_source=cg,
                             baseline_mean_s_per_source=bg, difference_s_per_source=cg-bg,
                             improvement_percent=100*(bg-cg)/bg if bg > 0 else None,
                             candidate_slower_worlds=int((delta[ids] > 0).sum()))
    candidate_mean, baseline_mean = float(c.mean()), float(b.mean())
    lo, hi = np.quantile(resamples, [0.025, 0.975], method="linear")
    return dict(worlds=len(worlds), candidate_mean_s_per_source=candidate_mean,
                baseline_mean_s_per_source=baseline_mean,
                mean_difference_s_per_source=float(delta.mean()),
                improvement_percent=(100*(baseline_mean-candidate_mean)/baseline_mean if baseline_mean > 0 else None),
                difference_ci95_s_per_source=[float(lo), float(hi)],
                candidate_slower_worlds=int((delta > 0).sum()),
                candidate_equal_worlds=int((delta == 0).sum()),
                candidate_faster_worlds=int((delta < 0).sum()), groups=groups,
                bootstrap=dict(**bootstrap, interval="two-sided percentile 95%",
                               numpy_version=np.__version__, rng="numpy.default_rng.PCG64",
                               independent_units="registered worlds within scenario group",
                               initialization_resampled=False))


def paired_rows(worlds: list[dict], candidate: list[float], c7: list[float], bc: list[float]) -> list[dict]:
    return [dict(world_id=w["world_id"], group=w["group"], candidate_s_per_source=c,
                 original_c7_s_per_source=a, corresponding_bc_s_per_source=b)
            for w, c, a, b in zip(worlds, candidate, c7, bc)]


def summarize(plan: dict, ledgers: dict[str, tuple[list[dict], list[dict], dict]]) -> dict:
    seeds, by_mode, bootstrap = plan_contract(plan)
    specs = part_specs(plan)
    c7_rows = ledgers["original_c7"][0]
    c7_counts = Counter(r.get("world_id") for r in c7_rows if isinstance(r.get("world_id"), str))
    reference_n = {r["world_id"]: r["n"] for r in c7_rows
                   if isinstance(r.get("world_id"), str) and c7_counts[r["world_id"]] == 1
                   and integer(r.get("n"), minimum=10, maximum=16)}
    parts = {spec["key"]: audit_part(spec, *ledgers[spec["key"]], by_mode, reference_n) for spec in specs}
    maps = {key: {r["world_id"]: r for r in rows if isinstance(r.get("world_id"), str)}
            for key, (rows, _, _) in ledgers.items()}
    algorithms = {}
    for algorithm in ALGORITHMS:
        modes = {}
        for mode, worlds in by_mode.items():
            selected = {}
            for seed in seeds:
                keys = [f"{algorithm}_init{seed}_ep{ep:04d}" for ep in plan[algorithm]["checkpoint_episodes"]]
                available = [key for key in keys if parts[key]["questions"][str(mode)]["eligible_for_selection"]]
                # min is stable: exact ties use the first preregistered checkpoint.
                best = min(available, key=lambda key: parts[key]["questions"][str(mode)]["mean_seconds_per_source"]) if available else None
                record = dict(seed=seed, selected_part=best,
                              selected_episode_count=parts[best]["episodes"] if best else None,
                              eligible_checkpoints=available,
                              unavailable_or_failed_checkpoints=[key for key in keys if key not in available],
                              selection_rule="minimum complete-checkpoint mean seconds/source; exact ties use preregistered order",
                              paired_comparison_available=False, comparisons=None,
                              improves_both_baselines=False)
                if best is not None:
                    record["mean_seconds_per_source"] = parts[best]["questions"][str(mode)]["mean_seconds_per_source"]
                    bc_key = f"bc_init{seed}"
                    if all(parts[key]["questions"][str(mode)]["eligible_for_selection"] for key in ("original_c7", bc_key)):
                        candidate = [maps[best][w["world_id"]]["average_s"] for w in worlds]
                        c7 = [maps["original_c7"][w["world_id"]]["average_s"] for w in worlds]
                        bc = [maps[bc_key][w["world_id"]]["average_s"] for w in worlds]
                        comparisons = {"original_c7": paired_statistics(candidate, c7, worlds, bootstrap),
                                       "corresponding_bc": paired_statistics(candidate, bc, worlds, bootstrap)}
                        record.update(paired_comparison_available=True, comparisons=comparisons,
                                      paired_worlds=paired_rows(worlds, candidate, c7, bc),
                                      improves_both_baselines=all(v["mean_difference_s_per_source"] < 0 for v in comparisons.values()))
                selected[str(seed)] = record
            ready = all(record["paired_comparison_available"] for record in selected.values())
            direction_count = sum(record["improves_both_baselines"] for record in selected.values())
            checks = dict(all_three_initializations_have_complete_choices_and_baselines=ready,
                          initializations_improving_both_baselines=direction_count,
                          at_least_two_of_three_improve_both=direction_count >= 2,
                          original_c7_mean_improvement_at_least_2_percent=False,
                          corresponding_bc_mean_improvement_at_least_2_percent=False,
                          original_c7_difference_ci95_upper_below_zero=False,
                          corresponding_bc_difference_ci95_upper_below_zero=False)
            aggregate = None
            if ready:
                records = [selected[str(seed)]["paired_worlds"] for seed in seeds]
                c = np.mean([[r["candidate_s_per_source"] for r in rows] for rows in records], axis=0).tolist()
                c7 = [r["original_c7_s_per_source"] for r in records[0]]
                bc = np.mean([[r["corresponding_bc_s_per_source"] for r in rows] for rows in records], axis=0).tolist()
                comparisons = {"original_c7": paired_statistics(c, c7, worlds, bootstrap),
                               "corresponding_bc": paired_statistics(c, bc, worlds, bootstrap)}
                for name, result in comparisons.items():
                    improvement = result["improvement_percent"]
                    checks[f"{name}_mean_improvement_at_least_2_percent"] = (
                        improvement is not None and improvement >= MIN_IMPROVEMENT_PERCENT)
                    checks[f"{name}_difference_ci95_upper_below_zero"] = result["difference_ci95_s_per_source"][1] < 0
                aggregate = dict(initializations=len(seeds), independent_worlds=len(worlds),
                                 initialization_evaluations=len(seeds)*len(worlds),
                                 candidate_and_bc_averaged_within_each_world_before_bootstrap=True,
                                 comparisons=comparisons, paired_worlds=paired_rows(worlds, c, c7, bc))
            passed = all(value for key, value in checks.items() if key != "initializations_improving_both_baselines")
            modes[str(mode)] = dict(initialization_choices=selected, aggregate=aggregate,
                                   promotion_checks=checks, meets_preregistered_selection_gate=passed,
                                   disposition="选择证据满足预登记门槛；不构成默认替换授权" if passed else "未满足预登记门槛；保留C7",
                                   unavailability_reasons=[] if ready else [
                                       f"初始化{seed}无完整可配对的已选检查点或对照"
                                       for seed, row in selected.items() if not row["paired_comparison_available"]])
        algorithms[algorithm] = modes
    return dict(version=ANALYSIS_VERSION,
                evidence_boundary=dict(evidence="checkpoint-selection evidence with selection bias",
                    final_blind_validation=False, official_validation=False, old_exposed_regression_is_not_new_validation=True,
                    policy_or_training_tuned_by_this_analysis=False, default_c7_replacement_authorized=False,
                    inference_scope="Twelve registered local scenario groups; no claim about official environment or unseen distributions",
                    interval_limitation="Exploratory percentile intervals after checkpoint selection; no correction for selection or multiple comparisons"),
                protocol=dict(initialization_seeds=seeds, worlds_per_question=96, scenario_groups_per_question=12,
                    bootstrap=bootstrap, paired_difference_sign="candidate minus baseline; negative is faster",
                    relative_improvement_formula="100 * (baseline mean - candidate mean) / baseline mean",
                    cross_initialization_rule="Each of at least two initializations must improve against both its own BC and original C7",
                    mean_gate_percent=MIN_IMPROVEMENT_PERCENT, exact_ties="earlier preregistered checkpoint"),
                inputs_collection_complete=all(q["collection_complete"] for p in parts.values() for q in p["questions"].values()),
                planned_parts=len(specs), planned_model_checkpoints=sum(p["category"] == "models" for p in specs),
                parts=parts, algorithms=algorithms,
                recorded_evaluation_cost=dict(episode_rows=sum(p["rows_recorded"] for p in parts.values()),
                    business_primitives=sum(p["recorded_cost"]["business_primitives"] for p in parts.values()),
                    execution_wall_s=sum(p["recorded_cost"]["execution_wall_s"] for p in parts.values()),
                    cost_rows_invalid=sum(p["recorded_cost"]["cost_rows_invalid"] for p in parts.values()),
                    note="Sum of saved evaluation rows across all parts, including rejected checkpoints. Not training cost or controlled machine throughput."))


def missing_checkpoint_reason(spec: dict, execution_root: Path) -> dict:
    if spec["category"] != "models":
        return dict(status="baseline_result_missing", reason="Baseline evaluation rows are unavailable")
    path = execution_root / f"results/g2/init_{spec['seed']}/{spec['algorithm']}/summary.json"
    if not path.exists():
        return dict(status="result_missing_training_completion_unknown", reason="No final training summary is available")
    encoded = path.read_bytes()
    summary = json.loads(encoded)
    positions = summary.get("checkpoint_positions", [])
    completed = summary.get("completed_training_episodes")
    detail = dict(training_summary_path=str(path.resolve()), training_summary_sha256=sha_bytes(encoded),
                  completed_training_episodes=completed, available_checkpoint_positions=positions,
                  training_stop_reason=summary.get("stop_reason"))
    if spec["episodes"] not in positions:
        return dict(status="not_executed_checkpoint_unavailable", **detail,
                    reason="Training ended before this checkpoint or did not retain it; this planned selection position was not executable")
    return dict(status="result_missing_for_available_checkpoint", **detail,
                reason="Training retained the checkpoint but selection rows are unavailable")


def number(value: float | None, digits: int = 3) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def render_report(summary: dict) -> str:
    lines = ["# G2检查点选择结果", "", "本报告只分析已保存的选择评估记录。先逐题检查全部96个注册world的身份、清除、异常和费用一致性，再在每个初始化的合格检查点中选择平均秒/源最小者。", "",
             "这是检查点选择后的本地证据，存在选择偏差，置信区间未校正选择和多重比较。它不是新的盲测、旧暴露回归的独立复验或官方Windows验证，也不授权默认替换C7。", "",
             "## 分题结论", "", "| 算法 | 题目 | 满足选择门槛 | 同时优于C7与本初始化BC的初始化数 | 相对C7改善 | 相对BC改善 |", "|---|---:|---|---:|---:|---:|"]
    for algorithm, modes in summary["algorithms"].items():
        for mode, result in modes.items():
            comparisons = result["aggregate"]["comparisons"] if result["aggregate"] else {}
            lines.append(f"| {algorithm.upper()} | {mode} | {'是' if result['meets_preregistered_selection_gate'] else '否'} | {result['promotion_checks']['initializations_improving_both_baselines']}/3 | {number(comparisons.get('original_c7', {}).get('improvement_percent'))}% | {number(comparisons.get('corresponding_bc', {}).get('improvement_percent'))}% |")
    lines += ["", "晋级需三个初始化均有完整可配对的选择；按同一world先平均三个初始化，再分别相对C7和对应BC检验：平均改善至少2%、配对差值95%区间上界严格小于0，并且至少两个相同初始化同时优于两种对照。未满足的题保留C7。", "",
              "## 每个初始化的选择与配对比较", "", "差值为候选减对照，负值表示更快；相对改善为`100×(对照均值−候选均值)/对照均值`。下表区间按12场景分层、world配对、10000次bootstrap，随机种子84771。精确并列时保留较早预登记检查点。", "",
              "| 算法 | 题目 | 初始化 | 选择训练局数 | 候选秒/源 | 对照 | 改善% | 差值95%区间（秒/源） |", "|---|---:|---:|---:|---:|---|---:|---|"]
    for algorithm, modes in summary["algorithms"].items():
        for mode, result in modes.items():
            for seed, record in result["initialization_choices"].items():
                comparisons = record["comparisons"] or {"不可配对": None}
                for baseline, comparison in comparisons.items():
                    interval = "—" if comparison is None else "["+", ".join(number(v) for v in comparison["difference_ci95_s_per_source"])+"]"
                    lines.append(f"| {algorithm.upper()} | {mode} | {seed} | {record['selected_episode_count'] or '—'} | {number(record.get('mean_seconds_per_source'))} | {baseline} | {number(comparison['improvement_percent'] if comparison else None)} | {interval} |")
    lines += ["", "## 三个初始化按world合并后的区间", "", "每题只有96个独立world单位；同一world的三个初始化先求平均，不把288次策略执行当作288个独立world。", "",
              "| 算法 | 题目 | 对照 | 候选均值 | 对照均值 | 配对差值均值 | 差值95%区间 | 候选更慢world数 |", "|---|---:|---|---:|---:|---:|---|---:|"]
    for algorithm, modes in summary["algorithms"].items():
        for mode, result in modes.items():
            if not result["aggregate"]:
                lines.append(f"| {algorithm.upper()} | {mode} | 无完整三初始化配对 | — | — | — | — | — |")
                continue
            for baseline, comparison in result["aggregate"]["comparisons"].items():
                interval = "["+", ".join(number(v) for v in comparison["difference_ci95_s_per_source"])+"]"
                lines.append(f"| {algorithm.upper()} | {mode} | {baseline} | {number(comparison['candidate_mean_s_per_source'])} | {number(comparison['baseline_mean_s_per_source'])} | {number(comparison['mean_difference_s_per_source'])} | {interval} | {comparison['candidate_slower_worlds']}/96 |")
    lines += ["", "## 全部预登记位置", "", "下表保留6个对照位置和24个模型检查点，每题分别显示。失败、缺失和未执行的检查点不参加该题选择，也不从报告中删除；不对成功子集给出耗时排名。", "",
              "| 位置 | 题目 | 状态 | 已记录/应记录 | 正常全清world | 失败行 | 无效行 | 重复ID | 缺失ID | 均值秒/源 |", "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|"]
    statuses = {"complete_success": "完整全清", "complete_with_failures": "完整但有失败", "not_executed_or_result_missing": "未执行或结果缺失", "incomplete_or_invalid": "不完整或无效"}
    for key, part in summary["parts"].items():
        for mode, q in part["questions"].items():
            status = statuses[q["status"]]
            if part.get("missing_reason", {}).get("status") == "not_executed_checkpoint_unavailable":
                status = "未执行：训练未提供此检查点"
            lines.append(f"| {key} | {mode} | {status} | {q['recorded_expected_rows']}/{q['expected_rows']} | {q['successful_worlds']} | {len(q['failed_rows'])} | {len(q['invalid_rows'])} | {len(q['duplicate_world_ids'])} | {len(q['missing_world_ids'])} | {number(q['mean_seconds_per_source'])} |")
    lines += ["", "## 分场景配对结果", "", "同时报告场景均值退步及单world退步。表中先按world平均三个初始化；若三初始化条件不满足，则该算法该题没有合并结果。", "",
              "| 算法 | 题目 | 对照 | 场景 | world数 | 候选秒/源 | 对照秒/源 | 改善% | 候选更慢world数 |", "|---|---:|---|---|---:|---:|---:|---:|---:|"]
    for algorithm, modes in summary["algorithms"].items():
        for mode, result in modes.items():
            if result["aggregate"]:
                for baseline, comparison in result["aggregate"]["comparisons"].items():
                    for group, group_result in comparison["groups"].items():
                        lines.append(f"| {algorithm.upper()} | {mode} | {baseline} | {group} | {group_result['worlds']} | {number(group_result['candidate_mean_s_per_source'])} | {number(group_result['baseline_mean_s_per_source'])} | {number(group_result['improvement_percent'])} | {group_result['candidate_slower_worlds']} |")
    cost = summary["recorded_evaluation_cost"]
    lines += ["", "## 费用与可复核范围", "",
              f"记录中共有{cost['episode_rows']}行评估执行，业务调用{cost['business_primitives']}次，逐局现实执行耗时合计{number(cost['execution_wall_s'])}秒。费用字段无效的行数为{cost['cost_rows_invalid']}。这里包含失败和被拒绝检查点；缺失或无法解析的记录成本未知，不记作零。上述耗时没有包含训练或文件I/O，不能用于受控机器速度排名。", "",
              "完整ID、失败原因、所有输入散列、每world配对数值、全部门槛布尔值和每初始化场景结果在`selection_summary.json`。本程序不运行环境、不训练模型、不生成世界，也不产生默认替换C7的授权。", ""]
    return "\n".join(lines)


def analyze_saved(execution_root: Path, results_root: Path, plan_path: Path) -> dict:
    encoded = plan_path.read_bytes()
    plan = json.loads(encoded)
    plan_contract(plan)
    specs = part_specs(plan)
    ledgers = {spec["key"]: read_ledger(results_root/spec["category"]/spec["key"]/"rows.jsonl") for spec in specs}
    summary = summarize(plan, ledgers)
    for spec in specs:
        part = summary["parts"][spec["key"]]
        if not part["input"]["exists"]:
            part["missing_reason"] = missing_checkpoint_reason(spec, execution_root)
    # Refuse to seal a mixture of different ledger versions while collection runs.
    for _, _, source in ledgers.values():
        path = Path(source["path"])
        if path.exists() != source["exists"] or (path.exists() and sha_bytes(path.read_bytes()) != source["sha256"]):
            raise RuntimeError("An input ledger changed while analysis ran; rerun after collection has settled")
    if plan_path.read_bytes() != encoded:
        raise RuntimeError("The registered plan changed while analysis ran")
    summary["provenance"] = dict(plan_path=str(plan_path.resolve()), plan_sha256=sha_bytes(encoded),
                                  analysis_path=str(Path(__file__).resolve()), analysis_sha256=sha_bytes(Path(__file__).read_bytes()),
                                  results_root=str(results_root.resolve()), environment_world_executions=0)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--results", type=Path, default=None)
    parser.add_argument("--plan", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None, help="New output directory; existing deliverables are never overwritten")
    args = parser.parse_args()
    root = args.execution_root.resolve()
    results = args.results.resolve() if args.results else root/"results/g2_selection"
    plan = args.plan.resolve() if args.plan else root/"data/g2_plan.json"
    out = args.out.resolve() if args.out else root/"analysis/selection_result"
    if any((out/name).exists() for name in ("selection_summary.json", "REPORT.md")):
        raise RuntimeError("Choose a new output directory; refusing to overwrite a prior analysis")
    summary = analyze_saved(root, results, plan)
    dump(out/"selection_summary.json", summary)
    (out/"REPORT.md").write_text(render_report(summary), encoding="utf-8")
    print(json.dumps(dict(output=str(out), planned_checkpoints=summary["planned_model_checkpoints"],
                          input_rows=summary["recorded_evaluation_cost"]["episode_rows"],
                          selection_gates={a: {q: r["meets_preregistered_selection_gate"] for q, r in modes.items()}
                                           for a, modes in summary["algorithms"].items()},
                          actual_world_executions=0), ensure_ascii=False))


if __name__ == "__main__":
    main()
