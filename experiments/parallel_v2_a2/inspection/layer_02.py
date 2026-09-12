"""Self-contained E1 candidate; embedded frozen parents are readable in ../parents/."""
import math, types
_P3 = types.ModuleType('_P3')
_P3.__file__ = __file__
exec(compile('<extracted nested source>', __file__ + '_P3', 'exec'), _P3.__dict__)
_P4 = types.ModuleType('_P4')
_P4.__file__ = __file__
exec(compile('<extracted nested source>', __file__ + '_P4', 'exec'), _P4.__dict__)
_GEOMETRY_MASKS = {}

def _discovery_masks(points):
    key = tuple(points)
    if key in _GEOMETRY_MASKS:
        return _GEOMETRY_MASKS[key]
    masks = [0] * len(points)
    state = 0
    for shell in range(6):
        rr = 1800 * math.sqrt((shell + 0.5) / 6)
        for sector in range(24):
            a = 2 * math.pi * (sector + 0.5) / 24
            (gx, gy) = (rr * math.cos(a), rr * math.sin(a))
            for reach in (1000.0, 1250.0, 1500.0):
                for emitter in range(16):
                    direction = None if emitter < 8 else 2 * math.pi * (emitter - 8) / 8
                    flag = 1 << state
                    state += 1
                    for (i, p) in enumerate(points):
                        (dx, dy) = (p[0] - gx, p[1] - gy)
                        if dx * dx + dy * dy <= reach * reach and (direction is None or dx * math.cos(direction) + dy * math.sin(direction) >= -1e-08):
                            masks[i] |= flag
    answer = (tuple(masks), (1 << state) - 1, state)
    _GEOMETRY_MASKS[key] = answer
    return answer

class ConditionalDirectional(_P4._LensDirectional):

    def _discovery_state(self, todo):
        known = {c for c in range(1, 21) if c in self.cleared or self.observations[c]}
        m = len(known)
        if not todo or m >= 16:
            return None
        unknown = next((c for c in range(1, 21) if c not in known))
        (masks, allmask, size) = _discovery_masks(self.points)
        covered = 0
        for i in self.scanned[unknown]:
            covered |= masks[i]
        remainder = allmask ^ covered
        count = remainder.bit_count()
        if not count:
            return None
        unobserved_fraction = count / size
        weights = {n: math.comb(n, m) * unobserved_fraction ** (n - m) for n in range(max(10, m), 17)}
        p16 = weights[16] / sum(weights.values())
        if self.config.get('conditional_discovery') == 'optimistic':
            p16 = 1.0
        return (masks, remainder, count, 16 - m, p16)

    def spatial_next_task(self, todo):
        if self.config.get('conditional_discovery', 'off') == 'off':
            return super().spatial_next_task(todo)
        state = self._discovery_state(todo)
        if state is None:
            return super().spatial_next_task(todo)
        tasks = [('station', i) for i in sorted(todo)] + [('source', c) for c in range(1, 21) if self.observations[c] and c not in self.cleared]
        positions = [self.position] + [self.points[k] if kind == 'station' else _P4._di_enclosing_circle(self.polygons[k])[0] for (kind, k) in tasks]
        n = len(tasks)
        ds = [[math.dist(a, b) for b in positions] for a in positions]
        remaining = set(range(1, n + 1))
        greedy = []
        p = 0
        while remaining:
            q = min(remaining, key=lambda j: (ds[p][j], j))
            greedy.append(q)
            remaining.remove(q)
            p = q

        def length(route):
            return ds[0][route[0]] + sum((ds[a][b] for (a, b) in zip(route, route[1:])))

        def improve(route, fixed_first=False):
            route = route[:]
            for _ in range(60):
                best = None
                delta = 0.0
                for i in range(int(fixed_first), n - 1):
                    before = 0 if i == 0 else route[i - 1]
                    a = route[i]
                    for j in range(i + 1, n):
                        b = route[j]
                        change = ds[before][b] - ds[before][a]
                        if j + 1 < n:
                            after = route[j + 1]
                            change += ds[a][after] - ds[b][after]
                        if change < delta - 1e-07:
                            delta = change
                            best = (i, j)
                if best is None:
                    break
                (i, j) = best
                route[i:j + 1] = reversed(route[i:j + 1])
            return route

        def reinsert(route):
            route = route[:]
            for _ in range(30):
                best = None
                delta = 0.0
                for (i, x) in enumerate(route):
                    before = 0 if i == 0 else route[i - 1]
                    after = route[i + 1] if i + 1 < n else None
                    remove = -ds[before][x]
                    if after is not None:
                        remove += ds[before][after] - ds[x][after]
                    short = route[:i] + route[i + 1:]
                    for j in range(n):
                        if j == i:
                            continue
                        left = 0 if j == 0 else short[j - 1]
                        right = short[j] if j < len(short) else None
                        change = remove + ds[left][x]
                        if right is not None:
                            change += ds[x][right] - ds[left][right]
                        if change < delta - 1e-07:
                            best = (i, j)
                            delta = change
                if best is None:
                    break
                (i, j) = best
                x = route.pop(i)
                route.insert(j, x)
                route = improve(route)
            return route
        starts = [greedy, list(range(1, n + 1)), list(range(n, 0, -1))]
        routes = [improve(x) for x in starts]
        routes += [reinsert(x) for x in routes]
        parent = min(routes, key=lambda r: (length(r), r))
        (masks, remainder, count, unseen, p16) = state

        def expected(route):
            full = length(route)
            score = full
            union = 0
            prev = 0.0
            for (pos, x) in enumerate(route):
                (kind, i) = tasks[x - 1]
                if kind != 'station':
                    continue
                union |= masks[i] & remainder
                cumulative = p16 * (union.bit_count() / count) ** unseen
                if cumulative > prev:
                    truncated = route[:pos + 1] + [y for y in route[pos + 1:] if tasks[y - 1][0] == 'source']
                    score -= (cumulative - prev) * (full - length(truncated))
                    prev = cumulative
            return score
        gains = sorted((x for x in parent if tasks[x - 1][0] == 'station'), key=lambda x: -(masks[tasks[x - 1][1]] & remainder).bit_count() / (ds[0][x] + 1))[:3]
        fronts = set(gains + greedy[:2] + parent[:2])
        for first in sorted(fronts):
            route = [first] + [x for x in parent if x != first]
            routes.append(improve(route, fixed_first=True))
        best = min(routes, key=lambda r: (expected(r), r))
        self.counters['conditional_route_calls'] = self.counters.get('conditional_route_calls', 0) + 1
        self.counters['conditional_changed_first'] = self.counters.get('conditional_changed_first', 0) + int(best[0] != parent[0])
        self.counters['conditional_proxy_saving_m'] = self.counters.get('conditional_proxy_saving_m', 0.0) + expected(parent) - expected(best)
        self.route_successor = positions[best[1]] if len(best) > 1 else None
        return tasks[best[0] - 1]
OPTIMIZED_CONFIGS = {3: dict(_P3.OPTIMIZED_CONFIGS[3]), 4: dict(_P4.OPTIMIZED_CONFIGS[4], **{'conditional_discovery': 'posterior'})}
BASELINE_CONFIG = dict(_P3.BASELINE_CONFIG)

class Solver:

    def __new__(cls, env, mode=3, **config):
        merged = {**OPTIMIZED_CONFIGS[mode], **config}
        if mode == 3:
            return _P3.Solver(env, mode=mode, **merged)
        return ConditionalDirectional(env, mode=mode, **merged)
