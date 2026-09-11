from pathlib import Path
import json,hashlib
P=Path(__file__).resolve().parents[1];ROOT=P.parents[1]
src=(P/'snapshots/r4_blocks.py').read_text()
old='                    if i==j:continue'
assert src.count(old)==1
src=src.replace(old,'                    if i!=0 or i==j:continue')
src=src.replace('# E1 R4: directed entry/service/exit task blocks; predictions only.','# E1 R5: only the immediate task has a predicted entry/service block; future targets keep centers.')
path=P/'snapshots/r5_immediate_block.py';path.write_text(src)
component=(P/'research/service_block_component.py').read_text().replace(old,'                    if i!=0 or i==j:continue')
(P/'research/immediate_block_component.py').write_text(component)
items=json.loads((P/'research/r4_candidates.json').read_text())[:2]
items.append(dict(name='r5_immediate_block',file=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),config={}))
(P/'research/r5_candidates.json').write_text(json.dumps(items,indent=2))
