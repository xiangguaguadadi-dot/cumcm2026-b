from pathlib import Path
import ast,json,hashlib
P=Path(__file__).resolve().parent;R=P.parents[1];parent=P/'snapshots/r2_one_round.py'
component='''
# R4 breaks only the finite optical fallback into persistent, paid blocks.
_FrozenR2OpticalSolver=Solver
class OpticalRoundDirectional(ServiceDirectional):
    def __init__(self,env,mode=4,**config):
        super().__init__(env,mode=mode,**config)
        self._e2_optical_queue={}

    def _e2_optical_task_point(self,ch):
        pending=self._e2_optical_queue.get(ch)
        return pending[0] if pending else _Q4._di_enclosing_circle(self.polygons[ch])[0]

    def cover_polygon(self,ch):
        if ch not in self._e2_optical_queue:
            self.counters['fallbacks']+=1
            self._e2_optical_queue[ch]=list(self.optical_route(ch,self.optical_points(ch)))
        queue=self._e2_optical_queue[ch]
        quota=len(queue) if self.virtual_time>=_Q4._di_VIRTUAL_SAFE_SWITCH_S else int(self.config['e2_optical_quota'])
        self.counters['e2_optical_blocks']=self.counters.get('e2_optical_blocks',0)+1
        for _ in range(min(quota,len(queue))):
            # Remove a cell only after its actual clear request returned.
            point=queue[0]
            if self.clear(point,ch):
                self._e2_optical_queue.pop(ch,None)
                return
            queue.pop(0)
        if not queue:
            raise RuntimeError('Persistent complete optical covering exhausted without success')

    def localize(self,ch):
        if ch not in self._e2_optical_queue:return super().localize(ch)
        self._active_target=ch
        try:self.cover_polygon(ch)
        finally:self._active_target=None
        self.share_observations(ch)
'''
base=(R/'experiments/20260911_stage4/baseline/R3_open_R5.py').read_text();node=next(n for n in ast.parse(base).body if isinstance(n,ast.ClassDef) and n.name=='_di_Solver');f=next(n for n in node.body if isinstance(n,ast.FunctionDef) and n.name=='spatial_next_task');method='\n'.join(base.splitlines()[f.lineno-1:f.end_lineno])+'\n';method=method.replace('_di_enclosing_circle(self.polygons[k])[0]','self._e2_optical_task_point(k)').replace('_di_dist','_Q4._di_dist');component+='\n'+method+'''
class Solver:
    def __new__(cls,env,mode=3,**config):
        if mode not in (3,4):raise ValueError('mode must be 3 or 4')
        if mode==3:return _FrozenR2OpticalSolver(env,mode=mode,**config)
        return OpticalRoundDirectional(env,mode=mode,**{**OPTIMIZED_CONFIGS[mode],**config})
'''
(P/'optical_round_component.py').write_text(component)
for quota in [1,3]:
 name=f'r4_optical_{quota}';config=dict(e2_optical_quota=quota);p=P/'snapshots'/(name+'.py');assert not p.exists();p.write_text(parent.read_text()+'\n'+component+'\nOPTIMIZED_CONFIGS[4].update('+repr(config)+')\n');p.with_suffix('.provenance.json').write_text(json.dumps(dict(candidate=str(p.relative_to(R)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),parent_sha256=hashlib.sha256(parent.read_bytes()).hexdigest(),q4_config=config,deployment_dependencies={}),indent=2)+'\n');print(name)
