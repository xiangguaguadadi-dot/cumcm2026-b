"""Read-only source identity, interface and attached proof verification."""
from pathlib import Path
import ast,json,hashlib,importlib.util,sys,argparse
ROOT=Path(__file__).resolve().parents[3];D=ROOT/'experiments/B3';BASE=ROOT/'experiments/20260911_breakthrough/baseline'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
class Normalize(ast.NodeTransformer):
 def __init__(self,prefix):self.prefix=prefix
 def visit_Name(self,node):
  if node.id.startswith(self.prefix):node.id=node.id[len(self.prefix):]
  return node
 def visit_FunctionDef(self,node):
  if node.name.startswith(self.prefix):node.name=node.name[len(self.prefix):]
  return self.generic_visit(node)
 def visit_ClassDef(self,node):
  if node.name.startswith(self.prefix):node.name=node.name[len(self.prefix):]
  return self.generic_visit(node)
def nodes(tree,prefix=''):
 selected={}
 for n in tree.body:
  name=n.name if isinstance(n,(ast.FunctionDef,ast.ClassDef)) else (n.targets[0].id if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) else None)
  if name and name.startswith(prefix):
   if prefix:name=name[len(prefix):];n=Normalize(prefix).visit(n)
   selected[name]=ast.dump(n,include_attributes=False)
 return selected
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--out',required=True);a=p.parse_args()
c=Path(a.candidate);tree=ast.parse(c.read_text());parts={}
for prefix,name in [('q3_','A1_space_R8.py'),('q4_','A4_directional_R6.py')]:
 original=nodes(ast.parse((BASE/name).read_text()));selected=nodes(ast.parse(c.read_text()),prefix)
 assert original.keys()==selected.keys()
 changed=[name for name in original if original[name]!=selected[name]]
 parts[prefix]={'parent_sha256':sha(BASE/name),'changed_global_definitions':changed,'same_global_definitions':len(original)-len(changed)}
assert parts['q3_']['changed_global_definitions']==[]
assert parts['q4_']['changed_global_definitions']==['certified_points']
attrs=sorted({n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute) and isinstance(n.value,ast.Attribute) and isinstance(n.value.value,ast.Name) and n.value.value.id=='self' and n.value.attr=='env'})
assert attrs==['clear','enter','exit','measure']
spec=importlib.util.spec_from_file_location('candidate_geometry_identity',c);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
certificate=json.loads((D/'research/certificate_21_999_1864.json').read_text());assert module.q4_certified_points(4)==certificate['points']
sys.path.insert(0,str(D/'research'));from certify_geometry import exact_verify
proof=exact_verify(certificate)
result={'candidate_sha256':sha(c),'parent_AST_comparison':parts,'env_accesses':attrs,'points_match_certificate':True,'certificate_sha256':sha(D/'research/certificate_21_999_1864.json'),'exact_verification':proof,'dependencies':{},'optional_coverage_file_exists':(c.parent/'coverage_points.json').exists()}
Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
