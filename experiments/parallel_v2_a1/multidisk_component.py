"""Finite optical policies with exact expected first-hit ordering on a surrogate.

The subset dynamic program minimizes path cost weighted by surviving hypothesis
mass. Every continuous cell remains on the returned route; hypotheses never
remove a disk or establish completeness.
"""
_MULTIDISK_PARENT=Solver

class MultiDiskSpatial(ThreeDiskSpatial):
    @staticmethod
    def _expected_order(position,points,targets):
        n=len(points);full=(1<<n)-1
        bits=[sum(1<<i for i,t in enumerate(targets) if math.dist(q,t)<=20.) for q in points]
        union=[0]*(1<<n)
        for mask in range(1,1<<n):
            low=mask&-mask;j=low.bit_length()-1;union[mask]=union[mask^low]|bits[j]
        survive=[1.-b.bit_count()/len(targets) for b in union]
        dp={}
        for j,q in enumerate(points):dp[(1<<j,j)]=(math.dist(position,q)/5.+3.,(j,))
        for mask in range(1,full+1):
            for last in range(n):
                prev=dp.get((mask,last))
                if prev is None:continue
                for j in range(n):
                    if mask>>j&1:continue
                    key=(mask|(1<<j),j)
                    value=(prev[0]+survive[mask]*(math.dist(points[last],points[j])/5.+3.),prev[1]+(j,))
                    if key not in dp or value<dp[key]:dp[key]=value
        best=min(dp[(full,last)] for last in range(n))
        return best[0]+2.,tuple(points[j] for j in best[1])

    def _three_disk_plan(self,ch):
        old=super()._three_disk_plan(ch)
        poly=self.polygons[ch];center,radius=_Q3._sp_enclosing_circle(poly)
        if not (20.<radius<=100.):return old
        a,b=max(((a,b) for i,a in enumerate(poly) for b in poly[i+1:]),key=lambda pair:math.dist(*pair))
        d=math.dist(a,b)
        if d<1e-6:return old
        u=((b[0]-a[0])/d,(b[1]-a[1])/d)
        vals=[u[0]*v[0]+u[1]*v[1] for v in poly];lo,hi=min(vals),max(vals)
        targets=self.belief_quadrature(poly,81)
        good=[t for t in targets if all(math.dist(t,q)>20.-1e-6 for q in self.failed_clear_points[ch])]
        if good:targets=good
        trial=self.trial_point(ch,center,radius)
        fail=[t for t in targets if math.dist(trial,t)>20.]
        base=math.dist(self.position,trial)/5.+3.+2.*(1.-len(fail)/len(targets))+sum(11.+math.dist(trial,t)/5. for t in fail)/len(targets)
        plans=[]
        if old:plans.append((self._sequence_cost(self.position,old,targets),old))
        for count in (4,5,6):
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
        if mode==3:return MultiDiskSpatial(env,mode=mode,**merged)
        return _MULTIDISK_PARENT(env,mode=mode,**merged)
