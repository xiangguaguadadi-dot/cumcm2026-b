"""Finite two-disk optical decision policy over the entire bounded polygon.

Splitting polygon cells and enclosing each cell in radius < 20 m circles is a
continuous certificate. Finite samples are used only for expected-cost ordering.
"""
_TWODISK_PARENT=Solver

class TwoDiskSpatial(A1ServiceSpatial):
    def _two_disk_plan(self,ch):
        poly=self.polygons[ch]
        center,radius=_Q3._sp_enclosing_circle(poly)
        if not (20.<radius<45.):return None
        a,b=max(((a,b) for i,a in enumerate(poly) for b in poly[i+1:]),key=lambda pair:math.dist(*pair))
        d=math.dist(a,b)
        if d<1e-6:return None
        u=((b[0]-a[0])/d,(b[1]-a[1])/d)
        values=[u[0]*v[0]+u[1]*v[1] for v in poly];lo,hi=min(values),max(values)
        targets=self.belief_quadrature(poly,81)
        valid=[t for t in targets if all(math.dist(t,q)>20.-1e-6 for q in self.failed_clear_points[ch])]
        if valid:targets=valid
        # The one-trial plus immediate bearing/correction comparator is a
        # planning model; it never modifies the feasible set or exit condition.
        fail=[t for t in targets if math.dist(center,t)>20.]
        base=math.dist(self.position,center)/5.+3.+2.*(1.-len(fail)/len(targets))
        base+=sum(11.+math.dist(center,t)/5. for t in fail)/len(targets)
        plans=[]
        for frac in (.35,.425,.5,.575,.65):
            cut=lo+frac*(hi-lo)
            cells=[_Q3._sp_clip(poly,u[0],u[1],cut),_Q3._sp_clip(poly,-u[0],-u[1],-cut)]
            if not all(cells):continue
            circles=[_Q3._sp_enclosing_circle(cell) for cell in cells]
            if any(r>20.-1e-5 for c,r in circles):continue
            for order in ((0,1),(1,0)):
                c1,r1=circles[order[0]];c2,r2=circles[order[1]]
                # Standoff stays inside an inscribed service disk, therefore
                # still covers every vertex of the corresponding full cell.
                margin=max(0.,20.-r1-1e-5);distance=math.dist(self.position,c1)
                if distance<=margin:q1=self.position
                elif distance>0:q1=(c1[0]+margin*(self.position[0]-c1[0])/distance,c1[1]+margin*(self.position[1]-c1[1])/distance)
                else:q1=c1
                margin=max(0.,20.-r2-1e-5);distance=math.dist(q1,c2)
                if distance<=margin:q2=q1
                elif distance>0:q2=(c2[0]+margin*(q1[0]-c2[0])/distance,c2[1]+margin*(q1[1]-c2[1])/distance)
                else:q2=c2
                # Convex norm maximum over a convex polygon occurs at a vertex.
                if not all(math.dist(q1,v)<=20.-1e-6 for v in cells[order[0]]):continue
                if not all(math.dist(q2,v)<=20.-1e-6 for v in cells[order[1]]):continue
                p=sum(math.dist(q1,t)<=20. for t in targets)/len(targets)
                cost=math.dist(self.position,q1)/5.+3.+p*2.+(1.-p)*(math.dist(q1,q2)/5.+5.)
                plans.append((cost,q1,q2))
        if not plans:return None
        best=min(plans)
        self.counters['two_disk_feasible']=self.counters.get('two_disk_feasible',0)+1
        if best[0]>=base:return None
        return best[1:]

    def _a1_service_round(self,ch):
        if ch in self.cleared:return
        plan=self._two_disk_plan(ch)
        if plan is None:return super()._a1_service_round(ch)
        self.counters['two_disk_used']=self.counters.get('two_disk_used',0)+1
        q1,q2=plan
        if self.clear(q1,ch):return
        # Source lay in the original polygon, partitioned into two covered
        # cells. Failure at q1 leaves it in q2's disk, even across overlap.
        self.clear(q2,ch,certified=True)

class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        if mode==3:return TwoDiskSpatial(env,mode=mode,**merged)
        return _TWODISK_PARENT(env,mode=mode,**merged)
