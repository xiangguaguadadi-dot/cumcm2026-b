# Safe additional negative-signal information from the public minimum RF radius.
def minradius_forbidden_constraints(p1,p2,q,whole_polygon_safe=False,sides=16):
    v1=(p1[0]-q[0],p1[1]-q[1]);v2=(p2[0]-q[0],p2[1]-q[1])
    cross=v1[0]*v2[1]-v1[1]*v2[0]
    if abs(cross)<=1e-8*max(1.,math.hypot(*v1)*math.hypot(*v2)):return None
    if cross<0:p1,p2=p2,p1;v1,v2=v2,v1
    constraints=[]
    for a,b in [(v1[1],-v1[0]),(-v2[1],v2[0])]:
        norm=math.hypot(a,b);constraints.append((a,b,a*q[0]+b*q[1]-1e-4*norm))
    # Strictly beyond the positive-observation segment, away from q.
    dx,dy=p2[0]-p1[0],p2[1]-p1[1];a,b=dy,-dx;c=a*p1[0]+b*p1[1]
    if a*q[0]+b*q[1]<c:a,b,c=-a,-b,-c
    norm=math.hypot(a,b)
    if norm<=1e-8:return None
    constraints.append((a,b,c-1e-4*norm))
    if not whole_polygon_safe:
        apothem=999.99*math.cos(math.pi/sides)
        for k in range(sides):
            a,b=math.cos(2*math.pi*k/sides),math.sin(2*math.pi*k/sides)
            constraints.append((a,b,a*q[0]+b*q[1]+apothem))
    return constraints

def exclude_convex_inner_region(poly,constraints):
    if not constraints:return poly
    # If every original vertex survives, convexifying the remainder returns P.
    if not any(all(a*x+b*y<c-1e-6*math.hypot(a,b) for a,b,c in constraints) for x,y in poly):return poly
    fragments=[]
    for a,b,c in constraints:
        fragments.extend(_C7._Q4._di_clip(poly,-a,-b,-c+1e-6*math.hypot(a,b)))
    if not fragments:raise RuntimeError('Minimum-radius negative information contradicts all positions')
    return _C7._Q3._geo_convex_hull(fragments)

class MinRadiusDirectional(HexDirectional):
    def refine_no_signal(self,ch):
        super().refine_no_signal(ch)
        if ch not in self.polygons or len(self.observations[ch])<2:return
        poly=self.polygons[ch];before=_C7.area(poly);positive=[p for p,_ in self.observations[ch][-6:]]
        for _ in range(self.config.get('minradius_passes',1)):
            old=poly
            for q in self.no_signal_points[ch][-16:]:
                whole=all(math.dist(p,q)<=999.99 for p in poly)
                if not whole and not self.config.get('minradius_partial',False):continue
                if min(math.dist(p,q) for p in poly)>1000+2*max(math.dist(poly[0],p) for p in poly):continue
                for i,p1 in enumerate(positive):
                    for p2 in positive[i+1:]:
                        constraints=minradius_forbidden_constraints(p1,p2,q,whole,self.config.get('minradius_sides',16))
                        new=exclude_convex_inner_region(poly,constraints)
                        self.counters['minradius_negative_pairs']=self.counters.get('minradius_negative_pairs',0)+1
                        poly=new
            if poly==old:break
        self.polygons[ch]=poly;after=_C7.area(poly)
        if after<before-1e-6:
            self.counters['minradius_negative_shrinks']=self.counters.get('minradius_negative_shrinks',0)+1
            self.counters['minradius_negative_area']=self.counters.get('minradius_negative_area',0.)+before-after
            self._visibility_cache.pop(ch,None)
