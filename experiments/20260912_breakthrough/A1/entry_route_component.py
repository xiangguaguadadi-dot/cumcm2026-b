"""D2 R3: align route proxies with the endpoint of the actual next service round."""
_A1_SERVICE_PARENT=Solver
class A1EntrySpatial(A1ServiceSpatial):
    def _a1_route_point(self,ch):
        center,radius=_Q3._sp_enclosing_circle(self.polygons[ch])
        if radius<=self.config.get('clear_trial_radius',100.) or self._a1_progress.get(ch,0)>=3:
            return center
        if len(self.observations[ch])==1:
            return self.second_point(ch)
        p,deg=self.observations[ch][-1]
        if math.dist(p,center)<25:
            theta=math.radians(deg)+math.pi/2
            return p[0]+35*math.cos(theta),p[1]+35*math.sin(theta)
        return center

    def spatial_next_task(self, todo):
        """Receding-horizon open tour of certified stations and known regions.
    
            Source centers are estimates used only for route ordering. They are
            never optical certificates; localization still uses its bounded set.
            Every route contains each remaining station and each pending source.
            """
        tasks = [('station', i) for i in sorted(todo)] + [('source', c) for c in range(1, 21) if self.observations[c] and c not in self.cleared]
        positions = [self.position] + [self.points[k] if kind == 'station' else self._a1_route_point(k) for kind, k in tasks]
        n = len(tasks)
        ds = [[_Q3._sp_dist(a, b) for b in positions] for a in positions]
        remaining = set(range(1, n + 1))
        greedy = []
        p = 0
        while remaining:
            q = min(remaining, key=lambda j: (ds[p][j], j))
            greedy.append(q)
            remaining.remove(q)
            p = q
    
        def improve(route):
            route = route[:]
            for _ in range(60):
                best = None
                delta = 0.0
                for i in range(n - 1):
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
                i, j = best
                route[i:j + 1] = reversed(route[i:j + 1])
            return route
        starts = [greedy, list(range(1, n + 1)), list(range(n, 0, -1))]
        routes = [improve(x) for x in starts]
    
        def reinsert(route):
            route = route[:]
            for _ in range(30):
                best = None
                delta = 0.0
                for i, x in enumerate(route):
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
                i, j = best
                x = route.pop(i)
                route.insert(j, x)
                route = improve(route)
            return route
        routes += [reinsert(x) for x in routes]
        length = lambda r: ds[0][r[0]] + sum((ds[a][b] for a, b in zip(r, r[1:])))
        best = min(routes, key=lambda r: (length(r), r))
        self.route_successor = positions[best[1]] if len(best) > 1 else None
        return tasks[best[0] - 1]

class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        if mode==3:return A1EntrySpatial(env,mode=mode,**merged)
        return _A1_SERVICE_PARENT(env,mode=mode,**merged)
