"""Q3 B3 ablation: bypass only the adaptive certified multi-disc service layers."""
from __future__ import annotations

import importlib.util
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
B3_PATH = ROOT / "最佳方法" / "代码" / "solver.py"

_spec = importlib.util.spec_from_file_location("registered_b3_multidisc_parent", B3_PATH)
_B3 = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_B3)


class MultiDiscOffSpatial(_B3._Spatial):
    """Retain B3 except Two/Three/MultiDiskSpatial._a1_service_round."""

    def _a1_service_round(self, ch):
        self.counters["multidisc_ablation_bypass_calls"] = (
            self.counters.get("multidisc_ablation_bypass_calls", 0) + 1
        )
        # This is the common parent immediately below all adaptive multi-disc
        # service layers. It retains continued bearing localization, one-point
        # trial clearing, and the inherited finite 25 m grid cover fallback.
        return _B3._P._Q3.TrialSpatial._a1_service_round(self, ch)


BASELINE_CONFIG = dict(_B3.BASELINE_CONFIG)
OPTIMIZED_CONFIGS = {mode: dict(cfg) for mode, cfg in _B3.OPTIMIZED_CONFIGS.items()}


class Solver:
    def __new__(cls, env, mode=3, **config):
        if mode != 3:
            raise ValueError("This registered ablation is Q3-only")
        merged = {**OPTIMIZED_CONFIGS[3], **config}
        return MultiDiscOffSpatial(env, mode=3, **merged)
