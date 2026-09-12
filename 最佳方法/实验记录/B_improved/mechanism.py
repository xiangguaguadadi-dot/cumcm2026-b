"""B route: polygon-adaptive measurement/clear lookahead, public observations only.

_P is the byte-for-byte embedded fusion_r5 parent, inserted by build_candidate.py.
The reliable feasible polygon and all clearing/discovery certificates stay in _P.
"""
import math
import heapq

_G = _P._Q3._Q3
_EPS = math.radians(1.005001)


def _wedge(poly, q, angle, half=_EPS):
    for a,b in ((math.sin(angle-half),-math.cos(angle-half)),
                (-math.sin(angle+half),math.cos(angle+half))):
        poly = _G._sp_clip(poly,a,b,a*q[0]+b*q[1])
    return poly


def _radius(poly):
    return _G._sp_enclosing_circle(poly)[1] if poly else 0.


def _future_radius_bound(poly,q,maxsplit=32):
    """Continuous future-bearing upper bound, no target/error distribution.

    Each reading interval is covered by its midpoint wedge widened by half the
    interval width. Its MEC bounds every actual posterior in that interval.
    Splitting the currently largest upper interval tightens a valid upper bound.
    Finite budget affects tightness, not the set inclusion construction.
    Floating-point geometry uses the parent's conservative tolerance.
    """
    center,_ = _G._sp_enclosing_circle(poly)
    ref = math.atan2(center[1]-q[1],center[0]-q[0])
    angles=[(math.atan2(p[1]-q[1],p[0]-q[0])-ref+math.pi)%(2*math.pi)-math.pi for p in poly]
    lo,hi=min(angles)-_EPS,max(angles)+_EPS
    if (hi-lo)/2+_EPS>=math.pi/2-1e-5:
        return _radius(poly),0.
    heap=[];serial=0;lower=0.
    def add(a,b):
        nonlocal serial,lower
        mid=(a+b)/2
        upper=_radius(_wedge(poly,q,ref+mid,_EPS+(b-a)/2))
        value=_radius(_wedge(poly,q,ref+mid))
        lower=max(lower,value)
        heapq.heappush(heap,(-upper,serial,a,b));serial+=1
    add(lo,hi)
    for _ in range(maxsplit):
        if -heap[0][0]<=lower+max(.25,.01*lower):break
        _,_,a,b=heapq.heappop(heap);mid=(a+b)/2
        add(a,mid);add(mid,b)
    return -heap[0][0],lower


class _Lookahead:
    def __init__(self,env,mode=3,**config):
        super().__init__(env,mode=mode,**config)
        self._b_cache={}

    def _b_proposals(self,ch,parent):
        poly=self.polygons[ch];p,deg=self.observations[ch][-1]
        center,_=_G._sp_enclosing_circle(poly)
        angle=math.radians(deg);u=(math.cos(angle),math.sin(angle));v=(-u[1],u[0])
        length=max(30.,sum((center[k]-p[k])*u[k] for k in (0,1)))
        out=[parent]
        # Different movement lengths are intentional: compare full future
        # task seconds rather than fixing the inherited baseline length.
        for advance in (.45,.75,1.0):
            for lateral in (60.,160.):
                for sign in (-1.,1.):
                    out.append((p[0]+advance*length*u[0]+sign*lateral*v[0],
                                p[1]+advance*length*u[1]+sign*lateral*v[1]))
        # A cheap short move toward the current route-local parent candidate.
        out.append(tuple(self.position[k]+.65*(parent[k]-self.position[k]) for k in (0,1)))
        return [q for i,q in enumerate(out) if not any(math.dist(q,old)<1e-5 for old in out[:i])
                and all(math.dist(q,old)>1. for old,_ in self.observations[ch])]

    def _b_expected_future(self,ch,q,targets):
        poly=self.polygons[ch];p,_=self.observations[ch][-1]
        cost=0.
        for t in targets:
            d=math.dist(q,t);old=math.dist(p,t)
            if d<=5.:
                cost+=5.;continue
            low=max(1000.,old)
            receive=1. if d<=low else max(0.,(1500.-d)/max(1e-9,1500.-low))
            if self.mode==4 and old>1e-8:
                cosine=sum((p[k]-t[k])*(q[k]-t[k]) for k in (0,1))/(d*old)
                # Conservative directional planning hypothesis, not a guarantee.
                receive*=1.-math.acos(max(-1.,min(1.,cosine)))/math.pi
            after=0.
            for error in (-_EPS,0.,_EPS):
                angle=math.atan2(t[1]-q[1],t[0]-q[0])+error
                posterior=_wedge(poly,q,angle)
                if not posterior:
                    after+=1000./3;continue
                c,r=_G._sp_enclosing_circle(posterior)
                move=max(0.,math.dist(q,c)-max(0.,20.-r))/5.
                value=move+5.
                if math.dist(c,t)>20.:
                    value+=8.+math.dist(c,t)/5.
                after+=value/3.
            lost=math.dist(q,p)/5.+35.+math.dist(p,t)/5.
            cost+=receive*after+(1.-receive)*lost
        return cost/len(targets)

    def second_point(self,ch):
        parent=super().second_point(ch)
        if len(self.observations[ch])!=1 or self.virtual_time>=180000.:
            return parent
        poly=self.polygons[ch]
        signature=(tuple(poly),tuple(self.observations[ch]),tuple(self.no_signal_points[ch]))
        old=self._b_cache.get(ch)
        if old is None or old[0]!=signature:
            targets=self.belief_quadrature(poly,9)
            self._b_cache[ch]=(signature,targets,{})
        _,targets,cache=self._b_cache[ch]
        def evaluate(q,need_bound=False):
            key=tuple(q)
            if key not in cache:
                cache[key]=[self._b_expected_future(ch,q,targets),
                            self.predicted_visibility(ch,q) if self.mode==4 else 1.,None]
            item=cache[key]
            if need_bound and item[2] is None:
                item[2]=_future_radius_bound(poly,q)
            return math.dist(self.position,q)/5.+5.+item[0],item[1],item[2]
        basecost,basevis,baserad=evaluate(parent,True)
        kept=[]
        for q in self._b_proposals(ch,parent):
            cost,vis,_=evaluate(q)
            # Q4 preserves the inherited probability-of-visibility planning
            # score. No omnidirectional reachability certificate is asserted.
            if cost>basecost+1e-8 or vis<basevis-1e-10:continue
            _,_,rad=evaluate(q,True)
            if rad[0]>baserad[0]+1e-8:continue
            kept.append((rad[0],cost,tuple(q)))
        best=min(kept)[2] if kept else parent
        self.counters['b_second_considered']=self.counters.get('b_second_considered',0)+1
        self.counters['b_second_changed']=self.counters.get('b_second_changed',0)+int(math.dist(best,parent)>1e-5)
        return best


class _Spatial(_Lookahead,_P._Q3.GuardedSpatial):pass
class _Directional(_Lookahead,_P._Q4.BiasLearningDirectional):pass

BASELINE_CONFIG=dict(_P.BASELINE_CONFIG)
OPTIMIZED_CONFIGS={mode:dict(cfg) for mode,cfg in _P.OPTIMIZED_CONFIGS.items()}

class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        return (_Spatial if mode==3 else _Directional)(env,mode=mode,**merged)
