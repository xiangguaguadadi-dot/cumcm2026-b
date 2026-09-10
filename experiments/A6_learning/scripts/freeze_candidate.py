"""Freeze selected configs into a standalone candidate; run only after training."""
import argparse,ast,json,hashlib
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];ROOT=BASE.parents[1]
p=argparse.ArgumentParser();p.add_argument('--round',type=int,required=True);a=p.parse_args()
selected=json.loads((BASE/'training'/f'r{a.round}'/'selected.json').read_text())
f=ROOT/'solver.py';source=f.read_text();tree=ast.parse(source)
node=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='OPTIMIZED_CONFIGS' for t in n.targets))
lines=source.splitlines(keepends=True)
new='OPTIMIZED_CONFIGS = '+repr({int(k):v['config'] for k,v in selected.items()})+'\n'
source=''.join(lines[:node.lineno-1])+new+''.join(lines[node.end_lineno:])
f.write_text(source)
snapshot=BASE/'snapshots'/f'r{a.round}_solver.py';snapshot.write_text(source)
meta={'round':a.round,'solver_sha256':hashlib.sha256(snapshot.read_bytes()).hexdigest(),'solver_path':str(snapshot.relative_to(ROOT)),'config_source':str((BASE/'training'/f'r{a.round}'/'selected.json').relative_to(ROOT)),'configs':{k:v['config'] for k,v in selected.items()}}
(BASE/'snapshots'/f'r{a.round}_metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
print(json.dumps(meta,ensure_ascii=False,indent=2))
