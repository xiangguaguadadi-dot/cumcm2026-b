
# Finite complete optical action policies transplanted from A1's geometry only.
_FIN_PARENT=Solver
_Q3=_C7._Q3
class FiniteOpticalBase(HexDirectional):
    belief_quadrature=_Q3._DecisionSpatial.belief_quadrature
    def trial_point(self,ch,center,radius):
        # Q4 parent trial is the MEC center; never apply Q3 no-signal disks.
        return center
class TwoDiskSpatial(FiniteOpticalBase):

    def _two_disk_plan(self, ch):
        poly = self.polygons[ch]
        (center, radius) = _Q3._sp_enclosing_circle(poly)
        if not 20.0 < radius < 45.0:
            return None
        (a, b) = max(((a, b) for (i, a) in enumerate(poly) for b in poly[i + 1:]), key=lambda pair: math.dist(*pair))
        d = math.dist(a, b)
        if d < 1e-06:
            return None
        u = ((b[0] - a[0]) / d, (b[1] - a[1]) / d)
        values = [u[0] * v[0] + u[1] * v[1] for v in poly]
        (lo, hi) = (min(values), max(values))
        targets = self.belief_quadrature(poly, 81)
        valid = [t for t in targets if all((math.dist(t, q) > 20.0 - 1e-06 for q in self._e2_failed_clear[ch]))]
        if valid:
            targets = valid
        fail = [t for t in targets if math.dist(center, t) > 20.0]
        base = math.dist(self.position, center) / 5.0 + 3.0 + 2.0 * (1.0 - len(fail) / len(targets))
        base += sum((11.0 + math.dist(center, t) / 5.0 for t in fail)) / len(targets)
        plans = []
        for frac in (0.35, 0.425, 0.5, 0.575, 0.65):
            cut = lo + frac * (hi - lo)
            cells = [_Q3._sp_clip(poly, u[0], u[1], cut), _Q3._sp_clip(poly, -u[0], -u[1], -cut)]
            if not all(cells):
                continue
            circles = [_Q3._sp_enclosing_circle(cell) for cell in cells]
            if any((r > 20.0 - 1e-05 for (c, r) in circles)):
                continue
            for order in ((0, 1), (1, 0)):
                (c1, r1) = circles[order[0]]
                (c2, r2) = circles[order[1]]
                margin = max(0.0, 20.0 - r1 - 1e-05)
                distance = math.dist(self.position, c1)
                if distance <= margin:
                    q1 = self.position
                elif distance > 0:
                    q1 = (c1[0] + margin * (self.position[0] - c1[0]) / distance, c1[1] + margin * (self.position[1] - c1[1]) / distance)
                else:
                    q1 = c1
                margin = max(0.0, 20.0 - r2 - 1e-05)
                distance = math.dist(q1, c2)
                if distance <= margin:
                    q2 = q1
                elif distance > 0:
                    q2 = (c2[0] + margin * (q1[0] - c2[0]) / distance, c2[1] + margin * (q1[1] - c2[1]) / distance)
                else:
                    q2 = c2
                if not all((math.dist(q1, v) <= 20.0 - 1e-06 for v in cells[order[0]])):
                    continue
                if not all((math.dist(q2, v) <= 20.0 - 1e-06 for v in cells[order[1]])):
                    continue
                p = sum((math.dist(q1, t) <= 20.0 for t in targets)) / len(targets)
                cost = math.dist(self.position, q1) / 5.0 + 3.0 + p * 2.0 + (1.0 - p) * (math.dist(q1, q2) / 5.0 + 5.0)
                plans.append((cost, q1, q2))
        if not plans:
            return None
        best = min(plans)
        self.counters['two_disk_feasible'] = self.counters.get('two_disk_feasible', 0) + 1
        if best[0] >= base:
            return None
        return best[1:]

    def _e2_service_round(self, ch):
        if ch in self.cleared:
            return
        if self._virtual_fallback(ch):
            return
        plan = self._two_disk_plan(ch)
        if plan is None:
            return super()._e2_service_round(ch)
        self.counters['two_disk_used'] = self.counters.get('two_disk_used', 0) + 1
        (q1, q2) = plan
        if self.clear(q1, ch):
            return
        self.clear(q2, ch, certified=True)

class ThreeDiskSpatial(TwoDiskSpatial):

    @staticmethod
    def _sequence_cost(position, points, targets):
        total = 0.0
        for target in targets:
            p = position
            cost = 0.0
            for q in points:
                cost += math.dist(p, q) / 5.0 + 3.0
                p = q
                if math.dist(q, target) <= 20.0:
                    cost += 2.0
                    break
            else:
                cost += 1000.0
            total += cost
        return total / len(targets)

    def _three_disk_plan(self, ch):
        poly = self.polygons[ch]
        (center, radius) = _Q3._sp_enclosing_circle(poly)
        if not 20.0 < radius < 65.0:
            return None
        (a, b) = max(((a, b) for (i, a) in enumerate(poly) for b in poly[i + 1:]), key=lambda pair: math.dist(*pair))
        d = math.dist(a, b)
        if d < 1e-06:
            return None
        u = ((b[0] - a[0]) / d, (b[1] - a[1]) / d)
        vals = [u[0] * v[0] + u[1] * v[1] for v in poly]
        (lo, hi) = (min(vals), max(vals))
        targets = self.belief_quadrature(poly, 81)
        good = [t for t in targets if all((math.dist(t, q) > 20.0 - 1e-06 for q in self._e2_failed_clear[ch]))]
        if good:
            targets = good
        trial = self.trial_point(ch, center, radius)
        fail = [t for t in targets if math.dist(trial, t) > 20.0]
        base = math.dist(self.position, trial) / 5.0 + 3.0 + 2.0 * (1.0 - len(fail) / len(targets)) + sum((11.0 + math.dist(trial, t) / 5.0 for t in fail)) / len(targets)
        old = self._two_disk_plan(ch)
        plans = []
        if old:
            plans.append((self._sequence_cost(self.position, old, targets), old))
        for (f1, f2) in ((1 / 3, 2 / 3), (0.3, 0.65), (0.35, 0.7)):
            b1 = lo + f1 * (hi - lo)
            b2 = lo + f2 * (hi - lo)
            cells = [_Q3._sp_clip(poly, u[0], u[1], b1), _Q3._sp_clip(_Q3._sp_clip(poly, -u[0], -u[1], -b1), u[0], u[1], b2), _Q3._sp_clip(poly, -u[0], -u[1], -b2)]
            if not all(cells):
                continue
            circles = [_Q3._sp_enclosing_circle(cell) for cell in cells]
            if any((r > 20.0 - 1e-05 for (c, r) in circles)):
                continue
            for order in ((0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0)):
                points = []
                p = self.position
                for k in order:
                    (c, r) = circles[k]
                    margin = max(0.0, 20.0 - r - 1e-05)
                    dist = math.dist(p, c)
                    q = p if dist <= margin else (c[0] + margin * (p[0] - c[0]) / dist, c[1] + margin * (p[1] - c[1]) / dist)
                    if not all((math.dist(q, v) <= 20.0 - 1e-06 for v in cells[k])):
                        break
                    points.append(q)
                    p = q
                if len(points) == 3:
                    plans.append((self._sequence_cost(self.position, points, targets), tuple(points)))
        if not plans:
            return None
        best = min(plans)
        if best[0] >= base:
            return None
        return best[1]

    def _e2_service_round(self, ch):
        if ch in self.cleared:
            return
        if self._virtual_fallback(ch):
            return
        plan = self._three_disk_plan(ch)
        if plan is None:
            return super()._e2_service_round(ch)
        self.counters['three_disk_used'] = self.counters.get('three_disk_used', 0) + 1
        for (i, q) in enumerate(plan):
            if self.clear(q, ch, certified=i == len(plan) - 1):
                return

class MultiDiskSpatial(ThreeDiskSpatial):

    @staticmethod
    def _expected_order(position, points, targets):
        n = len(points)
        full = (1 << n) - 1
        bits = [sum((1 << i for (i, t) in enumerate(targets) if math.dist(q, t) <= 20.0)) for q in points]
        union = [0] * (1 << n)
        for mask in range(1, 1 << n):
            low = mask & -mask
            j = low.bit_length() - 1
            union[mask] = union[mask ^ low] | bits[j]
        if union[full].bit_count() != len(targets):
            return float("inf"), tuple(points)
        survive = [1.0 - b.bit_count() / len(targets) for b in union]
        dp = {}
        for (j, q) in enumerate(points):
            dp[1 << j, j] = (math.dist(position, q) / 5.0 + 3.0, (j,))
        for mask in range(1, full + 1):
            for last in range(n):
                prev = dp.get((mask, last))
                if prev is None:
                    continue
                for j in range(n):
                    if mask >> j & 1:
                        continue
                    key = (mask | 1 << j, j)
                    value = (prev[0] + survive[mask] * (math.dist(points[last], points[j]) / 5.0 + 3.0), prev[1] + (j,))
                    if key not in dp or value < dp[key]:
                        dp[key] = value
        best = min((dp[full, last] for last in range(n)))
        return (best[0] + 2.0, tuple((points[j] for j in best[1])))

    def _three_disk_plan(self, ch):
        old = super()._three_disk_plan(ch)
        poly = self.polygons[ch]
        (center, radius) = _Q3._sp_enclosing_circle(poly)
        if not 20.0 < radius <= 100.0:
            return old
        (a, b) = max(((a, b) for (i, a) in enumerate(poly) for b in poly[i + 1:]), key=lambda pair: math.dist(*pair))
        d = math.dist(a, b)
        if d < 1e-06:
            return old
        u = ((b[0] - a[0]) / d, (b[1] - a[1]) / d)
        vals = [u[0] * v[0] + u[1] * v[1] for v in poly]
        (lo, hi) = (min(vals), max(vals))
        targets = self.belief_quadrature(poly, 81)
        good = [t for t in targets if all((math.dist(t, q) > 20.0 - 1e-06 for q in self._e2_failed_clear[ch]))]
        if good:
            targets = good
        trial = self.trial_point(ch, center, radius)
        fail = [t for t in targets if math.dist(trial, t) > 20.0]
        base = math.dist(self.position, trial) / 5.0 + 3.0 + 2.0 * (1.0 - len(fail) / len(targets)) + sum((11.0 + math.dist(trial, t) / 5.0 for t in fail)) / len(targets)
        plans = []
        if old:
            plans.append((self._sequence_cost(self.position, old, targets), old))
        for count in (4, 5, 6):
            points = []
            for k in range(count):
                left = lo + (hi - lo) * k / count
                right = lo + (hi - lo) * (k + 1) / count
                cell = _Q3._sp_clip(_Q3._sp_clip(poly, -u[0], -u[1], -left), u[0], u[1], right)
                if not cell:
                    break
                (c, r) = _Q3._sp_enclosing_circle(cell)
                if r > 20.0 - 1e-05:
                    break
                margin = max(0.0, 20.0 - r - 1e-05)
                dist = math.dist(self.position, c)
                q = self.position if dist <= margin else (c[0] + margin * (self.position[0] - c[0]) / dist, c[1] + margin * (self.position[1] - c[1]) / dist)
                if not all((math.dist(q, v) <= 20.0 - 1e-06 for v in cell)):
                    break
                points.append(q)
            if len(points) == count:
                plans.append(self._expected_order(self.position, points, targets))
        if not plans:
            return None
        best = min(plans)
        return best[1] if best[0] < base else None
