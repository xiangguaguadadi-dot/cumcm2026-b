"""Optimize convex strip direction using minimum-width polygon edge support."""
_ORIENTATION_PARENT=Solver

class OrientationSpatial(MultiDiskSpatial):
    def _three_disk_plan(self,ch):
        old=super()._three_disk_plan(ch)
        poly=self.polygons[ch];center,radius=_Q3._sp_enclosing_circle(poly)
        if not (20.<radius<=100.):return old
        candidates=[]
        for p,q in zip(poly,poly[1:]+poly[:1]):
            length=math.dist(p,q)
            if length<1e-8:continue
            u=((q[0]-p[0])/length,(q[1]-p[1])/length);v=(-u[1],u[0])
            across=[v[0]*t[0]+v[1]*t[1] for t in poly]
            along=[u[0]*t[0]+u[1]*t[1] for t in poly]
            width=max(across)-min(across)
            candidates.append((width,max(along)-min(along),u))
        if not candidates:return old
        u=min(candidates)[2]
        vals=[u[0]*v[0]+u[1]*v[1] for v in poly];lo,hi=min(vals),max(vals)
        targets=self.belief_quadrature(poly,81)
        good=[t for t in targets if all(math.dist(t,q)>20.-1e-6 for q in self.failed_clear_points[ch])]
        if good:targets=good
        trial=self.trial_point(ch,center,radius)
        fail=[t for t in targets if math.dist(trial,t)>20.]
        base=math.dist(self.position,trial)/5.+3.+2.*(1.-len(fail)/len(targets))+sum(11.+math.dist(trial,t)/5. for t in fail)/len(targets)
        plans=[]
        if old:plans.append((self._sequence_cost(self.position,old,targets),old))
        for count in (2,3,4,5,6):
            points=[]
            for k in range(count):
                left=lo+(hi-lo)*k/count;right=lo+(hi-lo)*(k+1)/count
                cell=_Q3._sp_clip(_Q3._sp_clip(poly,-u[0],-u[1],-left),u[0],u[1],right)
                if not cell:break
                c,r=_Q3._sp_enclosing_circle(cell)
                if r>20.-1e-5:break
                margin=max(0.,20.-r-1e-5);dist=math.dist(self.position,c)
                q=self.position if dist<=margin else (c[0]+margin*(self.position[0]-c[0])/dist,c[1]+margin*(self.position[1]-c[1])/dist)
                if not all(math.dist(q,v)<=20.-1e-6 for v in cell):break
                points.append(q)
            if len(points)==count:plans.append(self._expected_order(self.position,points,targets))
        if not plans:return None
        best=min(plans)
        return best[1] if best[0]<base else None

class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        if mode==3:return OrientationSpatial(env,mode=mode,**merged)
        return _ORIENTATION_PARENT(env,mode=mode,**merged)
