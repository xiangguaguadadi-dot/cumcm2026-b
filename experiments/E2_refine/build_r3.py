from pathlib import Path
import ast,json,hashlib
P=Path(__file__).resolve().parent;R=P.parents[1]
parent=P/'snapshots/r2_one_round.py';text=parent.read_text()
component='''
# R3 keeps actual failed optical disks. Radio no_signal never excludes a Q4 disk.
_FrozenR2Solver=Solver
class FailureDirectional(ServiceDirectional):
    def __init__(self,env,mode=4,**config):
        super().__init__(env,mode=mode,**config)
        self._e2_failed_clear={c:[] for c in range(1,21)}

    def _e2_refine_failures(self,ch):
        if not self.config.get('e2_failure_hull',False) or ch not in self.polygons:return
        poly=self.polygons[ch]
        for p in self._e2_failed_clear[ch]:
            if len(poly)>96:break
            result=_Q3._geo_outside_disk_hull(poly,p,20.-1e-6)
            if not result:raise RuntimeError('Failed clear contradicts retained location geometry')
            if len(result)<=96:poly=result
        self.polygons[ch]=poly

    def measure(self,p,ch):
        kind=super().measure(p,ch)
        if kind=='direction':self._e2_refine_failures(ch)
        return kind

    def clear(self,p,ch,certified=False):
        ok=super().clear(p,ch,certified=certified)
        if not ok:
            self._e2_failed_clear[ch].append(tuple(map(float,p)))
            self._e2_refine_failures(ch)
        return ok

    def _e2_cell_excluded(self,test,origin,u,v,ch):
        if not self.config.get('e2_failure_cells',False):return False
        world=[(origin[0]+q[0]*u[0]+q[1]*v[0],origin[1]+q[0]*u[1]+q[1]*v[1]) for q in test]
        # test is the full convex polygon/cell intersection. A disk is convex,
        # so vertex containment certifies all of that cell's feasible portion.
        excluded=any(all(math.dist(p,q)<=20.-1e-6 for q in world) for p in self._e2_failed_clear[ch])
        if excluded:self.counters['e2_excluded_cells']=self.counters.get('e2_excluded_cells',0)+1
        return excluded
'''
base=(R/'experiments/20260911_stage4/baseline/R3_open_R5.py').read_text()
node=next(n for n in ast.parse(base).body if isinstance(n,ast.ClassDef) and n.name=='_di_Solver')
f=next(n for n in node.body if isinstance(n,ast.FunctionDef) and n.name=='optical_points')
method='\n'.join(base.splitlines()[f.lineno-1:f.end_lineno])+'\n'
method=method.replace('_di_clip','_Q4._di_clip').replace('                if test:\n','                if test and not self._e2_cell_excluded(test,origin,u,v,ch):\n')
component+='\n'+method+'''
class Solver:
    def __new__(cls,env,mode=3,**config):
        if mode not in (3,4):raise ValueError('mode must be 3 or 4')
        if mode==3:return _FrozenR2Solver(env,mode=mode,**config)
        return FailureDirectional(env,mode=mode,**{**OPTIMIZED_CONFIGS[mode],**config})
'''
(P/'failure_component.py').write_text(component)
for name,config in [('r3_failure_hull',dict(e2_failure_hull=True,e2_failure_cells=False)),('r3_failure_cells',dict(e2_failure_hull=False,e2_failure_cells=True))]:
 p=P/'snapshots'/(name+'.py');assert not p.exists();p.write_text(text+'\n'+component+'\nOPTIMIZED_CONFIGS[4].update('+repr(config)+')\n')
 meta=dict(candidate=str(p.relative_to(R)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),parent_sha256=hashlib.sha256(parent.read_bytes()).hexdigest(),q4_config=config,deployment_dependencies={})
 p.with_suffix('.provenance.json').write_text(json.dumps(meta,indent=2)+'\n');print(name,meta['sha256'])
