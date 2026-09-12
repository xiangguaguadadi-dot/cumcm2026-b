"""C1: E1 conditional route plus E2 station cost gate; self-contained."""
import types, math
_E1 = types.ModuleType('embedded_E1_R1')
_E1.__file__ = __file__
exec(compile('<extracted nested source>', '<E1-R1>', 'exec'), _E1.__dict__)
_Q3 = _E1._P3
_Q4 = _E1._P4

class CostDirectional(_E1.ConditionalDirectional):

    def __init__(self, env, mode=4, **config):
        super().__init__(env, mode=mode, **config)
        self.e2_decisions = []

    @staticmethod
    def _e2_continuation_cost(poly, p):
        (c, r) = _Q4._di_enclosing_circle(poly)
        travel = max(0.0, math.dist(p, c) - max(0.0, 20.0 - r)) / 5.0
        return travel + 5.0 + (8.0 + max(0.0, r - 20.0) / 5.0 if r > 20.0 else 0.0) + (6.0 if r > 100.0 else 0.0)

    def _e2_gate(self, ch, p, context):
        poly = self.polygons[ch]
        (center, radius) = _Q4._di_enclosing_circle(poly)
        if radius <= 20.0 or math.dist(center, p) > 1500.0 + radius:
            return False
        if context == 'station' and self.config.get('e2_station_mode', 'cost') == 'uncertified':
            return True
        before = self._e2_continuation_cost(poly, p)
        receive = self.predicted_visibility(ch, p)
        if math.dist(center, p) <= 5.0:
            after = 5.0
        else:
            after = 0.0
            for error in (-0.8, 0.0, 0.8):
                angle = math.degrees(math.atan2(center[1] - p[1], center[0] - p[0])) + error
                posterior = _Q4._di_add_bearing(poly, p, angle)
                after += (self._e2_continuation_cost(posterior, p) if posterior else before) / 3.0
        measure_cost = 5.0 + float(ch != self.channel)
        net = receive * (before - after) - measure_cost
        take = net > 0.0
        self.counters['e2_gate_evaluations'] = self.counters.get('e2_gate_evaluations', 0) + 1
        if take:
            self.counters['e2_gate_accepted'] = self.counters.get('e2_gate_accepted', 0) + 1
        if self.config.get('e2_log_decisions', False):
            self.e2_decisions.append(dict(channel=ch, context=context, position=list(p), radius_m=radius, receive_proxy=receive, cost_before_s=before, cost_after_positive_s=after, net_proxy_s=net, take=take, observations=len(self.observations[ch]), virtual_time_s=self.virtual_time))
        return take

    def share_observations(self, exclude=None):
        style = self.config.get('e2_opportunity', 'cost')
        if style == 'parent':
            return super().share_observations(exclude)
        if style == 'off' or self._sharing:
            return
        self._sharing = True
        try:
            p = self.position
            for ch in range(1, 21):
                if self.virtual_time >= 180000.0 or self._sharing_spent_s >= 6000.0:
                    break
                if ch == exclude or ch in self.cleared or (not self.observations[ch]):
                    continue
                if min((math.dist(p, q) for (q, _) in self.observations[ch])) < 60.0:
                    continue
                if not self._e2_gate(ch, p, 'opportunity'):
                    continue
                before = self.virtual_time
                self.counters['opportunity_measures'] = self.counters.get('opportunity_measures', 0) + 1
                self.measure(p, ch)
                self._sharing_spent_s += self.virtual_time - before
        finally:
            self._sharing = False

    def scan_station(self, index, defer=False):
        if not self.config.get('e2_station_cost', False) or not defer:
            return super().scan_station(index, defer=defer)
        p = self.points[index]
        unknown = [c for c in range(1, 21) if c not in self.cleared and (not self.observations[c])]
        if self.channel in unknown:
            unknown.remove(self.channel)
            unknown.insert(0, self.channel)
        self.counters['scan_stations'] += 1
        for ch in unknown:
            self.measure(p, ch)
            self.scanned[ch].add(index)
        pending = [c for c in range(1, 21) if self.observations[c] and c not in self.cleared]
        for ch in pending:
            if any((math.dist(p, old) < 1e-05 for (old, _) in self.observations[ch])):
                continue
            if self._e2_gate(ch, p, 'station'):
                self.counters['e2_station_retests'] = self.counters.get('e2_station_retests', 0) + 1
                self.measure(p, ch)
OPTIMIZED_CONFIGS = {3: dict(_E1.OPTIMIZED_CONFIGS[3]), 4: dict(_E1.OPTIMIZED_CONFIGS[4], **{'e2_station_cost': True, 'e2_opportunity': 'parent'})}
BASELINE_CONFIG = dict(_E1.BASELINE_CONFIG)

class Solver:

    def __new__(cls, env, mode=3, **config):
        if mode not in (3, 4):
            raise ValueError('mode must be 3 or 4')
        merged = {**OPTIMIZED_CONFIGS[mode], **config}
        if mode == 3:
            return _Q3.Solver(env, mode=mode, **merged)
        return CostDirectional(env, mode=mode, **merged)

class ServiceDirectional(CostDirectional):

    def __init__(self, env, mode=4, **config):
        super().__init__(env, mode=mode, **config)
        self._e2_servicing = False
        self._e2_progress = {}

    def _e2_clear_here(self, exclude=None):
        if not self.config.get('e2_same_here', False) or self._e2_servicing:
            return
        self._e2_servicing = True
        try:
            p = self.position
            for ch in range(1, 21):
                if ch == exclude or ch in self.cleared or ch not in self.polygons:
                    continue
                if all((math.dist(p, v) <= 20.0 - 1e-06 for v in self.polygons[ch])):
                    self.counters['e2_same_here_clears'] = self.counters.get('e2_same_here_clears', 0) + 1
                    self.clear(p, ch, certified=True)
        finally:
            self._e2_servicing = False

    def measure(self, p, ch):
        kind = super().measure(p, ch)
        self._e2_clear_here()
        return kind

    def clear(self, p, ch, certified=False):
        success = super().clear(p, ch, certified=certified)
        self._e2_clear_here(exclude=ch)
        return success

    def localize(self, ch):
        if not self.config.get('e2_one_round', False):
            return super().localize(ch)
        self._active_target = ch
        self.counters['e2_service_rounds'] = self.counters.get('e2_service_rounds', 0) + 1
        try:
            self._e2_service_round(ch)
        finally:
            self._active_target = None
        self.share_observations(ch)

    def _e2_service_round(self, ch):
        if ch in self.cleared:
            return
        max_iter = int(self.config.get('localization_iterations', 9))
        start = self._e2_progress.get(ch, 0)
        for k in range(start, min(start + 1, max_iter)):
            self._e2_progress[ch] = k + 1
            if self._virtual_fallback(ch):
                return
            (center, radius) = _Q4._di_enclosing_circle(self.polygons[ch])
            if radius <= self.config.get('clear_trial_radius', 100.0) or k >= 3:
                clear_point = center
                if radius <= 20 and self.config.get('clear_standoff', True):
                    distance = _Q4._di_dist(self.position, center)
                    margin = max(0, 20 - radius - 1e-06)
                    if distance <= margin:
                        clear_point = self.position
                    elif distance > 0:
                        clear_point = (center[0] + margin * (self.position[0] - center[0]) / distance, center[1] + margin * (self.position[1] - center[1]) / distance)
                if radius <= 20 and self.config.get('route_clear', False):
                    clear_point = self.route_clear_point(center, radius, clear_point)
                if self.clear(clear_point, ch, certified=radius <= 20):
                    return
                if self._virtual_fallback(ch):
                    return
                kind = self.measure(center, ch)
                if ch in self.cleared:
                    return
                if self._virtual_fallback(ch):
                    return
                if kind == 'direction':
                    continue
                if self.rescue_bearing(ch, k):
                    if ch in self.cleared:
                        return
                    continue
                if self._virtual_fallback(ch):
                    return
            if len(self.observations[ch]) == 1:
                q = self.second_point(ch)
            else:
                (p, deg) = self.observations[ch][-1]
                dd = _Q4._di_dist(p, center)
                if dd < 25:
                    theta = math.radians(deg) + math.pi / 2
                    q = (p[0] + 35 * math.cos(theta), p[1] + 35 * math.sin(theta))
                else:
                    q = center
            if any((_Q4._di_dist(q, p) < 1e-05 for (p, d) in self.observations[ch])):
                q = (q[0] + 23.0, q[1] + 17.0)
            self.counters['localization_moves'] += 1
            kind = self.measure(q, ch)
            if ch in self.cleared:
                return
            if self._virtual_fallback(ch):
                return
            if kind == 'no_signal':
                (center, radius) = _Q4._di_enclosing_circle(self.polygons[ch])
                if len(self.observations[ch]) >= 2 or radius <= 100 or self.config.get('rescue_initial_clear', False):
                    if self.clear(center, ch):
                        return
                    if self._virtual_fallback(ch):
                        return
                self.rescue_bearing(ch, k)
                if ch in self.cleared:
                    return
        if self._e2_progress.get(ch, 0) >= max_iter:
            self.cover_polygon(ch)
OPTIMIZED_CONFIGS[4].update({'e2_one_round': True, 'e2_same_here': False})

class Solver:

    def __new__(cls, env, mode=3, **config):
        if mode not in (3, 4):
            raise ValueError('mode must be 3 or 4')
        merged = {**OPTIMIZED_CONFIGS[mode], **config}
        if mode == 3:
            return _Q3.Solver(env, mode=mode, **merged)
        return ServiceDirectional(env, mode=mode, **merged)

class FailureDirectional(ServiceDirectional):

    def __init__(self, env, mode=4, **config):
        super().__init__(env, mode=mode, **config)
        self._e2_failed_clear = {c: [] for c in range(1, 21)}

    def _e2_refine_failures(self, ch):
        if not self.config.get('e2_failure_hull', False) or ch not in self.polygons:
            return
        poly = self.polygons[ch]
        for p in self._e2_failed_clear[ch]:
            if len(poly) > 96:
                break
            result = _Q3._geo_outside_disk_hull(poly, p, 20.0 - 1e-06)
            if not result:
                raise RuntimeError('Failed clear contradicts retained location geometry')
            if len(result) <= 96:
                poly = result
        self.polygons[ch] = poly

    def measure(self, p, ch):
        kind = super().measure(p, ch)
        if kind == 'direction':
            self._e2_refine_failures(ch)
        return kind

    def clear(self, p, ch, certified=False):
        ok = super().clear(p, ch, certified=certified)
        if not ok:
            self._e2_failed_clear[ch].append(tuple(map(float, p)))
            self._e2_refine_failures(ch)
        return ok

    def _e2_cell_excluded(self, test, origin, u, v, ch):
        if not self.config.get('e2_failure_cells', False):
            return False
        world = [(origin[0] + q[0] * u[0] + q[1] * v[0], origin[1] + q[0] * u[1] + q[1] * v[1]) for q in test]
        excluded = any((all((math.dist(p, q) <= 20.0 - 1e-06 for q in world)) for p in self._e2_failed_clear[ch]))
        if excluded:
            self.counters['e2_excluded_cells'] = self.counters.get('e2_excluded_cells', 0) + 1
        return excluded

    def optical_points(self, ch):
        """Conservative 25m lattice cover, shared by cost selection and fallback."""
        poly = self.polygons[ch]
        (origin, deg) = self.observations[ch][0]
        angle = math.radians(deg)
        u = (math.cos(angle), math.sin(angle))
        v = (-u[1], u[0])
        local = [((p[0] - origin[0]) * u[0] + (p[1] - origin[1]) * u[1], (p[0] - origin[0]) * v[0] + (p[1] - origin[1]) * v[1]) for p in poly]
        spacing = 25.0
        lo = [math.floor((min((p[d] for p in local)) - spacing / 2) / spacing) for d in [0, 1]]
        hi = [math.ceil((max((p[d] for p in local)) + spacing / 2) / spacing) for d in [0, 1]]
        candidates = []
        for i in range(lo[0], hi[0] + 1):
            row = range(lo[1], hi[1] + 1) if i % 2 == 0 else range(hi[1], lo[1] - 1, -1)
            for j in row:
                test = local
                for (a, b, c) in [(1, 0, (i + 0.5) * spacing), (-1, 0, (-i + 0.5) * spacing), (0, 1, (j + 0.5) * spacing), (0, -1, (-j + 0.5) * spacing)]:
                    test = _Q4._di_clip(test, a, b, c)
                if test and (not self._e2_cell_excluded(test, origin, u, v, ch)):
                    candidates.append((origin[0] + i * spacing * u[0] + j * spacing * v[0], origin[1] + i * spacing * u[1] + j * spacing * v[1]))
        return candidates

def exclude_forced_visible_wedge(poly, p1, p2, q):
    v1 = (q[0] - p1[0], q[1] - p1[1])
    v2 = (q[0] - p2[0], q[1] - p2[1])
    cross = v1[0] * v2[1] - v1[1] * v2[0]
    if abs(cross) <= 1e-08 * max(1.0, math.hypot(*v1) * math.hypot(*v2)):
        return poly
    if cross < 0:
        (v1, v2) = (v2, v1)
    constraints = [(v1[1], -v1[0]), (-v2[1], v2[0])]
    fragments = []
    for (a, b) in constraints:
        c = a * q[0] + b * q[1]
        fragments += _Q4._di_clip(poly, -a, -b, -c + 1e-06 * math.hypot(a, b))
    return _Q3._geo_convex_hull(fragments)

def area(poly):
    return abs(sum((a[0] * b[1] - a[1] * b[0] for (a, b) in zip(poly, poly[1:] + poly[:1])))) / 2

class GeometryDirectional(FailureDirectional):

    def measure(self, p, ch):
        kind = super().measure(p, ch)
        if self.config.get('convex_no_signal', True) and kind in ('direction', 'no_signal'):
            self.refine_no_signal(ch)
        return kind

    def refine_no_signal(self, ch):
        if ch not in self.polygons or len(self.observations[ch]) < 2 or (not self.no_signal_points[ch]):
            return
        poly = self.polygons[ch]
        before = area(poly)
        positives = [p for (p, _) in self.observations[ch][-8:]]
        for q in self.no_signal_points[ch][-24:]:
            for (i, p1) in enumerate(positives):
                for p2 in positives[i + 1:]:
                    new = exclude_forced_visible_wedge(poly, p1, p2, q)
                    if not new:
                        raise RuntimeError('Convex footprint constraints exclude all source positions')
                    poly = new
        self.polygons[ch] = poly
        after = area(poly)
        self.counters['convex_negative_updates'] = self.counters.get('convex_negative_updates', 0) + 1
        if after < before - 1e-06:
            self.counters['convex_negative_shrinks'] = self.counters.get('convex_negative_shrinks', 0) + 1
        self.counters['convex_negative_area_removed'] = self.counters.get('convex_negative_area_removed', 0.0) + max(0.0, before - after)
        self._visibility_cache.pop(ch, None)
OPTIMIZED_CONFIGS[4].update({'e2_failure_hull': False, 'e2_failure_cells': True, 'convex_no_signal': True})

class Solver:

    def __new__(cls, env, mode=3, **config):
        if mode not in (3, 4):
            raise ValueError('mode must be 3 or 4')
        merged = {**OPTIMIZED_CONFIGS[mode], **config}
        if mode == 3:
            return _Q3.Solver(env, mode=mode, **merged)
        return GeometryDirectional(env, mode=mode, **merged)
