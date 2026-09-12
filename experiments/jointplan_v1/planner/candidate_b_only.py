"""B-only: explicit mixed-route action costs, original certified sites retained."""
import importlib.util
from pathlib import Path
_spec = importlib.util.spec_from_file_location("jointplan_b_base", Path(__file__).with_name("candidate_joint.py"))
_BASE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_BASE)
OPTIMIZED_CONFIGS = {m: dict(c, jointplan_geometry=False, jointplan_mixed=True) for m, c in _BASE.OPTIMIZED_CONFIGS.items()}
BASELINE_CONFIG = dict(_BASE.BASELINE_CONFIG)
class Solver:
    def __new__(cls, env, mode=3, **config):
        return _BASE.Solver(env, mode=mode, **{**OPTIMIZED_CONFIGS[mode], **config})
