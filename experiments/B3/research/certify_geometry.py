"""Finite quadtree certificate for continuous one-sided radio coverage.

A leaf square is covered when it lies in the convex hull of stations each at
most 1000 m from every point of the square. This implies every source in the
square has one eligible station in every closed emission half-plane.
Floating exploration is followed by exact rational/integer verification.
"""
from pathlib import Path
import json,math,time,argparse

def hull(points):
 ps=sorted(set(tuple(p) for p in points))
 def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
 lo=[];hi=[]
 for p in ps:
  while len(lo)>1 and cross(lo[-2],lo[-1],p)<=0:lo.pop()
  lo.append(p)
 for p in reversed(ps):
  while len(hi)>1 and cross(hi[-2],hi[-1],p)<=0:hi.pop()
  hi.append(p)
 return [list(p) for p in lo[:-1]+hi[:-1]]

def certify(P,maxdepth=17):
 start=time.perf_counter();stack=[(0,0,0)];leaves=[];failed=[];examined=0
 while stack:
  depth,ix,iy=stack.pop();size=3600/(2**depth);x=-1800+ix*size;y=-1800+iy*size
  examined+=1
  nx=max(x,0) if x>=0 else min(x+size,0);ny=max(y,0) if y>=0 else min(y+size,0)
  if nx*nx+ny*ny>1800**2+1e-7:
   leaves.append([depth,ix,iy,'outside']);continue
  corners=[(x,y),(x+size,y),(x+size,y+size),(x,y+size)]
  safe=[p for p in P if max((p[0]-a)**2+(p[1]-b)**2 for a,b in corners)<(1000-1e-5)**2]
  poly=hull(safe)
  covered=len(poly)>=3 and all((b[0]-a[0])*(q[1]-a[1])-(b[1]-a[1])*(q[0]-a[0])>=1e-5 for a,b in zip(poly,poly[1:]+poly[:1]) for q in corners)
  if covered:
   leaves.append([depth,ix,iy,[P.index(p) for p in poly]]);continue
  if depth==maxdepth:
   failed.append([depth,ix,iy]);continue
  stack.extend((depth+1,2*ix+i,2*iy+j) for i,j in ((0,0),(0,1),(1,0),(1,1)))
  if examined>2000000:raise RuntimeError('geometry exploration budget exceeded')
 return {'certified':not failed,'points':P,'leaves':leaves,'failed':failed,'leaf_count':len(leaves),'examined_cells':examined,'wall_seconds':time.perf_counter()-start,'maxdepth':maxdepth,'proof':'leaf square is contained in convex hull of common radius-1000 stations, or outside domain'}

def exact_verify(data):
 # Verify actual IEEE-754 station coordinates, not ideal decimal values.
 # Their denominators and all leaf coordinates are powers of two.
 ratios=[[(float(v).as_integer_ratio()) for v in p] for p in data['points']]
 unit=max(den for point in ratios for num,den in point)
 P=[tuple(num*(unit//den) for num,den in point) for point in ratios]
 total_num=0;maxdepth=max(l[0] for l in data['leaves']);seen=set()
 for depth,ix,iy,kind in data['leaves']:
  key=(depth,ix,iy);assert key not in seen;seen.add(key)
  assert 0<=ix<2**depth and 0<=iy<2**depth
  for parentdepth in range(depth):assert (parentdepth,ix//2**(depth-parentdepth),iy//2**(depth-parentdepth)) not in seen
  total_num+=4**(maxdepth-depth)
  scale=2**depth;size=3600*unit
  x=-1800*unit*scale+ix*size;y=-1800*unit*scale+iy*size
  corners=[(x,y),(x+size,y),(x+size,y+size),(x,y+size)]
  if kind=='outside':
   nx=max(x,0) if x>=0 else min(x+size,0);ny=max(y,0) if y>=0 else min(y+size,0)
   assert nx*nx+ny*ny>(1800*unit*scale)**2
  else:
   pp=[(P[i][0]*scale,P[i][1]*scale) for i in kind]
   assert len(set(pp))==len(pp)>=3
   assert all((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])>=0 for a,b in zip(pp,pp[1:]+pp[:1]) for p in pp)
   for p in pp:
    assert all((p[0]-q[0])**2+(p[1]-q[1])**2<(1000*unit*scale-1)**2 for q in corners)
   for a,b in zip(pp,pp[1:]+pp[:1]):
    assert all((b[0]-a[0])*(q[1]-a[1])-(b[1]-a[1])*(q[0]-a[0])>=0 for q in corners)
 # Check complete partition both ways: prefix-free and full square area.
 for d,i,j in seen:
  for k in range(d):assert (k,i//2**(d-k),j//2**(d-k)) not in seen
 assert total_num==4**maxdepth,'Uncovered area or overlap'
 return {'passed':True,'exact_integer_arithmetic':True,'leaf_count':len(seen),'actual_float_coordinates_verified':True,'station_common_denominator':unit,'coverage_radius_m':1000,'target_domain_radius_m':1800}

def ring(n,r,a=0):return [(round(r*math.cos(2*math.pi*k/n+a),6),round(r*math.sin(2*math.pi*k/n+a),6)) for k in range(n)]
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--inner',type=float,default=999);p.add_argument('--outer',type=float,default=1864);p.add_argument('--rotation',type=float,default=0);p.add_argument('--out',required=True);a=p.parse_args()
 P=[(0.,0.)]+ring(8,a.inner)+ring(12,a.outer,a.rotation);P=[list(p) for p in P]
 r=certify(P)
 if r['certified']:r['exact_verification']=exact_verify(r)
 Path(a.out).write_text(json.dumps(r,ensure_ascii=False,separators=(',',':')))
 print(json.dumps({k:v for k,v in r.items() if k not in ('leaves','points','failed')},ensure_ascii=False));print('failed count',len(r['failed']),'first',r['failed'][:10])
