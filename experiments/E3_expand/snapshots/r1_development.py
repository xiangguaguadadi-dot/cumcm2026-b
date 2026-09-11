"""Paid opportunistic initialization of as-yet undetected channels.

Inspired by multi-target initialization cost sharing in Vander Hook et al.
(Experimental Robotics, 2013). This implements stop reuse, not four-ray
signal-range fitting; directional no-signal observations never certify absence.
"""
import importlib.util
from pathlib import Path
_path=Path(__file__).resolve().parents[2]/'20260911_stage4/baseline/S1.py'
_spec=importlib.util.spec_from_file_location('e3_s1',_path)
_s1=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_s1)
BASELINE_CONFIG=dict(_s1.BASELINE_CONFIG)
OPTIMIZED_CONFIGS={m:dict(c,initialize_unknown=True,initialization_spacing_m=600.,initialization_on='clear') for m,c in _s1.OPTIMIZED_CONFIGS.items()}

class _InitializeMixin:
    def __init__(self,env,mode=3,**config):
        super().__init__(env,mode=mode,**config)
        self._initializing=False
        self._initialization_spent_s=0.

    def share_observations(self,exclude=None):
        super().share_observations(exclude)
        if self._initializing or self._sharing or exclude is None or not self.config.get('initialize_unknown',True):
            return
        if self.config.get('initialization_on','clear')=='clear' and exclude not in self.cleared:
            return
        if len(set(self.cleared)|{c for c in range(1,21) if self.observations[c]})>=16:
            return
        self._initializing=True;self._sharing=True
        try:
            p=self.position
            spacing=self.config.get('initialization_spacing_m',600.)
            for ch in range(1,21):
                if self.virtual_time>=180000 or self._initialization_spent_s>=3000:
                    break
                if ch in self.cleared or self.observations[ch] or ch==exclude:
                    continue
                previous=self.no_signal_points[ch]
                if previous and min(_s1._A4._di_dist(p,q) for q in previous)<spacing:
                    continue
                before=self.virtual_time
                self.counters['initialization_measures']=self.counters.get('initialization_measures',0)+1
                kind=self.measure(p,ch)
                if kind!='no_signal':
                    self.counters['initialization_detections']=self.counters.get('initialization_detections',0)+1
                self._initialization_spent_s+=self.virtual_time-before
        finally:
            self._sharing=False;self._initializing=False

class _Directional(_InitializeMixin,_s1._A4._LensDirectional):
    pass

class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        if mode==3:
            return _s1.Solver(env,mode=mode,**merged)
        return _Directional(env,mode=mode,**merged)
