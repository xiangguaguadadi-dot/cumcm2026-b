"""Q4 R5: continuous one-dimensional refinement of retained insertion phase."""
import importlib.util,math
from pathlib import Path
_path=Path(__file__).resolve().with_name('R1_rotation.py')
_spec=importlib.util.spec_from_file_location('_a2_r1_rotation',_path)
_R1=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_R1)
_C7=_R1._C7
BASELINE_CONFIG=dict(_R1.BASELINE_CONFIG)
OPTIMIZED_CONFIGS={3:dict(_R1.OPTIMIZED_CONFIGS[3]),4:dict(_R1.OPTIMIZED_CONFIGS[4],a2_rotation_proxy='insertion')}

class ContinuousDirectional(_R1.RotationDirectional):
    def _a2_choose_rotation(self):
        self._a2_rotated=True
        assert not any(any(i!=0 for i in seen) for seen in self.scanned.values())
        centers=[_C7._Q4._di_enclosing_circle(self.polygons[ch])[0]
            for ch in range(1,21) if self.observations[ch] and ch not in self.cleared]
        if not centers:return
        original=self.points[:]
        def points(angle):
            co,si=math.cos(angle),math.sin(angle)
            return [(co*x-si*y,si*x+co*y) for x,y in original]
        def score(angle):
            ps=points(angle)
            return sum(min(math.dist(c,p) for p in ps[1:]) for c in centers)
        step=math.pi/48
        angle=min((i*step for i in range(24)),key=score)
        baseline=score(angle);lo,hi=angle-step,angle+step;gold=(math.sqrt(5)-1)/2
        left=hi-gold*(hi-lo);right=lo+gold*(hi-lo);fl=score(left);fr=score(right)
        for _ in range(24):
            if fl<fr:
                hi,right,fr=right,left,fl;left=hi-gold*(hi-lo);fl=score(left)
            else:
                lo,left,fl=left,right,fr;right=lo+gold*(hi-lo);fr=score(right)
        best=min([angle,left,right],key=score)
        self.points=points(best)
        _C7._E1._GEOMETRY_MASKS[tuple(self.points)]=_C7._E1._discovery_masks(original)
        self.counters['a2_continuous_rotation']=1
        self.counters['a2_refinement_proxy_gain_m']=baseline-score(best)

class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        return _C7.Solver(env,mode=3,**merged) if mode==3 else ContinuousDirectional(env,mode=4,**merged)
