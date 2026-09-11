# This component is embedded into each self-contained candidate after frozen S1
# source modules have been created. It never reads evaluation data or the env.
import math

class CostDirectional(_Q4._LensDirectional):
    def __init__(self,env,mode=4,**config):
        super().__init__(env,mode=mode,**config)
        self.e2_decisions=[]

    @staticmethod
    def _e2_continuation_cost(poly,p):
        c,r=_Q4._di_enclosing_circle(poly)
        travel=max(0.,math.dist(p,c)-max(0.,20.-r))/5.
        return travel+5.+(8.+max(0.,r-20.)/5. if r>20. else 0.)+(6. if r>100. else 0.)

    def _e2_gate(self,ch,p,context):
        poly=self.polygons[ch]
        center,radius=_Q4._di_enclosing_circle(poly)
        if radius<=20. or math.dist(center,p)>1500.+radius:
            return False
        if context=='station' and self.config.get('e2_station_mode','cost')=='uncertified':
            return True
        before=self._e2_continuation_cost(poly,p)
        receive=self.predicted_visibility(ch,p)
        if math.dist(center,p)<=5.:
            # near triggers the automatic 5 s clear in the existing measure API.
            after=5.
        else:
            after=0.
            for error in (-.8,0.,.8):
                angle=math.degrees(math.atan2(center[1]-p[1],center[0]-p[0]))+error
                posterior=_Q4._di_add_bearing(poly,p,angle)
                after+=(self._e2_continuation_cost(posterior,p) if posterior else before)/3.
        measure_cost=5.+float(ch!=self.channel)
        # With a directional source, no_signal may be either range or bearing.
        # The real AND predicted no-signal polygon is deliberately left whole.
        net=receive*(before-after)-measure_cost
        take=net>0.
        self.counters['e2_gate_evaluations']=self.counters.get('e2_gate_evaluations',0)+1
        if take:self.counters['e2_gate_accepted']=self.counters.get('e2_gate_accepted',0)+1
        if self.config.get('e2_log_decisions',False):
            self.e2_decisions.append(dict(channel=ch,context=context,position=list(p),
                radius_m=radius,receive_proxy=receive,cost_before_s=before,
                cost_after_positive_s=after,net_proxy_s=net,take=take,
                observations=len(self.observations[ch]),virtual_time_s=self.virtual_time))
        return take

    def share_observations(self,exclude=None):
        style=self.config.get('e2_opportunity','cost')
        if style=='parent':return super().share_observations(exclude)
        if style=='off' or self._sharing:return
        self._sharing=True
        try:
            p=self.position
            for ch in range(1,21):
                if self.virtual_time>=180000. or self._sharing_spent_s>=6000.:break
                if ch==exclude or ch in self.cleared or not self.observations[ch]:continue
                if min(math.dist(p,q) for q,_ in self.observations[ch])<60.:continue
                if not self._e2_gate(ch,p,'opportunity'):continue
                before=self.virtual_time
                self.counters['opportunity_measures']=self.counters.get('opportunity_measures',0)+1
                self.measure(p,ch)
                self._sharing_spent_s+=self.virtual_time-before
        finally:self._sharing=False

    def scan_station(self,index,defer=False):
        if not self.config.get('e2_station_cost',False) or not defer:
            return super().scan_station(index,defer=defer)
        # Preserve the exact discovery action set and station/channel evidence.
        p=self.points[index]
        unknown=[c for c in range(1,21) if c not in self.cleared and not self.observations[c]]
        if self.channel in unknown:
            unknown.remove(self.channel);unknown.insert(0,self.channel)
        self.counters['scan_stations']+=1
        for ch in unknown:
            self.measure(p,ch)
            self.scanned[ch].add(index)
        pending=[c for c in range(1,21) if self.observations[c] and c not in self.cleared]
        for ch in pending:
            if any(math.dist(p,old)<1e-5 for old,_ in self.observations[ch]):continue
            if self._e2_gate(ch,p,'station'):
                self.counters['e2_station_retests']=self.counters.get('e2_station_retests',0)+1
                self.measure(p,ch)

OPTIMIZED_CONFIGS={3:dict(_Q3.OPTIMIZED_CONFIGS[3]),4:dict(_Q4.OPTIMIZED_CONFIGS[4])}
BASELINE_CONFIG=dict(_Q3.BASELINE_CONFIG)

class Solver:
    def __new__(cls,env,mode=3,**config):
        if mode not in (3,4):raise ValueError('mode must be 3 or 4')
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        if mode==3:return _Q3.Solver(env,mode=mode,**merged)
        return CostDirectional(env,mode=mode,**merged)
