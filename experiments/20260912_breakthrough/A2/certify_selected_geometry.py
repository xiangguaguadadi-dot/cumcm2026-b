"""Build and independently verify one new constant geometry; no solver runs."""
import argparse,hashlib,importlib.util,json,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
C=module(ROOT/'experiments/B3/research/certify_geometry.py','certificate_builder')
V=module(ROOT/'experiments/20260911_breakthrough/audit/verify_convex_cover.py','independent_verifier')
p=argparse.ArgumentParser();p.add_argument('--records',required=True);p.add_argument('--index',type=int,required=True);p.add_argument('--name',required=True);a=p.parse_args()
selected=json.loads(Path(a.records).read_text())[a.index];assert selected['passed']
out=HERE/'results'/a.name;out.mkdir(exist_ok=False)
(out/'selected.json').write_text(json.dumps(selected,indent=2)+'\n')
result=C.certify([list(x) for x in selected['sites']],maxdepth=17)
target=out/'certificate.json';target.write_text(json.dumps(result,separators=(',',':'))+'\n')
if result['certified']:
    exact=C.exact_verify(result);independent=V.check(target)
    (out/'exact.json').write_text(json.dumps(exact,indent=2)+'\n')
    (out/'independent.json').write_text(json.dumps(independent,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['points','leaves','failed']}),len(result['failed']),flush=True)
