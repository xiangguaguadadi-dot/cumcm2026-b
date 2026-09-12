"""Optical trial decision geometry. Samples rank actions; they never certify."""
_TRIAL_PARENT = Solver
TRIAL_VARIANT = 1

class TrialSpatial(A1ServiceSpatial):
    @staticmethod
    def _area_centroid(poly):
        a=0.;x=0.;y=0.
        for p,q in zip(poly,poly[1:]+poly[:1]):
            z=p[0]*q[1]-q[0]*p[1];a+=z;x+=(p[0]+q[0])*z;y+=(p[1]+q[1])*z
        if abs(a)<1e-8:return (sum(p[0] for p in poly)/len(poly),sum(p[1] for p in poly)/len(poly))
        return (x/(3*a),y/(3*a))

    def trial_point(self,ch,center,radius):
        poly=self.polygons[ch]
        centroid=self._area_centroid(poly)
        self.counters['trial_geometry_considered']=self.counters.get('trial_geometry_considered',0)+1
        if TRIAL_VARIANT==1:
            q=centroid
        else:
            targets=self.belief_quadrature(poly,81)
            def consistent(t):
                return (math.hypot(*t)<=1800+1e-6 and
                        all(math.dist(t,p)<=1500+1e-6 for p,_ in self.observations[ch]) and
                        all(math.dist(t,p)>=1000-1e-6 for p in self.no_signal_points[ch]) and
                        all(math.dist(t,p)>20-1e-6 for p in self.failed_clear_points[ch]))
            filtered=[t for t in targets if consistent(t)]
            if filtered:targets=filtered
            candidates=[center,centroid,self.position]+targets[::max(1,len(targets)//18)]
            # Pairwise circle-boundary candidates improve discrete 20 m coverage.
            for t in targets[::max(1,len(targets)//12)]:
                local=[v for v in targets if math.dist(t,v)<=20.]
                if local:candidates.append((sum(v[0] for v in local)/len(local),sum(v[1] for v in local)/len(local)))
            def score(q):
                total=math.dist(self.position,q)/5.+3.
                continuation=0.
                for t in targets:
                    d=math.dist(t,q)
                    if d<=20.:continuation+=2.
                    else:continuation+=11.+d/5.
                total+=continuation/len(targets)
                return total
            q=min(candidates,key=lambda q:(score(q),math.dist(q,center),q))
        self.counters['trial_geometry_shifted']=self.counters.get('trial_geometry_shifted',0)+int(math.dist(q,center)>1e-6)
        return q
