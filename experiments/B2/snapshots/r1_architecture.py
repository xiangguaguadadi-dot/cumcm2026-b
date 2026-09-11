"""B2: certified adaptive optical partitions. Only legal black-box observations.
Two local immutable parent modules are declared deployment dependencies.
"""
import importlib.util
import math
from pathlib import Path

def _parent(name):
    path=Path(__file__).resolve().parent/(name+'.py')
    spec=importlib.util.spec_from_file_location('b2_'+name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod
_A1=_parent('parent_a1');_A4=_parent('parent_a4')
OPTIMIZED_CONFIGS={3:dict(_A1.OPTIMIZED_CONFIGS[3]),4:dict(_A4.OPTIMIZED_CONFIGS[4],optical_partition='adaptive')}
BASELINE_CONFIG=dict(_A1.BASELINE_CONFIG)
dist=_A4.dist;clip=_A4.clip;enclosing_circle=_A4.enclosing_circle

class DirectionalSolver(_A4.Solver):
    def __init__(self,env,mode=4,**config):
        super().__init__(env,mode,**{**OPTIMIZED_CONFIGS[4],**config})

    def partition_points(self,ch,strategy):
        origin,deg=self.observations[ch][0]
        angle=math.radians(deg);u=(math.cos(angle),math.sin(angle));v=(-u[1],u[0])
        local=[((p[0]-origin[0])*u[0]+(p[1]-origin[1])*u[1],
                (p[0]-origin[0])*v[0]+(p[1]-origin[1])*v[1]) for p in self.polygons[ch]]
        global_point=lambda p:(origin[0]+p[0]*u[0]+p[1]*v[0],origin[1]+p[0]*u[1]+p[1]*v[1])
        points=[]
        if strategy=='naive28':
            spacing=28.0
            lo=[math.floor((min(p[d] for p in local)-spacing/2)/spacing) for d in (0,1)]
            hi=[math.ceil((max(p[d] for p in local)+spacing/2)/spacing) for d in (0,1)]
            for i in range(lo[0],hi[0]+1):
                js=range(lo[1],hi[1]+1) if i%2==0 else range(hi[1],lo[1]-1,-1)
                for j in js:
                    test=local
                    for a,b,c in [(1,0,(i+.5)*spacing),(-1,0,(-i+.5)*spacing),(0,1,(j+.5)*spacing),(0,-1,(-j+.5)*spacing)]:
                        test=clip(test,a,b,c)
                    if test:points.append((i*spacing,j*spacing))
        else:
            ymin=min(p[1] for p in local);ymax=max(p[1] for p in local)
            bands=max(1,math.ceil((ymax-ymin)/28.0))
            if bands>3:return None
            for j in range(bands):
                lower=ymin+(ymax-ymin)*j/bands
                upper=ymin+(ymax-ymin)*(j+1)/bands
                band=clip(clip(local,0,-1,-lower),0,1,upper)
                if not band:continue
                left=min(p[0] for p in band);end=max(p[0] for p in band)
                # Each strip is <=28m high. A 20m-wide rectangle has radius
                # sqrt(10^2+14^2)<20, so every nonterminal advance is >=20m.
                for iteration in range(40):
                    remainder=clip(band,-1,0,-left)
                    center,radius=enclosing_circle(remainder)
                    if radius<=19.9999:
                        points.append(center);left=end;break
                    low=left;high=min(end,left+40.0)
                    for _ in range(23):
                        right=(low+high)/2
                        cell=clip(remainder,1,0,right)
                        if not cell:low=right;continue
                        center,radius=enclosing_circle(cell)
                        if radius<=19.9999:low=right
                        else:high=right
                    if low-left<1e-5:return None
                    cell=clip(remainder,1,0,low)
                    center,radius=enclosing_circle(cell)
                    if radius>19.99991:return None
                    points.append(center);left=low
                if left<end-1e-6:return None
            points.sort(key=lambda p:(p[0],p[1]))
        self.counters['partition_points_proposed']=self.counters.get('partition_points_proposed',0)+len(points)
        return [global_point(p) for p in points]

    def optical_points(self,ch):
        parent=super().optical_points(ch)
        strategy=self.config.get('optical_partition','adaptive')
        if (strategy=='parent25' or self.virtual_time>=_A4.VIRTUAL_SAFE_SWITCH_S
                or enclosing_circle(self.polygons[ch])[1]>300):
            return parent
        points=self.partition_points(ch,strategy)
        if not points or len(points)>100:
            self.counters['partition_rejected']=self.counters.get('partition_rejected',0)+1
            return parent
        # Bound the complete two-ended route before any action is executed.
        # Parent fallback remains valid after the common virtual switch.
        def bound(q):
            return min(dist(self.position,q[0]),dist(self.position,q[-1]))/5+2*sum(dist(a,b) for a,b in zip(q,q[1:]))/5+3*len(q)+2
        if bound(points)>min(10000.0,bound(parent)+1000):
            self.counters['partition_rejected']=self.counters.get('partition_rejected',0)+1
            return parent
        self.counters['partition_calls']=self.counters.get('partition_calls',0)+1
        self.counters['partition_parent_points']=self.counters.get('partition_parent_points',0)+len(parent)
        self.counters['partition_used_points']=self.counters.get('partition_used_points',0)+len(points)
        return points

class Solver:
    def __new__(cls,env,mode=3,**config):
        if mode==3:return _A1.Solver(env,mode=mode,**config)
        if mode==4:return DirectionalSolver(env,mode=mode,**config)
        raise ValueError('mode must be 3 or 4')
