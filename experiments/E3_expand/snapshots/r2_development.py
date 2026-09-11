"""Multi-target value of the two geometric second-bearing alternatives.

Only hypothetical planning uses other target centers. Real regions are updated
exclusively by paid observations inherited from S1. This is a finite geometric
surrogate inspired by multi-target planning, not a reproduction of ATL/TD3.
"""
import importlib.util,math
from pathlib import Path
_path=Path(__file__).resolve().parents[2]/'20260911_stage4/baseline/S1.py'
_spec=importlib.util.spec_from_file_location('e3_joint_s1',_path)
_s1=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_s1)
_d=_s1._A4
BASELINE_CONFIG=dict(_s1.BASELINE_CONFIG)
OPTIMIZED_CONFIGS={m:dict(c,joint_weight=1.) for m,c in _s1.OPTIMIZED_CONFIGS.items()}
class _Directional(_d._LensDirectional):
    def second_point(self,ch):
        fallback=super().second_point(ch)
        weight=self.config.get('joint_weight',1.)
        if weight<=0:return fallback
        p,deg=self.observations[ch][-1];theta=math.radians(deg)
        ux,uy=math.cos(theta),math.sin(theta)
        center,radius=_d._di_enclosing_circle(self.polygons[ch])
        length=max(0,(center[0]-p[0])*ux+(center[1]-p[1])*uy)
        advance=max(30,length*self.config.get('advance_fraction',.78))
        lateral=max(45,min(190,length*self.config.get('lateral_fraction',.20)))
        candidates=[(p[0]+advance*ux-sign*lateral*uy,p[1]+advance*uy+sign*lateral*ux) for sign in [-1,1]]
        pending=[c for c in range(1,21) if c!=ch and c not in self.cleared and self.observations[c]]
        if not pending:return fallback
        def cost(q):
            travel=_d._di_dist(q,self.position)+.12*min(_d._di_dist(q,w) for w in self.points)
            visibility=self.config.get('visibility_penalty_m',600.)*(1-self.predicted_visibility(ch,q))
            benefit=0.
            for c in pending:
                poly=self.polygons[c];ctr,rad=_d._di_enclosing_circle(poly)
                if rad<=20 or _d._di_dist(q,ctr)>1500+rad:continue
                if min(_d._di_dist(q,old) for old,_ in self.observations[c])<60:continue
                bearing=math.degrees(math.atan2(ctr[1]-q[1],ctr[0]-q[0]))
                updated=_d._di_add_bearing(poly,q,bearing)
                if not updated:continue
                gain=max(0.,rad-_d._di_enclosing_circle(updated)[1])*self.predicted_visibility(c,q)
                # The inherited sharing action still decides and pays for each
                # actual measurement. This capped value avoids using a large
                # unlocalized polygon as an arbitrarily large planning reward.
                benefit+=max(0.,min(300.,gain)-30.)
            return travel+visibility-weight*benefit
        q=min(candidates,key=lambda q:(cost(q),q))
        self.counters['joint_second_choices']=self.counters.get('joint_second_choices',0)+1
        if _d._di_dist(q,fallback)>1e-8:self.counters['joint_second_changes']=self.counters.get('joint_second_changes',0)+1
        return q
class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        return _s1.Solver(env,mode=mode,**merged) if mode==3 else _Directional(env,mode=mode,**merged)
