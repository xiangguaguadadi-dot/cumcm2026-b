"""Build independently deployable source; never runtime-import another worktree."""
from pathlib import Path
import ast,io,tokenize,hashlib,json
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'experiments/B1'
def rename_source(source,prefix):
 tree=ast.parse(source);names=set()
 for n in tree.body:
  if isinstance(n,(ast.FunctionDef,ast.ClassDef)):names.add(n.name)
  elif isinstance(n,ast.Assign):
   names.update(x.id for target in n.targets for x in ast.walk(target) if isinstance(x,ast.Name))
 toks=[]
 for tok in tokenize.generate_tokens(io.StringIO(source).readline):
  if tok.type==tokenize.NAME and tok.string in names:tok=tok._replace(string=prefix+tok.string)
  toks.append(tok)
 return tokenize.untokenize(toks)
def build():
 a=ROOT/'experiments/20260911_agent_campaign/final_candidates/A1_space_R8.py'
 d=ROOT/'experiments/20260911_agent_campaign/final_candidates/A4_directional_R6.py'
 s='# B1 independent source: C0 parents plus explicitly budgeted opportunity sensing.\n'
 s+=rename_source(a.read_text(),'_sp_')+'\n\n'+rename_source(d.read_text(),'_di_')
 s+='\n\n'+(OUT/'research/sharing_component.py').read_text()
 p=OUT/'snapshots/r1_development.py';p.write_text(s)
 (OUT/'research/build_provenance.json').write_text(json.dumps(dict(parents={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (a,d)},transformation='token-level global identifier namespacing, source comments preserved; no dynamic exec or external imports',output=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()),indent=2))
 print(p,hashlib.sha256(p.read_bytes()).hexdigest())
if __name__=='__main__':build()
