import json,math,os
from scan import safe
out=os.path.dirname(__file__)
d=json.load(open(os.path.join(out,'results.json')))
cover=json.load(open(os.path.join(out,'continuous_bounds.json')))
full=json.load(open(os.path.join(out,'full_domain_results.json')))
rows=[]
for cert in cover['rows']:
    r=next(x for x in d['audits'] if x['name']==cert['name'] and x['narc']==128 and not x['outer'])
    q=r['q'];z=r['bearing_deg'];witness=[]
    for p in r['pair']:
        a1=math.degrees(math.atan2(p[1],p[0]));a2=math.degrees(math.atan2(p[1]-q[1],p[0]-q[0]))
        e2=math.remainder(z-a2,360)
        assert 5<math.hypot(*p)<1500+1e-7 and abs(a1)<1+1e-7
        assert math.dist(p,q)>5 and abs(e2)<1+1e-7
        assert math.dist(p,q)<=max(1000,math.hypot(*p))+1e-7
        witness.append({'source':p,'first_error_deg':-a1,'second_error_deg':e2,'radius_from_first':math.hypot(*p),'radius_from_second':math.dist(p,q)})
    assert safe(q)
    xdelta=min(p[0]-q[0] for p in r['polygon'])
    assert xdelta>5 and min(p[0] for p in r['polygon'])>5
    row={'name':r['name'],'q':q,'movement_m':r['move'],'movement_and_second_measure_seconds':r['move']/5+5,'angle_deg':r['angle_deg'],'safe':True,'worst_diameter_m_estimate':r['diameter'],'worst_mec_radius_m_estimate':next(x['worst_metric'] for x in d['mec_audits'] if x['name']==r['name']),'continuous_diameter_m_enclosure':[cert['diameter_lower_witness'],cert['diameter_upper_cover']],'continuous_mec_radius_m_enclosure':[cert['radius_lower_pair_bound'],cert['radius_upper_cover']],'worst_observation_deg':z,'ambiguity_witness':witness,'worst_polygon_min_x':min(p[0] for p in r['polygon']),'worst_polygon_min_x_displacement_from_second':xdelta,'bounds_grid_points':cert['grid_points']}
    rows.append(row)
with open(os.path.join(out,'final_comparison.json'),'w') as f:
    json.dump({'scope':'S1=(0,0), first reported angle=0 deg, delta=1 deg, relaxed source sector 5<r<=1500; unknown target-domain truncation omitted','method':'all possible second reported bearings; actual wedge intersection; exact polygon diameter and minimum enclosing circle; widened-wedge covering upper envelope','candidate_grid_count':full['count'],'candidate_grid':'b=25:25:1000 m; angle 0:1:floor(acos(b/2000)-1 deg), plus safety boundary; symmetry y>=0; selected radii directions refined to 0.05 deg','continuous_bounds_caveat':'geometric covering proof; ordinary floating point and tolerance checks, not interval-arithmetic certificate or continuous-global-optimum proof','rows':rows},f,indent=2)
print(json.dumps(rows,indent=2))
