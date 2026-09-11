
# R3 keeps actual failed optical disks. Radio no_signal never excludes a Q4 disk.
_FrozenR2Solver=Solver
class FailureDirectional(ServiceDirectional):
    def __init__(self,env,mode=4,**config):
        super().__init__(env,mode=mode,**config)
        self._e2_failed_clear={c:[] for c in range(1,21)}

    def _e2_refine_failures(self,ch):
        if not self.config.get('e2_failure_hull',False) or ch not in self.polygons:return
        poly=self.polygons[ch]
        for p in self._e2_failed_clear[ch]:
            if len(poly)>96:break
            result=_Q3._geo_outside_disk_hull(poly,p,20.-1e-6)
            if not result:raise RuntimeError('Failed clear contradicts retained location geometry')
            if len(result)<=96:poly=result
        self.polygons[ch]=poly

    def measure(self,p,ch):
        kind=super().measure(p,ch)
        if kind=='direction':self._e2_refine_failures(ch)
        return kind

    def clear(self,p,ch,certified=False):
        ok=super().clear(p,ch,certified=certified)
        if not ok:
            self._e2_failed_clear[ch].append(tuple(map(float,p)))
            self._e2_refine_failures(ch)
        return ok

    def _e2_cell_excluded(self,test,origin,u,v,ch):
        if not self.config.get('e2_failure_cells',False):return False
        world=[(origin[0]+q[0]*u[0]+q[1]*v[0],origin[1]+q[0]*u[1]+q[1]*v[1]) for q in test]
        # test is the full convex polygon/cell intersection. A disk is convex,
        # so vertex containment certifies all of that cell's feasible portion.
        excluded=any(all(math.dist(p,q)<=20.-1e-6 for q in world) for p in self._e2_failed_clear[ch])
        if excluded:self.counters['e2_excluded_cells']=self.counters.get('e2_excluded_cells',0)+1
        return excluded

    def optical_points(self,ch):
        """Conservative 25m lattice cover, shared by cost selection and fallback."""
        poly = self.polygons[ch]
        # Rotate coordinates along the first bearing, making the narrow wedge
        # bounding rectangle far smaller than its axis-aligned rectangle.
        origin,deg=self.observations[ch][0]
        angle=math.radians(deg)
        u=(math.cos(angle),math.sin(angle)); v=(-u[1],u[0])
        local=[((p[0]-origin[0])*u[0]+(p[1]-origin[1])*u[1],
                (p[0]-origin[0])*v[0]+(p[1]-origin[1])*v[1]) for p in poly]
        spacing=25.0
        lo=[math.floor((min(p[d] for p in local)-spacing/2)/spacing) for d in [0,1]]
        hi=[math.ceil((max(p[d] for p in local)+spacing/2)/spacing) for d in [0,1]]
        candidates=[]
        for i in range(lo[0],hi[0]+1):
            row=range(lo[1],hi[1]+1) if i%2==0 else range(hi[1],lo[1]-1,-1)
            for j in row:
                test=local
                for a,b,c in [(1,0,(i+.5)*spacing),(-1,0,(-i+.5)*spacing),
                              (0,1,(j+.5)*spacing),(0,-1,(-j+.5)*spacing)]:
                    test=_Q4._di_clip(test,a,b,c)
                if test and not self._e2_cell_excluded(test,origin,u,v,ch):
                    candidates.append((origin[0]+i*spacing*u[0]+j*spacing*v[0],
                                       origin[1]+i*spacing*u[1]+j*spacing*v[1]))
        return candidates

class Solver:
    def __new__(cls,env,mode=3,**config):
        if mode not in (3,4):raise ValueError('mode must be 3 or 4')
        if mode==3:return _FrozenR2Solver(env,mode=mode,**config)
        return FailureDirectional(env,mode=mode,**{**OPTIMIZED_CONFIGS[mode],**config})
