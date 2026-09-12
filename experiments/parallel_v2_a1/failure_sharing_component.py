"""Mechanism ablation: share paid observations at failed optical stop positions."""
_FAILURE_SHARING_PARENT=Solver

class FailureSharingSpatial(GuardedSpatial):
    def _a1_service_round(self,ch):
        if ch in self.cleared:return
        if self._virtual_fallback(ch):return
        plan=self._three_disk_plan(ch)
        if plan is None:return super()._a1_service_round(ch)
        self.counters['optical_sharing_plans']=self.counters.get('optical_sharing_plans',0)+1
        for i,q in enumerate(plan):
            if self.clear(q,ch,certified=i==len(plan)-1):return
            position=self.position
            self.share_observations(ch)
            if math.dist(self.position,position)>1e-7:
                raise RuntimeError('Expected same-location sharing moved during a certified optical plan')
            self.counters['optical_failure_share_stops']=self.counters.get('optical_failure_share_stops',0)+1

class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        if mode==3:return FailureSharingSpatial(env,mode=mode,**merged)
        return _FAILURE_SHARING_PARENT(env,mode=mode,**merged)
