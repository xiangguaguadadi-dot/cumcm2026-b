"""Execute the fixed 324 P1 interventions, stopping only for actual errors."""
import json,subprocess,sys,gzip
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];CAMPAIGN=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path(__file__).resolve().parent))
from audit import audit_batch,normalize
from runner import dump,digest

def main():
 dependencies=['planner/candidate_disabled.py','planner/mixed_planner.py','geometry/__init__.py','geometry/continuous.py','geometry/engine.py']
 base=CAMPAIGN/'data/p1_batches';reg=json.loads((base/'registration.json').read_text())
 assert reg['candidate_full_runs']==324
 anchor=audit_batch(CAMPAIGN/'results/p1_baseline')[1]
 results=[]
 for slot,count in enumerate(reg['slot_counts']):
  if not count:continue
  out=CAMPAIGN/f'results/p1_slot{slot:02}'
  cmd=[sys.executable,'-S','-B',str(CAMPAIGN/'core/runner.py'),'--candidate',str(CAMPAIGN/'planner/candidate_joint.py'),'--cases',str(base/f'slot{slot:02}_cases.json'),'--config-by-case',str(base/f'slot{slot:02}_config.json'),'--out',str(out),'--phase','P1','--label',f'slot{slot:02}']
  for name in dependencies:cmd+=['--dependency',str(CAMPAIGN/name)]
  cmd+=['--dependency',str(ROOT/'experiments/parallel_v2_coordinator/fusion_r5.py')]
  subprocess.run(cmd,cwd=ROOT,check=True)
  stats,records=audit_batch(out)
  assert all(r['row']['complete'] for r in records.values()),'Retained actual failure: stop and review'
  for cid,record in records.items():
   diag=record['data']['policy_diagnostics'];assert diag['replay_status']=='committed_once',(cid,diag['replay_status'])
   assert diag['interventions']==1
   decisions=[d for d in diag['decisions'] if d['status']=='commit_parent_schedule']
   assert len(decisions)==1
   d=decisions[0];n=d['history_version'];assert record['traces'][:n]==anchor[cid]['traces'][:n]
   assert d['commit_certificate']['status']=='certified'
  stats['prefixes_exact_and_single_certified_commit']=True
  dump(out/'independent_audit.json',stats);results.append(stats)
  dump(CAMPAIGN/'results/p1_progress.json',dict(slots_complete=len(results),candidate_runs=sum(r['runs'] for r in results),summaries=results))
 print(json.dumps(dict(completed_candidates=sum(r['runs'] for r in results),all_prefixes_exact=True)))
if __name__=='__main__':main()
