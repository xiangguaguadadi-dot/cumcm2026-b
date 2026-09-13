"""B3 ablation: disable only opportunistic paid-station retest gating."""
from __future__ import annotations
import importlib.util
from pathlib import Path

PARENT = Path(__file__).resolve().parents[3] / "experiments/20260913_q2_transfer/B_improved/B3_local_refinement.py"
spec = importlib.util.spec_from_file_location("frozen_b3_gate_parent", PARENT)
_b3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_b3)

BASELINE_CONFIG = dict(_b3.BASELINE_CONFIG)
OPTIMIZED_CONFIGS = {m: dict(c) for m, c in _b3.OPTIMIZED_CONFIGS.items()}
OPTIMIZED_CONFIGS[3]["a1_station_gate"] = False

class Solver:
    def __new__(cls, env, mode=3, **config):
        merged = {**OPTIMIZED_CONFIGS[mode], **config}
        return _b3.Solver(env, mode=mode, **merged)
