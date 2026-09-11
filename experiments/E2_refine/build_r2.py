from pathlib import Path
import ast,json,hashlib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
base=(ROOT/'experiments/20260911_stage4/baseline/R3_open_R5.py').read_text()
node=next(n for n in ast.parse(base).body if isinstance(n,ast.ClassDef) and n.name=='_di_Solver')
f=next(n for n in node.body if isinstance(n,ast.FunctionDef) and n.name=='localize')
method='\n'.join(base.splitlines()[f.lineno-1:f.end_lineno])+'\n'
method=method.replace('def localize(self,ch):','def _e2_service_round(self,ch):',1)
method=method.replace('        for k in range(max_iter):','        start=self._e2_progress.get(ch,0)\n        for k in range(start,min(start+1,max_iter)):\n            self._e2_progress[ch]=k+1',1)
old='        self.cover_polygon(ch)\n';idx=method.rfind(old);assert idx>=0
method=method[:idx]+'        if self._e2_progress.get(ch,0)>=max_iter:\n            self.cover_polygon(ch)\n'+method[idx+len(old):]
# Use the exact frozen helper names inside the copied, single-round body.
method=method.replace('_di_enclosing_circle','_Q4._di_enclosing_circle').replace('_di_dist','_Q4._di_dist')
component='''
# R2: the source-service unit changes; all source state is actual API history.
_FrozenR1Solver=Solver
class ServiceDirectional(CostDirectional):
    def __init__(self,env,mode=4,**config):
        super().__init__(env,mode=mode,**config)
        self._e2_servicing=False
        self._e2_progress={}

    def _e2_clear_here(self,exclude=None):
        if not self.config.get('e2_same_here',False) or self._e2_servicing:return
        self._e2_servicing=True
        try:
            p=self.position
            for ch in range(1,21):
                if ch==exclude or ch in self.cleared or ch not in self.polygons:continue
                if all(math.dist(p,v)<=20.-1e-6 for v in self.polygons[ch]):
                    self.counters['e2_same_here_clears']=self.counters.get('e2_same_here_clears',0)+1
                    self.clear(p,ch,certified=True)
        finally:self._e2_servicing=False

    def measure(self,p,ch):
        kind=super().measure(p,ch)
        self._e2_clear_here()
        return kind

    def clear(self,p,ch,certified=False):
        success=super().clear(p,ch,certified=certified)
        self._e2_clear_here(exclude=ch)
        return success

    def localize(self,ch):
        if not self.config.get('e2_one_round',False):return super().localize(ch)
        self._active_target=ch
        self.counters['e2_service_rounds']=self.counters.get('e2_service_rounds',0)+1
        try:self._e2_service_round(ch)
        finally:self._active_target=None
        self.share_observations(ch)

'''+method+'''
class Solver:
    def __new__(cls,env,mode=3,**config):
        if mode not in (3,4):raise ValueError('mode must be 3 or 4')
        if mode==3:return _FrozenR1Solver(env,mode=mode,**config)
        return ServiceDirectional(env,mode=mode,**{**OPTIMIZED_CONFIGS[mode],**config})
'''
(HERE/'service_component.py').write_text(component)
parent=HERE/'snapshots/r1_station_only.py';source=parent.read_text()
for name,config in [('r2_here',dict(e2_same_here=True,e2_one_round=False)),('r2_one_round',dict(e2_same_here=False,e2_one_round=True))]:
 p=HERE/'snapshots'/(name+'.py');assert not p.exists()
 p.write_text(source+'\n'+component+'\nOPTIMIZED_CONFIGS[4].update('+repr(config)+')\n')
 meta=dict(candidate=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),parent_sha256=hashlib.sha256(parent.read_bytes()).hexdigest(),q4_config=config,deployment_dependencies={})
 p.with_suffix('.provenance.json').write_text(json.dumps(meta,indent=2)+'\n');print(name,meta['sha256'])
