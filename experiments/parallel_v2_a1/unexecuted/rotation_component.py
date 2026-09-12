"""Q3 rotationally equivalent discovery cover chosen from observed geometry."""
_ROTATION_PARENT=Solver
ROTATION_TIMING='origin'

class RotationSpatial(GuardedSpatial):
    def __init__(self,env,mode=3,**config):
        super().__init__(env,mode=mode,**config);self._phase_chosen=False

    def _choose_phase(self):
        if self._phase_chosen:return
        self._phase_chosen=True
        if any(i!=0 for ids in self.scanned.values() for i in ids):return
        known=[c for c in range(1,21) if self.observations[c] and c not in self.cleared]
        if not known:return
        centers=[_Q3._sp_enclosing_circle(self.polygons[c])[0] for c in known]
        original=list(self.points);plans=[]
        for k in range(12):
            angle=math.pi*k/36.;co,si=math.cos(angle),math.sin(angle)
            points=[original[0]]+[(co*x-si*y,si*x+co*y) for x,y in original[1:]]
            value=self._phase_tour(points[1:]+centers)
            plans.append((value,k,points))
        value,k,points=min(plans)
        if value<plans[0][0]-1e-6:
            self.points=points
            self.counters['rotation_degrees']=5*k
            self.counters['rotation_proxy_gain_m']=plans[0][0]-value

    def _phase_tour(self,targets):
        points=[self.position]+targets;n=len(targets)
        ds=[[math.dist(a,b) for b in points] for a in points]
        greedy=[];todo=set(range(1,n+1));p=0
        while todo:
            q=min(todo,key=lambda q:(ds[p][q],q));todo.remove(q);greedy.append(q);p=q
        def improve(route):
            route=route[:]
            for _ in range(60):
                best=None;delta=0.
                for i in range(n-1):
                    before=0 if i==0 else route[i-1];a=route[i]
                    for j in range(i+1,n):
                        b=route[j];change=ds[before][b]-ds[before][a]
                        if j+1<n:
                            after=route[j+1];change+=ds[a][after]-ds[b][after]
                        if change<delta-1e-7:delta=change;best=(i,j)
                if best is None:break
                i,j=best;route[i:j+1]=reversed(route[i:j+1])
            return route
        routes=[improve(r) for r in (greedy,list(range(1,n+1)),list(range(n,0,-1)))]
        def length(route):return ds[0][route[0]]+sum(ds[a][b] for a,b in zip(route,route[1:]))
        return min(map(length,routes))

    def scan_station(self,index,defer=False):
        result=super().scan_station(index,defer=defer)
        if index==0 and ROTATION_TIMING=='origin':self._choose_phase()
        return result

    def spatial_next_task(self,todo):
        task=super().spatial_next_task(todo)
        if ROTATION_TIMING=='first_station' and not self._phase_chosen and task[0]=='station' and task[1]!=0:
            self._choose_phase();task=super().spatial_next_task(todo)
        return task

class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        if mode==3:return RotationSpatial(env,mode=mode,**merged)
        return _ROTATION_PARENT(env,mode=mode,**merged)
