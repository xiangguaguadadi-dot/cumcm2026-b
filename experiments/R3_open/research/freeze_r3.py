from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'experiments/R3_open'
t,d=[json.loads((OUT/f'results/r3_{x}/summary.json').read_text()) for x in ('train','development')]
assert all(g['complete']==g['cases'] for z in (t,d) for v in z.values() for g in v['groups'])
selected=min(d,key=lambda k:next(g['mean'] for g in d[k]['groups'] if g['mode']==4 and g['group']=='ALL'));assert selected=='naive_global'
s=(OUT/'snapshots/r3_development.py').read_text();needle="4:dict(_di_OPTIMIZED_CONFIGS[4],sharing_style='visibility',sharing_gain_m=30.)}"
assert s.count(needle)==1;s=s.replace(needle,"4:dict(_di_OPTIMIZED_CONFIGS[4],sharing_style='visibility',sharing_gain_m=30.,spatial_route=True,spatial_ready_radius=1e9)}")
(OUT/'snapshots/r3.py').write_text(s)
p=json.loads((OUT/'optimization_path.json').read_text());n=next(n for n in p['nodes'] if n['id']=='R3_R3');n.update(selected=selected,candidate='experiments/R3_open/snapshots/r3.py',candidate_sha256=hashlib.sha256(s.encode()).hexdigest(),status='frozen_before_regression',development_q4_parent=next(g['mean'] for g in d['R2']['groups'] if g['mode']==4 and g['group']=='ALL'),development_q4_candidate=next(g['mean'] for g in d[selected]['groups'] if g['mode']==4 and g['group']=='ALL'),training_q4_parent=next(g['mean'] for g in t['R2']['groups'] if g['mode']==4 and g['group']=='ALL'),training_q4_candidate=next(g['mean'] for g in t[selected]['groups'] if g['mode']==4 and g['group']=='ALL'))
(OUT/'optimization_path.json').write_text(json.dumps(p,ensure_ascii=False,indent=2))
src=(OUT/'research/audit_r2.py').read_text().replace("'snapshots/r2.py';parent=OUT/'snapshots/r1.py'","'snapshots/r3.py';parent=OUT/'snapshots/r2.py'").replace("assert changed==['_di_Solver'],changed","assert changed==['_di_Solver','OPTIMIZED_CONFIGS'],changed").replace("'results/r2_development/cases.json'","'results/r3_development/cases.json'").replace("{'stop_discovered':False}","{'spatial_route':False}").replace("'results/r2_source_audit.json'","'results/r3_source_audit.json'")
(OUT/'research/audit_r3.py').write_text(src)
print(n)
