"""Replay two saved inline development attempts into a NEW output directory.

This convenience entry point was reconstructed after the recorded executions;
it was syntax checked, not rerun during finalization. Original raw rows remain
the execution evidence. This does not generate new cases or rerun S1.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "experiments/E3_expand"


def load(path):
    name = "e3_replay_" + hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", choices=["r3_extended", "r4_guarded"], required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    target = args.out.resolve()
    if not target.is_relative_to((OUT / "results").resolve()):
        raise ValueError("--out must be a new directory inside E3_expand/results")
    if target.exists():
        raise FileExistsError("Original or existing result directories cannot be overwritten")
    if args.attempt == "r3_extended":
        source = OUT / "snapshots/r3_extended.py"
        expected = "0d9c14a487ad74506bbec3105cf5a3dbd002df179e415ada2c3f7e0d71820548"
        original = OUT / "results/r3_development"
        variants = [("convex_near", {})]
    else:
        source = OUT / "snapshots/r4_guarded.py"
        expected = "5d86c87d5a13c10fd6f34121c697d536878daf0ed2350bc81643785737f0dede"
        original = OUT / "results/r4_confirmation"
        variants = [
            ("both", {}),
            ("visibility", {"tree_margin_s": 0.0}),
            ("margin", {"tree_visibility_guard": False}),
        ]
    if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
        raise ValueError("Candidate bytes differ from the recorded attempt")
    dependencies = json.loads((OUT / "snapshots/r1_dependencies.json").read_text())
    for rel, expected_hash in dependencies.items():
        if hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() != expected_hash:
            raise ValueError(f"Dependency changed: {rel}")
    sys.path.insert(0, str(ROOT))
    driver = load(ROOT / "experiments/R3_open/research/develop_r4.py")
    cases = json.loads((original / "cases.json").read_text())
    target.mkdir()
    summary = {}
    started = time.perf_counter()
    for label, config in variants:
        module = load(source)
        begin = time.perf_counter()
        rows = [dict(driver.run_case(module, case, config), variant=label) for case in cases]
        (target / f"{label}_rows.json").write_text(json.dumps(rows, indent=2))
        summary[label] = dict(
            source=str(source.relative_to(ROOT)),
            sha256=expected,
            config=config,
            runs=len(rows),
            wall_s=time.perf_counter() - begin,
            groups=driver.summarize(rows),
            baseline_rows=str((original / "S1_rows.json").relative_to(ROOT)),
        )
        (target / "summary.json").write_text(json.dumps(summary, indent=2))
    (target / "budget.json").write_text(json.dumps(dict(
        actual_runs=len(cases) * len(variants),
        unique_cases=len(cases),
        new_unique_cases=0,
        reused_baseline_rows=len(cases),
        wall_s=time.perf_counter() - started,
        reconstructed_replay=True,
    ), indent=2))


if __name__ == "__main__":
    main()
