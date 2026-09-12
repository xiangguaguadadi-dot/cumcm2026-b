"""Empirical Bayes shared-angle-bias planning, with unchanged certificates.

Successful clear reports only a 20 m disk (near reports 5 m). Per-channel
likelihoods optimize positions inside that disk intersected with the retained
bearing polygon. A shared bias is an online planning hypothesis, never a
replacement for the official +/-1 degree bound or a source-location fact.
"""
def _eb_project(poly,q):
    if _a3_inside(poly,q):return q
    candidates=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        v=(b[0]-a[0],b[1]-a[1]);d=v[0]*v[0]+v[1]*v[1]
        t=max(0.,min(1.,((q[0]-a[0])*v[0]+(q[1]-a[1])*v[1])/d)) if d>1e-20 else 0.
        candidates.append((a[0]+t*v[0],a[1]+t*v[1]))
    return min(candidates,key=lambda p:math.dist(p,q))

def _eb_location(obs,poly,bias):
    q=(sum(p[0] for p in poly)/len(poly),sum(p[1] for p in poly)/len(poly))
    for _ in range(5):
        aa=ab=bb=ay=by=0.
        for p,degree in obs:
            angle=math.radians(degree-bias);a=-math.sin(angle);b=math.cos(angle)
            w=1./max(25.**2,math.dist(p,q)**2);rhs=a*p[0]+b*p[1]
            aa+=w*a*a;ab+=w*a*b;bb+=w*b*b;ay+=w*a*rhs;by+=w*b*rhs
        det=aa*bb-ab*ab
        if det<=1e-10*max(1e-20,aa*bb):break
        target=((bb*ay-ab*by)/det,(aa*by-ab*ay)/det)
        if not all(math.isfinite(x) for x in target):break
        target=_eb_project(poly,target)
        if math.dist(target,q)<1e-5:q=target;break
        q=target
    return q

def _eb_cost(obs,q,bias):
    errors=[(math.degrees(math.atan2(q[1]-p[1],q[0]-p[0]))-(d-bias)+180.)%360.-180.
        for p,d in obs if math.dist(p,q)>5.]
    return sum(min(e*e,4.) for e in errors)/len(errors) if errors else 0.

class BiasLearningDirectional(_A3_ORIGINAL_Q4):
    def __init__(self,env,mode=4,**config):
        super().__init__(env,mode=mode,**config)
        self._eb_grid=[-1.+i*.1 for i in range(21)]
        self._eb_losses=[0.]*21;self._eb_channels=set();self._eb_redirect=None
        self._eb_log_independent_evidence=0.
        self.eb_diagnostics=[]

    def _eb_learn(self,ch,point,near):
        obs=self.observations[ch]
        if ch in self._eb_channels or len(obs)<3 or ch not in self.polygons:return
        poly=self.polygons[ch][:];rr=5. if near else 20.
        for k in range(32):
            a=math.cos(2*math.pi*k/32);b=math.sin(2*math.pi*k/32)
            poly=_C7._Q4._di_clip(poly,a,b,a*point[0]+b*point[1]+rr+1e-6)
        if not poly:return
        losses=[_eb_cost(obs,_eb_location(obs,poly,bias),bias) for bias in self._eb_grid]
        floor=min(losses)
        if max(losses)-floor<.02:return
        self._eb_channels.add(ch)
        sigma=self.config.get('eb_sigma',.35)
        increment=[min(8.,(loss-floor)*min(8,len(obs))/(2*sigma*sigma)) for loss in losses]
        # Equal-prior contamination mixture: a calibrated channel may be
        # unrelated to the global shared bias. This bounds its influence.
        increment=[-math.log(.5+.5*math.exp(-v)) for v in increment]
        self._eb_log_independent_evidence+=math.log(sum(math.exp(-v) for v in increment)/len(increment))
        self._eb_losses=[old+value for old,value in zip(self._eb_losses,increment)]
        self.counters['eb_calibrated_channels']=len(self._eb_channels)
        self.eb_diagnostics.append(dict(channel=ch,observations=len(obs),success_radius=rr,
            bias_grid=self._eb_grid,local_losses=losses))

    def _eb_bias(self):
        if len(self._eb_channels)<self.config.get('eb_min_channels',2):return None
        floor=min(self._eb_losses);w=[math.exp(-(v-floor)) for v in self._eb_losses];total=sum(w)
        log_bayes_factor=math.log(total/len(w))-floor-self._eb_log_independent_evidence
        if log_bayes_factor<self.config.get('eb_min_log_bayes_factor',-1e9):return None
        mean=sum(x*p for x,p in zip(self._eb_grid,w))/total
        sd=math.sqrt(sum((x-mean)**2*p for x,p in zip(self._eb_grid,w))/total)
        if abs(mean)<self.config.get('eb_min_bias',.5) or sd>self.config.get('eb_max_sd',.25):return None
        if self.config.get('eb_bias_estimator','mean')=='map':mean=self._eb_grid[min(range(len(w)),key=lambda i:self._eb_losses[i])]
        self.counters['eb_last_bias_millideg']=round(mean*1000)
        return mean

    def _eb_predictive_location(self,ch,center,bias):
        floor=min(self._eb_losses)
        weights=[math.exp(-(v-floor)) for v in self._eb_losses]
        total=sum(weights);weights=[w/total for w in weights]
        atoms=[_eb_location(self.observations[ch],self.polygons[ch],b) for b in self._eb_grid]
        mean=(sum(w*q[0] for w,q in zip(weights,atoms)),sum(w*q[1] for w,q in zip(weights,atoms)))
        plugin=_eb_location(self.observations[ch],self.polygons[ch],bias)
        candidates=[tuple(center),plugin,mean,*atoms]
        # Profile-location atoms are a planning approximation. We maximize
        # their 20 m optical mass, tie-breaking by actual next movement.
        # This does not alter the reliable polygon or certify any clear.
        return min(candidates,key=lambda q:(
            -sum(w for w,a in zip(weights,atoms) if math.dist(q,a)<=20.),
            math.dist(self.position,q)))

    def clear(self,p,ch,certified=False):
        self._eb_redirect=None
        near=bool(self.trace and self.trace[-1].get('action')=='measure' and
            self.trace[-1].get('result')=='near' and self.trace[-1].get('channel')==ch)
        bias=self._eb_bias()
        if bias is not None and not certified and ch==self._active_target and len(self.observations[ch])>=2:
            center,radius=_C7._Q4._di_enclosing_circle(self.polygons[ch])
            if 20.<radius<=100. and math.dist(p,center)<1e-4:
                q=self._eb_predictive_location(ch,p,bias)
                if math.dist(q,p)>1e-4:
                    self._eb_redirect=(ch,tuple(p),q);p=q
                    self.counters['eb_adjusted_clears']=self.counters.get('eb_adjusted_clears',0)+1
        ok=super().clear(p,ch,certified=certified)
        if ok:self._eb_learn(ch,tuple(p),near)
        return ok

    def measure(self,p,ch):
        redirect=self._eb_redirect;self._eb_redirect=None
        if redirect and redirect[0]==ch and math.dist(p,redirect[1])<1e-5:p=redirect[2]
        return super().measure(p,ch)

OPTIMIZED_CONFIGS[4].update(eb_sigma=.35,eb_min_channels=2,eb_min_bias=.5,eb_max_sd=.25)
class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        return _A3_Q3.Solver(env,mode=3,**merged) if mode==3 else BiasLearningDirectional(env,mode=4,**merged)
