"""Q4 R4: retain R2 planning, then align the first actual station to paid pose."""
import importlib.util,math
from pathlib import Path
_path=Path(__file__).resolve().with_name('R1_rotation.py')
_spec=importlib.util.spec_from_file_location('_a2_r1_rotation',_path)
_R1=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_R1)
_C7=_R1._C7
BASELINE_CONFIG=dict(_R1.BASELINE_CONFIG)
OPTIMIZED_CONFIGS={3:dict(_R1.OPTIMIZED_CONFIGS[3]),4:dict(_R1.OPTIMIZED_CONFIGS[4],a2_rotation_proxy='insertion')}

class CommitDirectional(_R1.RotationDirectional):
    def scan_station(self,index,defer=False):
        if index!=0 and math.hypot(*self.position)>1e-8 and not any(any(i!=0 for i in seen) for seen in self.scanned.values()):
            original=self.points[:];target=original[index]
            angle=math.atan2(self.position[1],self.position[0])-math.atan2(target[1],target[0])
            co,si=math.cos(angle),math.sin(angle)
            points=[(co*x-si*y,si*x+co*y) for x,y in original]
            before=math.dist(self.position,target);after=math.dist(self.position,points[index])
            assert after<=before+1e-7
            self.points=points
            _C7._E1._GEOMETRY_MASKS[tuple(points)]=_C7._E1._discovery_masks(original)
            self.counters['a2_commit_rotation']=1
            self.counters['a2_commit_saved_immediate_m']=before-after
        return super().scan_station(index,defer=defer)

class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        return _C7.Solver(env,mode=3,**merged) if mode==3 else CommitDirectional(env,mode=4,**merged)
