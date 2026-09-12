"""P2 geometry mechanism 2: compensated Q3 arcs, parent task scheduling.

This entry requires the integrated sibling planner/ modules; it calls only the
same serial public environment interface through the planner executor.
"""
import importlib.util
from pathlib import Path
import sys

_DIR = Path(__file__).resolve().parent
_PACKAGE = '_jointplan_compensated_geometry'
if _PACKAGE not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_PACKAGE, _DIR / '__init__.py', submodule_search_locations=[str(_DIR)])
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_PACKAGE] = _module
    _spec.loader.exec_module(_module)
_spec = importlib.util.spec_from_file_location(_PACKAGE + '.compensated_engine', _DIR / 'compensated_engine.py')
_PROVIDER = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_PROVIDER)
_spec = importlib.util.spec_from_file_location('_jointplan_compensated_a_base', _DIR.parent / 'planner/candidate_a_only.py')
_BASE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_BASE)
OPTIMIZED_CONFIGS = {mode: dict(config, jointplan_geometry=True, jointplan_mixed=False,
                               jointplan_geometry_options={'block_sizes': [2], 'max_plans': 6, 'max_seconds': .35})
                     for mode, config in _BASE.OPTIMIZED_CONFIGS.items()}
BASELINE_CONFIG = dict(_BASE.BASELINE_CONFIG)


class Solver:
    def __new__(cls, env, mode=3, **config):
        merged = {**OPTIMIZED_CONFIGS[mode], **config}
        # A fixed source-defined module is the provider; no case-indexed plan
        # table or cached future result is part of this executable strategy.
        merged['jointplan_geometry_provider'] = _PROVIDER
        return _BASE.Solver(env, mode=mode, **merged)
