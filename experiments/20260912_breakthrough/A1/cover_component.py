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
