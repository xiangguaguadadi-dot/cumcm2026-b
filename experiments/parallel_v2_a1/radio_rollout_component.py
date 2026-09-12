"""Conservative optical gating against a one-bearing geometric continuation."""
_RADIO_ROLLOUT_PARENT=Solver

class RadioRolloutSpatial(GuardedSpatial):
    def _radio_rollout_gate(self,ch,plan):
        if plan is None:return None
        poly=self.polygons[ch];center,radius=_Q3._sp_enclosing_circle(poly)
        trial=self.trial_point(ch,center,radius)
        key=(ch,tuple(poly),self.position,self.channel,trial,tuple(self.failed_clear_points[ch]))
        cached=getattr(self,'_radio_rollout_cache',None)
        if cached and cached[0]==key:
            targets,radio=cached[1:]
        else:
            targets=self.belief_quadrature(poly,27)
            good=[t for t in targets if all(math.dist(t,q)>20.-1e-6 for q in self.failed_clear_points[ch])]
            if good:targets=good
            radio=math.dist(self.position,trial)/5.+3.
            future=0.
            for target in targets:
                if math.dist(target,trial)<=20.:
                    future+=2.;continue
                branch=0.
                failures=_Q3._geo_outside_disk_hull(poly,trial,20.-1e-6) or poly
                for error in (-.8,0.,.8):
                    old=next((deg for q,deg in self.observations[ch] if math.dist(q,trial)<1e-5),None)
                    bearing=old if old is not None else math.degrees(math.atan2(target[1]-trial[1],target[0]-trial[0]))+error
                    posterior=self.predicted_polygon(failures,trial,bearing)
                    if not posterior:
                        branch+=11.+math.dist(trial,target)/5.;continue
                    c,r=_Q3._sp_enclosing_circle(posterior)
                    distance=math.dist(trial,c)
                    cost=5.+float(self.channel!=ch)+max(0.,distance-max(0.,20.-r))/5.+5.
                    if math.dist(c,target)>20.:cost+=8.+math.dist(c,target)/5.
                    branch+=cost
                future+=branch/3.
            radio+=future/len(targets)
            self._radio_rollout_cache=(key,targets,radio)
        optical=self._sequence_cost(self.position,plan,targets)
        return plan if optical<radio else None

    def _two_disk_plan(self,ch):
        return self._radio_rollout_gate(ch,super()._two_disk_plan(ch))

    def _three_disk_plan(self,ch):
        return self._radio_rollout_gate(ch,super()._three_disk_plan(ch))

class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        if mode==3:return RadioRolloutSpatial(env,mode=mode,**merged)
        return _RADIO_ROLLOUT_PARENT(env,mode=mode,**merged)
