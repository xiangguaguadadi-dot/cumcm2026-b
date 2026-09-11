#!/usr/bin/env python3
"""Describe saved Q behavior without importing a policy, network or simulator.

Example (writes only the requested output directory):
  python verification/q_diagnostics.py --execution-root /path/to/20260911_rl_execution \
      --output-dir /path/to/new_diagnostic_output --phase training

Default deep mode reads each indexed gzip episode once. --rows-only uses the
existing coarse ledger and explicitly marks metadata diagnostics unavailable.
This tool never executes a world, checkpoint or selection policy.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import time

VERSION = "q-saved-behavior-diagnostics-v1"
CLOCK_CONTRACT = "training_extrema_v2_clocks_physical_only"
CLOCK_FIELDS = {"global_features.elapsed_real_1200", "global_features.remaining_real_1200"}
TRAIN_RE = re.compile(r"init_(\d+)$")
DEPLOY_RE = re.compile(r"q_init(\d+)_ep(\d+)$")
RANGE_REASONS = {"outside_behavior_feature_range", "unfitted_behavior_feature_range"}
CLOCK_REASONS = {"invalid_physical_clock_range", "invalid_clock_and_empirical_feature_range"}
LIMITS = [
    "仅描述已保存轨迹；没有运行环境、模型、训练或新的选择评估。",
    "teacher一致率比较的是每次Q实际遇到的同一快照中记录的teacher候选。",
    "没有在相同快照上重新评估BC，因此不能据此认定Q等同BC；不同策略到达的状态也不能直接逐动作比较。",
    "训练前缀包含持续变化的策略与显式探索，不代表相应冻结检查点的部署行为。",
    "训练混合策略的selection_reason可能描述探索前的基策略；报告另按explored_alternative区分实际动作。",
    "invalid_q_or_support同时包含非有限分数与其他无效支持情况，现有记录不足以全部归因为NaN/Inf。",
    "经验特征范围和BC支持集合都不是几何安全或置信度保证；时钟v2仅检查有限性和物理范围。",
    "保存的失败、零决策及有兜底的局均保留；缺失元数据不会被解释为零次触发。",
    "选择结果属于已暴露的检查点选择记录，本报告不产生新的盲测或官方成绩。",
]


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def integer(value):
    return type(value) is int and value >= 0


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sorted_counts(values):
    return dict(sorted(values.items(), key=lambda item: (-item[1], str(item[0]))))


class Stats:
    def __init__(self):
        self.n = 0
        self.total = 0.0
        self.minimum = None
        self.maximum = None

    def add(self, value):
        if not finite(value):
            return
        self.n += 1
        self.total += value
        self.minimum = value if self.minimum is None else min(self.minimum, value)
        self.maximum = value if self.maximum is None else max(self.maximum, value)

    def result(self):
        return {"n": self.n, "sum": self.total, "mean": self.total / self.n if self.n else None,
                "min": self.minimum, "max": self.maximum}


def action_category(reason, explored):
    if explored is True:
        return "exploration_alternative"
    if reason == "supported_q_argmax":
        return "supported_q_argmax"
    if reason in RANGE_REASONS:
        return "empirical_range_or_unfitted_fallback"
    if reason in CLOCK_REASONS:
        return "physical_clock_or_mixed_range_fallback"
    if reason == "invalid_q_or_support":
        return "invalid_q_or_support_fallback"
    if reason == "early_teacher_mixture":
        return "early_teacher_base"
    return "other_or_unspecified"


class Group:
    def __init__(self, phase, seed, checkpoint, mode, scope):
        self.identity = dict(phase=phase, initialization_seed=seed, checkpoint_episode=checkpoint,
                             question=mode, trajectory_policy_scope=scope)
        self.episodes = 0
        self.worlds = Counter()
        self.successes = 0
        self.failures = 0
        self.unknown_terminal = 0
        self.sources = Counter()
        self.total_decisions = 0
        self.decision_count_known_episodes = 0
        self.teacher_comparable = 0
        self.teacher_equal = 0
        self.reason_counts = Counter()
        self.actual_actions = Counter()
        self.reason_comparable = 0
        self.deep_decisions = 0
        self.metadata_decisions = 0
        self.training_selector_decisions = 0
        self.action_source_known = 0
        self.guard_missing_violation_list = 0
        self.exploration_flag_known = 0
        self.explored = 0
        self.selected_fallback = 0
        self.support_count = Stats()
        self.support_histogram = Counter()
        self.support_valid_sum = 0
        self.support_sum_with_valid = 0
        self.support_valid_rows = 0
        self.selected_outside_support = 0
        self.selected_support_comparable = 0
        self.range_fields = Counter()
        self.applied_range_fields = Counter()
        self.range_field_offending_rows = Counter()
        self.violation_reasons = Counter()
        self.range_list_present = 0
        self.contracts = Counter()
        self.clock_decisions = 0
        self.clocks = defaultdict(lambda: {"values": Stats(), "records": 0,
            "skip_true": 0, "physical_valid": 0, "physical_invalid": 0,
            "physical_unknown": 0, "skip_reasons": Counter()})
        self.virtual_time = Stats()
        self.tail_time = Stats()
        self.takeover_tail = Stats()
        self.takeover_count = 0
        self.takeover_reasons = Counter()
        self.takeover_tail_by_reason = defaultdict(Stats)
        self.business_calls = Stats()
        self.disagreements = Counter()

    def add(self, row, raw, ordinal):
        self.episodes += 1
        self.worlds[str(row.get("world_id", "unknown"))] += 1
        success = row.get("success")
        if success is True:
            self.successes += 1
        elif success is False:
            self.failures += 1
        else:
            self.unknown_terminal += 1
        self.business_calls.add(row.get("business_primitives"))
        decisions = raw.get("decisions") if isinstance(raw, dict) else None
        deep = isinstance(decisions, list)
        self.sources["full_episode" if deep else "row_only"] += 1
        total = raw.get("total_time_s", raw.get("virtual_time_s")) if deep else row.get("virtual_time_s")
        tail = raw.get("tail_time_s") if deep else row.get("tail_time_s")
        self.virtual_time.add(total)
        self.tail_time.add(tail)
        takeover_reason = raw.get("fallback_reason") if deep else row.get("fallback_reason")
        takeover = takeover_reason is not None or (finite(tail) and tail > 0)
        if takeover:
            reason = str(takeover_reason or "positive_tail_without_saved_reason")
            self.takeover_count += 1
            self.takeover_tail.add(tail)
            self.takeover_reasons[reason] += 1
            self.takeover_tail_by_reason[reason].add(tail)
        if not deep:
            n = row.get("decisions")
            matches = row.get("teacher_matches")
            if integer(n):
                self.decision_count_known_episodes += 1
                self.total_decisions += n
                if integer(matches) and matches <= n:
                    self.teacher_comparable += n
                    self.teacher_equal += matches
            reasons = row.get("selector_reasons")
            if isinstance(reasons, dict):
                valid_counts = {str(k): v for k, v in reasons.items() if integer(v)}
                self.reason_counts.update(valid_counts)
                self.reason_comparable += sum(valid_counts.values())
            return
        if integer(row.get("decisions")) and row["decisions"] != len(decisions):
            self.disagreements["row_decisions_vs_full_episode"] += 1
        self.decision_count_known_episodes += 1
        self.total_decisions += len(decisions)
        self.deep_decisions += len(decisions)
        episode_equal = 0
        episode_comparable = 0
        for decision in decisions:
            if not isinstance(decision, dict):
                self.disagreements["malformed_decision"] += 1
                continue
            snapshot = decision.get("snapshot")
            snapshot = snapshot if isinstance(snapshot, dict) else {}
            chosen = decision.get("index")
            teacher = snapshot.get("teacher_index")
            ids = snapshot.get("candidate_ids", [])
            valid = snapshot.get("valid_mask", [])
            candidates = snapshot.get("candidates", [])
            if integer(chosen) and integer(teacher) and chosen < len(ids) and teacher < len(ids):
                self.teacher_comparable += 1
                episode_comparable += 1
                self.teacher_equal += chosen == teacher
                episode_equal += chosen == teacher
            if integer(chosen) and chosen < len(candidates) and isinstance(candidates[chosen], dict):
                self.selected_fallback += candidates[chosen].get("kind") == "fallback"
            metadata = decision.get("metadata")
            if not isinstance(metadata, dict):
                continue
            self.metadata_decisions += 1
            saved_reason = metadata.get("selection_reason")
            reason = saved_reason if isinstance(saved_reason, str) and saved_reason else "unspecified"
            self.reason_counts[reason] += 1
            self.reason_comparable += 1
            explored = metadata.get("explored_alternative")
            if type(explored) is bool:
                self.exploration_flag_known += 1
                self.explored += explored
            training_selector = (metadata.get("training_only") is True
                                 or metadata.get("selector") == "q_training_mixture")
            self.training_selector_decisions += training_selector
            if (self.identity["phase"] == "training" or training_selector) and type(explored) is not bool:
                category = "training_exploration_status_unknown"
            else:
                category = action_category(reason, explored)
                self.action_source_known += reason != "unspecified"
            self.actual_actions[category] += 1
            self.contracts[str(metadata.get("feature_range_contract", "missing"))] += 1
            support_mask = metadata.get("support_mask")
            support = metadata.get("support_count")
            if isinstance(support_mask, list) and all(type(v) is bool for v in support_mask):
                observed_support = sum(support_mask)
                if integer(support) and support != observed_support:
                    self.disagreements["support_count_vs_mask"] += 1
                support = observed_support
                if integer(chosen) and chosen < len(support_mask):
                    self.selected_support_comparable += 1
                    self.selected_outside_support += not support_mask[chosen]
            if integer(support):
                self.support_count.add(support)
                self.support_histogram[str(support)] += 1
                if isinstance(valid, list) and all(type(v) is bool for v in valid):
                    if support > sum(valid):
                        self.disagreements["support_count_exceeds_valid_candidates"] += 1
                    else:
                        self.support_valid_sum += sum(valid)
                        self.support_sum_with_valid += support
                        self.support_valid_rows += 1
            violations = metadata.get("feature_range_violations")
            if reason in ({"outside_behavior_feature_range"} | CLOCK_REASONS) and not isinstance(violations, list):
                self.guard_missing_violation_list += 1
            if isinstance(violations, list):
                self.range_list_present += 1
                fields = set()
                for violation in violations:
                    if not isinstance(violation, dict):
                        continue
                    field = str(violation.get("field", "unknown_field"))
                    fields.add(field)
                    count = violation.get("offending_row_count")
                    if integer(count):
                        self.range_field_offending_rows[field] += count
                    self.violation_reasons[str(violation.get("reason", "unknown"))] += 1
                self.range_fields.update(fields)
                if explored is False or (self.identity["phase"] == "deployment" and not training_selector):
                    self.applied_range_fields.update(fields)
            checks = metadata.get("clock_feature_checks")
            if isinstance(checks, list):
                seen_clock_fields = {str(check.get("field")) for check in checks if isinstance(check, dict)}
                self.clock_decisions += CLOCK_FIELDS <= seen_clock_fields
                for check in checks:
                    if not isinstance(check, dict):
                        continue
                    clock = self.clocks[str(check.get("field", "unknown_clock"))]
                    clock["records"] += 1
                    clock["values"].add(check.get("observed_value"))
                    clock["skip_true"] += check.get("empirical_minmax_skipped") is True
                    clock["skip_reasons"][str(check.get("skip_reason", "missing"))] += 1
                    physical = check.get("physical_range_valid")
                    clock["physical_valid" if physical is True else "physical_invalid" if physical is False
                          else "physical_unknown"] += 1
        if episode_comparable == len(decisions) and integer(row.get("teacher_matches")):
            if row["teacher_matches"] != episode_equal:
                self.disagreements["row_teacher_matches_vs_full_episode"] += 1

    def result(self):
        known_decision_count = self.decision_count_known_episodes == self.episodes
        full_decisions = known_decision_count and self.deep_decisions == self.total_decisions
        all_metadata = full_decisions and self.metadata_decisions == self.total_decisions
        all_action_sources = all_metadata and self.action_source_known == self.total_decisions
        comparable = known_decision_count and self.teacher_comparable == self.total_decisions
        clocks = {}
        for field, values in sorted(self.clocks.items()):
            clocks[field] = {k: v.result() if isinstance(v, Stats) else sorted_counts(v)
                             if isinstance(v, Counter) else v for k, v in values.items()}
        actions = dict(self.actual_actions)
        return dict(**self.identity, episodes=self.episodes, unique_worlds=len(self.worlds),
            duplicate_world_id_rows=sum(n - 1 for n in self.worlds.values()),
            successes=self.successes, failures=self.failures, unknown_terminal=self.unknown_terminal,
            evidence_sources=dict(self.sources),
            decisions={"total": self.total_decisions,
                "episodes_with_known_decision_count": self.decision_count_known_episodes,
                "complete_decision_count_coverage": known_decision_count, "teacher_equal": self.teacher_equal,
                "teacher_comparable": self.teacher_comparable,
                "teacher_agreement_over_total": ratio(self.teacher_equal, self.total_decisions) if comparable else None,
                "teacher_agreement_over_comparable": ratio(self.teacher_equal, self.teacher_comparable),
                "full_snapshot_decisions": self.deep_decisions, "metadata_decisions": self.metadata_decisions},
            selection_reasons={"counts": sorted_counts(self.reason_counts),
                "decisions_with_reason_record": self.reason_comparable,
                "training_reason_may_describe_base_before_exploration": self.identity["phase"] == "training"},
            actual_action_categories={"counts": sorted_counts(self.actual_actions),
                "denominator_metadata_decisions": self.metadata_decisions,
                "decisions_with_resolved_action_source": self.action_source_known,
                "complete_for_all_decisions": all_action_sources,
                "proportions_over_total": {k: ratio(v, self.total_decisions) for k, v in actions.items()} if all_action_sources else None},
            exploration={"observed_alternatives": self.explored,
                "decisions_with_explicit_flag": self.exploration_flag_known,
                "fraction_among_flagged_decisions": ratio(self.explored, self.exploration_flag_known),
                "fraction_over_total": ratio(self.explored, self.total_decisions) if all_action_sources else None,
                "training_selector_metadata_decisions": self.training_selector_decisions},
            support={"candidate_count": self.support_count.result(), "count_histogram": sorted_counts(self.support_histogram),
                "decisions_with_count_and_valid_mask": self.support_valid_rows,
                "pooled_supported_candidates": self.support_sum_with_valid,
                "pooled_valid_candidates": self.support_valid_sum,
                "pooled_support_fraction": ratio(self.support_sum_with_valid, self.support_valid_sum),
                "selected_outside_recorded_support": self.selected_outside_support,
                "decisions_comparable_to_support_mask": self.selected_support_comparable,
                "scope": "only decisions that saved support metadata; in exploration this is the base Q gate"},
            range_violations={"base_decisions_by_field": sorted_counts(self.range_fields),
                "applied_nonexploratory_decisions_by_field": sorted_counts(self.applied_range_fields),
                "offending_candidate_or_channel_rows_by_field": sorted_counts(self.range_field_offending_rows),
                "violation_records_by_reason": sorted_counts(self.violation_reasons),
                "decisions_with_saved_violation_list": self.range_list_present,
                "guard_decisions_missing_violation_list": self.guard_missing_violation_list,
                "complete_decision_metadata_coverage": all_metadata,
                "scope": "field count is at most once per decision; fields can co-occur and must not be summed as unique decisions"},
            clocks={"contract_counts": sorted_counts(self.contracts), "expected_contract": CLOCK_CONTRACT,
                "decisions_with_complete_clock_feature_pair": self.clock_decisions, "fields": clocks,
                "expected_v2_metadata_decisions": self.contracts[CLOCK_CONTRACT],
                "unexpected_or_missing_contract_decisions": self.metadata_decisions - self.contracts[CLOCK_CONTRACT],
                "missing_clock_metadata_decisions": self.total_decisions - self.clock_decisions,
                "clock_v2_is_not_geometric_support": True},
            fallback={"takeover_episodes": self.takeover_count,
                "takeover_fraction": ratio(self.takeover_count, self.episodes),
                "selected_fallback_candidates_observed": self.selected_fallback,
                "tail_virtual_seconds_all_episodes": self.tail_time.result(),
                "tail_virtual_seconds_takeover_episodes": self.takeover_tail.result(),
                "whole_episode_virtual_seconds": self.virtual_time.result(),
                "tail_fraction_of_total_virtual_seconds": ratio(self.tail_time.total, self.virtual_time.total)
                    if self.tail_time.n == self.virtual_time.n == self.episodes else None,
                "takeover_reasons": sorted_counts(self.takeover_reasons),
                "tail_seconds_by_takeover_reason": {k: v.result() for k, v in sorted(self.takeover_tail_by_reason.items())}},
            business_primitive_calls=self.business_calls.result(),
            consistency_disagreements=sorted_counts(self.disagreements),
            diagnostic_flags={
                "all_observed_decisions_match_teacher": bool(self.total_decisions and comparable and self.teacher_equal == self.total_decisions),
                "no_actual_supported_q_argmax_observed": bool(self.total_decisions and all_action_sources and not actions.get("supported_q_argmax", 0)),
                "deployment_training_selector_metadata_observed": self.identity["phase"] == "deployment" and self.training_selector_decisions > 0,
                "deployment_exploration_observed": self.identity["phase"] == "deployment" and self.explored > 0,
                "bc_equivalence_assessed": False,
                "nonfinite_vs_other_invalid_support_distinguishable": False})


def discover(execution_root, phase):
    sources = []
    if phase in ("training", "both"):
        for ledger in sorted((execution_root / "results/g2").glob("init_*/q/rows.jsonl")):
            match = TRAIN_RE.fullmatch(ledger.parent.parent.name)
            if match:
                sources.append((ledger, "training", int(match[1]), None))
    if phase in ("deployment", "both"):
        for ledger in sorted((execution_root / "results/g2_selection/models").glob("q_init*_ep*/rows.jsonl")):
            match = DEPLOY_RE.fullmatch(ledger.parent.name)
            if match:
                sources.append((ledger, "deployment", int(match[1]), int(match[2])))
    return sources


def archive_for(root, ledger, row):
    stored = row.get("storage", {})
    name = stored.get("path") if isinstance(stored, dict) else None
    if isinstance(name, str):
        path = Path(name)
        return path if path.is_absolute() else root / path
    match = re.search(r":q([34]):(\d+)$", str(row.get("world_id", "")))
    return ledger.parent / "episodes" / f"q{int(match[1])}_{int(match[2]):04d}.json.gz" if match else None


def markdown_report(result):
    def percent(value):
        return "未核定" if value is None else f"{100 * value:.2f}%"
    lines = ["# Q 已保存行为诊断", "", f"工具版本：`{VERSION}`。新世界、新训练、新选择执行均为 0。",
             "", "按实际保存的决策统计；失败与兜底费用均保留。", "",
             "| 阶段 / 范围 | 初始化 | 检查点 | 题 | 局数 | teacher一致 / 总决策 | 实际支持Q动作 | 经验范围回退 | 探索动作 | 兜底尾费 / 秒 |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for group in result["groups"]:
        d = group["decisions"]
        a = group["actual_action_categories"]
        counts = a["counts"]
        complete = a["complete_for_all_decisions"]
        def action(name):
            return str(counts.get(name, 0)) if complete else f"已见{counts.get(name, 0)}（不完整）"
        stage = "训练全程" if group["trajectory_policy_scope"] == "training_changing_policy_all_recorded" else (
            "训练累计前缀" if group["phase"] == "training" else "冻结模型部署")
        teacher = f"{d['teacher_equal']}/{d['total']} ({percent(d['teacher_agreement_over_total'])})"
        tail = group["fallback"]["tail_virtual_seconds_all_episodes"]
        tail_text = f"{tail['sum']:.2f}" if tail["n"] == group["episodes"] else f"已知{tail['sum']:.2f}（缺失）"
        lines.append(f"| {stage} | {group['initialization_seed']} | {group['checkpoint_episode'] or '—'} | {group['question']} | "
                     f"{group['episodes']} | {teacher} | {action('supported_q_argmax')} | "
                     f"{action('empirical_range_or_unfitted_fallback')} | {action('exploration_alternative')} | {tail_text} |")
    if not result["groups"]:
        lines += ["", "没有发现符合输入路径的已保存Q记录；没有生成或执行任何选择场景。"]
    lines += ["", "判断方式：teacher一致比例很高只说明Q在这些自身轨迹状态上常选相同候选。结合实际支持Q动作与回退原因，可区分“Q主动选中teacher候选”和“范围保护强制回退”；仍不能据此证明Q等同BC。",
              "", "完整 JSON 另含支持集合候选数/占比、非有限或其他无效支持回退、逐字段范围原因、时钟v2检查、兜底原因及费用、缺失数据和分母。"]
    inconsistent_groups = sum(bool(group["consistency_disagreements"]) for group in result["groups"])
    if inconsistent_groups:
        lines += ["", f"有 {inconsistent_groups} 组出现账本、完整快照或支持元数据不一致；具体计数见 JSON，需核对后再解释其行为。"]
    if result["issues"]:
        lines += ["", f"发现 {len(result['issues'])} 项输入/一致性提示，详见 JSON；不据缺失元数据断言没有回退。"]
    lines += ["", "解释边界：", ""] + [f"- {text}" for text in LIMITS]
    lines += ["", "训练前缀只为与已登记检查点位置对照而汇总，不应跨组相加：它们与训练全程、其他前缀重叠。",
              "统计读取开始后的新写入记录可能不包含在本次快照中；每个输入账本的散列和实际读取行数已记录。", ""]
    return "\n".join(lines)


def diagnose(root, phase, rows_only):
    groups = {}
    inputs = []
    issues = []
    for ledger, stage, seed, checkpoint in discover(root, phase):
        encoded = ledger.read_bytes()
        records = []
        for line_number, line in enumerate(encoded.splitlines(), 1):
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError("ledger row is not an object")
                records.append((line_number, row))
            except (ValueError, UnicodeError) as error:
                issues.append(dict(path=str(ledger), line=line_number, kind="unreadable_ledger_row", error=str(error)))
        prefixes = []
        world_ids = [str(row.get("world_id", "unknown")) for _, row in records]
        chronology_complete = len(records) == len(encoded.splitlines()) and len(set(world_ids)) == len(world_ids)
        checkpoint_file = ledger.parent / "checkpoints.json"
        if stage == "training" and checkpoint_file.exists():
            try:
                registered = json.loads(checkpoint_file.read_text())
                if not isinstance(registered, list):
                    raise ValueError("checkpoint registry is not a list")
                prefixes = sorted({r["episodes"] for r in registered if isinstance(r, dict) and integer(r.get("episodes")) and r["episodes"] > 0})
                unavailable = [point for point in prefixes if point > len(records)]
                if unavailable:
                    issues.append(dict(path=str(checkpoint_file), kind="checkpoint_prefix_exceeds_saved_rows", checkpoint_episodes=unavailable))
                prefixes = [point for point in prefixes if point <= len(records)]
                if not chronology_complete:
                    issues.append(dict(path=str(ledger), kind="training_prefixes_omitted_due_to_missing_or_duplicate_rows"))
                    prefixes = []
            except (ValueError, KeyError, TypeError) as error:
                issues.append(dict(path=str(checkpoint_file), kind="unreadable_checkpoint_registry", error=str(error)))
        indexed_paths = set()
        loaded = 0
        for ordinal, (line_number, row) in enumerate(records, 1):
            mode = row.get("mode")
            if mode not in (3, 4):
                issues.append(dict(path=str(ledger), line=line_number, kind="missing_question"))
                continue
            raw = None
            path = archive_for(root, ledger, row)
            if path is not None:
                indexed_paths.add(path.resolve())
            if not rows_only:
                if path is None or not path.exists():
                    issues.append(dict(path=str(path) if path else None, ledger=str(ledger), line=line_number,
                                       kind="missing_episode_archive_using_row_counts"))
                elif not path.resolve().is_relative_to((ledger.parent / "episodes").resolve()):
                    issues.append(dict(path=str(path), ledger=str(ledger), line=line_number,
                                       kind="archive_outside_this_policy_episode_directory_using_row_counts"))
                else:
                    try:
                        archive_bytes = path.read_bytes()
                        storage = row.get("storage")
                        expected = storage.get("sha256") if isinstance(storage, dict) else None
                        if expected and sha_bytes(archive_bytes) != expected:
                            raise ValueError("archive SHA256 disagrees with row storage hash")
                        entry = json.loads(gzip.decompress(archive_bytes))
                        if not isinstance(entry, dict):
                            raise ValueError("episode envelope is not an object")
                        if entry.get("world_id") != row.get("world_id"):
                            raise ValueError("archive world_id disagrees with row")
                        raw = entry.get("raw")
                        if not isinstance(raw, dict) or not isinstance(raw.get("decisions"), list):
                            raise ValueError("archive has no complete decision list")
                        loaded += 1
                    except (ValueError, OSError, EOFError, TypeError) as error:
                        raw = None
                        issues.append(dict(path=str(path), kind="unreadable_or_inconsistent_archive_using_row_counts", error=str(error)))
            scopes = [(checkpoint, "frozen_q_checkpoint_deployment")] if stage == "deployment" else [
                (None, "training_changing_policy_all_recorded")]
            if stage == "training":
                scopes += [(point, "training_changing_policy_cumulative_prefix") for point in prefixes if ordinal <= point]
            for point, scope in scopes:
                key = (stage, seed, point, mode, scope)
                if key not in groups:
                    groups[key] = Group(stage, seed, point, mode, scope)
                groups[key].add(row, raw, ordinal)
            # The next iteration can release the full expanded episode; no corpus is retained.
            raw = None
            entry = None
        archives = {p.resolve() for p in (ledger.parent / "episodes").glob("*.json.gz")}
        unindexed = sorted(str(p) for p in archives - indexed_paths)
        inputs.append(dict(path=str(ledger), sha256=sha_bytes(encoded), bytes=len(encoded),
            valid_rows=len(records), total_lines=len(encoded.splitlines()), archives_loaded=loaded,
            checkpoint_prefixes_included=prefixes, unindexed_archive_count=len(unindexed),
            unindexed_archive_examples=unindexed[:20]))
    ordered = sorted(groups.values(), key=lambda g: (g.identity["initialization_seed"], g.identity["phase"],
        g.identity["checkpoint_episode"] or 0, g.identity["question"]))
    return dict(tool_version=VERSION, generated_at_utc=datetime.now(timezone.utc).isoformat(),
        execution_root=str(root), requested_phase=phase, rows_only=rows_only,
        task_worlds_executed=0, policy_evaluations_executed=0, optimizer_steps=0,
        new_fixture_definitions=0, comparison_to_same_state_bc="not_performed",
        inputs=inputs, groups=[group.result() for group in ordered], issues=issues, interpretation_limits=LIMITS)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--execution-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory for JSON and Chinese Markdown only")
    parser.add_argument("--phase", choices=("training", "deployment", "both"), default="both")
    parser.add_argument("--rows-only", action="store_true", help="Skip gzip reads; detailed metadata counts remain unavailable")
    args = parser.parse_args()
    root = args.execution_root.resolve()
    output = args.output_dir.resolve()
    if output.exists():
        parser.error("output directory already exists; choose a new diagnostic output directory")
    started = time.perf_counter()
    result = diagnose(root, args.phase, args.rows_only)
    result["diagnostic_wall_s"] = time.perf_counter() - started
    output.mkdir(parents=True, exist_ok=False)
    (output / "q_diagnostics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    (output / "Q_DIAGNOSTICS.md").write_text(markdown_report(result))
    print(json.dumps({"output_directory": str(output), "input_ledgers": len(result["inputs"]),
                      "groups": len(result["groups"]), "input_issues": len(result["issues"]),
                      "worlds_executed": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
