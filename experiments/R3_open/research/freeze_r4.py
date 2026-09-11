from pathlib import Path
import json,hashlib,datetime
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'experiments/R3_open'
t,d=[json.loads((OUT/f'results/r4_{x}/summary.json').read_text()) for x in ('train','development')]
assert all(g['complete']==g['cases'] for z in (t,d) for v in z.values() for g in v['groups'])
mean=lambda z,k:next(g['mean'] for g in z[k]['groups'] if g['mode']==4 and g['group']=='ALL')
assert mean(d,'route_clear')<mean(d,'R3')
s=(OUT/'snapshots/r4_development.py').read_text();needle='spatial_route=True,spatial_ready_radius=1e9)}';assert s.count(needle)==1;s=s.replace(needle,'spatial_route=True,spatial_ready_radius=1e9,route_clear=True)}');(OUT/'snapshots/r4.py').write_text(s)
p=json.loads((OUT/'optimization_path.json').read_text());n=next(n for n in p['nodes'] if n['id']=='R3_R4');n.update(selected='route_clear',candidate='experiments/R3_open/snapshots/r4.py',candidate_sha256=hashlib.sha256(s.encode()).hexdigest(),status='frozen_before_regression',frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),development_q4_parent=mean(d,'R3'),development_q4_candidate=mean(d,'route_clear'),training_q4_parent=mean(t,'R3'),training_q4_candidate=mean(t,'route_clear'));(OUT/'optimization_path.json').write_text(json.dumps(p,ensure_ascii=False,indent=2))
src=(OUT/'research/audit_r3.py').read_text().replace("'snapshots/r3.py';parent=OUT/'snapshots/r2.py'","'snapshots/r4.py';parent=OUT/'snapshots/r3.py'").replace("'results/r3_development/cases.json'","'results/r4_development/cases.json'").replace("{'spatial_route':False}","{'route_clear':False}").replace("'results/r3_source_audit.json'","'results/r4_source_audit.json'")
(OUT/'research/audit_r4.py').write_text(src);print(n)
