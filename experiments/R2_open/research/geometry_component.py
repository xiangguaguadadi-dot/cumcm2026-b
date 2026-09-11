# R2_open R1: bounded set refinement inside S0 Q3 opportunity sensing.
# Only actual interface observations affect the certified location polygon.
_geo_dist = _sp_dist
_geo_clip = _sp_clip
_geo_EPS = _sp_EPS


class _GeometrySpatial(_SharedSpatial):
    def __init__(self, env, mode=3, **config):
        super().__init__(env, mode=mode, **config)
        self.failed_clear_points = {c: [] for c in range(1, 21)}

    def _exclude_observed_disks(self, ch):
        if ch not in self.polygons:
            return
        poly = self.polygons[ch]
        disks = []
        if self.config.get('geom_no_signal', False):
            disks += [(p, 1000.0 - 1e-6) for p in self.no_signal_points[ch]]
        if self.config.get('geom_failure', False):
            disks += [(p, 20.0 - 1e-6) for p in self.failed_clear_points[ch]]
        for p, radius in disks:
            if len(poly) > 96:
                self.counters['geometry_budget_skips'] = self.counters.get('geometry_budget_skips', 0) + 1
                break
            refined = _geo_outside_disk_hull(poly, p, radius)
            if not refined:
                raise RuntimeError('Observed exclusion contradicts bounded bearing constraints')
            # Discarding a computationally large refinement is conservative.
            if len(refined) <= 96:
                poly = refined
        self.polygons[ch] = poly

    def measure(self, p, ch):
        # Update geometry BEFORE invoking opportunity sensing. Calling the
        # shared parent's wrapper first would score with a stale target set.
        kind = _sp_Solver.measure(self, p, ch)
        if kind == 'direction' and self.config.get('geom_tangent', False):
            self.polygons[ch] = _geo_add_bearing(self.polygons[ch], p, self.observations[ch][-1][1])
            if not self.polygons[ch]:
                raise RuntimeError('Physical tangent constraints removed all feasible points')
        if kind in ('direction', 'no_signal'):
            self._exclude_observed_disks(ch)
        if self._active_target is not None and not self._sharing:
            self.share_observations(self._active_target)
        return kind

    def clear(self, p, ch, certified=False):
        success = super().clear(p, ch, certified=certified)
        if not success:
            self.failed_clear_points[ch].append(tuple(p))
            self._exclude_observed_disks(ch)
        return success


BASELINE_CONFIG = dict(_sp_BASELINE_CONFIG)
OPTIMIZED_CONFIGS = {
    3: dict(_sp_OPTIMIZED_CONFIGS[3], sharing_style='visibility', sharing_gain_m=60.,
            geom_tangent=True, geom_no_signal=True, geom_failure=True),
    4: dict(_di_OPTIMIZED_CONFIGS[4]),
}


class Solver:
    def __new__(cls, env, mode=3, **config):
        if mode not in (3, 4):
            raise ValueError('mode must be 3 or 4')
        merged = {**OPTIMIZED_CONFIGS[mode], **config}
        parent = _GeometrySpatial if mode == 3 else _di_Solver
        return parent(env, mode=mode, **merged)
