from pathlib import Path
import json,datetime,hashlib,ast
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'experiments/R2_open'
def read(p):return json.loads(p.read_text())
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2))
p=read(OUT/'optimization_path.json');assert not any(r['id']=='R2_open_R3' for r in p['rounds'])
p['rounds'].append(dict(id='R2_open_R3',parents=['R2_open_R2'],inspired_by=['Javdani et al. 2014 Decision Region Determination'],status='preregistered',before=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),problem='B1 measures whenever radius gain >=60m, even if the changed set does not justify a paid action.',plan='Keep same arrival points, center hypothesis count=1, three bounded error nodes, actual polygons and hard budget. Compare original radius gate, at least 2/3 predicted certified clear gate, physical action-cost proxy gate and sharing off.',selection='All cases complete, Q4 exact control; lowest Q3 development mean (including parent); if no new variant wins, preserve diagnostic result and retain parent.',seed_range=[42000020,42000035],proxy='C(P,p)=max(0,dist(p,center)-max(0,20-r))/5+5+[r>20]*(8+max(0,r-20)/5)+[r>100]*6; net=C_before-6-E(C_after). This is a ranking proxy, not a proven cost bound or calibrated probability.',probability='One parent center hypothesis; error nodes -0.8,0,+0.8; unknown receive radius uniform interval constrained by actual positive/no-signal distances at this hypothesis. Inconsistent center falls back to parent gate. Includes near/no-signal predictions.')))
save(OUT/'optimization_path.json',p)
with (OUT/'optimization_path.md').open('a') as f:f.write('\n\n## R3 实验前：DRD启发的任务决策补测门控\n\n保留R2到达位置、每频道中心假说、真实集合与6000秒补测上限，新增±0.8/0度三个预测误差分支。比较原60米半径门控、至少2/3预测分支可认证clear、含6秒检测/8秒失败后补测和路程的动作费用代理、完全关闭补测。开发42000020–42000035，12场景×2题，全部完整且Q4相同后按Q3开发均值选择。费用代理/未知半径均匀先验均为建模假设，不声称论文HEC最优保证或官方先验。中心假说不满足已有接收/无信号约束时回原门控。资料来源由R1_atlas第1批备忘及DRD原文第3/8页核验。\n')
component='''# DRD-inspired task-value gates; finite hypotheses are planning only.
class _DecisionSpatial(_ActionSpatial):
    @staticmethod
    def _continuation_cost(poly,p):
        c,r=_sp_enclosing_circle(poly)
        travel=max(0.,_sp_dist(p,c)-max(0.,20.-r))/5.
        # One clear plus correction and another measurement if unresolved.
        # This intentionally simple proxy is not a theorem or empirical oracle.
        return travel+5.+(8.+max(0.,r-20.)/5. if r>20. else 0.)+(6. if r>100. else 0.)

    def _gate_prediction(self,ch,p):
        poly=self.polygons[ch];center,radius=_sp_enclosing_circle(poly)
        target=center  # Same one location hypothesis as parent visibility style.
        low=max([1000.]+[_sp_dist(target,q) for q,_ in self.observations[ch]])
        high=min([1500.]+[_sp_dist(target,q) for q in self.no_signal_points[ch]])
        if low>high+1e-6 or math.hypot(*target)>1800.+1e-6:
            return None
        dd=_sp_dist(target,p)
        if dd<=5.:
            return 1.,self._continuation_cost(poly,p)-11.
        receive=1. if dd<=low else 0. if dd>high else (high-dd)/max(1e-9,high-low)
        posterior_cost=0.;certificate=0.
        for error in (-.8,0.,.8):
            bearing=math.degrees(math.atan2(target[1]-p[1],target[0]-p[0]))+error
            posterior=_sp_add_bearing(poly,p,bearing)
            if posterior:
                _,rr=_sp_enclosing_circle(posterior)
                certificate+=float(rr<=20.)/3.
                posterior_cost+=self._continuation_cost(posterior,p)/3.
            else:
                posterior_cost+=self._continuation_cost(poly,p)/3.
        negative=_geo_outside_disk_hull(poly,p,1000.-1e-6)
        no_signal_cost=self._continuation_cost(negative or poly,p)
        net=self._continuation_cost(poly,p)-6.-(receive*posterior_cost+(1.-receive)*no_signal_cost)
        return receive*certificate,net

    def share_observations(self,exclude=None):
        gate=self.config.get('decision_gate','parent')
        if gate=='parent':
            return super().share_observations(exclude)
        if gate=='off' or self._sharing:
            return
        self._sharing=True
        try:
            p=self.position
            for ch in range(1,21):
                if self.virtual_time>=180000 or self._sharing_spent_s>=6000:
                    break
                if ch==exclude or ch in self.cleared or not self.observations[ch]:
                    continue
                if min(_sp_dist(p,old) for old,_ in self.observations[ch])<60:
                    continue
                poly=self.polygons[ch];center,radius=_sp_enclosing_circle(poly)
                if radius<=20 or _sp_dist(center,p)>1500+radius:
                    continue
                prediction=self._gate_prediction(ch,p)
                self.counters['decision_gate_evaluations']=self.counters.get('decision_gate_evaluations',0)+1
                if prediction is None:
                    self.counters['decision_gate_fallback']=self.counters.get('decision_gate_fallback',0)+1
                    bearing=math.degrees(math.atan2(center[1]-p[1],center[0]-p[0]))
                    posterior=_sp_add_bearing(poly,p,bearing)
                    value=max(0.,radius-_sp_enclosing_circle(posterior)[1]) if posterior else 0.
                    take=value>=self.config.get('sharing_gain_m',60.)
                else:
                    certificate,net=prediction
                    take=certificate>=2./3.-1e-9 if gate=='certificate' else net>0.
                if not take:
                    continue
                before=self.virtual_time
                self.counters['opportunity_measures']=self.counters.get('opportunity_measures',0)+1
                self.measure(p,ch)
                self._sharing_spent_s+=self.virtual_time-before
        finally:
            self._sharing=False

'''
(OUT/'research/r3_component.py').write_text(component)
s=(OUT/'snapshots/r2_solver.py').read_text().replace('BASELINE_CONFIG = dict(_sp_BASELINE_CONFIG)',component+'BASELINE_CONFIG = dict(_sp_BASELINE_CONFIG)',1).replace('parent = _ActionSpatial if mode == 3 else _di_Solver','parent = _DecisionSpatial if mode == 3 else _di_Solver').replace('active_information=False, same_location_clear=True),','active_information=False, same_location_clear=True, decision_gate="parent"),')
ast.parse(s);(OUT/'snapshots/r3_development.py').write_text(s)
save(OUT/'research/r3_variants.json',[dict(name=n,candidate='experiments/R2_open/snapshots/r3_development.py',config={'decision_gate':g}) for n,g in [('parent','parent'),('certificate','certificate'),('cost','cost'),('off','off')]])
source=Path('/Users/t/Documents/Codex/2026-09-10/new-chat/work/stage3/R1_atlas/experiments/R1_atlas/research/cache/drd_javdani2014.pdf')
lit=read(OUT/'literature.json');lit['R3_new_primary_source']=dict(title='Near Optimal Bayesian Active Learning for Decision Making',authors='Javdani et al.',year=2014,url='https://proceedings.mlr.press/v33/javdani14.html',pdf_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),actual_pages_read=[3,8],also_read='R1_atlas/research_updates/001_decision_value_and_dynamic_cover.md (all)',live_open='connection failed; source-specific cached full paper text read locally',transfer='Test decision-specific value instead of raw set shrink; continuous poly alone certifies clear; simple myopic proxy first',not_adopted='No HEC hypergraph; no known correct prior; fixed spatial error and moving cost differ; no approximation guarantee transfers.');save(OUT/'literature.json',lit)
print('R3 preregistered and built')
