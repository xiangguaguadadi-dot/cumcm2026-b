from pathlib import Path
import json,hashlib,datetime
OUT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
p=OUT/'snapshots/r5_development.py';b=OUT/'snapshots/r5_graph_corrected.py';assert not b.exists();b.write_bytes(p.read_bytes())
old='key=(tuple(poly),tuple(self.no_signal_points[ch]),tuple(self.failed_clear_points[ch]))';new='key=(tuple(poly),tuple(self.observations[ch]),tuple(self.no_signal_points[ch]),tuple(self.failed_clear_points[ch]))'
for f in (p,OUT/'research/r5_component.py'):
 text=f.read_text();assert text.count(old)==1;f.write_text(text.replace(old,new))
record=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),old_snapshot=str(b),old_sha256=sha(b),new_sha256=sha(p),original_results='results/r5_corrected_development',reason='Identical retained polygons can have different positive-observation histories. Those histories condition the hypothetical receive-radius interval, so they must be part of its cache key.',run_status='Two completed384x3 builds retained; final corrected384x3 reruns the same development cases. No new statistical sample, no exposed evaluation.',not_a_new_method='One-line state-cache correctness fix; same selection criterion and hypotheses.')
(OUT/'research/r5_cache_correction.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
p=OUT/'optimization_path.json';data=json.loads(p.read_text());data['rounds'][-1]['cache_correction']=record;data['rounds'][-1]['status']='final_development_correction_running';p.write_text(json.dumps(data,ensure_ascii=False,indent=2));print(record)
