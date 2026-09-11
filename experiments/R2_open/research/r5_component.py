def _decision_region_graphs(targets):
    """Finite surrogate: overlapping optical decision regions and colored EC2."""
    n=len(targets);actions=list(targets)
    actions.extend(((a[0]+b[0])/2.,(a[1]+b[1])/2.) for i,a in enumerate(targets) for b in targets[i+1:] if _sp_dist(a,b)<=40.)
    regions=sorted({sum((1<<j) for j,h in enumerate(targets) if _sp_dist(h,a)<=20.) for a in actions}-{0})
    assert all(any(r&(1<<j) for r in regions) for j in range(n))
    membership=[tuple(i for i,r in enumerate(regions) if r&(1<<j)) for j in range(n)]
    # A color combines nonoverlapping regions, as in DIRECt's reduced graph.
    degree=lambda i:sum(bool(regions[i]&r) for k,r in enumerate(regions) if i!=k)
    colors=[]
    for i in sorted(range(len(regions)),key=lambda i:(-degree(i),i)):
        for color in colors:
            if all(not(regions[i]&regions[k]) for k in color):
                color.append(i);break
        else:
            colors.append([i])
    graphs=[];seen=set()
    for color in colors:
        classes={}
        for j in range(n):
            covering=next((i for i in color if regions[i]&(1<<j)),None)
            label=('decision',covering) if covering is not None else ('outside',membership[j])
            classes[label]=classes.get(label,0)|(1<<j)
        partition=tuple(sorted(classes.values()))
        if partition in seen:
            continue
        seen.add(partition)
        denominator=n*n-sum(mask.bit_count()**2 for mask in partition)
        if not denominator:
            # One color already puts all finite hypotheses in a decision;
            # a continuous source certificate still requires the real polygon.
            return ()
        graphs.append((partition,denominator))
    return tuple(graphs)


def _decision_progress(graphs,survivors):
    if not survivors or not graphs:
        return None
    count=survivors.bit_count();remaining=1.
    for partition,denominator in graphs:
        numerator=count*count-sum((part&survivors).bit_count()**2 for part in partition)
        remaining*=max(0.,min(1.,numerator/denominator))
    return max(0.,min(1.,1.-remaining))


class _GraphSpatial(_LensSpatial):
    def _belief_plan(self,ch):
        poly=self.polygons[ch]
        key=(tuple(poly),tuple(self.observations[ch]),tuple(self.no_signal_points[ch]),tuple(self.failed_clear_points[ch]))
        cache=getattr(self,'_belief_plan_cache',None)
        if cache is None:
            self._belief_plan_cache={};cache=self._belief_plan_cache
        if ch in cache and cache[ch][0]==key:
            return cache[ch][1]
        targets=[];ranges=[]
        for h in self.planning_hypotheses(ch):
            low=max([1000.]+[_sp_dist(h,q) for q,_ in self.observations[ch]])
            high=min([1500.]+[_sp_dist(h,q) for q in self.no_signal_points[ch]])
            if low>high+1e-6 or math.hypot(*h)>1800.+1e-6 or any(_sp_dist(h,q)<20.-1e-6 for q in self.failed_clear_points[ch]):
                continue
            targets.append(h);ranges.append((low,high))
        plan=(targets,ranges,_decision_region_graphs(targets) if len(targets)>=2 else ())
        cache[ch]=(key,plan)
        return plan

    def _gate_prediction(self,ch,p):
        gate=self.config.get('belief_gate','parent')
        if gate=='parent':
            return super()._gate_prediction(ch,p)
        targets,ranges,graphs=self._belief_plan(ch)
        if len(targets)<2:
            self.counters['belief_fallbacks']=self.counters.get('belief_fallbacks',0)+1
            return super()._gate_prediction(ch,p)
        poly=self.polygons[ch];_,radius=_sp_enclosing_circle(poly)
        before=self._continuation_cost(poly,p)
        distances=[_sp_dist(h,p) for h in targets]
        bearings=[math.degrees(math.atan2(h[1]-p[1],h[0]-p[0])) for h in targets]
        near_mask=sum(1<<i for i,dd in enumerate(distances) if dd<=5.+1e-7)
        negative_mask=sum(1<<i for i,(dd,(low,high)) in enumerate(zip(distances,ranges)) if dd>low-1e-6)
        negative=_geo_outside_disk_hull(poly,p,1000.-1e-6)
        negative_cost=self._continuation_cost(negative or poly,p)
        future=0.;progress=0.;progress_valid=True
        for i,(target,(low,high)) in enumerate(zip(targets,ranges)):
            dd=distances[i]
            if dd<=5.:
                future+=5.
                value=_decision_progress(graphs,near_mask)
                if value is None:progress_valid=False
                else:progress+=value
                continue
            receive=1. if dd<=low else 0. if dd>high else (high-dd)/max(1e-9,high-low)
            direction_cost=0.;direction_progress=0.
            for error in (-.8,0.,.8):
                observed=bearings[i]+error
                posterior=_sp_add_bearing(poly,p,observed)
                direction_cost+=self._continuation_cost(posterior or poly,p)/3.
                mask=0
                for j,bearing in enumerate(bearings):
                    angle=abs((bearing-observed+180.)%360.-180.)
                    if distances[j]<=ranges[j][1]+1e-6 and angle<=math.degrees(_sp_EPS)+1e-7:
                        mask|=1<<j
                value=_decision_progress(graphs,mask)
                if value is None:progress_valid=False
                else:direction_progress+=value/3.
            future+=receive*direction_cost+(1.-receive)*negative_cost
            if receive<1.:
                value=_decision_progress(graphs,negative_mask)
                if value is None:progress_valid=False
                else:progress+=(1.-receive)*value
            progress+=receive*direction_progress
        n=len(targets);cost_net=before-6.-future/n
        self.counters['belief_evaluations']=self.counters.get('belief_evaluations',0)+1
        self.counters['belief_hypotheses_sum']=self.counters.get('belief_hypotheses_sum',0)+n
        if gate=='multi_cost' or not progress_valid:
            return 0.,cost_net
        expected_progress=progress/n
        # Convert dimensionless progress into a bounded-radius correction-cost
        # proxy. This heuristic price has no paper approximation guarantee.
        correction=8.+max(0.,radius-20.)/5.+(6. if radius>100. else 0.)
        net=expected_progress*correction-6.
        self.counters['graph_progress_sum']=self.counters.get('graph_progress_sum',0.)+expected_progress
        return 0.,net
