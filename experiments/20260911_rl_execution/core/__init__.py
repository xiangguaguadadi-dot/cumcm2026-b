"""Shared observable C7 macro controller for the approved RL execution."""
from .schema import (SCHEMA_VERSION, GENERATOR_VERSION, GLOBAL_DIM, CHANNEL_DIM,
                     CANDIDATE_DIM, validate_snapshot, teacher_selector)

def run_episode(env, mode=3, selector=None, **kwargs):
    from .engine import run_episode as _run
    return _run(env, mode=mode, selector=selector, **kwargs)
