"""Cover all continuous second observations by overlapping widened wedges."""
import json,math,os,time
from scan import sector,angular_range,posterior,diameter,mec,D
outdir=os.path.dirname(__file__)
data=json.load(open(os.path.join(outdir,'results.json')))
names=['default','optimized_length_670.820393249937','optimized_length_1000.0']
rows=[];start=time.time()
for name in names:
    src=next(r for r in data['audits'] if r['name']==name and r['narc']==128 and not r['outer'])
    q=src['q'];poly=sector(128,True);lo,hi=angular_range(q,poly)
    n=math.ceil((hi-lo)/(.01*D));h=(hi-lo)/n
    maxd=maxr=0.;bestd=bestr=None
    for i in range(n+1):
        z=lo+i*h
        p=posterior(q,z,poly,delta2=D+h/2)
        d,_=diameter(p);r,c=mec(p)
        if d>maxd:maxd,bestd=d,z
        if r>maxr:maxr,bestr=r,z
    row={'name':name,'q':q,'diameter_lower_witness':src['diameter'],'diameter_upper_cover':maxd,'radius_lower_pair_bound':src['diameter']/2,'radius_upper_cover':maxr,'grid_points':n+1,'grid_step_deg':h/D,'expanded_second_halfwidth_deg':1+h/D/2,'worst_diameter_grid_center_deg':math.degrees(bestd)%360,'worst_radius_grid_center_deg':math.degrees(bestr)%360,'narc':128,'outer_first_polygon':True,'floating_point_note':'geometric enclosure proof uses real arithmetic; Python floats, halfplane tolerance 1e-10 and MEC containment tolerance 1e-7 m^2, no interval arithmetic'}
    print(json.dumps(row),flush=True);rows.append(row)
with open(os.path.join(outdir,'continuous_bounds.json'),'w') as f:json.dump({'elapsed_seconds':time.time()-start,'rows':rows},f,indent=2)
