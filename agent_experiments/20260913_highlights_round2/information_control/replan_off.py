"""B3 ablation: finish one source's persistent service before global replanning."""
from __future__ import annotations
import importlib.util
from pathlib import Path

PARENT = Path(__file__).resolve().parents[3] / "experiments/20260913_q2_transfer/B_improved/B3_local_refinement.py"
spec = importlib.util.spec_from_file_location("frozen_b3_replan_parent", PARENT)
_b3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_b3)

class _NoReplanSpatial(_b3._Spatial):
    def localize(self, ch):
        self._active_target = ch
        try:
            max_iter = int(self.config.get("localization_iterations", 9))
            guard = max_iter + 2
            while ch not in self.cleared and self._a1_progress.get(ch, 0) < max_iter and guard:
                before = (self._a1_progress.get(ch, 0), self.virtual_time, len(self.trace))
                self.counters["a1_service_rounds"] = self.counters.get("a1_service_rounds", 0) + 1
                self._a1_service_round(ch)
                guard -= 1
                after = (self._a1_progress.get(ch, 0), self.virtual_time, len(self.trace))
                if after == before:
                    break
        finally:
            self._active_target = None
        self.share_observations(ch)

BASELINE_CONFIG = dict(_b3.BASELINE_CONFIG)
OPTIMIZED_CONFIGS = {m: dict(c) for m, c in _b3.OPTIMIZED_CONFIGS.items()}

class Solver:
    def __new__(cls, env, mode=3, **config):
        merged = {**OPTIMIZED_CONFIGS[mode], **config}
        if mode == 3:
            return _NoReplanSpatial(env, mode=mode, **merged)
        return _b3.Solver(env, mode=mode, **merged)
