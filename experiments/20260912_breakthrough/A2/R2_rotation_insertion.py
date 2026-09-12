"""Q4 R2: use source-to-future-site insertion proxy for the same certified rotation."""
import importlib.util
from pathlib import Path
_path=Path(__file__).resolve().with_name('R1_rotation.py')
_spec=importlib.util.spec_from_file_location('_a2_r1_rotation',_path)
_R1=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_R1)
BASELINE_CONFIG=dict(_R1.BASELINE_CONFIG)
OPTIMIZED_CONFIGS={3:dict(_R1.OPTIMIZED_CONFIGS[3]),4:dict(_R1.OPTIMIZED_CONFIGS[4],a2_rotation_proxy='insertion')}
class Solver:
    def __new__(cls,env,mode=3,**config):
        return _R1.Solver(env,mode=mode,**{**OPTIMIZED_CONFIGS[mode],**config})
