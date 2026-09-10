#!/bin/sh
set -eu
PYTHON=${PYTHON:-/Users/t/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3}
# Run from the repository root; use new --out directories to preserve prior results.
"$PYTHON" -m unittest discover -s tests -v
"$PYTHON" evaluate.py --verify-only
"$PYTHON" experiments/A5_learning/train_policy.py --round 1 --solver experiments/A5_learning/snapshots/r0_solver.py --out experiments/A5_learning/training/reproduce_r1
"$PYTHON" experiments/A5_learning/freeze_candidate.py --selected experiments/A5_learning/training/reproduce_r1/selected.json --template experiments/A5_learning/snapshots/r0_solver.py --out experiments/A5_learning/snapshots/reproduce_r1_solver.py
"$PYTHON" evaluate.py --suite quick --candidate experiments/A5_learning/snapshots/r1_solver.py --out results/A5_learning_reproduce_r1_quick
"$PYTHON" evaluate.py --suite full --candidate experiments/A5_learning/snapshots/r1_solver.py --out results/A5_learning_reproduce_r1_full
