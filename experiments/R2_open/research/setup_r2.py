from pathlib import Path
import ast,json,hashlib,datetime
root=Path('/Users/t/Documents/Codex/2026-09-10/new-chat/work/stage3/R2_open');out=root/'experiments/R2_open'
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2))
path=out/'optimization_path.json';data=json.loads(path.read_text());assert not any(r['id']=='R2_open_R2' for r in data['rounds'])
data['rounds'].append(dict(id='R2_open_R2',parents=['R2_open_R1','A2_information_R8'],status='preregistered',before=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),problem='Second bearing still uses fixed geometric placement; arrival location may already certify another discovered source.',plan='Transplant A2 active second-point expected action cost and introduce same-location all-vertex certified service; compare parent, active only, service only, naive both on fresh 12x12x2 cases.',selection='All cases complete; Q4 identical; choose lowest Q3 development mean among four variants. No new exposed tuning.',seed_range=[42000008,42000019],hypotheses='Active placement may reduce failed clears and route detours. Same-location certification may avoid visits for clustered sources; no claimed additivity.',new_guarantee='Same-location all-vertex distance <=20-eps certifies any source inside convex outer set; <=16 added clears, no added movement. Active points remain bounded and do not update authoritative set.')))
save(path,data)
with (out/'optimization_path.md').open('a') as f:f.write('\n\n## R2 实验前记录\n\n在R1上迁移A2的主动第二测点，以预测后续clear/修正动作秒数评分；同时独立测试到达点对其他已发现源的全顶点20米认证清除。开发42000008–42000019，12场景×2题；父法、主动测点、同址清除、两者直接组合，全部完整且Q4一致后按Q3开发均值选择。此记录先于执行。第二测点的假想观测只排序，不改变认证集合；同址清除只针对全部顶点距当前位置≤20−1e−6者，每源至多一次成功，附加≤80秒。后续完整冻结回归再决定保留。\n')
s=(out/'snapshots/r1_solver.py').read_text();a2=(root/'experiments/20260911_agent_campaign/final_candidates/A2_information_R8.py').read_text();cls=next(x for x in ast.parse(a2).body if isinstance(x,ast.ClassDef) and x.name=='Solver');defs={x.name:x for x in cls.body if isinstance(x,ast.FunctionDef)}
import sys
sys.path.insert(0,str(out/'research'));from build_candidate import rename
methods='\n\n'.join('    '+ast.get_source_segment(a2,defs[n]) for n in ['belief_quadrature','planning_hypotheses','predicted_polygon','second_point'])
methods=rename(methods,dict(dist='_sp_dist',enclosing_circle='_sp_enclosing_circle',EPS='_sp_EPS',clip='_sp_clip',baseline_second_point='_parent_second_point'))
component='''# R2: A2 action-cost second point plus same-location certified clear.
class _ActionSpatial(_GeometrySpatial):
    def __init__(self, env, mode=3, **config):
        super().__init__(env, mode=mode, **config)
        self._servicing = False

    def _parent_second_point(self, ch):
        return super().second_point(ch)

    def _serve_certified_here(self, exclude=None):
        if self._servicing or not self.config.get('same_location_clear',False):
            return
        self._servicing = True
        try:
            p=self.position
            for other in range(1,21):
                if other==exclude or other in self.cleared or other not in self.polygons:
                    continue
                # A norm is convex; checking vertices certifies the whole hull.
                if all(_sp_dist(p,v)<=20.0-1e-6 for v in self.polygons[other]):
                    self.counters['same_location_clears']=self.counters.get('same_location_clears',0)+1
                    self.clear(p,other,certified=True)
        finally:
            self._servicing=False

    def measure(self,p,ch):
        result=super().measure(p,ch)
        self._serve_certified_here(ch)
        return result

    def clear(self,p,ch,certified=False):
        success=super().clear(p,ch,certified=certified)
        if success:
            self._serve_certified_here(ch)
        return success

'''+methods+'\n\n'
s=s.replace('BASELINE_CONFIG = dict(_sp_BASELINE_CONFIG)',component+'BASELINE_CONFIG = dict(_sp_BASELINE_CONFIG)',1).replace('parent = _GeometrySpatial if mode == 3 else _di_Solver','parent = _ActionSpatial if mode == 3 else _di_Solver')
s=s.replace('geom_tangent=True, geom_no_signal=True, geom_failure=True),','geom_tangent=True, geom_no_signal=True, geom_failure=True, active_information=False, same_location_clear=False),')
(out/'snapshots/r2_development.py').write_text(s);ast.parse(s)
(out/'research/r2_component.py').write_text(component)
save(out/'research/r2_variants.json',[dict(name=name,candidate='experiments/R2_open/snapshots/r2_development.py',config=config) for name,config in [('parent',{}),('active',{'active_information':True}),('same_location',{'same_location_clear':True}),('both',{'active_information':True,'same_location_clear':True})]])
save(out/'research/r2_provenance.json',dict(parent_sha=hashlib.sha256((out/'snapshots/r1_solver.py').read_bytes()).hexdigest(),second_point_source=str(root/'experiments/20260911_agent_campaign/final_candidates/A2_information_R8.py'),source_methods=['belief_quadrature','planning_hypotheses','predicted_polygon','second_point'],renames='standard primitive namespace and parent method; no numerical changes',development_sha=hashlib.sha256(s.encode()).hexdigest()))
print('R2 preregistered and built')
