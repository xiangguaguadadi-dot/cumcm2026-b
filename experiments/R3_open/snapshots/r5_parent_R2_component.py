def _lens_arc_intervals(vertex,poly,rr):
    """Feasible intervals on one circle boundary of an intersection of disks."""
    tau=2*math.pi;arcs=[(0.,tau)]
    for other in poly:
        dx,dy=other[0]-vertex[0],other[1]-vertex[1];d=math.hypot(dx,dy)
        if d<1e-10:
            continue
        if d>2*rr:
            return []
        phi=math.atan2(dy,dx);alpha=math.acos(max(-1.,min(1.,d/(2*rr))))
        lo=(phi-alpha)%tau;hi=lo+2*alpha
        parts=[(lo,hi)] if hi<=tau else [(lo,tau),(0.,hi-tau)]
        arcs=[(max(a,c),min(b,d)) for a,b in arcs for c,d in parts if max(a,c)<=min(b,d)+1e-12]
        if not arcs:
            return []
    return arcs


def _lens_route_point(poly,start,target,fallback):
    """Bounded boundary search in the all-vertex 20 m action region.

    Includes the old feasible action, so its fixed-state route proxy cannot
    worsen. An intersecting straight segment has the global shortest proxy.
    Otherwise a sampled/refined arc search is heuristic; feasibility is exact
    up to the explicit strict numerical margin and always checked afterwards.
    """
    rr=20.-1e-7
    feasible=lambda q:all(_sp_dist(q,v)<=rr+1e-9 for v in poly)
    if not poly or len(poly)>32:
        return fallback
    cost=lambda q:_sp_dist(start,q)+(_sp_dist(q,target) if target is not None else 0.)
    choices=[fallback]
    if feasible(start):
        return start
    if target is not None:
        vx,vy=target[0]-start[0],target[1]-start[1];aa=vx*vx+vy*vy
        low,high=0.,1.
        if aa>1e-16:
            for v in poly:
                dx,dy=start[0]-v[0],start[1]-v[1]
                bb=2*(dx*vx+dy*vy);cc=dx*dx+dy*dy-rr*rr
                discriminant=bb*bb-4*aa*cc
                if discriminant<0:
                    low,high=1.,0.;break
                root=math.sqrt(discriminant)
                low=max(low,(-bb-root)/(2*aa));high=min(high,(-bb+root)/(2*aa))
                if low>high:
                    break
            if low<=high:
                q=(start[0]+low*vx,start[1]+low*vy)
                if feasible(q):
                    return q
    for v in poly:
        point=lambda a:(v[0]+rr*math.cos(a),v[1]+rr*math.sin(a))
        for lo,hi in _lens_arc_intervals(v,poly,rr):
            if hi<lo:
                continue
            width=hi-lo
            samples=[lo+width*i/16 for i in range(17)]
            values=[cost(point(a)) for a in samples]
            choices.extend([point(lo),point(hi)])
            # Search around every sampled local minimum, retaining endpoints.
            indices=[i for i in range(1,16) if values[i]<=values[i-1] and values[i]<=values[i+1]]
            indices=indices or [min(range(17),key=values.__getitem__)]
            for i in indices:
                left,right=samples[max(0,i-1)],samples[min(16,i+1)]
                golden=(math.sqrt(5)-1)/2
                a=right-golden*(right-left);b=left+golden*(right-left)
                fa,fb=cost(point(a)),cost(point(b))
                for _ in range(28):
                    if fa<=fb:
                        right,b,fb=b,a,fa;a=right-golden*(right-left);fa=cost(point(a))
                    else:
                        left,a,fa=a,b,fb;b=left+golden*(right-left);fb=cost(point(b))
                choices.extend([point(a),point(b)])
    valid=[q for q in choices if q==fallback or feasible(q)]
    return min(valid,key=lambda q:(cost(q),q))


class _LensSpatial(_DecisionSpatial):
    def route_clear_point(self,center,radius,original):
        fallback=super().route_clear_point(center,radius,original)
        style=self.config.get('lens_clear','parent')
        ch=self._active_target
        if style=='parent' or ch is None or radius>20:
            return fallback
        poly=self.polygons[ch]
        self.counters['lens_calls']=self.counters.get('lens_calls',0)+1
        if style=='nearest':
            q=self.nearest_certified_clear(poly,center,radius)
        else:
            target=getattr(self,'route_successor',None)
            q=_lens_route_point(poly,self.position,target,fallback)
            cost=lambda q:_sp_dist(self.position,q)+(_sp_dist(q,target) if target is not None else 0.)
            gain=cost(fallback)-cost(q)
            self.counters['lens_proxy_saved_m']=self.counters.get('lens_proxy_saved_m',0.)+gain
            assert gain>=-1e-7
        if max(_sp_dist(q,v) for v in poly)>20.+1e-8:
            raise RuntimeError('Lens action failed all-vertex containment check')
        return q
