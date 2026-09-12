#!/usr/bin/env python3
"""包内审计与实际本地复现；只依赖 Python 3.10+ 标准库。

历史登记中的绝对路径仅为存证，不用于定位文件。audit 不执行求解器；
run 不复用已保存的候选行，exposed 会实际执行全部 4800 个案例。
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import json
import math
from pathlib import Path, PurePosixPath
import sys
import time


# Also applies when multiprocessing re-executes this entry point under spawn.
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
CODE = ROOT / "代码"
ARCHIVE = ROOT / "实验记录"
MANIFEST = ROOT / "文件清单.json"
BEST_SHA = "e6a0666d644ceaa1d7ae69f19042b9ca022379f3e5a57d927e52bcf1a09360bd"
BASELINE_SHA = "0bda4f711b9e9716739af8aedf456cb1eeefb47d8ba3ed230ca682c8450a96ea"
PINNED = {
    "代码/solver.py": BEST_SHA,
    "代码/baseline.py": BASELINE_SHA,
    "代码/evaluate.py": "61088a2c9cd45b7026e4caaf9f7d55282a55d1114dfe74d179b086dafb0dc498",
    "代码/local_env.py": "99587518fa378e1bef2fbbaa9425ee907bea80885a69666b3765311cbcf4f42a",
    "代码/evaluation/manifest_v1.json": "431210a6d96e721d23c31698aa389702ea87dcffe8fee6250f71ce6e902be140",
}
B3_RESULTS = ARCHIVE / "B_improved" / "results"
VIRTUAL_FIELDS = (
    "mode", "group", "cleared_count", "source_count", "cleared_fraction",
    "average_clear_time_s", "total_virtual_time_s", "complete", "exit_reason",
    "error", "coverage_certificate", "requests", "distance_m", "clear_failures",
)
DATA_ROLE = "既有已暴露本地回归；不是新盲测，也不是官方模拟器结果"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def save_new(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def now():
    return datetime.now(timezone.utc).isoformat()


def contained(path, directory):
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


def manifest_file(relative):
    require(isinstance(relative, str), "文件清单的路径必须为字符串")
    name = PurePosixPath(relative)
    require(not name.is_absolute() and name.parts and ".." not in name.parts
            and "\\" not in relative, "文件清单含非法相对路径：" + relative)
    path = ROOT.joinpath(*name.parts)
    require(contained(path.resolve(), ROOT), "文件清单路径越出本包：" + relative)
    for ancestor in (path, *path.parents):
        if ancestor == ROOT:
            break
        require(not ancestor.is_symlink(), "包内文件不能依赖符号链接：" + relative)
    return path


def verify_package():
    require(MANIFEST.is_file(), "缺少文件清单.json；请使用完整的最佳方法包")
    record = read(MANIFEST)
    entries = record.get("files")
    require(isinstance(entries, dict) and entries, "文件清单.json 缺少非空 files 字典")
    required = set(PINNED) | {
        "复现.py", "代码/audit_pair.py", "数据/exposed_cases.json",
        "数据/exposure_manifest.json", "数据/baseline_case_metrics.json",
        "数据/baseline_summary.json", "实验记录/REGISTRATION.json",
        "实验记录/evaluate_transfer.py", "实验记录/SELECTION.json",
    }
    for suite in ("quick", "full", "exposed"):
        for filename in ("case_metrics.json", "summary.json",
                         "execution_registration.json", "executed_rows.jsonl"):
            required.add(f"实验记录/B_improved/results/B3_{suite}/{filename}")
    require(required <= entries.keys(),
            "文件清单缺少必要文件：" + ", ".join(sorted(required - entries.keys())))
    for relative, info in entries.items():
        require(isinstance(info, dict), "无效文件清单项：" + relative)
        path = manifest_file(relative)
        require(path.is_file(), "包文件不存在：" + relative)
        require(path.stat().st_size == info.get("bytes"), "文件长度不符：" + relative)
        require(sha(path) == info.get("sha256"), "文件 SHA256 不符：" + relative)
    for relative, digest in PINNED.items():
        require(sha(ROOT / relative) == digest, "已执行候选或冻结环境被改动：" + relative)
    # The original evaluator verifies this unchanged relative-path closure.
    frozen = read(CODE / "evaluation" / "manifest_v1.json")
    for relative, digest in frozen["sha256"].items():
        packaged = "代码/" + relative
        require(packaged in entries, "冻结 v1 依赖未列入包清单：" + packaged)
        require(sha(manifest_file(packaged)) == digest, "冻结 v1 散列不符：" + packaged)
    # The inherited strategy has an optional sibling-file lookup. The executed
    # B3 and fusion_r5 had no such file; do not silently change that condition.
    require(not (CODE / "coverage_points.json").exists(),
            "代码/coverage_points.json 会改变原候选的可选文件环境，请移出本包")
    return dict(manifest_sha256=sha(MANIFEST), verified_files=len(entries),
                source_commit=record.get("source_commit"), files=entries,
                frozen_manifest_sha256=sha(CODE / "evaluation" / "manifest_v1.json"))


def runtime_modules():
    # Explicit insertion also works with `python3 -I` and an unrelated cwd.
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(CODE))
    modules = []
    for name in ("evaluate", "audit_pair"):
        module = importlib.import_module(name)
        require(Path(module.__file__).resolve() == CODE / (name + ".py"),
                "导入了包外模块：" + name)
        modules.append(module)
    modules[0].verify()
    return modules


def index(rows, label):
    require(isinstance(rows, list), label + " 必须是案例列表")
    result = {}
    for row in rows:
        require(isinstance(row, dict) and isinstance(row.get("case_id"), str),
                label + " 含无效案例行")
        require(row["case_id"] not in result, label + " 有重复 ID：" + row["case_id"])
        result[row["case_id"]] = row
    return result


def select_cases(cases, suite):
    if suite == "exposed":
        return cases
    frozen = read(CODE / "evaluation" / "cases_v1.json")
    wanted = {c["case_id"] for c in frozen if suite == "full" or c["quick"]}
    selected = [c for c in cases if c["case_id"] in wanted]
    expected = 120 if suite == "quick" else 2400
    require(len(selected) == len(wanted) == expected, "包内 " + suite + " 案例数量不符")
    return selected


def archived_b3_checks(cases):
    """Check stored logs/reuse without following any historical absolute path."""
    results = []
    full_rows = read(B3_RESULTS / "B3_full" / "case_metrics.json")
    full_index = index(full_rows, "B3 full")
    for suite in ("quick", "full", "exposed"):
        directory = B3_RESULTS / ("B3_" + suite)
        rows = read(directory / "case_metrics.json")
        row_index = index(rows, "B3 " + suite)
        summary = read(directory / "summary.json")
        registration = read(directory / "execution_registration.json")
        chosen = select_cases(cases, suite)
        ids = [c["case_id"] for c in chosen]
        require([r["case_id"] for r in rows] == ids == registration["case_ids"],
                "B3 " + suite + " 原始行/登记/案例顺序不匹配")
        require(summary["paired_cases"] == len(chosen), "B3归档案例数不符")
        require(summary["candidate_sha256"] == registration["candidate_sha256"] == BEST_SHA,
                "B3归档候选SHA不符")
        require(summary["baseline_sha256"] == BASELINE_SHA, "B3归档父法SHA不符")
        require(summary["runner_sha256"] == sha(ARCHIVE / "evaluate_transfer.py"),
                "B3归档runnerSHA不符")
        require(summary["registration_sha256"] == sha(ARCHIVE / "REGISTRATION.json"),
                "B3归档登记SHA不符")
        with (directory / "executed_rows.jsonl").open(encoding="utf-8") as stream:
            executed = [json.loads(line) for line in stream if line.strip()]
        executed_index = index(executed, "B3 " + suite + " 执行日志")
        require(len(executed) == summary["actual_runs"] == registration["actual_runs_planned"],
                "B3归档实际执行数量不符")
        require(all(row_index.get(cid) == row for cid, row in executed_index.items()),
                "B3归档执行日志与最终行不一致")
        if suite == "exposed":
            require(summary["actual_runs"] == summary["reused_rows"] == 2400,
                    "B3 exposed复用/实际执行分母不符")
            require(registration["reused"]["rows_sha256"] ==
                    sha(B3_RESULTS / "B3_full" / "case_metrics.json"), "B3复用full的SHA不符")
            require(set(full_index).isdisjoint(executed_index) and
                    set(full_index) | set(executed_index) == set(row_index),
                    "B3复用行与新执行行有遗漏或重叠")
            require(all(row_index[cid] == row for cid, row in full_index.items()),
                    "B3 exposed未原样复用同SHA的full行")
        else:
            require(set(executed_index) == set(row_index) and summary["reused_rows"] == 0,
                    "B3 " + suite + " 不应复用旧行")
        require(sum(r.get("requests", 0) or 0 for r in executed) == summary["actual_requests"],
                "B3归档请求数量不符")
        results.append(dict(suite=suite, cases=len(rows), actual_runs=len(executed),
                            reused_rows=summary["reused_rows"], logs_match=True))
    return results


def load_evidence(audit_pair):
    cases = read(ROOT / "数据" / "exposed_cases.json")
    baseline = read(ROOT / "数据" / "baseline_case_metrics.json")
    saved = read(B3_RESULTS / "B3_exposed" / "case_metrics.json")
    cc, bb, ss = index(cases, "完整案例"), index(baseline, "fusion_r5缓存"), index(saved, "B3缓存")
    require(len(cc) == len(bb) == len(ss) == 4800 and set(cc) == set(bb) == set(ss),
            "案例、当前父法与B3必须为精确配对的4800个唯一ID")
    require({c["exposure_suite"] for c in cases} == {"v1", "previous_final"},
            "已暴露批次定义不符")
    for mode in (3, 4):
        for batch in ("v1", "previous_final"):
            require(sum(c["mode"] == mode and c["exposure_suite"] == batch for c in cases) == 1200,
                    "每题每批应为1200例")
    old = read(ARCHIVE / "REGISTRATION.json")
    mappings = {
        "数据/exposed_cases.json": "experiments/20260911_stage4/exposed_cases.json",
        "数据/exposure_manifest.json": "experiments/20260911_stage4/exposure_manifest.json",
        "数据/baseline_case_metrics.json": "experiments/parallel_v2_coordinator/fusion_r5_exposed/case_metrics.json",
        "数据/baseline_summary.json": "experiments/parallel_v2_coordinator/fusion_r5_exposed/summary.json",
    }
    for relative, original_name in mappings.items():
        require(sha(ROOT / relative) == old["files"][original_name],
                "包内数据与原始登记不一致：" + relative)
    provenance = read(ROOT / "数据" / "baseline_summary.json")
    require(provenance["candidate_sha256"] == old["baseline_sha256"] == BASELINE_SHA,
            "当前对照必须是fusion_r5，不能换成冻结v1旧基准")
    require(provenance["cases_sha256"] == sha(ROOT / "数据" / "exposed_cases.json"),
            "fusion_r5缓存的案例SHA不匹配")
    comparison = audit_pair.compare(saved, baseline, cases, bootstrap_repeats=2000)
    require(comparison["all_complete"], "已归档B3或fusion_r5存在未完成案例")
    stored_summary = read(B3_RESULTS / "B3_exposed" / "summary.json")
    found = {(s["mode"], s["suite"], s["group"]): s for s in comparison["comparisons"]}
    require(len(found) == len(stored_summary["comparisons"]), "B3归档汇总组合数量不符")
    for reported in stored_summary["comparisons"]:
        actual = found[(reported["mode"], reported["batch"], reported["group"])]
        require(actual["valid_comparison"] == reported["valid_comparison"], "归档可比性标记不符")
        for key in ("cases", "source_count", "candidate_complete", "baseline_complete",
                    "faster", "equal", "slower"):
            require(actual[key] == reported[key], "归档计数不符：" + key)
        for key in ("candidate_mean", "baseline_mean", "delta", "improvement_pct"):
            require(math.isclose(actual[key], reported[key], rel_tol=0, abs_tol=1e-9),
                    "归档统计重算不一致：" + key)
    selected = read(ARCHIVE / "SELECTION.json")
    for mode in ("3", "4"):
        choice = selected["selected_by_mode"][mode]
        require(choice["candidate_sha256"] == BEST_SHA and choice["version"] == "B3",
                "选择记录未指向同一B3候选")
        require(choice["exposed_rows_sha256"] == sha(B3_RESULTS / "B3_exposed" / "case_metrics.json"),
                "选择记录中的B3原始行SHA不符")
    archive_checks = archived_b3_checks(cases)
    return cases, baseline, saved, comparison, archive_checks


def output_path(raw):
    path = Path(raw).expanduser().resolve()
    require(not path.exists(), "输出目录已存在，禁止覆盖：" + str(path))
    if contained(path, ROOT):
        rel = path.relative_to(ROOT)
        require(len(rel.parts) >= 2 and rel.parts[0] == "验证产物",
                "包内输出只能放在 验证产物/新目录；归档目录不可写入")
    return path


def public_verification(verified):
    return {key: value for key, value in verified.items() if key != "files"}


def aggregate(comparison):
    return [r for r in comparison["comparisons"] if r["suite"] == "combined" and r["group"] == "ALL"]


def check_unchanged(verified, candidate_relative):
    require(sha(MANIFEST) == verified["manifest_sha256"], "执行期间包清单发生变化")
    for relative in ("复现.py", candidate_relative, "代码/evaluate.py", "代码/local_env.py",
                     "代码/audit_pair.py", "数据/exposed_cases.json", "数据/baseline_case_metrics.json"):
        require(sha(ROOT / relative) == verified["files"][relative]["sha256"],
                "执行期间文件发生变化：" + relative)


def reproduction(rows, saved):
    previous = index(saved, "重现对照原始行")
    mismatches = []
    for row in rows:
        old = previous[row["case_id"]]
        differences = {}
        for field in VIRTUAL_FIELDS:
            a, b = row.get(field), old.get(field)
            if type(a) in (int, float) and type(b) in (int, float):
                equal = math.isclose(a, b, rel_tol=0, abs_tol=1e-8)
            else:
                equal = a == b
            if not equal:
                differences[field] = dict(replayed=a, saved=b)
        if differences:
            mismatches.append(dict(case_id=row["case_id"], differences=differences))
    return dict(compared_cases=len(rows), all_virtual_rows_match=not mismatches,
                absolute_tolerance=1e-8, compared_fields=list(VIRTUAL_FIELDS),
                excluded_fields=["program_runtime_s", "worker_runtime_s", "variant"],
                mismatched_cases=len(mismatches), mismatches=mismatches)


def perform_audit(args, verified, audit_pair):
    _, _, _, comparison, archive_checks = load_evidence(audit_pair)
    after = verify_package()
    require(after["manifest_sha256"] == verified["manifest_sha256"], "审计期间包清单发生变化")
    out = output_path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    result = dict(status="passed", command="audit", recorded_at=now(), data_role=DATA_ROLE,
                  solver_runs_executed=0, package=public_verification(after),
                  candidate_sha256=BEST_SHA, baseline_sha256=BASELINE_SHA,
                  paired_cases=4800, archive_execution_checks=archive_checks,
                  saved_row_audit=comparison)
    save_new(out / "audit.json", result)
    print(json.dumps(dict(status="passed", command="audit", solver_runs_executed=0,
                          verified_files=after["verified_files"], paired_cases=4800,
                          modes=aggregate(comparison), output=str(out)), ensure_ascii=False))
    return 0


def perform_run(args, verified, evaluator, audit_pair):
    all_cases, baseline, saved, _, _ = load_evidence(audit_pair)
    cases = select_cases(all_cases, args.suite)
    relative = "代码/solver.py" if args.candidate == "best" else "代码/baseline.py"
    candidate = ROOT / relative
    digest = BEST_SHA if args.candidate == "best" else BASELINE_SHA
    reference = index(baseline, "当前父法缓存")
    refs = [reference[c["case_id"]] for c in cases]
    out = output_path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    registration = dict(command="run", registered_at=now(), suite=args.suite,
                        candidate=args.candidate, candidate_package_path=relative,
                        candidate_sha256=digest, baseline_sha256=BASELINE_SHA,
                        runner_sha256=sha(Path(__file__)), frozen_evaluator_sha256=sha(CODE / "evaluate.py"),
                        cases_sha256=sha(ROOT / "数据" / "exposed_cases.json"),
                        package=public_verification(verified), data_role=DATA_ROLE,
                        case_ids=[c["case_id"] for c in cases], planned_actual_runs=len(cases),
                        reused_candidate_rows=0, chunk_size=args.chunk_size,
                        note="本次逐例重新运行；exposed实际执行4800例，旧B3行只用于事后核对")
    save_new(out / "execution_registration.json", registration)
    rows = []
    current_batch = []
    started = time.perf_counter()
    try:
        with (out / "executed_rows.jsonl").open("x", encoding="utf-8") as log:
            for offset in range(0, len(cases), args.chunk_size):
                check_unchanged(verified, relative)
                current_batch = cases[offset:offset + args.chunk_size]
                got = evaluator.run_cases(current_batch, candidate, args.candidate == "baseline")
                expected_ids = [c["case_id"] for c in current_batch]
                if not isinstance(got, list) or [r.get("case_id") for r in got] != expected_ids:
                    save_new(out / "unexpected_batch.json", dict(expected_ids=expected_ids, returned=got))
                    raise ValueError("冻结runner返回的案例数量/ID与本批登记不符，原返回已保存")
                for row, case in zip(got, current_batch):
                    row = dict(row, exposure_suite=case["exposure_suite"], seed_cluster=case["seed"])
                    rows.append(row)
                    log.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
                log.flush()
                current_batch = []
                print(json.dumps(dict(completed_actual_runs=len(rows), planned_actual_runs=len(cases),
                                      failed_cases=sum(not audit_pair.complete(r) for r in rows),
                                      elapsed_s=round(time.perf_counter() - started, 3)), ensure_ascii=False), flush=True)
        after = verify_package()
        require(after["manifest_sha256"] == verified["manifest_sha256"], "执行前后包清单不同")
        evaluator.verify()
        comparison = audit_pair.compare(rows, refs, cases, bootstrap_repeats=2000)
        checked = reproduction(rows, saved if args.candidate == "best" else baseline)
        summary = dict(status="completed" if comparison["all_complete"] else "completed_with_failures",
                       command="run", suite=args.suite, candidate=args.candidate, data_role=DATA_ROLE,
                       candidate_sha256=digest, baseline_sha256=BASELINE_SHA,
                       package_before=public_verification(verified), package_after=public_verification(after),
                       actual_runs=len(rows), reused_candidate_rows=0, paired_cases=len(cases),
                       actual_requests=sum(r.get("requests", 0) or 0 for r in rows),
                       wall_seconds=time.perf_counter() - started,
                       all_complete=comparison["all_complete"],
                       failed_ids=[r["case_id"] for r in rows if not audit_pair.complete(r)],
                       comparisons=comparison["comparisons"], saved_row_reproduction=checked)
        save_new(out / "case_metrics.json", rows)
        save_new(out / "saved_row_reproduction.json", checked)
        save_new(out / "summary.json", summary)
        print(json.dumps(dict(status=summary["status"], actual_runs=len(rows), reused_candidate_rows=0,
                              all_complete=summary["all_complete"],
                              saved_virtual_rows_match=checked["all_virtual_rows_match"],
                              modes=aggregate(comparison), output=str(out)), ensure_ascii=False))
        return 0 if summary["all_complete"] and checked["all_virtual_rows_match"] else 1
    except BaseException as error:
        # Preserve every completed returned row. If interruption occurred inside
        # run_cases, do not invent results or execution counts for that batch.
        if not (out / "case_metrics.json").exists():
            save_new(out / "case_metrics.json", rows)
        if not (out / "summary.json").exists():
            save_new(out / "summary.json", dict(
                status="aborted", command="run", suite=args.suite, data_role=DATA_ROLE,
                candidate_sha256=digest, all_complete=False,
                completed_recorded_runs=len(rows), planned_actual_runs=len(cases),
                reused_candidate_rows=0, error=type(error).__name__ + ": " + str(error),
                unreturned_current_batch_ids=[c["case_id"] for c in current_batch],
                elapsed_s=time.perf_counter() - started,
                note="此前完整返回的行已保存；中断批次可能已有执行，但没有返回行，不能声称其已完成"))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="最佳方法包：原始行审计或重新运行本地案例；不依赖原仓库目录。",
        epilog="输出目录必须尚不存在；可放包外，或本包 验证产物/新目录。所有结果均非官方测试。")
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit", help="校验全部包文件并重算4800行指标，不执行求解器")
    audit.add_argument("--out", required=True, help="存放audit.json的新目录")
    run = sub.add_parser("run", help="实际重跑指定集合；不复用已保存的候选行")
    run.add_argument("--suite", choices=("quick", "full", "exposed"), required=True,
                     help="实际运行数量：quick=120，full=2400，exposed=4800")
    run.add_argument("--candidate", choices=("best", "baseline"), default="best",
                     help="best=B3（默认）；baseline=本轮fusion_r5父法")
    run.add_argument("--out", required=True, help="存放本次执行日志和结果的新目录")
    run.add_argument("--chunk-size", type=int, default=120, help="每批执行并落盘的案例数，默认120")
    args = parser.parse_args(argv)
    try:
        require(sys.version_info >= (3, 10), "需要 Python 3.10 或更新版本")
        output_path(args.out)
        if args.command == "run":
            require(args.chunk_size > 0, "--chunk-size 必须为正整数")
        verified = verify_package()
        evaluator, audit_pair = runtime_modules()
        if args.command == "audit":
            return perform_audit(args, verified, audit_pair)
        return perform_run(args, verified, evaluator, audit_pair)
    except KeyboardInterrupt:
        print("操作已中断；已返回的案例行保留在新输出目录。", file=sys.stderr)
        return 130
    except Exception as error:
        print("复现失败：" + type(error).__name__ + ": " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
