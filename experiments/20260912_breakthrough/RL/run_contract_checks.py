"""Run only synthetic research-contract unit tests and save inspectable results."""
from __future__ import annotations
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import time
import unittest

ROOT = Path(__file__).resolve().parent
target = ROOT / "test_contracts.py"
spec = importlib.util.spec_from_file_location("bc_rpi_contract_tests", target)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
suite = unittest.defaultTestLoader.loadTestsFromModule(module)
stream = io.StringIO()
start = time.monotonic()
result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
report = {
    "status": "pass" if result.wasSuccessful() else "fail",
    "evidence_kind": "synthetic specification fixtures and source-ledger consistency only",
    "not_verified": ["solver implementation", "real candidate generation", "real fork/clock", "G0 equivalence", "headroom", "training", "deployment latency", "generalization", "official performance"],
    "environment_executions": 0, "counterfactual_training_branches": 0, "model_updates": 0,
    "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
    "elapsed_s": time.monotonic() - start,
    "test_source_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
    "log": stream.getvalue(),
}
(ROOT / "contract_check_results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(stream.getvalue(), end="")
print(json.dumps({k: v for k, v in report.items() if k != "log"}, ensure_ascii=False))
raise SystemExit(0 if result.wasSuccessful() else 1)
