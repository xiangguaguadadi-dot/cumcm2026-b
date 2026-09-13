#!/usr/bin/env python3
"""Reconstruct and plot the B3 Q3/Q4 virtual-time decomposition.

This script reads saved rows only.  It does not import or execute the solver.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / "experiments/20260913_q2_transfer/B_improved/results/B3_exposed/case_metrics.json"
LOCAL_ENV = ROOT / "local_env.py"
EVALUATE = ROOT / "evaluate.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reconstruct(row: dict) -> dict:
    """Recover action counters omitted by evaluate.py from sufficient saved fields."""
    successes = int(row["cleared_count"])
    clear_attempts = successes + int(row["clear_failures"])
    # evaluate.py defines requests = measures + clear_attempts + entered + user_exit.
    # Every selected complete row has both the accepted enter and user exit.
    measures = int(row["requests"]) - clear_attempts - 2
    movement_s = float(row["distance_m"]) / 5.0
    measure_s = measures * 5.0
    optical_s = clear_attempts * 3.0
    laser_s = successes * 2.0
    # local_env.py defines total = movement + measures*5 + switches +
    # clear_attempts*3 + successes*2, while rounding each action to 1 us.
    raw_switches = float(row["total_virtual_time_s"]) - (
        movement_s + measure_s + optical_s + laser_s
    )
    switches = round(raw_switches)
    reconstruction_error_s = raw_switches - switches
    if measures < 0 or switches < 0 or switches > measures:
        raise AssertionError(f"invalid reconstructed counters for {row['case_id']}")
    if abs(reconstruction_error_s) > 1e-4:
        raise AssertionError(
            f"non-integral switch residual for {row['case_id']}: {raw_switches}"
        )
    total_from_components_s = movement_s + measure_s + switches + optical_s + laser_s
    return {
        "case_id": row["case_id"],
        "mode": int(row["mode"]),
        "question": f"Q{row['mode']}",
        "group": row["group"],
        "exposure_suite": row.get("exposure_suite"),
        "seed_cluster": row.get("seed_cluster"),
        "source_count": int(row["source_count"]),
        "cleared_count": successes,
        "complete": bool(row["complete"]),
        "distance_m": float(row["distance_m"]),
        "request_count": int(row["requests"]),
        "measure_count": measures,
        "channel_switch_count": switches,
        "clear_attempt_count": clear_attempts,
        "failed_clear_count": int(row["clear_failures"]),
        "successful_clear_count": successes,
        "movement_time_s": movement_s,
        "bearing_time_s": measure_s,
        "switch_time_s": float(switches),
        "optical_time_s": optical_s,
        "laser_time_s": laser_s,
        "total_from_components_s": total_from_components_s,
        "total_virtual_time_s": float(row["total_virtual_time_s"]),
        "accounting_error_s": total_from_components_s - float(row["total_virtual_time_s"]),
        "time_per_source_s": float(row["total_virtual_time_s"]) / successes,
    }


def summarize(rows: list[dict]) -> list[dict]:
    components = [
        ("movement", "移动时间", "movement_time_s"),
        ("bearing", "测向时间", "bearing_time_s"),
        ("switch", "换频时间", "switch_time_s"),
        ("optical", "光学定位", "optical_time_s"),
        ("laser", "激光清除", "laser_time_s"),
    ]
    output = []
    for mode in (3, 4):
        selected = [r for r in rows if r["mode"] == mode]
        total_mean = statistics.fmean(r["time_per_source_s"] for r in selected)
        for order, (key, label, field) in enumerate(components, 1):
            value = statistics.fmean(r[field] / r["cleared_count"] for r in selected)
            output.append(
                {
                    "question": f"Q{mode}",
                    "mode": mode,
                    "component_order": order,
                    "component_key": key,
                    "component_zh": label,
                    "mean_s_per_source": value,
                    "share_pct": 100.0 * value / total_mean,
                    "mean_total_s_per_source": total_mean,
                    "case_count": len(selected),
                    "source_count": sum(r["source_count"] for r in selected),
                    "all_complete": all(r["complete"] for r in selected),
                    "aggregation": "先逐例除以该例清除数，再对2400例取算术平均",
                    "evidence_role": "本地已暴露模拟回归；非盲测、非官方Windows成绩",
                }
            )
    return output


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def render_chart(summary: list[dict]) -> dict:
    """Write deterministic standalone SVG and rasterize it with librsvg."""
    questions = ["Q3", "Q4"]
    components = sorted({(r["component_order"], r["component_key"], r["component_zh"]) for r in summary})
    colors = {
        "movement": "#4C78A8",
        "bearing": "#F2CF5B",
        "switch": "#E07B39",
        "optical": "#72A76E",
        "laser": "#B279A2",
    }
    patterns = {"movement": None, "bearing": "diag", "switch": "cross", "optical": "dots", "laser": "backdiag"}
    by = {(r["question"], r["component_key"]): r for r in summary}
    totals = [by[(q, "movement")]["mean_total_s_per_source"] for q in questions]
    width, height = 840, 580
    left, right, top, bottom = 95, 805, 120, 450
    plot_h = bottom - top
    ymax = 520.0
    xs = [285, 615]
    bar_w = 160
    font = "PingFang SC, Hiragino Sans GB, Noto Sans CJK SC, Arial Unicode MS, sans-serif"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#FFFFFF"/>',
        '<defs>',
        '<pattern id="diag" width="9" height="9" patternUnits="userSpaceOnUse"><path d="M-2,2 L2,-2 M0,9 L9,0 M7,11 L11,7" stroke="#333A42" stroke-width="1.2" opacity="0.48"/></pattern>',
        '<pattern id="backdiag" width="9" height="9" patternUnits="userSpaceOnUse"><path d="M-2,7 L2,11 M0,0 L9,9 M7,-2 L11,2" stroke="#333A42" stroke-width="1.2" opacity="0.48"/></pattern>',
        '<pattern id="cross" width="10" height="10" patternUnits="userSpaceOnUse"><path d="M0,0 L10,10 M10,0 L0,10" stroke="#333A42" stroke-width="1.05" opacity="0.42"/></pattern>',
        '<pattern id="dots" width="8" height="8" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.1" fill="#333A42" opacity="0.5"/></pattern>',
        '</defs>',
        f'<g font-family="{font}">',
        '<text x="420" y="43" text-anchor="middle" font-size="23" font-weight="700" fill="#17202A">Q3、Q4 平均任务费用分解</text>',
        '<text x="420" y="70" text-anchor="middle" font-size="14" fill="#4B5563">移动 + 测向 + 换频 + 光学定位 + 激光清除</text>',
    ]
    for tick in range(0, 501, 100):
        y = bottom - tick / ymax * plot_h
        parts.append(f'<line x1="{left}" y1="{y:.2f}" x2="{right}" y2="{y:.2f}" stroke="#D9DEE3" stroke-width="1"/>')
        parts.append(f'<text x="82" y="{y + 5:.2f}" text-anchor="end" font-size="12" fill="#4B5563">{tick}</text>')
    parts += [
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="#6B7280" stroke-width="1.2"/>',
        f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="#6B7280" stroke-width="1.2"/>',
        '<text x="25" y="285" text-anchor="middle" font-size="14" fill="#30363D" transform="rotate(-90 25 285)">平均任务费用（秒/源）</text>',
    ]
    for i, q in enumerate(questions):
        cumulative = 0.0
        for _, key, _ in components:
            value = by[(q, key)]["mean_s_per_source"]
            y1 = bottom - (cumulative + value) / ymax * plot_h
            h = value / ymax * plot_h
            x = xs[i] - bar_w / 2
            parts.append(f'<rect x="{x:.2f}" y="{y1:.2f}" width="{bar_w}" height="{h:.2f}" fill="{colors[key]}" stroke="#2F3337" stroke-width="0.8"/>')
            pattern = patterns[key]
            if pattern:
                parts.append(f'<rect x="{x:.2f}" y="{y1:.2f}" width="{bar_w}" height="{h:.2f}" fill="url(#{pattern})"/>')
            if value >= 7.0:
                parts.append(f'<text x="{xs[i]}" y="{y1 + h / 2 + 4:.2f}" text-anchor="middle" font-size="12" font-weight="600" fill="#17202A">{value:.1f}</text>')
            cumulative += value
        total_y = bottom - totals[i] / ymax * plot_h
        parts.append(f'<text x="{xs[i]}" y="{total_y - 12:.2f}" text-anchor="middle" font-size="15" font-weight="700" fill="#1F2933">合计 {totals[i]:.2f}</text>')
        label = "第三问 Q3" if q == "Q3" else "第四问 Q4"
        parts.append(f'<text x="{xs[i]}" y="477" text-anchor="middle" font-size="15" fill="#30363D">{label}</text>')
    legend_x = [140, 275, 410, 545, 680]
    for lx, (_, key, label) in zip(legend_x, components):
        parts.append(f'<rect x="{lx}" y="500" width="23" height="15" rx="1" fill="{colors[key]}" stroke="#2F3337" stroke-width="0.8"/>')
        if patterns[key]:
            parts.append(f'<rect x="{lx}" y="500" width="23" height="15" rx="1" fill="url(#{patterns[key]})"/>')
        parts.append(f'<text x="{lx + 31}" y="512" font-size="12.5" fill="#30363D">{label}</text>')
    parts += [
        '<text x="420" y="553" text-anchor="middle" font-size="11" fill="#5B6470">本地已暴露模拟回归；每题 n=2,400 例、30,970 个源；先按例计算秒/源，再跨例取算术平均。</text>',
        '</g></svg>',
    ]
    svg = HERE / "time_cost_breakdown_q3_q4.svg"
    png = HERE / "time_cost_breakdown_q3_q4.png"
    svg.write_text("\n".join(parts) + "\n", encoding="utf-8")
    dimensions = [3024, 2088]
    subprocess.run(
        ["rsvg-convert", "-w", str(dimensions[0]), "-h", str(dimensions[1]), "-o", str(png), str(svg)],
        check=True,
    )
    return {"font_stack": font, "renderer": "rsvg-convert", "svg": svg.name, "png": png.name, "png_dimensions_px": dimensions}


def main() -> None:
    source_rows = json.loads(SOURCE.read_text())
    assert len(source_rows) == 4800
    assert all(r["variant"] == "candidate" for r in source_rows)
    assert all(r["complete"] and r["cleared_count"] == r["source_count"] for r in source_rows)
    rows = [reconstruct(r) for r in source_rows]
    assert {m: sum(r["mode"] == m for r in rows) for m in (3, 4)} == {3: 2400, 4: 2400}
    summary = summarize(rows)
    question_summary = []
    for mode in (3, 4):
        q = f"Q{mode}"
        selected = [r for r in summary if r["mode"] == mode]
        values = {r["component_key"]: r["mean_s_per_source"] for r in selected}
        question_summary.append(
            {
                "question": q,
                "case_count": selected[0]["case_count"],
                "source_count": selected[0]["source_count"],
                "movement_time_s_per_source": values["movement"],
                "bearing_time_s_per_source": values["bearing"],
                "switch_time_s_per_source": values["switch"],
                "optical_time_s_per_source": values["optical"],
                "laser_time_s_per_source": values["laser"],
                "five_part_sum_s_per_source": sum(values.values()),
                "direct_mean_total_s_per_source": selected[0]["mean_total_s_per_source"],
                "all_complete": selected[0]["all_complete"],
                "aggregation": selected[0]["aggregation"],
                "evidence_role": selected[0]["evidence_role"],
            }
        )

    write_csv(HERE / "per_case_costs.csv", rows)
    write_csv(HERE / "chart_data.csv", summary)
    (HERE / "chart_data.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    write_csv(HERE / "question_summary.csv", question_summary)
    chart = render_chart(summary)
    provenance = {
        "source": str(SOURCE.relative_to(ROOT)),
        "source_sha256": sha256(SOURCE),
        "equivalent_packaged_copy": "最佳方法/实验记录/B_improved/results/B3_exposed/case_metrics.json",
        "equivalent_copy_sha256": sha256(ROOT / "最佳方法/实验记录/B_improved/results/B3_exposed/case_metrics.json"),
        "local_env": str(LOCAL_ENV.relative_to(ROOT)),
        "local_env_sha256": sha256(LOCAL_ENV),
        "evaluate": str(EVALUATE.relative_to(ROOT)),
        "evaluate_sha256": sha256(EVALUATE),
        "chart": chart,
    }
    (HERE / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
