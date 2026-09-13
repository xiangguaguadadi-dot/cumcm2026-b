import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
checks=[]
for name,worlds in [('quick_v1',60),('full_v1',1200),('pressure_v1',24)]:
    d=HERE/name;reg=json.loads((d/'registration.json').read_text());summary=json.loads((d/'summary.json').read_text())
    rows=[json.loads(x) for x in (d/'rows.jsonl').read_text().splitlines()]
    ids={r['case_id'] for r in rows}
    checks.append({'run':name,'rows':len(rows),'expected_rows':2*worlds,'row_count_matches':len(rows)==2*worlds,'worlds':len(ids),
      'two_arms_each':all(sum(r['case_id']==i for r in rows)==2 for i in ids),
      'all_complete_recomputed':all(r['complete'] for r in rows),
      'directional_exclusions_recomputed':sum(h.get('true_type')=='directional' and not h.get('true_heading_retained') for r in rows for h in r['heading_certificates']),
      'rows_hash_matches':sha(d/'rows.jsonl')==summary['rows_sha256'],
      'runner_hash_matches':sha(HERE/'run_experiment.py')==reg['runner_sha256'],
      'c7_hash_matches':sha(HERE.parents[2]/'experiments/20260911_stage4/combination/geometry_fusions/C7_both.py')==reg['c7_sha256']})
stress_reg=json.loads((HERE/'stress_registration.json').read_text());stress=json.loads((HERE/'continuous_stress_result.json').read_text())
checks.append({'run':'continuous_stress','script_hash_matches':sha(HERE/'continuous_stress.py')==stress_reg['stress_script_sha256'],
 'implementation_hash_matches':sha(HERE/'run_experiment.py')==stress_reg['certificate_implementation_sha256'],
 'status':stress['status'],'directional_exclusions':stress['directional_exclusions'],'omni_certified':stress['omni_certified']})
passed=all(all(v is True for k,v in c.items() if k in ('row_count_matches','two_arms_each','all_complete_recomputed','rows_hash_matches','runner_hash_matches','c7_hash_matches','script_hash_matches','implementation_hash_matches')) and c.get('directional_exclusions_recomputed',0)==0 and c.get('directional_exclusions',0)==0 and c.get('status','pass')=='pass' for c in checks)
out={'status':'pass' if passed else 'fail','checks':checks}
(HERE/'FINAL_AUDIT.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
