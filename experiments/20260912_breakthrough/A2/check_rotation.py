"""Transport every continuous-certificate leaf, not only sample source points."""
import importlib.util,json,math,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
spec=importlib.util.spec_from_file_location('original_independent_checker',ROOT/'experiments/20260911_breakthrough/audit/verify_convex_cover.py')
V=importlib.util.module_from_spec(spec);spec.loader.exec_module(V)
certificate=ROOT/'experiments/B3/research/certificate_21_999_1864.json'
original=V.check(certificate);data=json.loads(certificate.read_text())
md=1e10;mh=1e10;n=0
for step in range(24):
    angle=math.pi*step/48;co,si=math.cos(angle),math.sin(angle)
    rotate=lambda p:(co*p[0]-si*p[1],si*p[0]+co*p[1])
    points=[rotate(p) for p in data['points']]
    for d,i,j,kind in data['leaves']:
        if kind=='outside':continue
        side=3600/(2**d);left=-1800+i*side;bottom=-1800+j*side
        corners=[rotate(p) for p in [(left,bottom),(left+side,bottom),(left+side,bottom+side),(left,bottom+side)]]
        pp=[points[k] for k in kind];poly=V.hull(pp)
        margin=min(1000-math.dist(p,q) for p in pp for q in corners)
        assert margin>0.1
        md=min(md,margin)
        for a,b in zip(poly,poly[1:]+poly[:1]):
            dx,dy=b[0]-a[0],b[1]-a[1]
            margin=min((dx*(q[1]-a[1])-dy*(q[0]-a[0]))/math.hypot(dx,dy) for q in corners)
            assert margin>0.0007
            mh=min(mh,margin)
        n+=1
result=dict(status='pass',original=original,rotations=24,covered_cell_rotations=n,
    minimum_rotated_range_margin_m=md,minimum_rotated_hull_margin_m=mh,
    proof='Orthogonal transport of continuous certificate; floating checks are not a replacement exact certificate')
(HERE/'results/rotation_certificate_check.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
