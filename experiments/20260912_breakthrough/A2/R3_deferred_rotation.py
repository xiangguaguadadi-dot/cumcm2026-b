"""Q4 R3: keep phase free until the first non-origin physical scan.

Re-optimize using actual paid service endpoint; never move a scanned site.
"""
import importlib.util,math
from pathlib import Path
_path=Path(__file__).resolve().with_name('R1_rotation.py')
_spec=importlib.util.spec_from_file_location('_a2_r1_rotation',_path)
_R1=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_R1)
_C7=_R1._C7
BASELINE_CONFIG=dict(_R1.BASELINE_CONFIG)
OPTIMIZED_CONFIGS={3:dict(_R1.OPTIMIZED_CONFIGS[3]),4:dict(_R1.OPTIMIZED_CONFIGS[4])}

class DeferredDirectional(_C7.GeometryDirectional):
    def __init__(self,env,mode=4,**config):
        super().__init__(env,mode=mode,**config)
        self._a2_canonical=self.points[:]
        self._a2_pose_signature=None

    def _a2_maybe_rotate(self):
        if not any(0 in seen for seen in self.scanned.values()):return
        if any(any(i!=0 for i in seen) for seen in self.scanned.values()):return
        centers=[_C7._Q4._di_enclosing_circle(self.polygons[ch])[0]
            for ch in range(1,21) if self.observations[ch] and ch not in self.cleared]
        signature=(self.position,tuple(centers))
        if signature==self._a2_pose_signature:return
        self._a2_pose_signature=signature
        best=None;steps=24
        for k in range(steps):
            angle=math.pi*k/(2*steps);co,si=math.cos(angle),math.sin(angle)
            points=[(co*x-si*y,si*x+co*y) for x,y in self._a2_canonical]
            score=min(math.dist(self.position,p) for p in points[1:])
            score+=sum(min(math.dist(c,p) for p in points[1:]) for c in centers)
            if best is None or score<best[0]-1e-7:best=(score,k,points)
        self.points=best[2]
        _C7._E1._GEOMETRY_MASKS[tuple(self.points)]=_C7._E1._discovery_masks(self._a2_canonical)
        self.counters['a2_rotation_updates']=self.counters.get('a2_rotation_updates',0)+1
        self.counters['a2_rotation_angle_index']=best[1]

    def next_station(self,todo):
        self._a2_maybe_rotate()
        return super().next_station(todo)

    def spatial_next_task(self,todo):
        self._a2_maybe_rotate()
        return super().spatial_next_task(todo)

class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        return _C7.Solver(env,mode=3,**merged) if mode==3 else DeferredDirectional(env,mode=4,**merged)
