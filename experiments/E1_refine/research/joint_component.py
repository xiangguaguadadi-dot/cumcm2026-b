# E1 R3: coordinate descent of all certified clear regions on a full open tour.
class JointMixin:
    def spatial_next_task(self, todo):
        """Receding-horizon open tour of certified stations and known regions.

        Source centers are estimates used only for route ordering. They are
        never optical certificates; localization still uses its bounded set.
        Every route contains each remaining station and each pending source.
        """
        if self.config.get('joint_clear_style','off')=='off':return super().spatial_next_task(todo)
        self._joint_clear_target=None
        geom=_P3 if self.mode==3 else _P4
        circle=geom._sp_enclosing_circle if self.mode==3 else geom._di_enclosing_circle
        tasks=[('station',i) for i in sorted(todo)]+[
            ('source',c) for c in range(1,21)
            if self.observations[c] and c not in self.cleared]
        positions=[self.position]+[
            self.points[k] if kind=='station' else circle(self.polygons[k])[0]
            for kind,k in tasks]
        n=len(tasks)
        ds=[[math.dist(a,b) for b in positions] for a in positions]
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
        certified={x:tasks[x-1][1] for x in best if tasks[x-1][0]=='source'
                   and 0<len(self.polygons[tasks[x-1][1]])<=32
                   and circle(self.polygons[tasks[x-1][1]])[1]<20.-1e-6}
        self.counters['joint_route_calls']=self.counters.get('joint_route_calls',0)+1
        self.counters['joint_certified_regions']=self.counters.get('joint_certified_regions',0)+len(certified)
        def refine(route):
            points={x:positions[x] for x in route}
            if not certified:return points,length(route)
            def cost():return math.dist(self.position,points[route[0]])+sum(math.dist(points[a],points[b])for a,b in zip(route,route[1:]))
            before=cost()
            for sweep in range(3):
                prior=cost()
                order=range(len(route)) if sweep%2==0 else range(len(route)-1,-1,-1)
                for i in order:
                    x=route[i]
                    if x not in certified:continue
                    prev=self.position if i==0 else points[route[i-1]]
                    nxt=points[route[i+1]] if i+1<len(route) else None
                    poly=self.polygons[certified[x]]
                    q=geom._lens_route_point(poly,prev,nxt,points[x])
                    if all(math.dist(q,v)<=20.-1e-8 for v in poly):points[x]=q
                if prior-cost()<1e-5:break
            after=cost()
            assert after<=before+1e-6
            return points,after
        points,score=refine(best)
        if self.config.get('joint_clear_style')=='reorder':
            options=[(score,best,points)]
            for route in routes:
                if route==best:continue
                q,value=refine(route);options.append((value,route,q))
            score,best,points=min(options,key=lambda z:(z[0],z[1]))
        self.counters['joint_proxy_saved_m']=self.counters.get('joint_proxy_saved_m',0.)+length(best)-score
        self.route_successor=points[best[1]] if len(best)>1 else None
        if best[0] in certified:self._joint_clear_target=(certified[best[0]],points[best[0]])
        return tasks[best[0]-1]
    def route_clear_point(self,center,radius,original):
        fallback=super().route_clear_point(center,radius,original)
        item=getattr(self,'_joint_clear_target',None)
        if item is None or item[0]!=self._active_target or radius>20:return fallback
        q=item[1];poly=self.polygons[self._active_target]
        if not poly or any(math.dist(q,v)>20.-1e-8 for v in poly):return fallback
        target=getattr(self,'route_successor',None)
        cost=lambda p:math.dist(self.position,p)+(math.dist(p,target)if target is not None else 0.)
        return min((fallback,q),key=lambda p:(cost(p),p))

class JointSpatial(JointMixin,_P3._LensSpatial):pass
class JointDirectional(JointMixin,_P4._LensDirectional):pass
