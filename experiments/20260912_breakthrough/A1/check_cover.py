"""Synthetic tests for D3; samples diagnose, while the convex-cell proof certifies."""
import importlib.util
import json
import math
import random
import time
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('a1_cover',HERE/'snapshots/r6a.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
base=module._Q3._sp_certified_points(3)
rng=random.Random(951207)
start=time.perf_counter()
records=[]
accepted=0
for i in range(600):
    points=base[:]
    if i:
        j=1+i%6
        angle=(j-1)*math.pi/3+rng.uniform(-.6,.6)
        radius=rng.uniform(600.,1900.)
        points[j]=(radius*math.cos(angle),radius*math.sin(angle))
    safe,upper,vertices=module.a1_cover_certificate(points)
    if safe:
        accepted+=1
        # Independent dense boundary and random disk diagnostics; not the proof.
        probes=[(1800.*math.cos(2*math.pi*k/1440),1800.*math.sin(2*math.pi*k/1440)) for k in range(1440)]
        for _ in range(200):
            a=rng.random()*2*math.pi;r=1800.*math.sqrt(rng.random())
            probes.append((r*math.cos(a),r*math.sin(a)))
        observed=max(min(math.dist(p,q) for q in points) for p in probes)
        assert observed<1000. and observed<=upper+1e-5
    else:observed=None
    records.append(dict(id=i,safe=safe,upper=upper,vertices=vertices,sampled_max=observed))
assert records[0]['safe'] and accepted>1
assert not module.a1_cover_certificate(base[:-1])[0]
assert not module.a1_cover_certificate([(0.,0.)])[0]
assert module.a1_cover_certificate(base+[base[0]])[0]
out=dict(synthetic_layouts=len(records),accepted=accepted,all_checks=True,
         interpretation='Convex Voronoi-cell outer-polygon certificate; random/boundary checks are diagnostics only',
         wall_s=time.perf_counter()-start,records=records)
(HERE/'results/r6_geometry_checks.json').write_text(json.dumps(out,indent=2))
print({k:v for k,v in out.items() if k!='records'})
