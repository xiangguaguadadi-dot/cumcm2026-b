"""Conservative no-signal geometry from convex receive footprints.

The receive disk or half-disk contains its source s and every positive station.
Thus a no-signal q cannot belong to triangle(s, p1, p2). The forbidden source
positions form q + cone(q-p1, q-p2). Remove that wedge, then take the convex hull
of the remaining polygons, which is an outer approximation of all true sources.
"""
import importlib.util,math
from pathlib import Path
_path=Path(__file__).resolve().parents[2]/'20260911_stage4/baseline/S1.py'
_spec=importlib.util.spec_from_file_location('e3_convex_s1',_path)
_s1=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_s1)
_d=_s1._A4
BASELINE_CONFIG=dict(_s1.BASELINE_CONFIG)
OPTIMIZED_CONFIGS={m:dict(c,convex_no_signal=True) for m,c in _s1.OPTIMIZED_CONFIGS.items()}

def exclude_forced_visible_wedge(poly,p1,p2,q):
    v1=(q[0]-p1[0],q[1]-p1[1]);v2=(q[0]-p2[0],q[1]-p2[1])
    cross=v1[0]*v2[1]-v1[1]*v2[0]
    if abs(cross)<=1e-8*max(1.,math.hypot(*v1)*math.hypot(*v2)):
        return poly
    if cross<0:v1,v2=v2,v1
    constraints=[(v1[1],-v1[0]),(-v2[1],v2[0])]
    fragments=[]
    for a,b in constraints:
        c=a*q[0]+b*q[1]
        # Outside each wedge half-plane, with a conservative 1e-6 m margin.
        fragments+=_d._di_clip(poly,-a,-b,-c+1e-6*math.hypot(a,b))
    return _s1._A1._geo_convex_hull(fragments)

def area(poly):
    return abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(poly,poly[1:]+poly[:1])))/2

class _Directional(_d._LensDirectional):
    def measure(self,p,ch):
        kind=super().measure(p,ch)
        if self.config.get('convex_no_signal',True) and kind in ('direction','no_signal'):
            self.refine_no_signal(ch)
        return kind
    def refine_no_signal(self,ch):
        if ch not in self.polygons or len(self.observations[ch])<2 or not self.no_signal_points[ch]:return
        poly=self.polygons[ch];before=area(poly)
        positives=[p for p,_ in self.observations[ch][-8:]]
        for q in self.no_signal_points[ch][-24:]:
            for i,p1 in enumerate(positives):
                for p2 in positives[i+1:]:
                    new=exclude_forced_visible_wedge(poly,p1,p2,q)
                    if not new:raise RuntimeError('Convex footprint constraints exclude all source positions')
                    poly=new
        self.polygons[ch]=poly
        after=area(poly)
        self.counters['convex_negative_updates']=self.counters.get('convex_negative_updates',0)+1
        if after<before-1e-6:self.counters['convex_negative_shrinks']=self.counters.get('convex_negative_shrinks',0)+1
        self.counters['convex_negative_area_removed']=self.counters.get('convex_negative_area_removed',0.)+max(0.,before-after)
        # The existing probabilistic planning cache must reflect the new hull.
        self._visibility_cache.pop(ch,None)
class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        return _s1.Solver(env,mode=mode,**merged) if mode==3 else _Directional(env,mode=mode,**merged)
