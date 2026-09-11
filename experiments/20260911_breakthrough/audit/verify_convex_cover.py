"""Independent exact checker for B3 square/convex-hull coverage certificates.
No source generation, solver execution, or imports from the author's verifier.
"""
from pathlib import Path
from decimal import Decimal
import argparse,hashlib,json,math

def hull(points):
    def cross(o,a,b):return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    points=sorted(set(points))
    lower=[]
    for p in points:
        while len(lower)>1 and cross(lower[-2],lower[-1],p)<=0:lower.pop()
        lower.append(p)
    upper=[]
    for p in reversed(points):
        while len(upper)>1 and cross(upper[-2],upper[-1],p)<=0:upper.pop()
        upper.append(p)
    return lower[:-1]+upper[:-1]

def check(path):
    data=json.loads(path.read_text())
    assert data['certified'] and not data['failed']
    U=1000000
    points=[]
    for pair in data['points']:
        p=[]
        for value in pair:
            decimal=Decimal(str(value))*U
            assert decimal==decimal.to_integral_value()
            p.append(int(decimal))
        assert max(map(abs,p))<=2000000*U
        points.append(tuple(p))
    assert len(points)==len(set(points))
    leaves=data['leaves']
    keys={(d,x,y) for d,x,y,_ in leaves}
    assert len(keys)==len(leaves)
    depthmax=max(k[0] for k in keys)
    assert sum(4**(depthmax-d) for d,x,y in keys)==4**depthmax
    for d,x,y in keys:
        assert 0<=x<2**d and 0<=y<2**d
        for k in range(d):assert (k,x//2**(d-k),y//2**(d-k)) not in keys
    outside=covered=0
    min_distance_margin=float('inf');min_hull_margin=float('inf')
    for d,i,j,kind in leaves:
        S=2**d
        left=(-1800*S+3600*i)*U;bottom=(-1800*S+3600*j)*U
        right=left+3600*U;top=bottom+3600*U
        corners=[(left,bottom),(right,bottom),(right,top),(left,top)]
        if kind=='outside':
            closestx=left if left>0 else right if right<0 else 0
            closesty=bottom if bottom>0 else top if top<0 else 0
            assert closestx**2+closesty**2>(1800*U*S)**2
            outside+=1
            continue
        assert isinstance(kind,list) and len(set(kind))>=3
        pp=[(points[k][0]*S,points[k][1]*S) for k in kind]
        # Rebuild convex hull independently; do not trust the stored ordering.
        poly=hull(pp)
        assert len(poly)>=3
        for p in pp:
            d2=max((p[0]-q[0])**2+(p[1]-q[1])**2 for q in corners)
            assert d2<(1000*U*S)**2
            min_distance_margin=min(min_distance_margin,1000-math.sqrt(d2)/(U*S))
        for a,b in zip(poly,poly[1:]+poly[:1]):
            dx,dy=b[0]-a[0],b[1]-a[1]
            cross=min(dx*(q[1]-a[1])-dy*(q[0]-a[0]) for q in corners)
            assert cross>=0
            min_hull_margin=min(min_hull_margin,cross/math.hypot(dx,dy)/(U*S))
        covered+=1
    return dict(status='pass',certificate=str(path),certificate_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        exact_integer_checks=True,author_verifier_imported=False,station_count=len(points),leaves=len(leaves),
        covered_leaves=covered,outside_leaves=outside,maximum_actual_depth=depthmax,
        min_distance_margin_m_approx=min_distance_margin,min_hull_margin_m_approx=min_hull_margin,
        theorem='Every source q in each covered square lies in the convex hull of stations within 1000m of every square point. Any closed emission half-plane through q contains at least one such station; otherwise all convex-combination projections would be strictly negative. Complete dyadic partition covers the domain. This is a continuous certificate, not sampled directions.',
        limitation='Validates these exact finite-decimal stations under the stated geometric model, not their correct use in a solver or official simulator behavior.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('certificate');p.add_argument('--out',required=True);a=p.parse_args()
    result=check(Path(a.certificate).resolve());Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
