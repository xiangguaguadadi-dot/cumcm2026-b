"""Q4 observation-only angular residual proposal, never a certificate.

R1 selects iteratively reweighted bearing-line least squares. R2/R3 may
use a fitted cost-sensitive gate. Only unproved center clear actions change;
the original polygon, coverage certificate and finite fallback are retained.
"""
_A3_TRAIN_HOOK = None  # Evaluator may observe detached public features.

def _a3_inside(poly,q):
    signs=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        z=(b[0]-a[0])*(q[1]-a[1])-(b[1]-a[1])*(q[0]-a[0])
        if abs(z)>1e-6:signs.append(z>0)
    return not signs or all(s==signs[0] for s in signs)

def _a3_estimate(obs,center,poly):
    q=center
    for _ in range(5):
        aa=ab=bb=ay=by=0.
        for p,degree in obs:
            angle=math.radians(degree);a=-math.sin(angle);b=math.cos(angle)
            weight=1./max(25.**2,math.dist(p,q)**2)
            rhs=a*p[0]+b*p[1]
            aa+=weight*a*a;ab+=weight*a*b;bb+=weight*b*b
            ay+=weight*a*rhs;by+=weight*b*rhs
        det=aa*bb-ab*ab
        if det<=1e-10*max(1e-20,aa*bb):return center
        proposed=((bb*ay-ab*by)/det,(aa*by-ab*ay)/det)
        if not all(math.isfinite(x) for x in proposed):return center
        if not _a3_inside(poly,proposed):
            # A line estimator is a planning proxy. Keep the proposal in the
            # reliable set by convex interpolation; never shrink that set.
            alpha=1.
            for _ in range(20):
                alpha*=.5
                proposed=(q[0]+alpha*(proposed[0]-q[0]),q[1]+alpha*(proposed[1]-q[1]))
                if _a3_inside(poly,proposed):break
            if not _a3_inside(poly,proposed):return center
        if math.dist(q,proposed)<1e-4:return proposed
        q=proposed
    return q

def _a3_features(s,ch,center,radius,proposal):
    obs=s.observations[ch]
    differences=[]
    for p,d in obs:
        angle=math.degrees(math.atan2(center[1]-p[1],center[0]-p[0]))
        differences.append((angle-d+180.)%360.-180.)
    cross=max((abs(math.sin(math.radians(a[1]-b[1])))
        for a in obs for b in obs),default=0.)
    shift=math.dist(center,proposal)
    move_delta=(math.dist(s.position,center)-math.dist(s.position,proposal))/5.
    f=[1.,min(len(obs),16)/8.,radius/100.,shift/20.,move_delta/5.,
       cross,min(math.dist(s.position,center),2000)/1000.,
       sum(differences)/len(differences),sum(x*x for x in differences)/len(differences),
       min(len(s.no_signal_points[ch]),20)/10.,
       min(len(s._e2_failed_clear[ch]),10)/5.,
       radius*cross/100.,shift*cross/20.,radius*shift/2000.,
       min(math.dist(obs[-1][0],center),2000)/1000.]
    return f

class ObservationResidualDirectional(_A3_ORIGINAL_Q4):
    def __init__(self,env,mode=4,**config):
        super().__init__(env,mode=mode,**config)
        self._a3_redirect=None
        self._a3_cover_depth=0
        self.a3_public_decisions=[]

    def cover_polygon(self,ch):
        self._a3_cover_depth+=1
        self._a3_redirect=None
        try:return super().cover_polygon(ch)
        finally:self._a3_cover_depth-=1

    def clear(self,p,ch,certified=False):
        self._a3_redirect=None
        if self._a3_cover_depth or getattr(self,"_protected_clear_plan",False):
            return super().clear(p,ch,certified=certified)
        if not certified and ch==self._active_target and len(self.observations[ch])>=2:
            center,radius=_C7._Q4._di_enclosing_circle(self.polygons[ch])
            if 20.<radius<=100. and math.dist(p,center)<1e-4:
                proposal=_a3_estimate(self.observations[ch],center,self.polygons[ch])
                f=_a3_features(self,ch,center,radius,proposal)
                if _A3_TRAIN_HOOK is not None:
                    _A3_TRAIN_HOOK({'features':f,'channel':ch,'center':center,'proposal':proposal,
                        'position':self.position,'radius':radius,'virtual_time_s':self.virtual_time})
                style=self.config.get('a3_style','wls')
                gain=sum(a*b for a,b in zip(f,self.config.get('a3_weights',[0.]*len(f))))
                take=style=='wls' or (style=='learned' and gain>self.config.get('a3_threshold',0.))
                if math.dist(proposal,center)>1e-4:
                    self.counters['a3_eligible']=self.counters.get('a3_eligible',0)+1
                if take and math.dist(proposal,center)>1e-4:
                    self.counters['a3_residual_actions']=self.counters.get('a3_residual_actions',0)+1
                    original=tuple(p);p=proposal
                    self._a3_redirect=(ch,original,p)
        return super().clear(p,ch,certified=certified)

    def measure(self,p,ch):
        redirect=self._a3_redirect
        self._a3_redirect=None
        if not self._a3_cover_depth and not getattr(self,"_protected_clear_plan",False) and redirect and redirect[0]==ch and math.dist(p,redirect[1])<1e-5:
            # The parent follows a failed trial with a paid measurement at
            # that same trial point. Preserve this physical action relation.
            p=redirect[2]
        return super().measure(p,ch)

OPTIMIZED_CONFIGS[4].update(a3_style='wls')
class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        return _A3_Q3.Solver(env,mode=3,**merged) if mode==3 else ObservationResidualDirectional(env,mode=4,**merged)
