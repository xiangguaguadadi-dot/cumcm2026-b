"""Extend the finite optical action policy to three certified convex strips."""
_THREEDISK_PARENT=Solver

class ThreeDiskSpatial(TwoDiskSpatial):
    @staticmethod
    def _sequence_cost(position,points,targets):
        total=0.
        for target in targets:
            p=position;cost=0.
            for q in points:
                cost+=math.dist(p,q)/5.+3.;p=q
                if math.dist(q,target)<=20.:
                    cost+=2.;break
            else:cost+=1000. # only a planning penalty; not a certificate
            total+=cost
        return total/len(targets)

    def _three_disk_plan(self,ch):
        poly=self.polygons[ch];center,radius=_Q3._sp_enclosing_circle(poly)
        if not (20.<radius<65.):return None
        a,b=max(((a,b) for i,a in enumerate(poly) for b in poly[i+1:]),key=lambda pair:math.dist(*pair))
        d=math.dist(a,b)
        if d<1e-6:return None
        u=((b[0]-a[0])/d,(b[1]-a[1])/d)
        vals=[u[0]*v[0]+u[1]*v[1] for v in poly];lo,hi=min(vals),max(vals)
        targets=self.belief_quadrature(poly,81)
        good=[t for t in targets if all(math.dist(t,q)>20.-1e-6 for q in self.failed_clear_points[ch])]
        if good:targets=good
        trial=self.trial_point(ch,center,radius)
        fail=[t for t in targets if math.dist(trial,t)>20.]
        base=math.dist(self.position,trial)/5.+3.+2.*(1.-len(fail)/len(targets))+sum(11.+math.dist(trial,t)/5. for t in fail)/len(targets)
        old=self._two_disk_plan(ch)
        plans=[]
        if old:plans.append((self._sequence_cost(self.position,old,targets),old))
        for f1,f2 in ((1/3,2/3),(.3,.65),(.35,.7)):
            b1=lo+f1*(hi-lo);b2=lo+f2*(hi-lo)
            cells=[_Q3._sp_clip(poly,u[0],u[1],b1),_Q3._sp_clip(_Q3._sp_clip(poly,-u[0],-u[1],-b1),u[0],u[1],b2),_Q3._sp_clip(poly,-u[0],-u[1],-b2)]
            if not all(cells):continue
            circles=[_Q3._sp_enclosing_circle(cell) for cell in cells]
            if any(r>20.-1e-5 for c,r in circles):continue
            for order in ((0,1,2),(0,2,1),(1,0,2),(1,2,0),(2,0,1),(2,1,0)):
                points=[];p=self.position
                for k in order:
                    c,r=circles[k];margin=max(0.,20.-r-1e-5);dist=math.dist(p,c)
                    q=p if dist<=margin else (c[0]+margin*(p[0]-c[0])/dist,c[1]+margin*(p[1]-c[1])/dist)
                    if not all(math.dist(q,v)<=20.-1e-6 for v in cells[k]):break
                    points.append(q);p=q
                if len(points)==3:plans.append((self._sequence_cost(self.position,points,targets),tuple(points)))
        if not plans:return None
        best=min(plans)
        if best[0]>=base:return None
        return best[1]

    def _a1_service_round(self,ch):
        if ch in self.cleared:return
        if self._virtual_fallback(ch):return
        plan=self._three_disk_plan(ch)
        if plan is None:return super()._a1_service_round(ch)
        self.counters['three_disk_used']=self.counters.get('three_disk_used',0)+1
        for i,q in enumerate(plan):
            if self.clear(q,ch,certified=i==len(plan)-1):return

class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        if mode==3:return ThreeDiskSpatial(env,mode=mode,**merged)
        return _THREEDISK_PARENT(env,mode=mode,**merged)
