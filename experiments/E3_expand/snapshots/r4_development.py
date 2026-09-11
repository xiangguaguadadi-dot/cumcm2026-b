"""Finite observation-tree lookahead for the first localization move in Q4.

Predict two paid observations, including the possibility of no-signal and a
failed optical clear. All targets below are observation-derived hypotheses.
The tree only ranks real actions; no hypothetical bearing enters actual state.
"""
import importlib.util,math
from pathlib import Path
_path=Path(__file__).resolve().parents[2]/'20260911_stage4/baseline/S1.py'
_spec=importlib.util.spec_from_file_location('e3_tree_s1',_path)
_s1=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_s1)
_d=_s1._A4
BASELINE_CONFIG=dict(_s1.BASELINE_CONFIG)
OPTIMIZED_CONFIGS={m:dict(c,tree_depth=2,tree_error_risk='mean') for m,c in _s1.OPTIMIZED_CONFIGS.items()}

class _Directional(_d._LensDirectional):
    def second_point(self,ch):
        fallback=super().second_point(ch)
        poly=self.polygons[ch];old,deg=self.observations[ch][-1]
        center,radius=_d._di_enclosing_circle(poly);theta=math.radians(deg)
        u=(math.cos(theta),math.sin(theta));v=(-u[1],u[0])
        length=max(30.,sum((center[i]-old[i])*u[i] for i in (0,1)))
        candidates=[fallback]
        for adv in (.45,.75,.95):
            for lat in (65.,160.):
                for sign in (-1,1):candidates.append((old[0]+adv*length*u[0]+sign*lat*v[0],old[1]+adv*length*u[1]+sign*lat*v[1]))
        hypotheses=self.visibility_hypotheses(ch)
        if not hypotheses:return fallback
        # Fixed quantile compression of the already observation-conditioned
        # position/orientation/range prior; no source or scenario access.
        cumulative=[];total=0.
        for h in hypotheses:total+=h[4];cumulative.append((total,h))
        hs=[next(h for cw,h in cumulative if cw>=total*(k+.5)/9.) for k in range(9)]
        def visible(h,q):
            s,n,lo,hi,_=h
            return _d._di_dist(s,q)<=(lo+hi)/2 and (n is None or sum(n[i]*(q[i]-s[i]) for i in (0,1))>=0)
        def aggregate(costs):return max(costs) if self.config.get('tree_error_risk','mean')=='max' else sum(costs)/len(costs)
        def leaf(P,p,h):
            c,r=_d._di_enclosing_circle(P);s=h[0]
            return _d._di_dist(p,c)/5.+5.+(0. if _d._di_dist(c,s)<=20 else 8.+_d._di_dist(c,s)/5.)
        def future(P,p,h,depth):
            c,r=_d._di_enclosing_circle(P);s=h[0]
            if depth<=0:return leaf(P,p,h)
            if r<=100:
                cost=_d._di_dist(p,c)/5.
                if _d._di_dist(c,s)<=20:return cost+5.
                cost+=3.
            else:cost=0.
            # After a failed clear, or an unresolved second-bearing region,
            # the parent takes a paid bearing at the current region center.
            q=c;cost+=_d._di_dist(p,q)/5. if r>100 else 0.
            cost+=6.
            if not visible(h,q):return cost+_d._di_dist(q,old)/5.+_d._di_dist(old,s)/5.+35.
            if _d._di_dist(q,s)<=5:return cost+5.
            angle=math.degrees(math.atan2(s[1]-q[1],s[0]-q[0]))
            options=[]
            for e in (-.8,0.,.8):
                P2=_d._di_add_bearing(P,q,angle+e)
                options.append(1000. if not P2 else future(P2,q,h,depth-1))
            return cost+aggregate(options)
        depth=int(self.config.get('tree_depth',2))
        def score(q):
            cost=_d._di_dist(self.position,q)/5.+6.;vals=[]
            for h in hs:
                s=h[0]
                if not visible(h,q):vals.append(_d._di_dist(q,old)/5.+_d._di_dist(old,s)/5.+35.);continue
                if _d._di_dist(q,s)<=5:vals.append(5.);continue
                angle=math.degrees(math.atan2(s[1]-q[1],s[0]-q[0]));outcomes=[]
                for e in (-.8,0.,.8):
                    P2=_d._di_add_bearing(poly,q,angle+e)
                    outcomes.append(1000. if not P2 else future(P2,q,h,depth-1))
                vals.append(aggregate(outcomes))
            return cost+sum(vals)/len(vals)
        q=min(candidates,key=lambda q:(score(q),q))
        self.counters['tree_decisions']=self.counters.get('tree_decisions',0)+1
        if _d._di_dist(q,fallback)>1e-8:self.counters['tree_changed_decisions']=self.counters.get('tree_changed_decisions',0)+1
        return q
class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        return _s1.Solver(env,mode=mode,**merged) if mode==3 else _Directional(env,mode=mode,**merged)
