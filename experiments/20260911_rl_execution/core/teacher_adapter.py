"""Frozen-evaluator adapter for shared-core teacher regression only.

No neural model or training is used. Core completion failures are raised even
when the underlying simulator happened to exit, so frozen evaluate.py cannot
mistake a wrapper failure for a passed candidate.
"""
from pathlib import Path as _Path
import sys as _sys

_execution_root=str(_Path(__file__).resolve().parents[1])
if _execution_root not in _sys.path:_sys.path.insert(0,_execution_root)
from core import run_episode as _run_episode, teacher_selector as _teacher_selector

__all__=['OPTIMIZED_CONFIGS','Solver']
OPTIMIZED_CONFIGS={3:{},4:{}}

class Solver:
    def __init__(self,env,mode=3,**conf):
        self._env=env;self._mode=mode;self._conf=conf
    def run(self):
        raw=_run_episode(self._env,mode=self._mode,selector=_teacher_selector,c7_config=self._conf)
        if not raw.get('success',False):
            raise RuntimeError('Shared core teacher failed: '+str(raw.get('error') or raw.get('terminal')))
        return {'coverage_complete':bool(raw['observed_completion_certified']),
                'completion_certified':bool(raw['observed_completion_certified']),
                'virtual_time_s':raw['total_time_s'],'cleared_count':raw['cleared_count'],
                'fallback_reason':raw['fallback_reason'],'normal_exit':raw['normal_exit']}
