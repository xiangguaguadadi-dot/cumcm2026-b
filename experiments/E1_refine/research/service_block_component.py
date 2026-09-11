# E1 R4: directed entry/service/exit task blocks; predictions only.
class ServiceBlockMixin:
    def spatial_next_task(self, todo):
        """Receding-horizon open tour of certified stations and known regions.

        Source centers are estimates used only for route ordering. They are
        never optical certificates; localization still uses its bounded set.
        Every route contains each remaining station and each pending source.
        """
        geom=_P3 if self.mode==3 else _P4
        circle=geom._sp_enclosing_circle if self.mode==3 else geom._di_enclosing_circle
        tasks=[('station',i) for i in sorted(todo)]+[
            ('source',c) for c in range(1,21)
            if self.observations[c] and c not in self.cleared]
        positions=[self.position]+[
            self.points[k] if kind=='station' else circle(self.polygons[k])[0]
            for kind,k in tasks]
        n=len(tasks)
        entries=[[b for b in positions]for a in positions]
        old_position=self.position
        try:
            for j,(kind,ch) in enumerate(tasks,1):
                if kind!='source' or len(self.observations[ch])!=1:continue
                center,radius=circle(self.polygons[ch])
                if radius<=self.config.get('clear_trial_radius',100.):continue
                for i,prev in enumerate(positions):
                    if i==j:continue
                    # Predict the unchanged parent's first sensing location
                    # from the preceding block's center-valued exit forecast.
                    self.position=prev
                    entries[i][j]=self.second_point(ch)
        finally:self.position=old_position
        ds=[[math.dist(a,entries[i][j])+math.dist(entries[i][j],b) for j,b in enumerate(positions)]for i,a in enumerate(positions)]
        remaining=set(range(1,n+1));greedy=[];p=0
        while remaining:
            q=min(remaining,key=lambda j:(ds[p][j],j))
            greedy.append(q);remaining.remove(q);p=q
        def improve(route):
            route=route[:]
            for _ in range(60):
                best=None;delta=0.
                reverse_prefix=[0.]
                for a,b in zip(route,route[1:]):reverse_prefix.append(reverse_prefix[-1]+ds[b][a]-ds[a][b])
                for i in range(n-1):
                    before=0 if i==0 else route[i-1]
                    a=route[i]
                    for j in range(i+1,n):
                        b=route[j]
                        change=ds[before][b]-ds[before][a]+reverse_prefix[j]-reverse_prefix[i]
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
        self.route_successor=entries[best[0]][best[1]] if len(best)>1 else None
        self.counters['service_block_calls']=self.counters.get('service_block_calls',0)+1
        return tasks[best[0]-1]
class BlockSpatial(ServiceBlockMixin,_P3._LensSpatial):pass
class BlockDirectional(ServiceBlockMixin,_P4._LensDirectional):pass
