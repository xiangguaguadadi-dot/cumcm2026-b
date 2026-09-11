
# R2: the source-service unit changes; all source state is actual API history.
_FrozenR1Solver=Solver
class ServiceDirectional(CostDirectional):
    def __init__(self,env,mode=4,**config):
        super().__init__(env,mode=mode,**config)
        self._e2_servicing=False
        self._e2_progress={}

    def _e2_clear_here(self,exclude=None):
        if not self.config.get('e2_same_here',False) or self._e2_servicing:return
        self._e2_servicing=True
        try:
            p=self.position
            for ch in range(1,21):
                if ch==exclude or ch in self.cleared or ch not in self.polygons:continue
                if all(math.dist(p,v)<=20.-1e-6 for v in self.polygons[ch]):
                    self.counters['e2_same_here_clears']=self.counters.get('e2_same_here_clears',0)+1
                    self.clear(p,ch,certified=True)
        finally:self._e2_servicing=False

    def measure(self,p,ch):
        kind=super().measure(p,ch)
        self._e2_clear_here()
        return kind

    def clear(self,p,ch,certified=False):
        success=super().clear(p,ch,certified=certified)
        self._e2_clear_here(exclude=ch)
        return success

    def localize(self,ch):
        if not self.config.get('e2_one_round',False):return super().localize(ch)
        self._active_target=ch
        self.counters['e2_service_rounds']=self.counters.get('e2_service_rounds',0)+1
        try:self._e2_service_round(ch)
        finally:self._active_target=None
        self.share_observations(ch)

    def _e2_service_round(self,ch):
        if ch in self.cleared:
            return
        max_iter = int(self.config.get('localization_iterations',9))
        start=self._e2_progress.get(ch,0)
        for k in range(start,min(start+1,max_iter)):
            self._e2_progress[ch]=k+1
            if self._virtual_fallback(ch):
                return
            center,radius = _Q4._di_enclosing_circle(self.polygons[ch])
            if radius <= self.config.get('clear_trial_radius',100.0) or k >= 3:
                clear_point=center
                if radius<=20 and self.config.get('clear_standoff',True):
                    distance=_Q4._di_dist(self.position,center)
                    margin=max(0,20-radius-1e-6)
                    if distance<=margin:
                        clear_point=self.position
                    elif distance>0:
                        clear_point=(center[0]+margin*(self.position[0]-center[0])/distance,
                                     center[1]+margin*(self.position[1]-center[1])/distance)
                if radius<=20 and self.config.get('route_clear',False):
                    clear_point=self.route_clear_point(center,radius,clear_point)
                if self.clear(clear_point,ch,certified=radius<=20):
                    return
                if self._virtual_fallback(ch):
                    return
                # A measurement at a failed optical attempt adds no movement.
                kind = self.measure(center,ch)
                if ch in self.cleared:
                    return
                if self._virtual_fallback(ch):
                    return
                if kind == 'direction':
                    continue
                if self.rescue_bearing(ch,k):
                    if ch in self.cleared:
                        return
                    continue
                if self._virtual_fallback(ch):
                    return
            if len(self.observations[ch]) == 1:
                q = self.second_point(ch)
            else:
                # At this distance ±1 degree amounts to only a few metres;
                # moving toward the feasible-set center quickly shrinks it.
                p,deg = self.observations[ch][-1]
                dd = _Q4._di_dist(p,center)
                if dd < 25:
                    theta = math.radians(deg)+math.pi/2
                    q = (p[0]+35*math.cos(theta),p[1]+35*math.sin(theta))
                else:
                    q = center
            # Do not average the same-location, fixed environmental error.
            if any(_Q4._di_dist(q,p)<1e-5 for p,d in self.observations[ch]):
                q = (q[0]+23.0,q[1]+17.0)
            self.counters['localization_moves'] += 1
            kind = self.measure(q,ch)
            if ch in self.cleared:
                return
            if self._virtual_fallback(ch):
                return
            if kind == 'no_signal':
                # Optical clearing is independent of antenna direction.
                center,radius = _Q4._di_enclosing_circle(self.polygons[ch])
                if (len(self.observations[ch])>=2 or radius<=100 or
                        self.config.get('rescue_initial_clear',False)):
                    if self.clear(center,ch):
                        return
                    if self._virtual_fallback(ch):
                        return
                self.rescue_bearing(ch,k)
                if ch in self.cleared:
                    return
        if self._e2_progress.get(ch,0)>=max_iter:
            self.cover_polygon(ch)

class Solver:
    def __new__(cls,env,mode=3,**config):
        if mode not in (3,4):raise ValueError('mode must be 3 or 4')
        if mode==3:return _FrozenR1Solver(env,mode=mode,**config)
        return ServiceDirectional(env,mode=mode,**{**OPTIMIZED_CONFIGS[mode],**config})
