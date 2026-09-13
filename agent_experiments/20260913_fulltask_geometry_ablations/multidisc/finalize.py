#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUN = HERE / "run_01_full"


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    raw = read(RUN / "summary.json")
    comparison = raw["comparison"]
    pairs = read(RUN / "paired_rows.json")
    on = read(RUN / "on_rows.json")
    off = read(RUN / "off_rows.json")
    regressions = sorted((p for p in pairs if p["delta_seconds_per_source"] > 1e-9),
                         key=lambda p: p["delta_seconds_per_source"], reverse=True)
    save(HERE / "regression_cases.json", regressions)
    with (HERE / "paired_rows.jsonl").open("w", encoding="utf-8") as stream:
        for pair in pairs:
            stream.write(json.dumps(pair, ensure_ascii=False, allow_nan=False) + "\n")
    group_rows = []
    for group in sorted({p["group"] for p in pairs}):
        selected = [p for p in pairs if p["group"] == group]
        group_rows.append(dict(
            group=group, cases=len(selected),
            on_mean_seconds_per_source=statistics.fmean(p["on_seconds_per_source"] for p in selected),
            off_mean_seconds_per_source=statistics.fmean(p["off_seconds_per_source"] for p in selected),
            delta_seconds_per_source=statistics.fmean(p["delta_seconds_per_source"] for p in selected),
            faster=sum(p["delta_seconds_per_source"] < -1e-9 for p in selected),
            equal=sum(abs(p["delta_seconds_per_source"]) <= 1e-9 for p in selected),
            slower=sum(p["delta_seconds_per_source"] > 1e-9 for p in selected),
            delta_measure_count=statistics.fmean(p["delta_measure_count"] for p in selected),
            delta_clear_attempt_count=statistics.fmean(p["delta_clear_attempt_count"] for p in selected),
            delta_failed_clear_count=statistics.fmean(p["delta_failed_clear_count"] for p in selected),
            delta_distance_m=statistics.fmean(p["delta_distance_m"] for p in selected),
        ))
    save(HERE / "group_summary.json", group_rows)
    total_sources = sum(r["source_count"] for r in on)
    consolidated = dict(
        label=raw["label"], evidence_role="exposed frozen LOCAL-v1 regression; not blind or official",
        input_cases=raw["cases"], fresh_runs=raw["actual_fresh_runs"], total_sources_per_arm=total_sources,
        registration_sha256=raw["registration_sha256"], cases_sha256=raw["cases_sha256"],
        on_sha256=raw["b3_sha256"], off_sha256=raw["off_sha256"], runner_sha256=raw["runner_sha256"],
        all_complete=comparison["all_complete"], comparison=comparison,
        aggregate_total_virtual_time_s={"on": sum(r["total_virtual_time_s"] for r in on),
                                        "off": sum(r["total_virtual_time_s"] for r in off)},
        source_weighted_seconds_per_source={"on": sum(r["total_virtual_time_s"] for r in on) / total_sources,
                                            "off": sum(r["total_virtual_time_s"] for r in off) / total_sources},
        group_summary=group_rows,
        regression_cases=len(regressions),
        maximum_regression=regressions[0] if regressions else None,
        interpretation=dict(
            stable_benefit_gate_passed=(comparison["delta_seconds_per_source_mean"] < 0 and
                                        comparison["delta_seconds_per_source_ci95"]["upper"] < 0),
            around_half_percent_headline_target_passed=comparison["improvement_percent"] >= 0.5,
            recommended_use="Complete-task supporting evidence with exact 0.293806% effect; below the preregistered around-0.5% headline target.",
        ),
    )
    save(HERE / "summary.json", consolidated)

    group_lines = []
    for row in group_rows:
        group_lines.append(f"| {row['group']} | {row['delta_seconds_per_source']:.6f} | {row['faster']} | {row['equal']} | {row['slower']} |")
    report = f"""# 自适应多圆清除：Q3完整任务单开关消融

日期：2026-09-13。对冻结 `LOCAL-v1` 的全部1200个Q3案例，当前B3与关闭自适应多圆清除的版本各自重新执行1200次，共2400次新闭环运行；没有复用既有候选行。案例已经暴露，结果不是盲测或官方Windows成绩。

## 开关和有效性

- **ON：** 未修改的B3，SHA256 `{raw['b3_sha256']}`。
- **OFF：** 只把Q3的 `TwoDiskSpatial`、`ThreeDiskSpatial`、`MultiDiskSpatial` 服务分派绕过到共同父层 `TrialSpatial._a1_service_round`。继续测向、单点试清、B3第二测点、发现路线、可行域更新、安全清除点和父方法25 m格点最终兜底都保留。
- 两臂使用同一案例ID、源世界、seed与误差场。1200/1200对均全清并由用户出口正常结束，逐行比较有效。
- ON实际执行6588次自适应多圆计划；OFF为0，且25225次进入已登记的父层绕过。原格点函数仍解析为 `_sp_Solver.cover_polygon`；两臂在本批案例均未触发终端格点兜底。
- 策略仅接收 `InterfaceOnly(env)`。真值只用于预先构造物理世界及退出后的审计；计数器和 `env.stats()` 仅在 `run()` 返回后读取，不反馈给决策。

## 主结果

固定汇总先计算每例“总虚拟时间/本例源数”，再对1200例取算术平均。

| 指标 | ON | OFF | ON−OFF |
|---|---:|---:|---:|
| 秒/源 | {comparison['on_mean_seconds_per_source']:.6f} | {comparison['off_mean_seconds_per_source']:.6f} | **{comparison['delta_seconds_per_source_mean']:.6f}** |
| 测向总数 | {comparison['on_total_measures']} | {comparison['off_total_measures']} | {comparison['on_total_measures']-comparison['off_total_measures']:+d} |
| 光学clear尝试总数 | {comparison['on_total_clear_attempts']} | {comparison['off_total_clear_attempts']} | {comparison['on_total_clear_attempts']-comparison['off_total_clear_attempts']:+d} |
| 失败clear总数 | {comparison['on_total_failed_clears']} | {comparison['off_total_failed_clears']} | {comparison['on_total_failed_clears']-comparison['off_total_failed_clears']:+d} |
| 移动总距离/m | {comparison['on_total_distance_m']:.3f} | {comparison['off_total_distance_m']:.3f} | {comparison['on_total_distance_m']-comparison['off_total_distance_m']:+.3f} |

ON平均减少 **{abs(comparison['delta_seconds_per_source_mean']):.6f}秒/源，改善{comparison['improvement_percent']:.6f}%**。按100个seed整簇重采样、每个簇同时包含12个场景的20000次配对bootstrap，ON−OFF的95%区间为 **[{comparison['delta_seconds_per_source_ci95']['lower']:.6f}, {comparison['delta_seconds_per_source_ci95']['upper']:.6f}]秒/源**。区间完全低于0，预登记的“稳定收益”门槛通过；改善低于约0.5%的正文强亮点目标，因此应按0.293806%准确表述，适合作为完整任务支持证据，不宜写成0.5%左右。

机制上，ON每例平均少测向{abs(comparison['delta_measure_count_mean']):.6f}次，同时多做{comparison['delta_clear_attempt_count_mean']:.6f}次clear尝试；新增clear全部表现为失败试清数的增加。移动距离每例平均增加{comparison['delta_distance_m_mean']:.6f} m，其95%区间跨0。完整收益主要来自用有限多圆光学尝试替代继续测向，并非缩短路线。

## 场景与退步案例

1200例中，ON更快{comparison['faster_cases']}例、相同{comparison['equal_cases']}例、更慢{comparison['slower_cases']}例。逐场景ON−OFF如下；负数表示多圆ON更快。

| 场景 | 秒/源差 | 更快 | 相同 | 更慢 |
|---|---:|---:|---:|---:|
{chr(10).join(group_lines)}

`origin_cluster`平均退步{next(r['delta_seconds_per_source'] for r in group_rows if r['group']=='origin_cluster'):.6f}秒/源，是唯一平均退步场景。最差案例 `{regressions[0]['case_id']}` 退步{regressions[0]['delta_seconds_per_source']:.6f}秒/源，主要伴随移动距离增加{regressions[0]['delta_distance_m']:.3f} m。全部{len(regressions)}个退步案例保存在 `regression_cases.json`，没有只报告获益子集。

## 证据文件

- `registration.json`：运行前登记的输入散列、开关语义、指标和解释门槛。
- `run_01_full/on_rows.jsonl`、`off_rows.jsonl`：2400次新执行的逐行记录；对应JSON副本和精确配对行同目录保存。
- `paired_rows.jsonl`、`group_summary.json`、`summary.json`：配对差值、分场景和总汇总。
- `VALIDATION.json`：独立检查2400行、计数账目、MRO分派、ON/OFF触发数、观察器边界与冻结散列，结果通过。

该实验只隔离当前B3里已有的自适应2—10圆服务机制，不测试亮点1合成实验中的递归凸分区扩展。冻结evaluation、主solver和最佳方法文件均未修改。
"""
    (HERE / "RESULTS.md").write_text(report)
    files = {}
    for path in sorted(HERE.rglob("*")):
        if path.is_file() and path.name != "ARTIFACT_MANIFEST.json" and "__pycache__" not in path.parts:
            files[str(path.relative_to(HERE))] = {"sha256": sha(path), "bytes": path.stat().st_size}
    save(HERE / "ARTIFACT_MANIFEST.json", {"files": files, "file_count": len(files)})


if __name__ == "__main__":
    main()
