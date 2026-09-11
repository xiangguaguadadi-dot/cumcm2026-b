from pathlib import Path
import json,hashlib,datetime
OUT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
src=OUT/'snapshots/r5_development.py';backup=OUT/'snapshots/r5_initial_graph.py';assert not backup.exists();backup.write_bytes(src.read_bytes());oldsha=sha(src)
old="        if denominator:\n            graphs.append((partition,denominator))"
new="        if not denominator:\n            # One color already puts all finite hypotheses in a decision;\n            # a continuous source certificate still requires the real polygon.\n            return ()\n        graphs.append((partition,denominator))"
assert src.read_text().count(old)==1
for p in (src,OUT/'research/r5_component.py'):
 text=p.read_text();assert text.count(old)==1;p.write_text(text.replace(old,new))
record=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),old_snapshot=str(backup),old_sha256=oldsha,new_sha256=sha(src),original_results='results/r5_development',reason='An ECD color with zero original edge mass means a finite decision already succeeds. Omitting that color could invent residual ambiguity. Return the explicit degenerate signal and fall back to multi-cost, without any continuous certificate change.',run_status='Original384x3 all complete and retained; corrected full384x3 will rerun same development cases. They are not fresh or independent replication.',data_boundary='This correction was prompted by source/logic review, not selection of exposed performance. No R5 exposed run exists.')
(OUT/'research/r5_code_correction.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
p=OUT/'optimization_path.json';data=json.loads(p.read_text());data['rounds'][-1]['in_development_correction']=record;p.write_text(json.dumps(data,ensure_ascii=False,indent=2))
print(record)
