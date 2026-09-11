# DRD-inspired task-value gates; finite hypotheses are planning only.
class _DecisionSpatial(_ActionSpatial):
    @staticmethod
    def _continuation_cost(poly,p):
        c,r=_sp_enclosing_circle(poly)
        travel=max(0.,_sp_dist(p,c)-max(0.,20.-r))/5.
        # One clear plus correction and another measurement if unresolved.
        # This intentionally simple proxy is not a theorem or empirical oracle.
        return travel+5.+(8.+max(0.,r-20.)/5. if r>20. else 0.)+(6. if r>100. else 0.)

    def _gate_prediction(self,ch,p):
        poly=self.polygons[ch];center,radius=_sp_enclosing_circle(poly)
        target=center  # Same one location hypothesis as parent visibility style.
        low=max([1000.]+[_sp_dist(target,q) for q,_ in self.observations[ch]])
        high=min([1500.]+[_sp_dist(target,q) for q in self.no_signal_points[ch]])
        if low>high+1e-6 or math.hypot(*target)>1800.+1e-6:
            return None
        dd=_sp_dist(target,p)
        if dd<=5.:
            return 1.,self._continuation_cost(poly,p)-11.
        receive=1. if dd<=low else 0. if dd>high else (high-dd)/max(1e-9,high-low)
        posterior_cost=0.;certificate=0.
        for error in (-.8,0.,.8):
            bearing=math.degrees(math.atan2(target[1]-p[1],target[0]-p[0]))+error
            posterior=_sp_add_bearing(poly,p,bearing)
            if posterior:
                _,rr=_sp_enclosing_circle(posterior)
                certificate+=float(rr<=20.)/3.
                posterior_cost+=self._continuation_cost(posterior,p)/3.
            else:
                posterior_cost+=self._continuation_cost(poly,p)/3.
        negative=_geo_outside_disk_hull(poly,p,1000.-1e-6)
        no_signal_cost=self._continuation_cost(negative or poly,p)
        net=self._continuation_cost(poly,p)-6.-(receive*posterior_cost+(1.-receive)*no_signal_cost)
        return receive*certificate,net

    def share_observations(self,exclude=None):
        gate=self.config.get('decision_gate','parent')
        if gate=='parent':
            return super().share_observations(exclude)
        if gate=='off' or self._sharing:
            return
        self._sharing=True
        try:
            p=self.position
            for ch in range(1,21):
                if self.virtual_time>=180000 or self._sharing_spent_s>=6000:
                    break
                if ch==exclude or ch in self.cleared or not self.observations[ch]:
                    continue
                if min(_sp_dist(p,old) for old,_ in self.observations[ch])<60:
                    continue
                poly=self.polygons[ch];center,radius=_sp_enclosing_circle(poly)
                if radius<=20 or _sp_dist(center,p)>1500+radius:
                    continue
                prediction=self._gate_prediction(ch,p)
                self.counters['decision_gate_evaluations']=self.counters.get('decision_gate_evaluations',0)+1
                if prediction is None:
                    self.counters['decision_gate_fallback']=self.counters.get('decision_gate_fallback',0)+1
                    bearing=math.degrees(math.atan2(center[1]-p[1],center[0]-p[0]))
                    posterior=_sp_add_bearing(poly,p,bearing)
                    value=max(0.,radius-_sp_enclosing_circle(posterior)[1]) if posterior else 0.
                    take=value>=self.config.get('sharing_gain_m',60.)
                else:
                    certificate,net=prediction
                    take=certificate>=2./3.-1e-9 if gate=='certificate' else net>0.
                if not take:
                    continue
                before=self.virtual_time
                self.counters['opportunity_measures']=self.counters.get('opportunity_measures',0)+1
                self.measure(p,ch)
                self._sharing_spent_s+=self.virtual_time-before
        finally:
            self._sharing=False

