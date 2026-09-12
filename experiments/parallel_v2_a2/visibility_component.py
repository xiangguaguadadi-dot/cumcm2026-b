# Exact integration over continuous emitter orientation conditional on point samples.
# Samples and probabilities only choose actions. No feasible-region constraints change.
class ContinuousVisibility(RotationDirectional):
    def _cv_distribution(self,ch):
        poly=self.polygons[ch]
        signature=(tuple(poly),tuple(self.observations[ch]),tuple(self.no_signal_points[ch]))
        cache=getattr(self,'_cv_cache',{}).get(ch)
        if cache and cache[0]==signature:return cache[1]
        center=(sum(p[0] for p in poly)/len(poly),sum(p[1] for p in poly)/len(poly))
        samples=[(center,1.)]+[((.75*p[0]+.25*center[0],.75*p[1]+.25*center[1]),1.) for p in poly]
        if self.config.get('cv_area',False):
            samples=[]
            for p,q in zip(poly,poly[1:]+poly[:1]):
                area=abs((p[0]-center[0])*(q[1]-center[1])-(p[1]-center[1])*(q[0]-center[0]))/2
                if area>1e-12:
                    for a,b,c in [(2/3,1/6,1/6),(1/6,2/3,1/6),(1/6,1/6,2/3)]:
                        samples.append(((a*center[0]+b*p[0]+c*q[0],a*center[1]+b*p[1]+c*q[1]),area/3))
        answer=[];tau=2*math.pi
        for s,spatial_weight in samples:
            if self.config.get('cv_failures',False) and any(math.dist(s,p)<=20 for p in self._e2_failed_clear[ch]):continue
            positives=[(p[0]-s[0],p[1]-s[1]) for p,_ in self.observations[ch]]
            negatives=[(p[0]-s[0],p[1]-s[1]) for p in self.no_signal_points[ch]]
            low=max([1000.]+[math.hypot(*v) for v in positives])
            if low>=1500:continue
            omni_upper=min([1500.]+[math.hypot(*v) for v in negatives])
            if omni_upper>low:answer.append((s,low,omni_upper,None,None,.5*spatial_weight*(omni_upper-low)))
            breaks={0.,tau}
            for x,y in positives+negatives:
                phi=math.atan2(y,x)
                breaks.update(((phi-math.pi/2)%tau,(phi+math.pi/2)%tau))
            angles=sorted(breaks)
            for a,b in zip(angles,angles[1:]):
                mid=(a+b)/2;co,si=math.cos(mid),math.sin(mid)
                if any(co*x+si*y < -1e-8 for x,y in positives):continue
                high=min([1500.]+[math.hypot(x,y) for x,y in negatives if co*x+si*y>=0])
                if high>low:answer.append((s,low,high,a,b,.5*spatial_weight*(high-low)*(b-a)/tau))
        if not hasattr(self,'_cv_cache'):self._cv_cache={}
        self._cv_cache[ch]=(signature,answer)
        return answer

    def predicted_visibility(self,ch,q):
        dist=self._cv_distribution(ch);total=sum(row[5] for row in dist)
        if total<=0:return super().predicted_visibility(ch,q)
        hit=0.;tau=2*math.pi
        for s,low,high,a,b,w in dist:
            dx,dy=q[0]-s[0],q[1]-s[1]
            radius=math.hypot(dx,dy)
            radial=max(0.,min(1.,(high-max(low,radius))/(high-low)))
            if not radial:continue
            frac=1.
            if a is not None:
                phi=math.atan2(dy,dx)%tau
                length=sum(max(0.,min(b,phi+math.pi/2+k*tau)-max(a,phi-math.pi/2+k*tau)) for k in (-1,0,1))
                frac=max(0.,min(1.,length/(b-a)))
            hit+=w*radial*frac
        return hit/total

    def visibility_hypotheses(self,ch):
        if not self.config.get('cv_optical',False):return super().visibility_hypotheses(ch)
        return [(s,None if a is None else (math.cos((a+b)/2),math.sin((a+b)/2)),low,high,w) for s,low,high,a,b,w in self._cv_distribution(ch)]
