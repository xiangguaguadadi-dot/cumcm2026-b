"""Physical feedback fixtures for the unchanged Q4 convex-wedge function.

Fixture polygons are declared conservative supersets containing the source,
not claims of exact posteriors from a complete policy history.
"""
import hashlib,importlib.util,json,math,random,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('q4_information_runner',HERE/'q4_experiment.py')
R=importlib.util.module_from_spec(sp);sp.loader.exec_module(R)
R.init_worker()
def visible(s,p,radius,direction):
    if math.dist(s,p)>radius+1e-10:return False
    return direction is None or math.cos(math.atan2(p[1]-s[1],p[0]-s[0])-direction)>=-1e-12
def transform(p,s,theta):return (s[0]+p[0]*math.cos(theta)-p[1]*math.sin(theta),s[1]+p[0]*math.sin(theta)+p[1]*math.cos(theta))
def main():
    out=HERE/'q4_stress';out.mkdir(exist_ok=False);rng=random.Random(2026091304);fixtures=[]
    def add(name,s,p1,p2,q,radius,direction,poly):
        legal=visible(s,p1,radius,direction) and visible(s,p2,radius,direction) and not visible(s,q,radius,direction)
        new=R.WEDGE(poly,p1,p2,q) if legal else poly
        before=R.area(poly);after=R.area(new)
        v1=(q[0]-p1[0],q[1]-p1[1]);v2=(q[0]-p2[0],q[1]-p2[1]);cross=v1[0]*v2[1]-v1[1]*v2[0]
        fixtures.append(dict(fixture_id=name,source=s,positive_points=[p1,p2],negative_point=q,reception_radius=radius,emission_direction=direction,
            legal_positive_positive_negative_feedback=legal,polygon_before=poly,polygon_after=new,
            area_before_m2=before,area_after_m2=after,area_removed_m2=max(0.,before-after),
            near_collinear_skip=abs(cross)<=1e-8*max(1.,math.hypot(*v1)*math.hypot(*v2)),
            source_inside_before=R.contains(poly,s),source_inside_after=R.contains(new,s),
            q_actually_visible=visible(s,q,radius,direction)))
    # A readable constructive example: two front-side receptions and a rear
    # non-reception remove a left-pointing forbidden wedge from an outer box.
    add('constructed_two_positive_one_negative',(0.,0.),(100.,-50.),(100.,50.),(-10.,0.),1000.,0.,[(-300.,-20.),(100.,-20.),(100.,20.),(-300.,20.)])
    for i in range(1000):
        a=rng.uniform(-math.pi,math.pi);rr=800*math.sqrt(rng.random());s=(rr*math.cos(a),rr*math.sin(a));theta=rng.uniform(-math.pi,math.pi)
        radius=rng.choice([1000.,1500.,rng.uniform(1000.,1500.)]);direction=None if i%5==0 else theta
        def positive():
            ang=theta+rng.uniform(-1.45,1.45);rad=rng.uniform(10.,.98*radius)
            return (s[0]+rad*math.cos(ang),s[1]+rad*math.sin(ang))
        p1,p2=positive(),positive()
        if direction is None or i%2==0:
            ang=rng.uniform(-math.pi,math.pi);rad=radius+rng.uniform(.001,700.)
        else:ang=theta+math.pi+rng.uniform(-1.4,1.4);rad=rng.uniform(10.,.95*radius)
        q=(s[0]+rad*math.cos(ang),s[1]+rad*math.sin(ang))
        # A transformed convex box is deliberately broader than the bearing
        # posterior. Safety of exclusion must hold for any containing superset.
        lx,rx,dy=-rng.uniform(100.,1000.),rng.uniform(100.,1000.),rng.uniform(10.,200.)
        poly=[transform(p,s,theta) for p in [(lx,-dy),(rx,-dy),(rx,dy),(lx,dy)]]
        add(f'random_physical_{i:04d}',s,p1,p2,q,radius,direction,poly)
    box=[(-1700.,-100.),(1700.,-100.),(1700.,600.),(-1700.,600.)]
    for eps in (0.,1e-12,1e-10,1e-8,1e-6,1e-4,1e-2,1.):
        add(f'near_collinear_eps_{eps}',(0.,0.),(100.,0.),(100.,eps),(-100.,0.),1000.,0.,box)
    offsets=[-1e-4,-1e-6,-1e-8,-1e-10,0.,1e-10,1e-8,1e-6,1e-4]
    for eps in offsets:
        add(f'halfplane_boundary_offset_{eps}',(0.,0.),(500.,100.),(500.,-100.),(-eps,500.),1000.,0.,box)
        for radius in (1000.,1500.):
            add(f'range_boundary_r{radius}_offset_{eps}',(0.,0.),(200.,100.),(200.,-100.),(radius+eps,0.),radius,0.,box)
    with (out/'fixtures.jsonl').open('w') as f:
        for x in fixtures:f.write(json.dumps(x)+'\n')
    legal=[f for f in fixtures if f['legal_positive_positive_negative_feedback']]
    summary=dict(fixtures=len(fixtures),legal_negative_feedback_fixtures=len(legal),
        boundary_fixtures_returning_positive_not_used=len(fixtures)-len(legal),
        source_false_exclusions=sum(not f['source_inside_after'] for f in legal),
        near_collinear_skips=sum(f['near_collinear_skip'] for f in legal),effective_area_shrinks=sum(f['area_removed_m2']>1e-6 for f in legal),
        constructive_example=fixtures[0],label='Constructed physical-geometry fixtures, not task runs; no sampling claim replaces the convexity proof',
        script_sha256=R.sha(Path(__file__)),candidate_sha256=R.sha(R.SOURCE))
    R.write(out/'summary.json',summary);print(json.dumps(summary),flush=True)
if __name__=='__main__':main()
