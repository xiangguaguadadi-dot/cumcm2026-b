"""D3: constrained minimax Voronoi relocation of future scan sites."""
_A1_ADAPTIVE_COVER_PARENT=Solver

def a1_voronoi_cells(points):
    cells=[]
    for i,p in enumerate(points):
        cell=_A1_DOMAIN
        for j,q in enumerate(points):
            if i==j:continue
            dx,dy=q[0]-p[0],q[1]-p[1];length=math.hypot(dx,dy)
            if length<1e-8:continue
            cell=_Q3._sp_clip(cell,dx/length,dy/length,
                (q[0]*q[0]+q[1]*q[1]-p[0]*p[0]-p[1]*p[1])/(2*length)+1e-6)
            if not cell:break
        cells.append(cell)
    return cells

def a1_station_path(start,points):
    """Exact open station-only path, <=6 points, used as a planning guard."""
    n=len(points)
    if not n:return 0.
    ds=[[math.dist(p,q) for q in points] for p in points]
    dp={(1<<j,j):math.dist(start,p) for j,p in enumerate(points)}
    for mask in range(1,1<<n):
        for last in range(n):
            key=(mask,last)
            if key not in dp:continue
            for nxt in range(n):
                if mask>>nxt&1:continue
                next_key=(mask|(1<<nxt),nxt)
                value=dp[key]+ds[last][nxt]
                if value<dp.get(next_key,float('inf')):dp[next_key]=value
    return min(dp[((1<<n)-1,j)] for j in range(n))

class A1AdaptiveCoverSpatial(A1CoverSpatial):
    def spatial_next_task(self,todo):
        p=self.position
        eligible=(todo and 0 not in todo and self.virtual_time<180000. and
                  self._a1_last_cover_stop!=p and math.hypot(*p)>=800. and
                  not any(math.dist(p,self.points[i])<1e-5 for i in range(len(self.points)) if i not in todo))
        if eligible:
            self._a1_last_cover_stop=p
            before_path=None
            for index in sorted(todo,key=lambda i:(math.dist(p,self.points[i]),i))[:2]:
                if math.dist(p,self.points[index])>1000.:continue
                old=self.points[index]
                proposal=self.points[:];proposal[index]=p
                start=time.perf_counter()
                iterations=0
                for iteration in range(5):
                    self.counters['a1_cover_checks']=self.counters.get('a1_cover_checks',0)+1
                    safe,radius,vertices=a1_cover_certificate(proposal)
                    if safe:break
                    if iteration==4:break
                    cells=a1_voronoi_cells(proposal)
                    new=proposal[:]
                    for j in todo:
                        if j==index or not cells[j]:continue
                        new[j]=_Q3._sp_enclosing_circle(cells[j])[0]
                    proposal=new;iterations+=1
                self.counters['a1_cover_cpu_s']=self.counters.get('a1_cover_cpu_s',0.)+time.perf_counter()-start
                if not safe:continue
                if iterations:
                    if before_path is None:before_path=a1_station_path(p,[self.points[j] for j in sorted(todo)])
                    after_path=a1_station_path(p,[proposal[j] for j in sorted(todo) if j!=index])
                    if after_path>before_path+1e-6:
                        self.counters['a1_cover_path_rejects']=self.counters.get('a1_cover_path_rejects',0)+1
                        continue
                else:after_path=None
                assert all(j not in self.scanned[ch] for j in todo for ch in range(1,21)
                           if not self.observations[ch] and ch not in self.cleared)
                self.points=proposal
                self.counters['a1_cover_replacements']=self.counters.get('a1_cover_replacements',0)+1
                self.counters['a1_cover_adaptive_relocations']=self.counters.get('a1_cover_adaptive_relocations',0)+int(iterations>0)
                self.a1_cover_events.append(dict(index=index,old=old,new=p,points=proposal,minimax_iterations=iterations,
                    station_path_before=before_path,station_path_after=after_path,
                    covering_radius_upper=radius,vertices=vertices,virtual_time_s=self.virtual_time,
                    unknown=[ch for ch in range(1,21) if not self.observations[ch] and ch not in self.cleared]))
                self.route_successor=None
                return 'station',index
        return A1ServiceSpatial.spatial_next_task(self,todo)

class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        if mode==3:return A1AdaptiveCoverSpatial(env,mode=mode,**merged)
        return _A1_ADAPTIVE_COVER_PARENT(env,mode=mode,**merged)
