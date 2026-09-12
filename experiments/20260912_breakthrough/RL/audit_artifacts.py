"""Read-only artifact/source verification, plus a generated audit report.

Does not fetch sources, run a solver, inspect any world truth, or fit a model.
"""
from __future__ import annotations
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
acquisition = json.loads((ROOT / "sources/acquisition.json").read_text())
corpus = json.loads((ROOT / "literature.json").read_text())
tests = json.loads((ROOT / "contract_check_results.json").read_text())
errors = []
hash_rows = []
for record in acquisition["sources"]:
    for attempt in record["acquisitions"]:
        if attempt["returncode"] != 0:
            continue
        path = ROOT / attempt["path"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        ok = digest == attempt["sha256"] and path.stat().st_size == attempt["bytes"]
        hash_rows.append({"source_id": record["id"], "path": attempt["path"], "matches_recorded_bytes_sha256": ok})
        if not ok:
            errors.append("source hash mismatch: " + str(path))

links = []
for path in sorted(ROOT.glob("*.md")):
    text = path.read_text()
    for destination in re.findall(r"\]\(([^\s)]+)\)", text):
        if destination.startswith(("https://", "http://", "#")):
            continue
        target = (path.parent / destination.split("#")[0]).resolve()
        exists = target.exists()
        links.append({"document": path.name, "target": destination, "exists": exists})
        if not exists:
            errors.append(f"broken local link: {path.name} -> {destination}")

core = [r for r in corpus["records"] if r["corpus_layer"] == "core"]
if len(corpus["records"]) != 16 or len(core) != 9:
    errors.append("corpus counts")
if len({r["stable_id"] for r in corpus["records"]}) != 16:
    errors.append("duplicate stable ID")
map_text = (ROOT / "LITERATURE_MAP.md").read_text()
proposal = (ROOT / "PROPOSAL.md").read_text()
for record in corpus["records"]:
    if map_text.count("### " + record["id"] + " ·") != 1:
        errors.append("map leaf count: " + record["id"])
for record in core:
    if record["id"].split("_")[0] not in proposal:
        errors.append("core omitted from proposal: " + record["id"])

test_tree = ast.parse((ROOT / "test_contracts.py").read_text())
test_count = sum(isinstance(n, ast.FunctionDef) and n.name.startswith("test_") for n in ast.walk(test_tree))
if test_count != tests["tests_run"] or tests["status"] != "pass":
    errors.append("test result/source mismatch")
actual_test_hash = hashlib.sha256((ROOT / "test_contracts.py").read_bytes()).hexdigest()
if tests["test_source_sha256"] != actual_test_hash:
    errors.append("test SHA changed since run")

checks = {
    "status": "pass" if not errors else "fail",
    "evidence_kind": "artifact consistency only; no algorithm effectiveness claim",
    "source_acquisition_success_count": len(hash_rows),
    "source_acquisition_failed_count": sum(a["returncode"] != 0 for r in acquisition["sources"] for a in r["acquisitions"]),
    "hash_checks": hash_rows,
    "local_markdown_link_checks": links,
    "corpus_counts": corpus["counts"],
    "classification_primary_branches": dict(Counter(r["primary_classification_path"][1] for r in corpus["records"])),
    "synthetic_tests": {"count": test_count, "status": tests["status"], "source_sha256": actual_test_hash},
    "environment_executions": 0, "model_updates": 0,
    "implementation_directory_exists": (ROOT / "implementation").exists(),
    "errors": errors,
    "artifact_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.iterdir()) if p.is_file() and p.name != "artifact_audit.json"},
}
(ROOT / "artifact_audit.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({k: checks[k] for k in ("status", "source_acquisition_success_count", "source_acquisition_failed_count", "corpus_counts", "synthetic_tests", "implementation_directory_exists", "errors")}, ensure_ascii=False))
raise SystemExit(0 if not errors else 1)
