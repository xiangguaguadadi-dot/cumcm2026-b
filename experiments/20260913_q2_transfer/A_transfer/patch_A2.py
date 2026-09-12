"""Q2 transfer A2: same-baseline minimax accuracy without downstream cost gate.

Only public retained polygons, bearing observations, current position and the
parent's directional visibility planning model are used. No search coverage,
posterior update, optical certificate, clearing action or rescue is changed.
Finite bearing quadrature ranks points; it is never a correctness certificate.
"""
import math

_Q2A_EPS=math.radians(1.005001)
_Q2A_BASE_SOLVER=Solver

def _q2a_clip(poly,a,b,c):
    if not poly:return []
    out=[];p=poly[-1];fp=a*p[0]+b*p[1]-c
    for q in poly:
        fq=a*q[0]+b*q[1]-c
        if (fp<=1e-8)!=(fq<=1e-8):
            t=fp/(fp-fq);out.append((p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])))
        if fq<=1e-8:out.append(q)
        p,fp=q,fq
    return out

def _q2a_circle(poly):
    # Parent implementation returns a verified enclosing radius, not D/2.
    return _Q3._Q3._sp_enclosing_circle(poly)

def _q2a_posterior(poly,q,z):
    lo=z-_Q2A_EPS;hi=z+_Q2A_EPS
    for a,b in ((math.sin(lo),-math.cos(lo)),(-math.sin(hi),math.cos(hi))):
        poly=_q2a_clip(poly,a,b,a*q[0]+b*q[1])
    # Normal reports exclude r<=5; this chord is a conservative outer hull.
    a,b=-math.cos(z),-math.sin(z)
    return _q2a_clip(poly,a,b,a*q[0]+b*q[1]-5*math.cos(_Q2A_EPS))

def _q2a_worst_radius(poly,q,count=80):
    center,_=_q2a_circle(poly)
    ref=math.atan2(center[1]-q[1],center[0]-q[0])
    angles=[ref+math.remainder(math.atan2(p[1]-q[1],p[0]-q[0])-ref,2*math.pi) for p in poly]
    lo,hi=min(angles)-_Q2A_EPS,max(angles)+_Q2A_EPS
    if hi-lo>math.pi+2*_Q2A_EPS:lo,hi=ref-math.pi,ref+math.pi
    zs=[lo+(hi-lo)*i/count for i in range(count+1)]
    zs += [a+e for a in angles for e in (-_Q2A_EPS,_Q2A_EPS)]
    worst=0.
    for z in zs:
        post=_q2a_posterior(poly,q,z)
        if post:worst=max(worst,_q2a_circle(post)[1])
    return worst

class _Q2ATransfer:
    def second_point(self,ch):
        old=super().second_point(ch)
        self.counters['q2a_calls']=self.counters.get('q2a_calls',0)+1
        if len(self.observations[ch])!=1:return old
        poly=self.polygons[ch]
        center,radius=_q2a_circle(poly)
        if radius<=100.:return old
        p,deg=self.observations[ch][0]
        b=math.dist(p,old)
        # Short baselines already serve local refinement; the Q2 full-sector
        # calculation is not transplanted into near-field/degenerate steps.
        if b<60. or b>1000.:return old
        u=(math.cos(math.radians(deg)),math.sin(math.radians(deg)))
        v=(-u[1],u[0])
        dx,dy=old[0]-p[0],old[1]-p[1]
        oldangle=abs(math.atan2(dx*v[0]+dy*v[1],dx*u[0]+dy*u[1]))
        # The real target-circle and prior no-signal clipping inform L.
        length=min(1500.,max(math.dist(p,g) for g in poly))
        if length<max(100.,b*.55):return old
        co=max(-1.,min(1.,3*length*b*math.cos(_Q2A_EPS)/(2*length*length+b*b)))
        analytic=min(math.acos(co),math.acos(b/2000.)-_Q2A_EPS)
        if analytic<=0.:return old
        angles=(analytic,(analytic+oldangle)/2)
        incoming=math.dist(self.position,old)
        old_route=incoming+math.dist(old,center)
        old_visibility=self.predicted_visibility(ch,old) if self.mode==4 else 1.
        candidates=[]
        for a in angles:
            for sign in (-1.,1.):
                x=b*math.cos(a);y=sign*b*math.sin(a)
                q=(p[0]+x*u[0]+y*v[0],p[1]+x*u[1]+y*v[1])
                if math.dist(q,self.position)>incoming+1e-6:continue
                # These are range-safe Q2 candidates. For mode 4 this says
                # nothing about unknown emission half-plane visibility.
                if x*x+y*y>2000*(x*math.cos(_Q2A_EPS)-abs(y)*math.sin(_Q2A_EPS))+1e-6:continue
                visibility=self.predicted_visibility(ch,q) if self.mode==4 else 1.
                if self.mode==4 and visibility<old_visibility-.01:continue
                route=math.dist(self.position,q)+math.dist(q,center)
                candidates.append((q,visibility,route))
        if not candidates:return old
        old_r=_q2a_worst_radius(poly,old)
        best=old;best_r=old_r
        for q,visibility,route in candidates:
            r=_q2a_worst_radius(poly,q)
            self.counters['q2a_geometry_evals']=self.counters.get('q2a_geometry_evals',0)+1
            if r>=old_r*.97:continue
            # Mechanism ablation: after the unchanged movement and Q4
            # visibility gates, choose only by bounded-error localization.
            # This deliberately tests whether better precision itself helps
            # the existing full task; no downstream time benefit is asserted.
            if r<best_r-1e-8:
                best,best_r=q,r
        if best!=old:
            self.counters['q2a_selected']=self.counters.get('q2a_selected',0)+1
            self.counters['q2a_radius_reduction_m']=self.counters.get('q2a_radius_reduction_m',0.)+old_r-best_r
            self.counters['q2a_incoming_saved_m']=self.counters.get('q2a_incoming_saved_m',0.)+incoming-math.dist(self.position,best)
        return best

class _Q2ASpatial(_Q2ATransfer,_Q3.GuardedSpatial):pass
class _Q2ADirectional(_Q2ATransfer,_Q4.BiasLearningDirectional):pass

class Solver:
    def __new__(cls,env,mode=3,**config):
        if mode not in (3,4):raise ValueError('mode must be 3 or 4')
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        return (_Q2ASpatial if mode==3 else _Q2ADirectional)(env,mode=mode,**merged)
