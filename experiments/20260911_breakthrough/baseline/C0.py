"""Strong task-wise control: exact prior A1 R8 for Q3, A4 R6 for Q4.
This is explicit mode dispatch, not a new algorithmic improvement.
Dependencies are immutable source snapshots in the same directory.
"""
import importlib.util
from pathlib import Path

def _load(name):
    path = Path(__file__).resolve().parent / (name + '.py')
    spec = importlib.util.spec_from_file_location('control_' + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

_A1 = _load('A1_space_R8')
_A4 = _load('A4_directional_R6')
OPTIMIZED_CONFIGS = {3: dict(_A1.OPTIMIZED_CONFIGS[3]), 4: dict(_A4.OPTIMIZED_CONFIGS[4])}
BASELINE_CONFIG = dict(_A1.BASELINE_CONFIG)

class Solver:
    def __new__(cls, env, mode=3, **config):
        if mode not in (3, 4):
            raise ValueError('mode must be 3 or 4')
        parent = _A1 if mode == 3 else _A4
        return parent.Solver(env, mode=mode, **config)
