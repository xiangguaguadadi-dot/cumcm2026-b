
"""D1: task-value gating of existing paid-station Q3 retests only."""
_A1_PARENT = Solver

class A1StationSpatial(_Q3._LensSpatial):
    def scan_station(self,index,defer=False):
        if not defer or not self.config.get('a1_station_gate',True):
            return super().scan_station(index,defer=defer)
        p=self.points[index]
        unknown=[c for c in range(1,21) if c not in self.cleared and not self.observations[c]]
        if self.channel in unknown:
            unknown.remove(self.channel);unknown.insert(0,self.channel)
        self.counters['scan_stations']+=1
        for ch in unknown:
            self.measure(p,ch)
            self.scanned[ch].add(index)
        # Preserve C7's origin-silent adaptive certified ring verbatim.
        if (self.mode==3 and index==0 and not self.cleared and
                not any(self.observations.values()) and
                self.config.get('adaptive_ring',True) and
                not any(i!=0 for indices in self.scanned.values() for i in indices)):
            rr=1800*math.cos(math.pi/6)
            self.points=[(0.,0.)]+[(rr*math.cos(i*math.pi/3),rr*math.sin(i*math.pi/3)) for i in range(6)]
        for ch in range(1,21):
            if ch in self.cleared or not self.observations[ch]:continue
            if any(math.dist(p,old)<1e-5 for old,_ in self.observations[ch]):continue
            center,radius=_Q3._sp_enclosing_circle(self.polygons[ch])
            if math.dist(center,p)>1500.+radius:continue
            self.counters['a1_station_considered']=self.counters.get('a1_station_considered',0)+1
            if radius<=20.:
                take=False
            else:
                prediction=self._gate_prediction(ch,p)
                take=prediction is None or prediction[1]>0.
            if take:
                self.counters['a1_station_taken']=self.counters.get('a1_station_taken',0)+1
                self.measure(p,ch)
            else:
                self.counters['a1_station_skipped']=self.counters.get('a1_station_skipped',0)+1

class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        if mode==3:return A1StationSpatial(env,mode=mode,**merged)
        return _A1_PARENT(env,mode=mode,**merged)

"""D2: persist Q3 localization progress across global route decisions."""
_A1_STATION_PARENT=Solver

class A1ServiceSpatial(A1StationSpatial):
    def __init__(self,env,mode=3,**config):
        super().__init__(env,mode=mode,**config)
        self._a1_progress={}

    def localize(self,ch):
        self._active_target=ch
        self.counters['a1_service_rounds']=self.counters.get('a1_service_rounds',0)+1
        try:self._a1_service_round(ch)
        finally:self._active_target=None
        self.share_observations(ch)

    def _a1_service_round(self,ch):
        if ch in self.cleared:return
        max_iter=int(self.config.get('localization_iterations',9))
        start=self._a1_progress.get(ch,0)
        for k in range(start,min(start+1,max_iter)):
            self._a1_progress[ch]=k+1
            if self._virtual_fallback(ch):return
            center,radius=_Q3._sp_enclosing_circle(self.polygons[ch])
            if radius<=self.config.get('clear_trial_radius',100.) or k>=3:
                clear_point=center
                if radius<=20 and self.config.get('clear_standoff',True):
                    distance=math.dist(self.position,center)
                    margin=max(0.,20-radius-1e-6)
                    if distance<=margin:clear_point=self.position
                    elif distance>0:
                        clear_point=(center[0]+margin*(self.position[0]-center[0])/distance,
                                     center[1]+margin*(self.position[1]-center[1])/distance)
                if radius<=20 and self.config.get('route_clear',True):
                    clear_point=self.route_clear_point(center,radius,clear_point)
                if self.clear(clear_point,ch,certified=radius<=20):return
                if self._virtual_fallback(ch):return
                kind=self.measure(center,ch)
                if ch in self.cleared or self._virtual_fallback(ch):return
                if kind=='direction':continue
                if self.rescue_bearing(ch,k):
                    if ch in self.cleared:return
                    continue
                if self._virtual_fallback(ch):return
            if len(self.observations[ch])==1:q=self.second_point(ch)
            else:
                p,deg=self.observations[ch][-1]
                if math.dist(p,center)<25:
                    theta=math.radians(deg)+math.pi/2
                    q=(p[0]+35*math.cos(theta),p[1]+35*math.sin(theta))
                else:q=center
            if any(math.dist(q,p)<1e-5 for p,d in self.observations[ch]):q=(q[0]+23.,q[1]+17.)
            self.counters['localization_moves']+=1
            kind=self.measure(q,ch)
            if ch in self.cleared or self._virtual_fallback(ch):return
            if kind=='no_signal':
                center,radius=_Q3._sp_enclosing_circle(self.polygons[ch])
                if len(self.observations[ch])>=2 or radius<=100 or self.config.get('rescue_initial_clear',False):
                    if self.clear(center,ch):return
                    if self._virtual_fallback(ch):return
                self.rescue_bearing(ch,k)
                if ch in self.cleared:return
        if self._a1_progress.get(ch,0)>=max_iter:self.cover_polygon(ch)

class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        if mode==3:return A1ServiceSpatial(env,mode=mode,**merged)
        return _A1_STATION_PARENT(env,mode=mode,**merged)

"""D3: replace future Q3 scan sites only under a continuous cover certificate."""
import time
_A1_COVER_PARENT=Solver
_A1_DOMAIN_RADIUS=1800./math.cos(math.pi/256)+1e-6
_A1_DOMAIN=[(_A1_DOMAIN_RADIUS*math.cos(2*math.pi*k/256),
             _A1_DOMAIN_RADIUS*math.sin(2*math.pi*k/256)) for k in range(256)]

def a1_cover_certificate(points):
    """Cover a circumscribed polygon by expanded nearest-site Voronoi cells.

    Each convex cell is clipped by normalized outward-relaxed bisectors. If
    all of its vertices are in its site's strict 1000 m disk, convexity puts
    the entire cell in that disk. The cells cover the outer polygon, which
    contains the physical source disk. This is a sufficient certificate,
    never a finite sampling criterion or an assumption on source density.
    """
    worst=0.;vertices=0
    # A failed necessary check is only a fast rejection, never a certificate.
    for x in _A1_DOMAIN[::8]:
        if min(math.dist(x,p) for p in points)>1000.-1e-3:
            return False,None,0
    for i,p in enumerate(points):
        cell=_A1_DOMAIN
        for j,q in enumerate(points):
            if i==j:continue
            dx,dy=q[0]-p[0],q[1]-p[1]
            length=math.hypot(dx,dy)
            if length<1e-8:continue
            a,b=dx/length,dy/length
            c=(q[0]*q[0]+q[1]*q[1]-p[0]*p[0]-p[1]*p[1])/(2*length)+1e-6
            cell=_Q3._sp_clip(cell,a,b,c)
            if not cell:break
        if not cell:continue
        radius=max(math.dist(x,p) for x in cell)
        vertices+=len(cell)
        worst=max(worst,radius)
        if radius>1000.-1e-3:return False,worst,vertices
    return True,worst,vertices

class _A1CoverageExit:
    """Four-method interface wrapper verifies real negative evidence at exit."""
    def __init__(self,delegate,owner):self.delegate,self.owner=delegate,owner
    def enter(self):return self.delegate.enter()
    def measure(self,x,y,channel):return self.delegate.measure(x,y,channel)
    def clear(self,x,y,channel):return self.delegate.clear(x,y,channel)
    def exit(self):
        solver=self.owner
        if len(solver.cleared)<16:
            cache={}
            for ch in range(1,21):
                if ch in solver.cleared:continue
                if solver.observations[ch]:raise RuntimeError('Uncleared positive channel at continuous-cover exit')
                points=tuple(sorted(set(solver.no_signal_points[ch])))
                if not points:raise RuntimeError('No real negative measurements for absent channel')
                if points not in cache:cache[points]=a1_cover_certificate(points)
                safe,radius,vertices=cache[points]
                if not safe:raise RuntimeError('Actual per-channel negative observations do not cover the source domain')
                solver.a1_exit_coverage.append(dict(channel=ch,points=points,radius=radius,vertices=vertices))
        return self.delegate.exit()

class A1CoverSpatial(A1ServiceSpatial):
    def __init__(self,env,mode=3,**config):
        super().__init__(env,mode=mode,**config)
        self._a1_last_cover_stop=None
        self.a1_cover_events=[]
        self.a1_exit_coverage=[]
        self.env=_A1CoverageExit(env,self)

    def spatial_next_task(self,todo):
        p=self.position
        if (todo and 0 not in todo and self.virtual_time<180000. and
                self._a1_last_cover_stop!=p and
                not any(math.dist(p,self.points[i])<1e-5 for i in range(len(self.points)) if i not in todo)):
            self._a1_last_cover_stop=p
            for index in sorted(todo,key=lambda i:(math.dist(p,self.points[i]),i)):
                if math.dist(p,self.points[index])>1000.:continue
                proposal=self.points[:]
                proposal[index]=p
                self.counters['a1_cover_checks']=self.counters.get('a1_cover_checks',0)+1
                start=time.perf_counter()
                safe,radius,vertices=a1_cover_certificate(proposal)
                self.counters['a1_cover_cpu_s']=self.counters.get('a1_cover_cpu_s',0.)+time.perf_counter()-start
                if not safe:continue
                old=self.points[index]
                # Only an unvisited index can change coordinates. Returning
                # it as the next station causes the real scan_station action
                # to measure every still-unknown channel before marking it.
                assert all(index not in self.scanned[ch] for ch in range(1,21) if not self.observations[ch] and ch not in self.cleared)
                self.points[index]=p
                self.counters['a1_cover_replacements']=self.counters.get('a1_cover_replacements',0)+1
                self.a1_cover_events.append(dict(index=index,old=old,new=p,points=proposal,
                    covering_radius_upper=radius,vertices=vertices,virtual_time_s=self.virtual_time,
                    unknown=[ch for ch in range(1,21) if not self.observations[ch] and ch not in self.cleared]))
                self.route_successor=None
                return 'station',index
        return super().spatial_next_task(todo)

class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        if mode==3:return A1CoverSpatial(env,mode=mode,**merged)
        return _A1_COVER_PARENT(env,mode=mode,**merged)

"""D3 R7: jointly rotate only future sites to fit a certified paid stop."""
_A1_ROTATING_COVER_PARENT=Solver
class A1RotatingCoverSpatial(A1CoverSpatial):
    def spatial_next_task(self,todo):
        p=self.position
        eligible=(todo and 0 not in todo and self.virtual_time<180000. and
                  self._a1_last_cover_stop!=p and
                  not any(math.dist(p,self.points[i])<1e-5 for i in range(len(self.points)) if i not in todo))
        if eligible:
            self._a1_last_cover_stop=p
            for index in sorted(todo,key=lambda i:(math.dist(p,self.points[i]),i)):
                if math.dist(p,self.points[index])>1000.:continue
                old=self.points[index]
                delta=math.atan2(p[1],p[0])-math.atan2(old[1],old[0])
                delta=(delta+math.pi)%(2*math.pi)-math.pi
                if abs(delta)>math.pi/6:continue
                for angle in (0.,delta):
                    proposal=self.points[:]
                    cc,ss=math.cos(angle),math.sin(angle)
                    for j in todo:
                        q=self.points[j]
                        proposal[j]=(cc*q[0]-ss*q[1],ss*q[0]+cc*q[1])
                    proposal[index]=p
                    self.counters['a1_cover_checks']=self.counters.get('a1_cover_checks',0)+1
                    start=time.perf_counter()
                    safe,radius,vertices=a1_cover_certificate(proposal)
                    self.counters['a1_cover_cpu_s']=self.counters.get('a1_cover_cpu_s',0.)+time.perf_counter()-start
                    if not safe:continue
                    assert all(j not in self.scanned[ch] for j in todo for ch in range(1,21)
                               if not self.observations[ch] and ch not in self.cleared)
                    self.points=proposal
                    self.counters['a1_cover_replacements']=self.counters.get('a1_cover_replacements',0)+1
                    self.counters['a1_cover_rotations']=self.counters.get('a1_cover_rotations',0)+int(abs(angle)>1e-10)
                    self.a1_cover_events.append(dict(index=index,old=old,new=p,points=proposal,rotation=angle,
                        covering_radius_upper=radius,vertices=vertices,virtual_time_s=self.virtual_time,
                        unknown=[ch for ch in range(1,21) if not self.observations[ch] and ch not in self.cleared]))
                    self.route_successor=None
                    return 'station',index
        return A1ServiceSpatial.spatial_next_task(self,todo)

class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        if mode==3:return A1RotatingCoverSpatial(env,mode=mode,**merged)
        return _A1_ROTATING_COVER_PARENT(env,mode=mode,**merged)

"""D3 R9: original R7 certified rotation, then bounded minimax fallback."""
_A1_HYBRID_COVER_PARENT=Solver
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

class A1HybridCoverSpatial(A1RotatingCoverSpatial):
    def spatial_next_task(self,todo):
        p=self.position
        eligible=(todo and 0 not in todo and self.virtual_time<180000. and
                  self._a1_last_cover_stop!=p and
                  not any(math.dist(p,self.points[i])<1e-5 for i in range(len(self.points)) if i not in todo))
        if eligible:
            self._a1_last_cover_stop=p
            for index in sorted(todo,key=lambda i:(math.dist(p,self.points[i]),i)):
                if math.dist(p,self.points[index])>1000.:continue
                old=self.points[index]
                delta=math.atan2(p[1],p[0])-math.atan2(old[1],old[0])
                delta=(delta+math.pi)%(2*math.pi)-math.pi
                if abs(delta)>math.pi/6:continue
                for angle in (0.,delta):
                    proposal=self.points[:]
                    cc,ss=math.cos(angle),math.sin(angle)
                    for j in todo:
                        q=self.points[j]
                        proposal[j]=(cc*q[0]-ss*q[1],ss*q[0]+cc*q[1])
                    proposal[index]=p
                    self.counters['a1_cover_checks']=self.counters.get('a1_cover_checks',0)+1
                    start=time.perf_counter()
                    safe,radius,vertices=a1_cover_certificate(proposal)
                    self.counters['a1_cover_cpu_s']=self.counters.get('a1_cover_cpu_s',0.)+time.perf_counter()-start
                    if not safe:continue
                    assert all(j not in self.scanned[ch] for j in todo for ch in range(1,21)
                               if not self.observations[ch] and ch not in self.cleared)
                    self.points=proposal
                    self.counters['a1_cover_replacements']=self.counters.get('a1_cover_replacements',0)+1
                    self.counters['a1_cover_rotations']=self.counters.get('a1_cover_rotations',0)+int(abs(angle)>1e-10)
                    self.a1_cover_events.append(dict(index=index,old=old,new=p,points=proposal,rotation=angle,
                        covering_radius_upper=radius,vertices=vertices,virtual_time_s=self.virtual_time,
                        unknown=[ch for ch in range(1,21) if not self.observations[ch] and ch not in self.cleared]))
                    self.route_successor=None
                    return 'station',index
            if math.hypot(*p)>=800.:
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
        if mode==3:return A1HybridCoverSpatial(env,mode=mode,**merged)
        return _A1_HYBRID_COVER_PARENT(env,mode=mode,**merged)

"""D3 R10: rotated initialization for constrained minimax fallback."""
_A1_ROTATED_MINIMAX_PARENT=Solver
class A1RotatedMinimaxSpatial(A1HybridCoverSpatial):
    def spatial_next_task(self,todo):
        p=self.position
        eligible=(todo and 0 not in todo and self.virtual_time<180000. and
                  self._a1_last_cover_stop!=p and
                  not any(math.dist(p,self.points[i])<1e-5 for i in range(len(self.points)) if i not in todo))
        if eligible:
            self._a1_last_cover_stop=p
            for index in sorted(todo,key=lambda i:(math.dist(p,self.points[i]),i)):
                if math.dist(p,self.points[index])>1000.:continue
                old=self.points[index]
                delta=math.atan2(p[1],p[0])-math.atan2(old[1],old[0])
                delta=(delta+math.pi)%(2*math.pi)-math.pi
                if abs(delta)>math.pi/6:continue
                for angle in (0.,delta):
                    proposal=self.points[:]
                    cc,ss=math.cos(angle),math.sin(angle)
                    for j in todo:
                        q=self.points[j]
                        proposal[j]=(cc*q[0]-ss*q[1],ss*q[0]+cc*q[1])
                    proposal[index]=p
                    self.counters['a1_cover_checks']=self.counters.get('a1_cover_checks',0)+1
                    start=time.perf_counter()
                    safe,radius,vertices=a1_cover_certificate(proposal)
                    self.counters['a1_cover_cpu_s']=self.counters.get('a1_cover_cpu_s',0.)+time.perf_counter()-start
                    if not safe:continue
                    assert all(j not in self.scanned[ch] for j in todo for ch in range(1,21)
                               if not self.observations[ch] and ch not in self.cleared)
                    self.points=proposal
                    self.counters['a1_cover_replacements']=self.counters.get('a1_cover_replacements',0)+1
                    self.counters['a1_cover_rotations']=self.counters.get('a1_cover_rotations',0)+int(abs(angle)>1e-10)
                    self.a1_cover_events.append(dict(index=index,old=old,new=p,points=proposal,rotation=angle,
                        covering_radius_upper=radius,vertices=vertices,virtual_time_s=self.virtual_time,
                        unknown=[ch for ch in range(1,21) if not self.observations[ch] and ch not in self.cleared]))
                    self.route_successor=None
                    return 'station',index
            if math.hypot(*p)>=800.:
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
            if math.hypot(*p)>=800.:
                before_path=None
                for index in sorted(todo,key=lambda i:(math.dist(p,self.points[i]),i))[:2]:
                    if math.dist(p,self.points[index])>1000.:continue
                    old=self.points[index]
                    delta=(math.atan2(p[1],p[0])-math.atan2(old[1],old[0])+math.pi)%(2*math.pi)-math.pi
                    if abs(delta)>math.pi/6 or abs(delta)<1e-8:continue
                    cc,ss=math.cos(delta),math.sin(delta)
                    proposal=self.points[:]
                    for j in todo:
                        q=self.points[j]
                        proposal[j]=(cc*q[0]-ss*q[1],ss*q[0]+cc*q[1])
                    proposal[index]=p
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
                    self.counters['a1_cover_rotated_minimax']=self.counters.get('a1_cover_rotated_minimax',0)+1
                    self.counters['a1_cover_replacements']=self.counters.get('a1_cover_replacements',0)+1
                    self.counters['a1_cover_adaptive_relocations']=self.counters.get('a1_cover_adaptive_relocations',0)+int(iterations>0)
                    self.a1_cover_events.append(dict(index=index,old=old,new=p,points=proposal,minimax_iterations=iterations,pre_rotation=delta,
                        station_path_before=before_path,station_path_after=after_path,
                        covering_radius_upper=radius,vertices=vertices,virtual_time_s=self.virtual_time,
                        unknown=[ch for ch in range(1,21) if not self.observations[ch] and ch not in self.cleared]))
                    self.route_successor=None
                    return 'station',index
        return A1ServiceSpatial.spatial_next_task(self,todo)

class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        if mode==3:return A1RotatedMinimaxSpatial(env,mode=mode,**merged)
        return _A1_ROTATED_MINIMAX_PARENT(env,mode=mode,**merged)

"""D3: shorten a selected station's incoming leg under the same certificate."""
_A1_PARTIAL_STATION_PARENT=Solver
_A1_PARTIAL_SPATIAL_PARENT=A1RotatedMinimaxSpatial

class A1PartialStationSpatial(_A1_PARTIAL_SPATIAL_PARENT):
    def spatial_next_task(self,todo):
        task=super().spatial_next_task(todo)
        if not task or task[0]!='station' or task[1]==0 or self.virtual_time>=180000.:
            return task
        index=task[1]
        p=self.position
        old=self.points[index]
        distance=math.dist(p,old)
        if distance<2.:
            return task
        # The chosen index is still unvisited; all previously scanned sites
        # retain their real coordinates. This cannot invent negative evidence.
        assert index in todo
        assert all(index not in self.scanned[ch] for ch in range(1,21)
                   if not self.observations[ch] and ch not in self.cleared)
        start=time.perf_counter()
        lo,hi=0.,1.
        best=self.points[:]
        safe,radius,vertices=a1_cover_certificate(best)
        self.counters['a1_cover_checks']=self.counters.get('a1_cover_checks',0)+1
        if not safe:
            self.counters['a1_cover_cpu_s']=self.counters.get('a1_cover_cpu_s',0.)+time.perf_counter()-start
            return task
        for _ in range(10):
            t=(lo+hi)/2.
            point=(p[0]+t*(old[0]-p[0]),p[1]+t*(old[1]-p[1]))
            proposal=self.points[:]
            proposal[index]=point
            self.counters['a1_cover_checks']+=1
            accepted,new_radius,new_vertices=a1_cover_certificate(proposal)
            if accepted:
                hi=t;best=proposal;radius=new_radius;vertices=new_vertices
            else:
                lo=t
        self.counters['a1_cover_cpu_s']=self.counters.get('a1_cover_cpu_s',0.)+time.perf_counter()-start
        saved=distance-math.dist(p,best[index])
        if saved<2.:
            return task
        self.points=best
        self.counters['a1_partial_station_moves']=self.counters.get('a1_partial_station_moves',0)+1
        self.counters['a1_partial_incoming_saved_m']=self.counters.get('a1_partial_incoming_saved_m',0.)+saved
        self.a1_cover_events.append(dict(index=index,old=old,new=best[index],points=best,
            partial_incoming_leg=True,incoming_distance_saved_m=saved,
            covering_radius_upper=radius,vertices=vertices,virtual_time_s=self.virtual_time,
            unknown=[ch for ch in range(1,21) if not self.observations[ch] and ch not in self.cleared]))
        # Keep the same selected station and downstream service successor.
        # For a fixed subsequent waypoint, shortening this incoming segment
        # cannot increase the two-edge Euclidean path (triangle inequality).
        # Unknown observations may change later tasks; this is not a whole-run
        # nonregression guarantee and actual candidate evaluation is required.
        return task

class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        if mode==3:return A1PartialStationSpatial(env,mode=mode,**merged)
        return _A1_PARTIAL_STATION_PARENT(env,mode=mode,**merged)
