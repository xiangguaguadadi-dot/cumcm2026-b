"""Q3 compatibility adapter. No RL engine, wrapper, hooks, or strategy changes."""
import hashlib
import importlib.util
from .vendor import REPO

LATEST_Q3_ENTRY=REPO/'experiments/20260912_breakthrough/final_candidates/combined.py'
LATEST_Q3_SHA256='08dbe1dc5018b98c3b4ac0b128953174e4067be96b22683e61b030f10087ef01'
_MODULE=None


def module():
    global _MODULE
    if hashlib.sha256(LATEST_Q3_ENTRY.read_bytes()).hexdigest()!=LATEST_Q3_SHA256:
        raise RuntimeError('Execution-time latest Q3 entry changed')
    if _MODULE is None:
        spec=importlib.util.spec_from_file_location('_bc_rpi_latest_nonrl_q3',LATEST_Q3_ENTRY)
        _MODULE=importlib.util.module_from_spec(spec);spec.loader.exec_module(_MODULE)
    return _MODULE


def Solver(backend,mode=3,**config):
    if mode!=3:raise ValueError('This exact pass-through is Q3 only')
    return module().Solver(backend,mode=mode,**config)
