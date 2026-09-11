"""Counterexample search only: finite samples do not certify continuous coverage."""
import numpy as np,json,time,math
from pathlib import Path
OUT=Path(__file__).parent
angles=np.arange(720)*2*np.pi/720
radii=np.linspace(0,1800,91)
S=np.array([(r*math.cos(a),r*math.sin(a)) for r in radii for a in angles])
def ring(n,r,a=0):return np.array([(r*math.cos(2*math.pi*k/n+a),r*math.sin(2*math.pi*k/n+a)) for k in range(n)])
def check(P):
 # Each sample is covered in all closed directions iff eligible polar angles
 # have no gap greater than pi. Source coincident with a point is always near.
 v=P[None,:,:]-S[:,None,:];d=np.linalg.norm(v,axis=2);theta=np.mod(np.arctan2(v[:,:,1],v[:,:,0]),2*np.pi)
 theta=np.where(d<=1000,theta,np.inf);t=np.sort(theta,axis=1);count=np.sum(np.isfinite(t),axis=1)
 gap=np.where(np.isfinite(t[:,1:]),np.diff(t,axis=1),0).max(axis=1)
 last=t[np.arange(len(S)),np.maximum(0,count-1)]
 gap=np.maximum(gap,t[:,0]+2*np.pi-last)
 bad=(count<2)|(gap>np.pi+1e-8);bad=np.where(d.min(axis=1)<1e-8,False,bad)
 indices=np.flatnonzero(bad)
 return {'sample_count':len(S),'uncovered_samples':len(indices),'worst_angle_gap_deg':float(np.nanmax(gap)*180/np.pi),'counterexamples':[S[i].tolist() for i in indices[::max(1,len(indices)//20)][:20]]}
records=[];start=time.perf_counter()
for ni in (7,8):
 for ri in (850,925,999):
  for rotation in (0,math.pi/24,math.pi/12):
   P=np.vstack(([0,0],ring(ni,ri),ring(12,1864,rotation)))
   result={'inner_n':ni,'inner_r':ri,'outer_n':12,'outer_r':1864,'rotation':rotation,'points':P.tolist(),**check(P)}
   records.append(result);print(ni,ri,rotation,result['uncovered_samples'],flush=True)
(OUT/'geometry_probe.json').write_text(json.dumps({'note':'Finite counterexample search, not continuous certificate','wall_s':time.perf_counter()-start,'configurations':records},indent=2))
