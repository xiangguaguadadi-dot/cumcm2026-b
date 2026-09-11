"""Build self-contained B1 opportunity sensing x B3 certified stations."""
from pathlib import Path
import ast, hashlib, json

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'experiments/R3_open'
PARENT=ROOT/'experiments/20260911_stage3/baseline'

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    b1=PARENT/'B1_R1.py'; b3=PARENT/'B3_R1.py'
    source=b1.read_text()
    old=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='_di_certified_points')
    b3text=b3.read_text()
    new=next(n for n in ast.parse(b3text).body if isinstance(n,ast.FunctionDef) and n.name=='q4_certified_points')
    replacement=ast.get_source_segment(b3text,new).replace('q4_certified_points','_di_certified_points')
    lines=source.splitlines(keepends=True)
    source=''.join(lines[:old.lineno-1])+replacement+'\n'+''.join(lines[old.end_lineno:])
    source=source.replace('# B1 independent source: C0 parents plus explicitly budgeted opportunity sensing.', '# R3_open R1: B1 source with B3 certified Q4 station geometry; Q3 retains B1.')
    ast.parse(source)
    path=OUT/'snapshots/r1_development.py';path.write_text(source)
    (OUT/'research/r1_build_provenance.json').write_text(json.dumps(dict(
        parents={str(p):digest(p) for p in (b1,b3)},
        change='replace only _di_certified_points body with B3 q4_certified_points; Q3 B1 unchanged',
        output=str(path),sha256=digest(path)),indent=2))
    print(path,digest(path))

if __name__=='__main__':main()
