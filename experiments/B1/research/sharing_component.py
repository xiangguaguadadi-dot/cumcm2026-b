class _OpportunitySensing:
    """Reuses arrival points; hypothetical beliefs only determine paid actions."""
    def __init__(self, env, mode=3, **config):
        super().__init__(env, mode=mode, **config)
        self._active_target = None
        self._sharing = False
        self._sharing_spent_s = 0.0

    def measure(self, p, ch):
        kind = super().measure(p, ch)
        if self._active_target is not None and not self._sharing:
            self.share_observations(self._active_target)
        return kind

    def localize(self, ch):
        self._active_target = ch
        try:
            super().localize(ch)
        finally:
            self._active_target = None
        self.share_observations(ch)

    def share_observations(self, exclude=None):
        style = self.config.get('sharing_style','naive')
        if style == 'off' or self._sharing:
            return
        self._sharing = True
        try:
            p = self.position
            for ch in range(1,21):
                # Each supplemental measure costs <=6 s, or <=11 s with near
                # immediately cleared. Hard cap makes the bound compositional.
                if self.virtual_time >= 180000 or self._sharing_spent_s >= 6000:
                    break
                if ch == exclude or ch in self.cleared or not self.observations[ch]:
                    continue
                if min(_sp_dist(p,old) for old,_ in self.observations[ch]) < 60:
                    continue
                poly = self.polygons[ch]
                center,radius = _sp_enclosing_circle(poly)
                if radius <= 20 or _sp_dist(center,p) > 1500+radius:
                    continue
                targets = [center]
                if style == 'quadrature':
                    # Spread hypotheses over the retained region; unlike a
                    # point estimate, these never enter the actual polygon.
                    far = max(poly,key=lambda q:_sp_dist(q,center))
                    other = max(poly,key=lambda q:_sp_dist(q,far))
                    targets += [(.25*center[0]+.75*q[0],.25*center[1]+.75*q[1]) for q in (far,other)]
                gains=[]
                for target in targets:
                    bearing=math.degrees(math.atan2(target[1]-p[1],target[0]-p[0]))
                    predicted=_sp_add_bearing(poly,p,bearing)
                    gains.append(max(0.,radius-_sp_enclosing_circle(predicted)[1]) if predicted else 0.)
                gain=sum(gains)/len(gains)
                if style in ('visibility','quadrature') and self.mode == 4:
                    gain *= self.predicted_visibility(ch,p)
                threshold=self.config.get('sharing_gain_m',30.)
                if gain < threshold:
                    continue
                before=self.virtual_time
                self.counters['opportunity_measures']=self.counters.get('opportunity_measures',0)+1
                self.measure(p,ch)
                self._sharing_spent_s += self.virtual_time-before
        finally:
            self._sharing = False

class _SharedSpatial(_OpportunitySensing, _sp_Solver):
    pass

class _SharedDirectional(_OpportunitySensing, _di_Solver):
    pass

BASELINE_CONFIG=dict(_sp_BASELINE_CONFIG)
OPTIMIZED_CONFIGS={3:dict(_sp_OPTIMIZED_CONFIGS[3],sharing_style='naive',sharing_gain_m=30.),
                   4:dict(_di_OPTIMIZED_CONFIGS[4],sharing_style='visibility',sharing_gain_m=30.)}
class Solver:
    def __new__(cls,env,mode=3,**config):
        if mode not in (3,4):
            raise ValueError('mode must be 3 or 4')
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        parent=_SharedSpatial if mode==3 else _SharedDirectional
        return parent(env,mode=mode,**merged)
