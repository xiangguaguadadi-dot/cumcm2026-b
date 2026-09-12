"""Standalone Q2 bounded-error design audit, standard library only.

Uses direct convex polygon clipping of the first sector and every possible
second reported bearing. A thin annular sector is represented by its convex
hull (near r=5 arc sagitta < 0.000762 m). Radial arc can be inscribed or
circumscribed to check numerical geometry sensitivity. This is a discrete
optimization audit, not a certificate of continuous global optimality.
"""
import math, json, time, os, sys

D = math.pi / 180
R = 1500.0

def clip(poly, a, b, c):
    if not poly: return []
    out = []
    px, py = poly[-1]; pv = a*px+b*py-c
    for x,y in poly:
        v = a*x+b*y-c
        if (v >= -1e-10) != (pv >= -1e-10):
            u = pv/(pv-v)
            out.append((px+u*(x-px), py+u*(y-py)))
        if v >= -1e-10: out.append((x,y))
        px,py,pv = x,y,v
    return out

def sector(n=32, outer=False):
    if outer:
        # Tangent polygon outside the circular arc; tangent contacts include
        # the two angular endpoints. Thus enclosure includes the true sector.
        arc = [(R*math.cos(-D), R*math.sin(-D))]
        for k in range(n):
            a = -D + 2*D*(k+.5)/n
            rr=R/math.cos(D/n)
            arc.append((rr*math.cos(a),rr*math.sin(a)))
        arc.append((R*math.cos(D),R*math.sin(D)))
    else:
        arc=[(R*math.cos(-D+2*D*k/n),R*math.sin(-D+2*D*k/n)) for k in range(n+1)]
    return [(5*math.cos(D),-5*math.sin(D))]+arc+[(5*math.cos(D),5*math.sin(D))]

def posterior(q, z, poly, delta2=D):
    # cross(lower_ray, p-q) >= 0, cross(upper_ray,p-q) <= 0.
    lo=z-delta2; hi=z+delta2
    a,b=-math.sin(lo), math.cos(lo)
    p=clip(poly,a,b,a*q[0]+b*q[1])
    a,b=math.sin(hi),-math.cos(hi)
    p=clip(p,a,b,a*q[0]+b*q[1])
    # A normal second report implies r2 > 5. The chord replaces the tiny
    # inner circular arc with its convex hull, max sagitta 5(1-cos D).
    a,b=math.cos(z),math.sin(z)
    return clip(p,a,b,a*q[0]+b*q[1]+5*math.cos(delta2))

def diameter(poly):
    val=0.; pair=None
    for i,(x,y) in enumerate(poly):
        for p in poly[i+1:]:
            d=(p[0]-x)**2+(p[1]-y)**2
            if d>val: val=d; pair=[(x,y),p]
    return math.sqrt(val),pair

def mec(poly):
    # Exact minimum circle of finite polygon vertices by support enumeration.
    if not poly:return 0.,None
    if len(poly)==1:return 0.,poly[0]
    diameter_value,pair=diameter(poly)
    if pair is None:return 0.,poly[0]
    c=((pair[0][0]+pair[1][0])/2,(pair[0][1]+pair[1][1])/2)
    r2=diameter_value**2/4
    if all((p[0]-c[0])**2+(p[1]-c[1])**2<=r2+1e-7 for p in poly):
        return diameter_value/2,c
    best=float('inf'); bc=None
    def test(c,r2):
        nonlocal best,bc
        if r2<best and all((p[0]-c[0])**2+(p[1]-c[1])**2 <= r2+1e-7 for p in poly):
            best,bc=r2,c
    for i,p in enumerate(poly):
        for j in range(i+1,len(poly)):
            q=poly[j]; c=((p[0]+q[0])/2,(p[1]+q[1])/2)
            test(c,(p[0]-c[0])**2+(p[1]-c[1])**2)
            for r in poly[j+1:]:
                bx,by=q[0]-p[0],q[1]-p[1]; cx,cy=r[0]-p[0],r[1]-p[1]
                det=2*(bx*cy-by*cx)
                if abs(det)<1e-10:continue
                b2=bx*bx+by*by;c2=cx*cx+cy*cy
                ux=(b2*cy-c2*by)/det;uy=(bx*c2-cx*b2)/det
                test((p[0]+ux,p[1]+uy),ux*ux+uy*uy)
    return math.sqrt(best),bc

def safe(q):
    x,y=q;l2=x*x+y*y
    return l2<=1000000+1e-7 and l2<=2000*(x*math.cos(D)-abs(y)*math.sin(D))+1e-7

def angular_range(q,poly):
    # q above/below first narrow wedge; use fixed reference to unwrap.
    ref=math.atan2(-q[1],750-q[0])
    angles=[ref+math.remainder(math.atan2(y-q[1],x-q[0])-ref,2*math.pi) for x,y in poly]
    if max(angles)-min(angles)>math.pi+1e-8:
        return -math.pi,math.pi
    return min(angles)-D,max(angles)+D

def worst(q, nobs=500, narc=16, refine=True, with_mec=False, outer=False):
    poly=sector(narc,outer);lo,hi=angular_range(q,poly)
    step=(hi-lo)/nobs
    # Angular endpoints of all polygon vertices, +/- D, capture active-boundary
    # changes which a uniform grid can otherwise narrowly miss.
    zs=[lo+step*i for i in range(nobs+1)]
    ref=(lo+hi)/2
    for x,y in poly:
        a=ref+math.remainder(math.atan2(y-q[1],x-q[0])-ref,2*math.pi)
        zs.extend([a-D,a+D])
    vals=[]
    fn=(lambda p:mec(p)[0]) if with_mec else (lambda p:diameter(p)[0])
    for z in zs:
        p=posterior(q,z,poly)
        vals.append((fn(p),z))
    vals.sort(reverse=True)
    best,z=vals[0]
    if refine:
        # Golden-section local maxima in intervals around the eight best grid
        # outcomes; multiple starts reduce missed narrow maxima.
        for _,zz in vals[:8]:
            a=max(lo,zz-step);b=min(hi,zz+step)
            ratio=(math.sqrt(5)-1)/2
            c=b-ratio*(b-a);e=a+ratio*(b-a)
            fc=fn(posterior(q,c,poly));fe=fn(posterior(q,e,poly))
            for _ in range(36):
                if fc>fe:
                    b=e;e=c;fe=fc;c=b-ratio*(b-a);fc=fn(posterior(q,c,poly))
                else:
                    a=c;c=e;fc=fe;e=a+ratio*(b-a);fe=fn(posterior(q,e,poly))
            v=max(fc,fe);zz=c if fc>fe else e
            if v>best:best,z=v,zz
    p=posterior(q,z,poly)
    diam,pair=diameter(p)
    rad,center=mec(p)
    return dict(q=q,move=math.hypot(*q),angle_deg=math.degrees(math.atan2(q[1],q[0])),safe=safe(q),worst_metric=best,metric='mec_radius' if with_mec else 'diameter',bearing_deg=math.degrees(z)%360,diameter=diam,mec_radius=rad,center=center,pair=pair,polygon=p,nobs=nobs,narc=narc,outer=outer)

def polar(l,a):return (l*math.cos(a*D),l*math.sin(a*D))

def main():
    outdir=os.path.dirname(__file__);start=time.time()
    budget=math.hypot(600,300)
    rows=[]
    # 1 degree candidate grid, then 0.05 degrees around each budget winner.
    for length in [300.,500.,budget,800.,1000.]:
        maxa=math.degrees(math.acos(length/2000))-1
        angs=[float(i) for i in range(1,math.floor(maxa)+1)]+[maxa]
        rr=[worst(polar(length,a),nobs=160,narc=8) for a in angs]
        win=min(rr,key=lambda r:r['worst_metric'])
        aa=win['angle_deg']
        refine_angles=[aa+k*.05 for k in range(-20,21) if 0<aa+k*.05<=maxa]
        rr.extend(worst(polar(length,a),nobs=320,narc=16) for a in refine_angles)
        win=min(rr,key=lambda r:r['worst_metric'])
        rows.extend(rr)
        print(json.dumps(dict(stage='candidate_search',length=length,best=win),ensure_ascii=False),flush=True)
    selected=[('default',(600.,300.)),('straight',(budget,0.))]
    for ll in [budget,1000.]:
        aa=math.acos(3*R*ll*math.cos(D)/(2*R*R+ll*ll))/D
        selected.append(('analytic_linear_length_'+str(ll),polar(ll,aa)))
    for length in [300.,500.,budget,800.,1000.]:
        win=min([r for r in rows if abs(r['move']-length)<1e-5],key=lambda r:r['worst_metric'])
        selected.append(('optimized_length_'+str(length),win['q']))
    audited=[]
    for name,q in selected:
        for nobs,narc,out in [(1200,32,False),(3600,128,False),(3600,128,True)]:
            r=worst(q,nobs,narc,outer=out);r['name']=name;audited.append(r)
            print(json.dumps(dict(stage='audit',result=r),ensure_ascii=False),flush=True)
    # Direct MEC optimization for finalists: avoid assuming radius = D/2.
    mec_audits=[]
    for name,q in selected:
        r=worst(q,700,32,with_mec=True);r['name']=name;mec_audits.append(r)
        print(json.dumps(dict(stage='mec_audit',result=r),ensure_ascii=False),flush=True)
    result=dict(first_angle_deg=0,delta_deg=1,source_radial_range=[5,1500],elapsed_seconds=time.time()-start,candidate_rows=rows,audits=audited,mec_audits=mec_audits)
    with open(os.path.join(outdir,'results.json'),'w') as f:json.dump(result,f,indent=2)

if __name__=='__main__':main()
