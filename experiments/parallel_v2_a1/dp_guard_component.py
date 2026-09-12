"""Make the DP's finite distribution coverage precondition explicit."""
_DP_GUARD_PARENT=Solver

class GuardedSpatial(OrientationSpatial):
    @staticmethod
    def _expected_order(position,points,targets):
        if not targets or not all(any(math.dist(p,t)<=20. for p in points) for t in targets):
            raise ValueError('Optical DP requires its planning hypotheses to be covered by the complete certified disk family')
        return MultiDiskSpatial._expected_order(position,points,targets)

class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        if mode==3:return GuardedSpatial(env,mode=mode,**merged)
        return _DP_GUARD_PARENT(env,mode=mode,**merged)
