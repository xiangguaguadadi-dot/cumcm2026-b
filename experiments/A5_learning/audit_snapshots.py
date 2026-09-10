"""Read-only structural and artifact provenance checks for A5 snapshots."""
import ast,hashlib,json,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1]
protected=['initial_polygon','add_bearing','certified_points','cover_polygon','measure','clear','_virtual_fallback','_time_guard','rescue_bearing','scan_station','localize','next_station','enclosing_circle']
def methods(path):
 tree=ast.parse(path.read_text());return {n.name:ast.dump(n,include_attributes=False) for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))},tree
base,_=methods(P/'snapshots/r0_solver.py');rows=[]
for path in sorted((P/'snapshots').glob('r*_solver.py')):
 fs,t=methods(path);attrs=sorted({n.attr for n in ast.walk(t) if isinstance(n,ast.Attribute) and isinstance(n.value,ast.Attribute) and isinstance(n.value.value,ast.Name) and n.value.value.id=='self' and n.value.attr=='env'})
 certificate=path.read_text().split('        unresolved=[c for c in range(1,21) if c not in self.cleared]')[1]
 base_certificate=(P/'snapshots/r0_solver.py').read_text().split('        unresolved=[c for c in range(1,21) if c not in self.cleared]')[1]
 rows.append(dict(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  protected_function_unchanged={k:fs[k]==base[k] for k in protected},exit_certificate_tail_identical=certificate==base_certificate,
                  simulator_attribute_calls=attrs,simulator_boundary_valid=attrs==['clear','enter','exit','measure']))
assert all(all(r['protected_function_unchanged'].values()) and r['exit_certificate_tail_identical'] and r['simulator_boundary_valid'] for r in rows)
# Frozen manifest checks remain the authoritative evaluation integrity check.
r=subprocess.run([__import__('sys').executable,str(ROOT/'evaluate.py'),'--verify-only'],capture_output=True,text=True,check=True)
report=dict(note='Static structural check, not a hostile-code sandbox proof; exact protected functions and exit tail preserved.',snapshots=rows,frozen_verification=r.stdout.strip())
(P/'snapshot_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
