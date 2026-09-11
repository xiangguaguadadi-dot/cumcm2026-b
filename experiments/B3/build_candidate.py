"""Build a standard-library standalone candidate with exact parent namespaces."""
from pathlib import Path
import ast,tokenize,io,json,hashlib
ROOT=Path(__file__).resolve().parents[2];D=ROOT/'experiments/B3';BASE=ROOT/'experiments/20260911_breakthrough/baseline'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def renamed(s,prefix):
 tree=ast.parse(s);names={n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
 for n in tree.body:
  if isinstance(n,ast.Assign):names.update(t.id for t in n.targets if isinstance(t,ast.Name))
 names={n:prefix+n for n in names}
 ts=[]
 for t in tokenize.generate_tokens(io.StringIO(s).readline):
  if t.type==tokenize.NAME and t.string in names:t=t._replace(string=names[t.string])
  ts.append(t)
 return tokenize.untokenize(ts)
q3=(BASE/'A1_space_R8.py').read_text();q4=(BASE/'A4_directional_R6.py').read_text()
points=json.loads((D/'research/certificate_21_999_1864.json').read_text())['points']
start=q4.index('    # Seven sectors, each split into four triangles.')
end=q4.index('\n\n\ndef default_points',start)
q4=q4[:start]+'''    # B3: exact-decimal 21-station continuous half-plane coverage certificate.
    # Each certified quadtree leaf lies in the convex hull of stations all
    # within 1000m of the entire leaf; at least one is in every closed
    # emission half-plane. See research/certificate_21_999_1864.json.
    return '''+repr(points)+q4[end:]
head='''"""B3 R1: new certified 21-station Q4 coverage; C0's Q3 is unchanged.
Self-contained standard-library source. Q3/Q4 namespaces are renamed parent
snapshots, avoiding cross-mode changes to global helpers. No training weights.
"""\n'''
tail='''\nOPTIMIZED_CONFIGS={3:dict(q3_OPTIMIZED_CONFIGS[3]),4:dict(q4_OPTIMIZED_CONFIGS[4])}
BASELINE_CONFIG=dict(q3_BASELINE_CONFIG)
class Solver:
    def __new__(cls,env,mode=3,**config):
        if mode not in (3,4):raise ValueError('mode must be 3 or 4')
        parent=q3_Solver if mode==3 else q4_Solver
        return parent(env,mode=mode,**config)
'''
code=head+renamed(q3,'q3_')+'\n\n'+renamed(q4,'q4_')+tail
out=D/'snapshots/r1_solver.py';out.write_text(code)
(D/'snapshots/r1_metadata.json').write_text(json.dumps({'candidate_sha256':sha(out),'parent_files':{n:sha(BASE/n) for n in ('A1_space_R8.py','A4_directional_R6.py')},'changes':['Q4 certified_points replaced by 21 exact-decimal stations; remaining Q4 operations unchanged','Namespace-only renaming of both parents; Q3 operations unchanged'],'certificate_sha256':sha(D/'research/certificate_21_999_1864.json'),'dependencies':{},'config':'same parent configs'},indent=2))
print(sha(out))
