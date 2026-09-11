"""Generate final cases only after actual research freeze and committed review.

This script has not generated the third-stage final cohort during development.
All source and exclusion identities are checked before drawing any new seeds.
"""
from __future__ import annotations
import argparse
import ast
import json
import math
import random
import subprocess
import sys
import time
from pathlib import Path

from final_review import ROOT, sha, read, save, verify_registry


def generate(registry_path, out):
    registry_path = Path(registry_path).resolve()
    registry = verify_registry(registry_path)
    exclusions = read(ROOT / registry["seed_exclusion_path"])
    assert exclusions["review_complete"] is True and not exclusions["unresolved_sources"]
    excluded = set(exclusions["seeds"])
    ranges = [(r["start"], r["stop"]) for r in exclusions["ranges"]]
    assert all(type(lo) is int and type(hi) is int and lo < hi for lo, hi in ranges)
    known = read(Path(__file__).resolve().parent / "exposed_cases.json")
    assert {c["seed"] for c in known} <= excluded
    sys.path.insert(0, str(ROOT))
    import evaluate
    from local_env import Source

    evaluate.verify()
    source = ROOT / "evaluation/generate_cases.py"
    tree = ast.parse(source.read_text())
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "sources"
             or isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "groups" for t in n.targets)]
    assert len(nodes) == 2
    namespace = dict(math=math, random=random, Source=Source)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), namespace)
    assert len(namespace["groups"]) == 12
    out = Path(out).resolve()
    assert not out.exists(), "Use a new directory; never overwrite cases"
    seeds = []
    rng = random.SystemRandom()
    while len(seeds) < 100:
        seed = rng.randrange(10**8, 2**31)
        if seed not in excluded and seed not in seeds and not any(lo <= seed < hi for lo, hi in ranges):
            seeds.append(seed)
    cases = []
    for mode in (3, 4):
        for group, scenario, noise in namespace["groups"]:
            for seed in seeds:
                sources = [vars(s) for s in namespace["sources"](seed, mode, scenario)]
                assert 10 <= len(sources) <= 16
                assert len({s["channel"] for s in sources}) == len(sources)
                if mode == 4:
                    assert {s["direction"] is not None for s in sources} == {True, False}
                cases.append(dict(case_id=f"LOCAL-stage3-final-q{mode}-{group}-{seed}", mode=mode,
                                  group=group, noise=noise, seed=seed, quick=False, sources=sources))
    assert len(cases) == 2400
    # Registry/deployment identity must remain unchanged through generation.
    assert verify_registry(registry_path) == registry
    out.mkdir(parents=True, exist_ok=False)
    save(out / "cases.json", cases)
    manifest = dict(role="stage3_final_new_seed_local", cases=2400, seed_clusters=100, seeds=seeds,
                    generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    registry_sha256=sha(registry_path), seed_exclusion_sha256=registry["seed_exclusion_sha256"],
                    registry_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                    cases_sha256=sha(out / "cases.json"), generator_script_sha256=sha(__file__),
                    frozen_source_generator_sha256=sha(source), frozen_manifest_sha256=sha(ROOT / "evaluation/manifest_v1.json"),
                    distribution_note="New seed clusters under the same 12 local assumptions; Q4 mixed directional and omnidirectional sources. Not official or out-of-distribution testing.")
    save(out / "manifest.json", manifest)
    print(json.dumps(manifest))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    generate(args.registry, args.out)
