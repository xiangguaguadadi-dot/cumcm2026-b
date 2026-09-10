"""Apply trained configuration to a self-contained solver snapshot."""
import argparse,ast,hashlib,importlib.util,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--selected',required=True);p.add_argument('--template',required=True);p.add_argument('--out',required=True);a=p.parse_args()
source=Path(a.template);spec=importlib.util.spec_from_file_location('template',source);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
selected=json.loads(Path(a.selected).read_text());conf={mode:{**m.OPTIMIZED_CONFIGS[mode],**selected['modes'][str(mode)]['config']} for mode in (3,4)}
s=source.read_text();tree=ast.parse(s);node=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='OPTIMIZED_CONFIGS' for t in n.targets));lines=s.splitlines(keepends=True)
s=''.join(lines[:node.lineno-1])+'OPTIMIZED_CONFIGS = '+repr(conf)+'\n'+''.join(lines[node.end_lineno:])
out=Path(a.out);out.write_text(s);print(json.dumps(dict(path=str(out),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),selected=a.selected),indent=2))
