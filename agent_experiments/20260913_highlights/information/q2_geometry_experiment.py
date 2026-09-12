"""Q2: 80 first-state/budget conditions, two separately reported error bounds.

Candidate search is finite and explicitly not globally optimal. Continuous
reading upper bounds cover every reading interval with a widened wedge.
Lower bounds have explicit legal, observationally indistinguishable pairs.
No simulator, evaluation-world truth, or task-performance results are used.
"""
import argparse, concurrent.futures, hashlib, importlib.util, json, math
import multiprocessing, statistics, sys, time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
PREVIOUS=ROOT/'最佳方法/文档/第二问精度研究/numerical/scan.py'
spec=importlib.util.spec_from_file_location('previous_q2_geometry',PREVIOUS)
CORE=importlib.util.module_from_spec(spec);spec.loader.exec_module(CORE)
clip=CORE.clip;mec=CORE.mec;diameter=CORE.diameter
D=math.pi/180.;BUDGETS=[300.,500.,math.sqrt(450000.),850.,1000.]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def prior(radius,theta,delta,narc=32,ndisk=256,outer=True):
    # Work in the first-station/first-bearing coordinate system. In this frame
    # the actual 1800 m target disk has center (-r*cos(theta),r*sin(theta)).
    c=(-radius*math.cos(theta),radius*math.sin(theta))
    if outer:
        arc=[(1500*math.cos(-delta),1500*math.sin(-delta))]
        for k in range(narc):
            a=-delta+2*delta*(k+.5)/narc;rr=1500/math.cos(delta/narc)
            arc.append((rr*math.cos(a),rr*math.sin(a)))
        arc.append((1500*math.cos(delta),1500*math.sin(delta)))
        poly=[(5*math.cos(delta),-5*math.sin(delta))]+arc+[(5*math.cos(delta),5*math.sin(delta))]
    else:
        arc=[((1500-1e-7)*math.cos(-delta+2*delta*k/narc),(1500-1e-7)*math.sin(-delta+2*delta*k/narc)) for k in range(narc+1)]
        poly=[(5.,-5*math.tan(delta))]+arc+[(5.,5*math.tan(delta))]
        poly=clip(poly,1.,0.,5.+1e-6)
    for k in range(ndisk):
        a=2*math.pi*(k+(0 if outer else .5))/ndisk;nx,ny=math.cos(a),math.sin(a)
        rr=1800. if outer else 1800*math.cos(math.pi/ndisk)-1e-7
        poly=clip(poly,-nx,-ny,-rr-nx*c[0]-ny*c[1])
    return poly,c
def posterior(poly,q,z,delta,inner=False):
    lo=z-delta;hi=z+delta
    a,b=-math.sin(lo),math.cos(lo);p=clip(poly,a,b,a*q[0]+b*q[1])
    a,b=math.sin(hi),-math.cos(hi);p=clip(p,a,b,a*q[0]+b*q[1])
    a,b=math.cos(z),math.sin(z)
    # A normal reading has range>5. The outward chord is conservative; the
    # inner half-plane is a legal subset used exclusively for pair witnesses.
    return clip(p,a,b,a*q[0]+b*q[1]+(5.+1e-6 if inner else 5*math.cos(delta)))
def angular_range(poly,q,delta):
    if not poly:return -math.pi,math.pi
    cross=[(b[0]-a[0])*(q[1]-a[1])-(b[1]-a[1])*(q[0]-a[0]) for a,b in zip(poly,poly[1:]+poly[:1])]
    if all(x>=-1e-9 for x in cross) or all(x<=1e-9 for x in cross):return -math.pi,math.pi
    angles=sorted(math.atan2(v[1]-q[1],v[0]-q[0])%(2*math.pi) for v in poly)
    gaps=[((angles[(i+1)%len(angles)]-angles[i])%(2*math.pi),i) for i in range(len(angles))]
    gap,i=max(gaps);lo=angles[(i+1)%len(angles)];hi=lo+2*math.pi-gap
    return lo-delta,hi+delta
def safe(q,delta,budget):
    rr=q[0]*q[0]+q[1]*q[1]
    return rr<=min(1e6,budget*budget)+1e-7 and rr<=2000*(q[0]*math.cos(delta)-abs(q[1])*math.sin(delta))+1e-7
def safety(q,delta,budget):
    centers=[(0.,0.),(1000*math.cos(delta),1000*math.sin(delta)),(1000*math.cos(delta),-1000*math.sin(delta))]
    return dict(safe=safe(q,delta,budget),move_m=math.hypot(*q),budget_m=budget,
        budget_slack_m=budget-math.hypot(*q),three_disk_min_slack_m=min(1000-math.dist(q,c) for c in centers))
def readings(poly,q,delta,n):
    lo,hi=angular_range(poly,q,delta);step=(hi-lo)/n;zs=[lo+i*step for i in range(n+1)]
    ref=(lo+hi)/2
    for v in poly:
        a=ref+math.remainder(math.atan2(v[1]-q[1],v[0]-q[0])-ref,2*math.pi)
        zs.extend([max(lo,min(hi,a-delta)),max(lo,min(hi,a+delta))])
    return zs
def coarse_score(poly,q,delta,n=64):
    best=-1.;zbest=0.
    for z in readings(poly,q,delta,n):
        r,_=mec(posterior(poly,q,z,delta))
        if r>best:best,zbest=r,z
    return best,zbest
def polar(b,a):return (b*math.cos(a),b*math.sin(a))
def candidate_points(b,delta):
    fixed=polar(b,math.atan(.5))
    phi=math.acos(3*1500*b*math.cos(delta)/(2*1500**2+b*b))
    phimax=math.acos(b/2000)-delta
    analytic=polar(b,min(phi,phimax))
    points=[fixed,analytic,(analytic[0],-analytic[1]),(fixed[0],-fixed[1])]
    # Finite point search under a common movement CAP; report actual movement
    # so a shorter chosen move is never disguised as identical distance.
    for fraction in (.25,.5,.75,1.):
        bb=b*fraction;amax=math.acos(bb/2000)-delta
        for k in range(-10,11):points.append(polar(bb,k*amax/10))
    unique={tuple(round(v,10) for v in q):q for q in points if safe(q,delta,b)}
    return fixed,analytic,list(unique.values())
def one_coarse(condition):
    started=time.perf_counter();r,theta_deg,b,delta_deg=condition;theta=theta_deg*D;delta=delta_deg*D
    poly,c=prior(r,theta,delta);fixed,analytic,points=candidate_points(b,delta)
    scores=[]
    for q in points:
        value,z=coarse_score(poly,q,delta,64);scores.append(dict(q=q,sampled_radius_m=value,worst_sampled_reading_rad=z))
    scores.sort(key=lambda v:(v['sampled_radius_m'],math.hypot(*v['q']),v['q']))
    # Refine a bounded neighborhood around the coarse winner and retain both
    # named comparators, so their candidates cannot silently be dropped.
    winner=scores[0]['q'];bw=math.hypot(*winner);aw=math.atan2(winner[1],winner[0]);fine=[fixed,analytic]+[s['q'] for s in scores[:5]]
    for db in (-.05,0.,.05):
        for da in (-2.,-1.,0.,1.,2.):
            q=polar(min(b,max(1.,bw+db*b)),aw+da*D)
            if safe(q,delta,b):fine.append(q)
    fine=list({tuple(round(v,9) for v in q):q for q in fine}.values());refined=[]
    for q in fine:
        value,z=coarse_score(poly,q,delta,256);refined.append(dict(q=q,sampled_radius_m=value,worst_sampled_reading_rad=z))
    best=min(refined,key=lambda v:(v['sampled_radius_m'],math.hypot(*v['q']),v['q']))
    methods=[]
    for name,q in [('fixed',fixed),('analytic',analytic),('actual_prior_search',best['q'])]:
        row=next(v for v in refined if math.dist(v['q'],q)<1e-7)
        methods.append(dict(method=name,**row,**safety(q,delta,b)))
    return dict(condition_id=f'r{r}_theta{theta_deg}_b{b:.9f}_delta{delta_deg}',first_station_radius_m=r,first_bearing_relative_deg=theta_deg,
        budget_m=b,error_halfwidth_deg=delta_deg,prior_outer_polygon=poly,target_center_local=c,methods=methods,
        candidate_rows=scores,refined_rows=refined,coarse_n_readings=64,refined_n_readings=256,
        label='Finite candidate/reading search; sampled maxima are NOT continuous worst-case bounds',elapsed_s=time.perf_counter()-started)
def valid_pair(pair,q,z,delta,c):
    if not pair:return False,{}
    checks=[]
    for p in pair:
        d1=math.hypot(*p);d2=math.dist(p,q);target=math.dist(p,c)
        e1=abs(math.atan2(p[1],p[0]));e2=abs(math.remainder(math.atan2(p[1]-q[1],p[0]-q[0])-z,2*math.pi))
        ok=5.<d1<=1500.+1e-6 and 5.<d2<=1500.+1e-6 and target<=1800.+1e-6 and e1<=delta+1e-9 and e2<=delta+1e-9
        checks.append(dict(source=p,first_distance_m=d1,second_distance_m=d2,target_radius_m=target,first_error_deg=e1/D,second_error_deg=e2/D,legal=ok,common_reception_radius_m=1500.))
    return all(x['legal'] for x in checks),dict(common_first_reading_deg=0.,common_second_reading_deg=z/D%360.,source_checks=checks)
def lower_at(poly_inner,q,z,delta,c):
    p=posterior(poly_inner,q,z,delta,inner=True)
    d,pair=diameter(p)
    if not pair:return 0.,None
    # Move infinitesimally toward an interior convex combination to avoid
    # floating point endpoint values marginally outside true circular arcs.
    center=(sum(x for x,y in p)/len(p),sum(y for x,y in p)/len(p))
    pair=[(v[0]+1e-10*(center[0]-v[0]),v[1]+1e-10*(center[1]-v[1])) for v in pair]
    legal,details=valid_pair(pair,q,z,delta,c)
    if not legal:return 0.,dict(invalid_pair=pair,**details)
    return math.dist(*pair)/2,dict(pair=pair,pair_distance_m=math.dist(*pair),**details)
def one_bound(task):
    condition,step_deg=task;started=time.perf_counter()
    r=condition['first_station_radius_m'];theta=condition['first_bearing_relative_deg']*D;delta=condition['error_halfwidth_deg']*D
    po,c=prior(r,theta,delta,narc=64,ndisk=512,outer=True);pi,_=prior(r,theta,delta,narc=128,ndisk=512,outer=False)
    rows=[]
    for method in condition['methods']:
        q=method['q'];lo,hi=angular_range(po,q,delta);n=max(1,math.ceil((hi-lo)/(step_deg*D)));h=(hi-lo)/n
        upper=5.;bestz=None;bestcenter=None;lower=0.;witness=None;invalid=[]
        for i in range(n+1):
            z=lo+i*h;p=posterior(po,q,z,delta+h/2);rr,cc=mec(p)
            # Recheck all vertices explicitly: even a numerically imperfect
            # MEC center yields a valid enclosing radius after this recheck.
            if p and cc:rr=max(math.dist(v,cc) for v in p)+1e-6
            if rr>upper:upper,bestz,bestcenter=rr,z,cc
        zs=readings(pi,q,delta,256)+[method['worst_sampled_reading_rad']]
        if bestz is not None:zs += [bestz-h/2,bestz,bestz+h/2]
        for z in zs:
            ll,ww=lower_at(pi,q,z,delta,c)
            if ww and 'invalid_pair' in ww:invalid.append(ww)
            if ll>lower:lower,witness=ll,ww
        rows.append(dict(method=method['method'],q=q,**safety(q,delta,condition['budget_m']),
            radius_lower_legal_pair_m=lower,radius_upper_continuous_enclosure_m=upper,gap_m=upper-lower,
            witness=witness,invalid_witness_candidates=invalid,reading_cells=n,grid_points=n+1,step_deg=h/D,
            widened_second_halfwidth_deg=(delta+h/2)/D,worst_upper_reading_deg=None if bestz is None else bestz/D%360.,
            worst_upper_center=bestcenter,near_branch_upper_m=5.,thresholds={str(t):('guaranteed' if upper<=t else 'impossible_for_this_point' if lower>t else 'unresolved') for t in (20,50,100)}))
    fixed=next(x for x in rows if x['method']=='fixed');opt=next(x for x in rows if x['method']=='actual_prior_search')
    relation='certified_better' if opt['radius_upper_continuous_enclosure_m']<fixed['radius_lower_legal_pair_m'] else 'certified_worse' if opt['radius_lower_legal_pair_m']>fixed['radius_upper_continuous_enclosure_m'] else 'unresolved_or_equal'
    return dict(condition_id=condition['condition_id'],first_station_radius_m=r,first_bearing_relative_deg=condition['first_bearing_relative_deg'],budget_m=condition['budget_m'],error_halfwidth_deg=condition['error_halfwidth_deg'],
        methods=rows,optimized_vs_fixed=relation,outer_prior=po,inner_prior=pi,target_center_local=c,elapsed_s=time.perf_counter()-started,
        label='Continuous reading enclosure in real-arithmetic geometry, evaluated with double precision and explicit margins; not interval arithmetic; finite q search')
def lower_theorem():
    rows=[]
    for deg in (1.,1.005001):
        d=deg*D;a=1500/(1+math.sin(d));r=1500*math.sin(d)/(1+math.sin(d));c=(a,0.)
        examples=[]
        for q in [(600.,300.),polar(1000.,35.11*D),(1000.,0.)]:
            u=((c[0]-q[0])/math.dist(c,q),(c[1]-q[1])/math.dist(c,q));pair=[(c[0]+sign*r*u[0],sign*r*u[1]) for sign in (-1,1)]
            z=math.atan2(u[1],u[0]);ok,details=valid_pair(pair,q,z,d,(0.,0.))
            examples.append(dict(q=q,three_disk_safe=safe(q,d,1000.),pair=pair,separation_m=math.dist(*pair),legal=ok,**details))
        rows.append(dict(error_halfwidth_deg=deg,center_m=c,radius_lower_m=r,diameter_lower_m=2*r,safe_q_norm_upper_m=1005.,
            source_norm_lower_m=a-r,second_range_lower_m=a-r-1005.,examples=examples))
    return dict(label='Analytic indistinguishability lower bound, independent of numerical candidate search',
        assumptions=['omnidirectional source','first station at target center, first reading 0','normal readings range>5','unknown reception radius in [1000,1500]',
            'second point guarantees reception for every first-consistent source/radius','bounded errors may differ at different measurement positions'],
        proof=['Near source (5+epsilon,0), reception radius1000, forces ||q-(5,0)||<=1000, hence ||q||<=1005.',
            'Disk center a=1500/(1+sin delta), radius r=a sin delta lies inside the first sector.',
            'q is outside this disk; the two endpoints of its diameter through q have identical second true bearing.',
            'Both produce first reading0 and the same normal second reading with legal radius1500; their separation2r forces posterior enclosing radius>=r.'],rows=rows)
def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['coarse','representatives','all_bounds'],default='coarse');p.add_argument('--workers',type=int,default=2);p.add_argument('--step-deg',type=float,default=.05);a=p.parse_args()
    out=HERE/('q2_'+a.stage);out.mkdir(exist_ok=False)
    write(out/'invocation.json',dict(argv=sys.argv,script_sha256=sha(Path(__file__)),geometry_helper_sha256=sha(PREVIOUS),registration_sha256=sha(HERE/'registration.json')))
    if a.stage=='coarse':
        write(out/'lower_theorem_recheck.json',lower_theorem())
        geometries=[(0,0)]+[(r,t) for r in (600,1200,1750) for t in (0,45,90,135,180)]
        tasks=[(r,t,b,d) for d in (1.,1.005001) for r,t in geometries for b in BUDGETS];fn=one_coarse
    else:
        data=[json.loads(l) for l in (HERE/'q2_coarse/condition_rows.jsonl').read_text().splitlines()]
        if a.stage=='representatives':data=[c for c in data if c['first_station_radius_m']==0 or abs(c['budget_m']-math.sqrt(450000.))<1e-6]
        tasks=[(c,a.step_deg) for c in data];fn=one_bound
    started=time.perf_counter();rows=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=multiprocessing.get_context('spawn')) as pool:
        with (out/'condition_rows.jsonl').open('w') as f:
            for row in pool.map(fn,tasks,chunksize=1):
                rows.append(row);f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush()
                print(json.dumps(dict(stage=a.stage,conditions=len(rows),total=len(tasks),condition_id=row['condition_id'],elapsed_s=time.perf_counter()-started)),flush=True)
    summary=dict(stage=a.stage,conditions=len(rows),methods_per_condition=3,condition_method_rows=3*len(rows),wall_s=time.perf_counter()-started,error_bounds_separately={})
    for d in (1.,1.005001):
        part=[r for r in rows if r['error_halfwidth_deg']==d]
        z=dict(conditions=len(part),all_safe=all(m['safe'] for r in part for m in r['methods']))
        if a.stage!='coarse':
            z.update(comparisons={key:sum(r['optimized_vs_fixed']==key for r in part) for key in ('certified_better','certified_worse','unresolved_or_equal')},
                all_lower_le_upper=all(m['radius_lower_legal_pair_m']<=m['radius_upper_continuous_enclosure_m']+1e-6 for r in part for m in r['methods']),
                maximum_gap_m=max(m['gap_m'] for r in part for m in r['methods']),
                invalid_witness_candidates=sum(len(m['invalid_witness_candidates']) for r in part for m in r['methods']))
        summary['error_bounds_separately'][str(d)]=z
    write(out/'summary.json',summary);print(json.dumps(summary),flush=True)
if __name__=='__main__':main()
