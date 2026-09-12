"""Copy bounded geometric operators from the independent A1 branch into Q4.
No Q3 no-signal posterior filtering is imported. Copies and hashes freeze provenance.
"""
import ast,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
A1=HERE.parents[2]/'a1/experiments/parallel_v2_a1'
# HERE.parents[2] is the common worktree parent (parallel_v2).
if not A1.exists():A1=Path('/Users/t/ai project/数学建模2026/agent_experiments/20260912_parallel_v2/a1/experiments/parallel_v2_a1')
base=(HERE/'snapshots/hex_r6.py').read_text();classes=[];provenance=[]
for filename,name in [('twodisk_component.py','TwoDiskSpatial'),('three_disk_component.py','ThreeDiskSpatial'),('multidisk_component.py','MultiDiskSpatial')]:
 path=A1/filename;s=path.read_text();tree=ast.parse(s);node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==name)
 text=ast.unparse(node).replace('A1ServiceSpatial','FiniteOpticalBase').replace('failed_clear_points','_e2_failed_clear').replace('_a1_service_round','_e2_service_round')
 if name=='TwoDiskSpatial':text=text.replace('if ch in self.cleared:\n            return','if ch in self.cleared:\n            return\n        if self._virtual_fallback(ch):\n            return')
 if name=='MultiDiskSpatial':
  text=text.replace('        survive = [','        if union[full].bit_count() != len(targets):\n            return float("inf"), tuple(points)\n        survive = [')
 classes.append(text);provenance.append(dict(path=str(path),sha256=hashlib.sha256(s.encode()).hexdigest(),class_copied=name))
bridge='''
# Finite complete optical action policies transplanted from A1's geometry only.
_FIN_PARENT=Solver
_Q3=_C7._Q3
class FiniteOpticalBase(HexDirectional):
    belief_quadrature=_Q3._DecisionSpatial.belief_quadrature
    def trial_point(self,ch,center,radius):
        # Q4 parent trial is the MEC center; never apply Q3 no-signal disks.
        return center
'''
for i,name in enumerate(['TwoDiskSpatial','ThreeDiskSpatial','MultiDiskSpatial'],1):
 tail=bridge+'\n\n'.join(classes[:i])+f'''
class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={{**OPTIMIZED_CONFIGS[mode],**config}}
        return _FIN_PARENT(env,mode=3,**merged) if mode==3 else {name}(env,mode=4,**merged)
'''
 (HERE/'snapshots'/f'finite_r{i}.py').write_text(base+tail)
(HERE/'finite_component.py').write_text(bridge+'\n\n'.join(classes)+'\n')
(HERE/'finite_provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
