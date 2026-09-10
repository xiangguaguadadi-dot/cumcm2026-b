#!/bin/sh
set -eu
PYTHON=${PYTHON:-/Users/t/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3}
# Run from the repository root. Refuse to overwrite any recorded results.
"$PYTHON" -m unittest discover -s tests -v
"$PYTHON" evaluate.py --verify-only
for round in 1 2 3; do
    case "$round" in
        1) template=experiments/A5_learning/snapshots/r0_solver.py; train=48; dev=72; gate=0 ;;
        2) template=experiments/A5_learning/templates/r2_solver_template.py; train=96; dev=144; gate=1.28 ;;
        3) template=experiments/A5_learning/templates/r3_solver_template.py; train=144; dev=216; gate=1.28 ;;
    esac
    out=experiments/A5_learning/training/reproduce_r${round}
    candidate=experiments/A5_learning/snapshots/reproduce_r${round}_solver.py
    "$PYTHON" experiments/A5_learning/train_policy.py --round "$round" --solver "$template" --train "$train" --dev "$dev" --selection-z "$gate" --out "$out"
    "$PYTHON" experiments/A5_learning/freeze_candidate.py --selected "$out/selected.json" --template "$template" --out "$candidate"
    cmp "$candidate" "experiments/A5_learning/snapshots/r${round}_solver.py"
    "$PYTHON" evaluate.py --suite quick --candidate "$candidate" --out "results/A5_learning_reproduce_r${round}_quick"
    "$PYTHON" evaluate.py --suite full --candidate "$candidate" --out "results/A5_learning_reproduce_r${round}_full"
done
