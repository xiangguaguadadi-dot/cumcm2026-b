# R2: A2 action-cost second point plus same-location certified clear.
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

    def belief_quadrature(self,poly,count=9):
        """Deterministic area-uniform quadrature, used only to rank actions.

        Samples are hypotheses inside the bounded-error polygon, never true
        source coordinates. They do not participate in correctness certificates.
        """
        center=(sum(p[0] for p in poly)/len(poly),sum(p[1] for p in poly)/len(poly))
        triangles=[];total=0.0
        for a,b in zip(poly,poly[1:]+poly[:1]):
            area=abs((a[0]-center[0])*(b[1]-center[1])-(a[1]-center[1])*(b[0]-center[0]))/2
            if area>1e-12:
                total+=area;triangles.append((total,a,b))
        if not triangles:
            return [center]
        samples=[]
        for k in range(count):
            area=total*(k+.5)/count
            _,a,b=next(t for t in triangles if t[0]>=area)
            # Irrational rotations decorrelate radial and angular coordinates.
            rr=math.sqrt(((k+.5)*0.618033988749895)%1)
            v=((k+.5)*0.414213562373095)%1
            samples.append(((1-rr)*center[0]+rr*((1-v)*a[0]+v*b[0]),
                            (1-rr)*center[1]+rr*((1-v)*a[1]+v*b[1])))
        return samples

    def planning_hypotheses(self,ch):
        """Rank with observation-consistent hypotheses, not outer-hull holes.

        Filtering never changes the authoritative polygon or any certificate.
        A finite empty proposal set is a sampling failure, not source absence.
        """
        poly=self.polygons[ch]
        original=self.belief_quadrature(poly)
        def consistent(target):
            if math.hypot(*target)>1800+1e-6:
                return False
            if any(_sp_dist(target,p)>1500+1e-6 for p,_ in self.observations[ch]):
                return False
            if self.mode==3 and any(_sp_dist(target,p)<1000-1e-6 for p in self.no_signal_points[ch]):
                return False
            return True
        if all(consistent(t) for t in original):
            return original
        proposals=[t for t in self.belief_quadrature(poly,81) if consistent(t)]
        if not proposals:
            return original
        n=min(9,len(proposals))
        return [proposals[min(len(proposals)-1,int((i+.5)*len(proposals)/n))] for i in range(n)]

    def predicted_polygon(self,poly,q,deg):
        # The full retained polygon remains authoritative. The two half-plane
        # prediction is only a cheap planning surrogate and never updates it.
        lo,hi=math.radians(deg)-_sp_EPS,math.radians(deg)+_sp_EPS
        for a,b in [(math.sin(lo),-math.cos(lo)),(-math.sin(hi),math.cos(hi))]:
            poly=_sp_clip(poly,a,b,a*q[0]+b*q[1])
        return poly

    def second_point(self,ch):
        if not self.config.get('active_information',self.mode==3):
            return self._parent_second_point(ch)
        poly=self.polygons[ch];p,deg=self.observations[ch][-1]
        center,radius=_sp_enclosing_circle(poly)
        theta=math.radians(deg);u=(math.cos(theta),math.sin(theta));v=(-u[1],u[0])
        length=max(30,(center[0]-p[0])*u[0]+(center[1]-p[1])*u[1])
        candidates=[self._parent_second_point(ch)]
        for advance in (.35,.65,.95):
            for lateral in (45.,100.,175.):
                for sign in (-1,1):
                    candidates.append((p[0]+advance*length*u[0]+sign*lateral*v[0],
                                       p[1]+advance*length*u[1]+sign*lateral*v[1]))
        targets=self.planning_hypotheses(ch)
        def score(q):
            future=0.0
            for target in targets:
                dd=_sp_dist(q,target)
                if dd>1500:
                    future+=_sp_dist(q,p)/5+35+_sp_dist(p,target)/5
                    continue
                observed_cost=0.0
                for error in (-.8,0.,.8):
                    bearing=math.degrees(math.atan2(target[1]-q[1],target[0]-q[0]))+error
                    posterior=self.predicted_polygon(poly,q,bearing)
                    if not posterior:
                        observed_cost+=1000.0/3
                        continue
                    c,r=_sp_enclosing_circle(posterior)
                    # Predict one clear, then the cost of correcting a failed
                    # point estimate. All quantities are virtual seconds.
                    cost=_sp_dist(q,c)/5+5
                    if _sp_dist(c,target)>20:
                        cost+=8+_sp_dist(c,target)/5
                    observed_cost+=cost/3
                if self.mode==4:
                    # Planning prior, not a guarantee: condition unknown receive
                    # radius on the old visible position and conservatively use
                    # an unknown directional half-plane for every source.
                    old_distance=_sp_dist(p,target)
                    low=max(1000.0,old_distance)
                    receive=1.0 if dd<=low else max(0.0,(1500.0-dd)/max(1e-9,1500.0-low))
                    if dd>1e-8 and old_distance>1e-8:
                        cosine=((p[0]-target[0])*(q[0]-target[0])+(p[1]-target[1])*(q[1]-target[1]))/(dd*old_distance)
                        receive*=1-math.acos(max(-1.,min(1.,cosine)))/math.pi
                    loss_cost=_sp_dist(q,p)/5+_sp_dist(p,target)/5+25.0
                    future+=receive*observed_cost+(1-receive)*loss_cost
                else:
                    future+=observed_cost
            return _sp_dist(self.position,q)/5+5+future/len(targets)
        return min(candidates,key=lambda q:(score(q),q))

