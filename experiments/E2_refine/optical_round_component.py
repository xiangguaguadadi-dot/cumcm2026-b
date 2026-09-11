
# R4 breaks only the finite optical fallback into persistent, paid blocks.
_FrozenR2OpticalSolver=Solver
class OpticalRoundDirectional(ServiceDirectional):
    def __init__(self,env,mode=4,**config):
        super().__init__(env,mode=mode,**config)
        self._e2_optical_queue={}

    def _e2_optical_task_point(self,ch):
        pending=self._e2_optical_queue.get(ch)
        return pending[0] if pending else _Q4._di_enclosing_circle(self.polygons[ch])[0]

    def cover_polygon(self,ch):
        if ch not in self._e2_optical_queue:
            self.counters['fallbacks']+=1
            self._e2_optical_queue[ch]=list(self.optical_route(ch,self.optical_points(ch)))
        queue=self._e2_optical_queue[ch]
        quota=len(queue) if self.virtual_time>=_Q4._di_VIRTUAL_SAFE_SWITCH_S else int(self.config['e2_optical_quota'])
        self.counters['e2_optical_blocks']=self.counters.get('e2_optical_blocks',0)+1
        for _ in range(min(quota,len(queue))):
            # Remove a cell only after its actual clear request returned.
            point=queue[0]
            if self.clear(point,ch):
                self._e2_optical_queue.pop(ch,None)
                return
            queue.pop(0)
        if not queue:
            raise RuntimeError('Persistent complete optical covering exhausted without success')

    def localize(self,ch):
        if ch not in self._e2_optical_queue:return super().localize(ch)
        self._active_target=ch
        try:self.cover_polygon(ch)
        finally:self._active_target=None
        self.share_observations(ch)

    def spatial_next_task(self, todo):
        """Receding-horizon open tour of certified stations and known regions.

        Source centers are estimates used only for route ordering. They are
        never optical certificates; localization still uses its bounded set.
        Every route contains each remaining station and each pending source.
        """
        tasks=[('station',i) for i in sorted(todo)]+[
            ('source',c) for c in range(1,21)
            if self.observations[c] and c not in self.cleared]
        positions=[self.position]+[
            self.points[k] if kind=='station' else self._e2_optical_task_point(k)
            for kind,k in tasks]
        n=len(tasks)
        ds=[[_Q4._di_dist(a,b) for b in positions] for a in positions]
        remaining=set(range(1,n+1));greedy=[];p=0
        while remaining:
            q=min(remaining,key=lambda j:(ds[p][j],j))
            greedy.append(q);remaining.remove(q);p=q
        def improve(route):
            route=route[:]
            for _ in range(60):
                best=None;delta=0.
                for i in range(n-1):
                    before=0 if i==0 else route[i-1]
                    a=route[i]
                    for j in range(i+1,n):
                        b=route[j]
                        change=ds[before][b]-ds[before][a]
                        if j+1<n:
                            after=route[j+1];change+=ds[a][after]-ds[b][after]
                        if change<delta-1e-7:delta=change;best=(i,j)
                if best is None:break
                i,j=best;route[i:j+1]=reversed(route[i:j+1])
            return route
        # Multiple deterministic starts guard against short-sighted nearest
        # neighbor choices while keeping the total cost tied to physical metres.
        starts=[greedy,list(range(1,n+1)),list(range(n,0,-1))]
        routes=[improve(x) for x in starts]
        def reinsert(route):
            route=route[:]
            for _ in range(30):
                best=None;delta=0.
                for i,x in enumerate(route):
                    before=0 if i==0 else route[i-1]
                    after=route[i+1] if i+1<n else None
                    remove=-ds[before][x]
                    if after is not None:remove+=ds[before][after]-ds[x][after]
                    short=route[:i]+route[i+1:]
                    for j in range(n):
                        if j==i:continue
                        left=0 if j==0 else short[j-1]
                        right=short[j] if j<len(short) else None
                        change=remove+ds[left][x]
                        if right is not None:change+=ds[x][right]-ds[left][right]
                        if change<delta-1e-7:best=(i,j);delta=change
                if best is None:break
                i,j=best;x=route.pop(i);route.insert(j,x)
                route=improve(route)
            return route
        # Keep every original 2-opt tour as well: extra search cannot worsen
        # the fixed-state distance proxy, although online realized cost may vary.
        routes+= [reinsert(x) for x in routes]
        length=lambda r:ds[0][r[0]]+sum(ds[a][b] for a,b in zip(r,r[1:]))
        best=min(routes,key=lambda r:(length(r),r))
        self.route_successor=positions[best[1]] if len(best)>1 else None
        return tasks[best[0]-1]

class Solver:
    def __new__(cls,env,mode=3,**config):
        if mode not in (3,4):raise ValueError('mode must be 3 or 4')
        if mode==3:return _FrozenR2OpticalSolver(env,mode=mode,**config)
        return OpticalRoundDirectional(env,mode=mode,**{**OPTIMIZED_CONFIGS[mode],**config})
