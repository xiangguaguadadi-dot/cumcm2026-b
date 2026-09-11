"""Source/parent identity and known station certificate checks."""
from pathlib import Path
import ast,json,hashlib,importlib.util,sys

ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'experiments/R3_open'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def defs(p):
    d={}
    for n in ast.parse(p.read_text()).body:
        name=n.name if isinstance(n,(ast.FunctionDef,ast.ClassDef)) else n.targets[0].id if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) else None
        if name:d[name]=ast.dump(n,include_attributes=False)
    return d
def load(p):
    s=importlib.util.spec_from_file_location('source_'+sha(p)[:10],p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

candidate=OUT/'snapshots/r3.py';parent=OUT/'snapshots/r2.py'
a,b=defs(parent),defs(candidate)
assert a.keys()==b.keys()
changed=[k for k in a if a[k]!=b[k]]
assert changed==['_di_Solver','OPTIMIZED_CONFIGS'],changed
tree=ast.parse(candidate.read_text())
attrs=sorted({n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute) and isinstance(n.value,ast.Attribute) and isinstance(n.value.value,ast.Name) and n.value.value.id=='self' and n.value.attr=='env'})
assert attrs==['clear','enter','exit','measure'],attrs
forbidden={'case_id','seed','scenario','LocalEnv','Source','expected_rows','exposed_cases'}
bad=sorted({n.id for n in ast.walk(tree) if isinstance(n,ast.Name) and n.id in forbidden})
assert not bad,bad
module=load(candidate)
certificate=ROOT/'experiments/B3/research/certificate_21_999_1864.json'
cert=json.loads(certificate.read_text());assert module._di_certified_points(4)==cert['points']
sys.path.insert(0,str(ROOT/'experiments/B3/research'))
from certify_geometry import exact_verify
proof=exact_verify(cert)
sys.path.insert(0,str(OUT/'research'))
from develop_r1 import run_case
ref=load(parent)
cases=json.loads((OUT/'results/r3_development/cases.json').read_text())
selected=[next(c for c in cases if c['mode']==m and c['group']==g) for m in (3,4) for g in sorted({c['group'] for c in cases})]
fields=['cleared_count','source_count','complete','exit_reason','error','average_clear_time_s','total_virtual_time_s','distance_m','requests','clear_failures']
rows=[]
for case in selected:
    x=run_case(ref,case,{})
    y=run_case(module,case,{'spatial_route':False} if case['mode']==4 else {})
    differences={k:[x[k],y[k]] for k in fields if x[k]!=y[k]}
    assert not differences,(case['case_id'],differences)
    rows.append(dict(case_id=case['case_id'],mode=case['mode'],reference=x,candidate=y,compared_fields=fields,differences=differences))
result=dict(candidate_sha256=sha(candidate),parent_sha256=sha(parent),changed_definitions=changed,env_accesses=attrs,forbidden_names=bad,
    q3_parent_AST_equal=True,certificate_sha256=sha(certificate),points_match=True,exact_verification=proof,
    finite_parent_equivalence=dict(actual_runs=48,unique_cases=24,rows=rows),dependencies={},optional_coverage_file_exists=(candidate.parent/'coverage_points.json').exists())
(OUT/'results/r3_source_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='finite_parent_equivalence'},ensure_ascii=False))
