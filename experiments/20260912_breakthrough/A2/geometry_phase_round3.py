"""Third topology round: align 7/13-ring angular bottlenecks at half beat phase."""
import importlib.util,json,math,time
from pathlib import Path
import geometry_search as G
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
C=module(ROOT/'experiments/B3/research/certify_geometry.py','certificate_builder')
V=module(ROOT/'experiments/20260911_breakthrough/audit/verify_convex_cover.py','independent_verifier')
out=HERE/'results/geometry_phase_round3';out.mkdir(exist_ok=False)
records=[]
for offset in [0.,math.pi/364,-math.pi/364]:
    phase=math.pi/91+offset
    sites=[(0.,0.)]+G.ring(7,999.)+G.ring(13,1800/math.cos(math.pi/13)+.2,phase)
    rec=dict(inner_n=7,outer_n=13,inner_r=999.,outer_r=1800/math.cos(math.pi/13)+.2,phase=phase,sites=sites,
        **G.probe(sites,radial=181,angular=1440))
    if rec['passed']:
        cert=C.certify([list(p) for p in sites],maxdepth=17)
        name='certificate_'+str(len(records))+'.json';target=out/name
        target.write_text(json.dumps(cert,separators=(',',':'))+'\n')
        rec.update(certified=cert['certified'],certificate=name,failed_cells=len(cert['failed']))
        if cert['certified']:
            rec['exact']=C.exact_verify(cert);rec['independent']=V.check(target)
    records.append(rec)
    print({k:v for k,v in rec.items() if k not in ['sites','failures','exact','independent']},flush=True)
    (out/'records.json').write_text(json.dumps(records,indent=2)+'\n')
