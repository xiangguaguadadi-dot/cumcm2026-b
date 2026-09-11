"""Inventory case seeds without generating cases or executing policy code.

JSON/JSONL/CSV records are parsed, content-identical files share parsing work.
Python seed statements remain explicit review items; they are not executed.
An inventory while research is active is provisional and cannot authorize final
generation. Refresh after source freeze and resolve every parse/review item.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import re
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def extract(value):
    seeds, formats = set(), set()

    def numeric(v):
        if isinstance(v, bool):
            return
        if isinstance(v, int):
            seeds.add(v)
        elif isinstance(v, str) and re.fullmatch(r"-?\d+", v):
            seeds.add(int(v))
        elif isinstance(v, (list, tuple)):
            for x in v:
                numeric(x)

    def walk(v):
        if isinstance(v, dict):
            for k, x in v.items():
                if "seed" in k.lower():
                    numeric(x)
                    formats.add(k)
                if k == "case_id" and isinstance(x, str):
                    m = re.search(r"-(\d+)$", x)
                    if m:
                        seeds.add(int(m[1]))
                        formats.add("case_id_numeric_suffix_conservative")
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(value)
    return sorted(seeds), sorted(formats)


def parse_file(path, data):
    body = data.decode("utf-8-sig")
    if path.suffix == ".py":
        tree = ast.parse(body)
        lines = body.splitlines()
        # Every seed mention is retained with source line; formulas are manually
        # reviewed alongside the concrete case records, never silently ignored.
        items = [dict(line=i, text=s.strip()) for i, s in enumerate(lines, 1)
                 if re.search(r"seed|make_case|make_training_case|SystemRandom", s, re.I)]
        # Literal RNG seeds are an additional conservative exclusion, even when
        # they control optimization rather than environment cases.
        literals = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", getattr(node.func, "id", ""))
                if name in ("Random", "seed") and node.args:
                    v = node.args[0]
                    if isinstance(v, ast.Constant) and type(v.value) is int:
                        literals.add(v.value)
        return dict(seeds=sorted(literals), formats=["python_rng_literal"] if literals else [],
                    python_seed_lines=items)
    if path.suffix == ".csv":
        obj = list(csv.DictReader(io.StringIO(body)))
    elif path.suffix == ".jsonl":
        obj = [json.loads(line) for line in body.splitlines() if line.strip()]
    else:
        obj = json.loads(body)
    seeds, formats = extract(obj)
    return dict(seeds=seeds, formats=formats, python_seed_lines=[])


def default_roots():
    assignments = json.loads((ROOT / "experiments/20260911_agent_campaign/assignments.json").read_text())
    roots = [ROOT]
    roots += [Path(a["worktree"]) for a in assignments["assignments"]]
    common = ROOT.parent.parent  # current shared new-chat/work
    roots += [common / "breakthrough" / x for x in ("B1", "B2", "B3", "B4")]
    roots += [ROOT.parent / x for x in ("R2_open", "R3_open")]
    roots.append(common)  # Includes pre-freeze exploration and diagnostic data.
    return roots


def collect(roots, out):
    out.mkdir(parents=True, exist_ok=False)
    seen = {}
    files, errors, seeds = [], [], set()
    for root in roots:
        root = root.resolve()
        if not root.is_dir():
            errors.append(dict(path=str(root), error="missing_scan_root"))
            continue
        for path in sorted(root.rglob("*")):
            if path.suffix not in (".json", ".jsonl", ".csv", ".py") or not path.is_file():
                continue
            rel = path.relative_to(root)
            if root == ROOT.parent.parent and rel.parts[0] in ("stage3", "breakthrough"):
                continue  # Individually scanned above; avoid recursive copies.
            if any(x in (".git", "__pycache__", ".cache", ".venv", "node_modules") for x in rel.parts):
                continue
            # Exclude generated inventories themselves, not any experimental
            # evidence. They only reproduce seeds from the scanned sources.
            if any(x.startswith("seed_inventory_") for x in rel.parts):
                continue
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if digest not in seen:
                try:
                    seen[digest] = parse_file(path, data)
                except Exception as e:
                    seen[digest] = dict(error=type(e).__name__ + ": " + str(e))
            result = seen[digest]
            entry = dict(path=str(path), sha256=digest, bytes=len(data))
            if "error" in result:
                errors.append(dict(entry, error=result["error"]))
            else:
                seeds.update(result["seeds"])
                entry.update(seed_count=len(result["seeds"]), formats=result["formats"])
            files.append(entry)
    unique = {k: v for k, v in seen.items() if "error" not in v and
              (v["seeds"] or v["python_seed_lines"])}
    report = dict(status="provisional_requires_source_freeze_and_manual_script_review",
                  created_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                  scanner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  roots=[str(p.resolve()) for p in roots], files=files,
                  unique_parsed_contents=len(seen), extracted_seed_count=len(seeds),
                  errors=errors, source_contents=unique,
                  shared_work_excluded_subdirectories=["stage3", "breakthrough"],
                  scope_note="All saved JSON, JSONL, CSV, and Python under listed experiment roots, including original pre-freeze work. Stage3 and breakthrough trees are scanned individually, not recursively twice through work. Numeric case-id suffixes, numeric seed-related metadata (including counts/range endpoints), and optimizer RNG seeds over-exclude conservatively. Script formulas require explicit review before final registration. No case generation or policy execution.")
    (out / "inventory.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    (out / "seeds.json").write_text(json.dumps(sorted(seeds), indent=2) + "\n")
    print(json.dumps(dict(files=len(files), unique_contents=len(seen), seeds=len(seeds),
                          errors=len(errors), python_sources_to_review=sum(bool(v.get("python_seed_lines")) for v in seen.values()), out=str(out))))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--roots", nargs="+")
    args = p.parse_args()
    collect([Path(x) for x in args.roots] if args.roots else default_roots(), Path(args.out).resolve())
