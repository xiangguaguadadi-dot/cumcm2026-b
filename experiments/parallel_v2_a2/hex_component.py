# Triangular lattice Voronoi cells: circumradius R<20, inradius sqrt(3)*R/2.
# Every source lies in one of these regular closed hexagons, whose six vertices
# are <=R from its center. Only empty polygon-cell intersections or cells
# entirely inside a recorded failed-clear disk are discarded.
class HexDirectional(RotationDirectional):
    def _hex_points(self,ch,phase='anchor',rotation=0.):
        poly=self.polygons[ch];origin,deg=self.observations[ch][0]
        if phase=='center':origin=_C7._Q4._di_enclosing_circle(poly)[0]
        angle=math.radians(deg)+rotation
        u=(math.cos(angle),math.sin(angle));v=(-u[1],u[0])
        local=[((p[0]-origin[0])*u[0]+(p[1]-origin[1])*u[1],(p[0]-origin[0])*v[0]+(p[1]-origin[1])*v[1]) for p in poly]
        radius=19.999;dx=1.5*radius;dy=math.sqrt(3)*radius;inrad=dy/2
        normals=[(math.cos(math.pi/6+k*math.pi/3),math.sin(math.pi/6+k*math.pi/3)) for k in range(6)]
        ilo=math.floor((min(p[0] for p in local)-radius)/dx);ihi=math.ceil((max(p[0] for p in local)+radius)/dx)
        jlo=math.floor((min(p[1] for p in local)-radius)/dy)-1;jhi=math.ceil((max(p[1] for p in local)+radius)/dy)+1
        result=[]
        for i in range(ilo,ihi+1):
            js=range(jlo,jhi+1) if i%2==0 else range(jhi,jlo-1,-1)
            for j in js:
                x=i*dx;y=(j+.5*(i%2))*dy;cell=local
                for a,b in normals:
                    cell=_C7._Q4._di_clip(cell,a,b,a*x+b*y+inrad)
                    if not cell:break
                if cell and not self._e2_cell_excluded(cell,origin,u,v,ch):
                    result.append((origin[0]+x*u[0]+y*v[0],origin[1]+x*u[1]+y*v[1]))
        return result

    def optical_points(self,ch):
        style=self.config.get('hex_style','anchor')
        if style!='portfolio':return self._hex_points(ch,style)
        candidates=[super().optical_points(ch),self._hex_points(ch,'anchor'),self._hex_points(ch,'center'),self._hex_points(ch,'center',math.pi/6)]
        weights={}
        for s,n,lo,hi,w in self.visibility_hypotheses(ch):
            if not any(math.dist(s,p)<=20 for p in self._e2_failed_clear[ch]):weights[s]=weights.get(s,0.)+w
        if not weights:weights={p:1. for p in self.polygons[ch]}
        def score(points):
            remaining=dict(weights);total=0.;prev=self.position
            for p in self.optical_route(ch,points):
                cost=math.dist(prev,p)/5+3;total+=cost*sum(remaining.values());prev=p
                remaining={q:w for q,w in remaining.items() if math.dist(p,q)>20}
            return total
        return min(candidates,key=score)
