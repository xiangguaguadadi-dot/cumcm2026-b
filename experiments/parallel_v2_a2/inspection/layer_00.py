"""A2 retained R2, self-contained packaging of frozen C7 + adaptive phase.
No cases, scores, or live truth are read by this deployment.
"""
import types, math
_C7 = types.ModuleType('_a2_frozen_c7')
_C7.__file__ = __file__
exec(compile('<extracted nested source>', __file__ + ':C7', 'exec'), _C7.__dict__)
BASELINE_CONFIG = dict(_C7.BASELINE_CONFIG)
OPTIMIZED_CONFIGS = {3: dict(_C7.OPTIMIZED_CONFIGS[3]), 4: dict(_C7.OPTIMIZED_CONFIGS[4], a2_rotation=True, a2_rotations=24, a2_rotation_proxy='insertion')}

def open_tour_score(points, start):
    vertices = [start] + points
    n = len(points)
    ds = [[math.dist(a, b) for b in vertices] for a in vertices]
    remaining = set(range(1, n + 1))
    route = []
    previous = 0
    while remaining:
        nxt = min(remaining, key=lambda j: (ds[previous][j], j))
        remaining.remove(nxt)
        route.append(nxt)
        previous = nxt
    for _ in range(40):
        best = None
        gain = -1e-07
        for i in range(n - 1):
            before = 0 if i == 0 else route[i - 1]
            a = route[i]
            for j in range(i + 1, n):
                b = route[j]
                delta = ds[before][b] - ds[before][a]
                if j + 1 < n:
                    after = route[j + 1]
                    delta += ds[a][after] - ds[b][after]
                if delta < gain:
                    best = (i, j)
                    gain = delta
        if best is None:
            break
        (i, j) = best
        route[i:j + 1] = reversed(route[i:j + 1])
    return ds[0][route[0]] + sum((ds[a][b] for (a, b) in zip(route, route[1:])))

class RotationDirectional(_C7.GeometryDirectional):

    def __init__(self, env, mode=4, **config):
        super().__init__(env, mode=mode, **config)
        self._a2_rotated = False

    def scan_station(self, index, defer=False):
        super().scan_station(index, defer=defer)
        if self.config.get('a2_rotation', True) and index == 0 and (not self._a2_rotated):
            self._a2_choose_rotation()

    def _a2_choose_rotation(self):
        self._a2_rotated = True
        if any((any((i != 0 for i in seen)) for seen in self.scanned.values())):
            raise RuntimeError('Rotation attempted after non-origin evidence')
        if math.dist(self.points[0], (0.0, 0.0)) > 1e-12:
            raise RuntimeError('Common-rotation certificate requires fixed origin')
        centers = [_C7._Q4._di_enclosing_circle(self.polygons[ch])[0] for ch in range(1, 21) if self.observations[ch] and ch not in self.cleared]
        if not centers:
            return
        original = self.points[:]
        best_score = None
        best_angle = 0.0
        best_points = original
        steps = int(self.config.get('a2_rotations', 24))
        for k in range(steps):
            angle = math.pi * k / (2 * steps)
            (co, si) = (math.cos(angle), math.sin(angle))
            points = [(co * x - si * y, si * x + co * y) for (x, y) in original]
            if self.config.get('a2_rotation_proxy') == 'insertion':
                score = sum((min((math.dist(c, p) for p in points[1:])) for c in centers))
            else:
                score = open_tour_score(points[1:] + centers, self.position)
            if best_score is None or score < best_score - 1e-07:
                (best_score, best_angle, best_points) = (score, angle, points)
        self.points = best_points
        _C7._E1._GEOMETRY_MASKS[tuple(self.points)] = _C7._E1._discovery_masks(original)
        self.counters['a2_rotation_angle_millirad'] = int(best_angle * 1000)
        self.counters['a2_rotation_applied'] = int(abs(best_angle) > 1e-12)

class Solver:

    def __new__(cls, env, mode=3, **config):
        if mode not in (3, 4):
            raise ValueError('mode must be 3 or 4')
        merged = {**OPTIMIZED_CONFIGS[mode], **config}
        return _C7.Solver(env, mode=3, **merged) if mode == 3 else RotationDirectional(env, mode=4, **merged)
