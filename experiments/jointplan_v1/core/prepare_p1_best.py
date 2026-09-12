"""Post-hoc finite best: diagnostic upper bound on gain, never an actor policy."""
import json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text())
def main():
 base={r['case_id']:r for r in read(ROOT/'results/p1_baseline/case_metrics.json')}
 candidates={cid:[(-1,r)] for cid,r in base.items()}
 configs={}
 for slot in range(12):
  p=ROOT/f'results/p1_slot{slot:02}'
  a=read(p/'independent_audit.json');assert a['passed'] and a['prefixes_exact_and_single_certified_commit']
  configs[slot]=read(ROOT/f'data/p1_batches/slot{slot:02}_config.json')
  for row in read(p/'case_metrics.json'):candidates[row['case_id']].append((slot,row))
 selected={cid:min(values,key=lambda pair:(pair[1]['total_virtual_time_s'],pair[0])) for cid,values in candidates.items()}
 cfg={cid:configs[slot][cid] if slot>=0 else {'jointplan_intervention_limit':0,'jointplan_geometry':False,'jointplan_mixed':False} for cid,(slot,row) in selected.items()}
 out=ROOT/'data/p1_best';out.mkdir(exist_ok=False)
 (out/'config.json').write_text(json.dumps(cfg,separators=(',',':'))+'\n')
 (out/'cases.json').write_text((ROOT/'data/p0_exposed48.json').read_text())
 result=dict(role='post_hoc_finite_best_diagnostic_not_deployable',worlds=48,candidate_runs=324,decisions={cid:dict(slot=slot,baseline_seconds_per_source=base[cid]['average_clear_time_s'],selected_seconds_per_source=row['average_clear_time_s'],run_id=row['run_id']) for cid,(slot,row) in selected.items()},modes={str(q):dict(worlds=len(ids:=[cid for cid,r in base.items() if r['mode']==q]),baseline=statistics.mean(base[c]['average_clear_time_s'] for c in ids),finite_best=statistics.mean(selected[c][1]['average_clear_time_s'] for c in ids),worlds_improved=sum(selected[c][0]>=0 for c in ids)) for q in (3,4)})
 (out/'selection.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='decisions'}))
if __name__=='__main__':main()
