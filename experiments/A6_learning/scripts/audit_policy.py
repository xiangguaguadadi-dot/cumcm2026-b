"""Evidence for interface boundary and preservation of analytic certificates."""
import ast,hashlib,json,sys
from pathlib import Path
base=Path(__file__).resolve().parents[1];root=base.parents[1]
path=Path(sys.argv[1]) if len(sys.argv)>1 else root/'solver.py'
a=ast.parse((base/'snapshots/baseline_solver.py').read_text());b=ast.parse(path.read_text())
def functions(tree):return {x.name:ast.dump(x,include_attributes=False) for x in ast.walk(tree) if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))}
af,bf=functions(a),functions(b)
protected=['certified_points','initial_polygon','clip','add_bearing','enclosing_circle','cover_polygon','_virtual_fallback','_time_guard','scan_station','measure','clear','rescue_bearing','localize']
s=(base/'snapshots/baseline_solver.py').read_text();t=path.read_text()
checks={name:af[name]==bf[name] for name in protected}
checks['exit_certificate_unchanged']=s[s.index('        unresolved='):]==t[t.index('        unresolved='):]
attrs=sorted({x.attr for x in ast.walk(b) if isinstance(x,ast.Attribute) and isinstance(x.value,ast.Attribute) and isinstance(x.value.value,ast.Name) and x.value.value.id=='self' and x.value.attr=='env'})
checks['env_calls_exact_four']=attrs==['clear','enter','exit','measure']
checks['no_training_import']=not any(isinstance(x,ast.ImportFrom) and x.module and ('local_env' in x.module or 'evaluation' in x.module) for x in ast.walk(b))
checks['coverage_override_absent']=not (path.parent/'coverage_points.json').exists() and not(root/'coverage_points.json').exists()
result=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),checks=checks,env_attributes=attrs,all_passed=all(checks.values()))
print(json.dumps(result,ensure_ascii=False,indent=2))
if not result['all_passed']:raise SystemExit(1)
