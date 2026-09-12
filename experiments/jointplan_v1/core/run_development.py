"""Predeclared first development ablation: anchor/A/B/A+B on the same 96 worlds."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];C=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path(__file__).resolve().parent))
from audit import audit_batch
from paired_stats import compare
from runner import dump,digest

def main():
 assert json.loads((C/'results/P1_RESULT.json').read_text())['passed']
 defs=[('anchor','experiments/parallel_v2_coordinator/fusion_r5.py'),('a_only','experiments/jointplan_v1/planner/candidate_a_only.py'),('b_only','experiments/jointplan_v1/planner/candidate_b_only.py'),('joint','experiments/jointplan_v1/planner/candidate_joint.py')]
 deps=[C/p for p in ('planner/candidate_disabled.py','planner/candidate_joint.py','planner/mixed_planner.py','geometry/__init__.py','geometry/continuous.py','geometry/engine.py')]+[ROOT/'experiments/parallel_v2_coordinator/fusion_r5.py']
 source={str(p):digest(p) for p in deps+[ROOT/p for _,p in defs]+[Path(__file__).resolve()]}
 dump(C/'data/development96/ablation_registration.json',dict(arms=defs,source_files=source,selection='Compare each question separately; no failure-subset speed claims. Development results may guide later versions.',cases_sha256=digest(C/'data/development96/cases.json')))
 results=[];anchor=None
 for label,path in defs:
  assert all(digest(p)==s for p,s in source.items())
  out=C/('results/dev_r1_'+label)
  if label!='anchor':subprocess.run([sys.executable,'-S','-B',str(C/'core/check_rules.py'),str(C/('results/dev_r1_'+label+'_rules'))],cwd=ROOT,check=True)
  cmd=[sys.executable,'-S','-B',str(C/'core/runner.py'),'--candidate',str(ROOT/path),'--cases',str(C/'data/development96/cases.json'),'--out',str(out),'--phase','P2','--label',label]
  for dep in deps+[Path(__file__).resolve()]:cmd+=['--dependency',str(dep)]
  subprocess.run(cmd,cwd=ROOT,check=True)
  audit,_=audit_batch(out);dump(out/'independent_audit.json',audit)
  rows=json.loads((out/'case_metrics.json').read_text())
  if anchor is None:anchor=rows
  comparison=compare(anchor,rows);dump(out/'paired_comparison.json',comparison)
  results.append(dict(arm=label,audit=audit,mode_summaries=[r for r in comparison if r['group']=='ALL']))
  dump(C/'results/dev_r1_progress.json',dict(arms=results))
  print(json.dumps(dict(arm=label,modes=[r for r in comparison if r['group']=='ALL'])),flush=True)
  assert audit['modes']['3']['complete']==48 and audit['modes']['4']['complete']==48,'Actual failure retained: review before continuing'
 print(json.dumps(dict(complete_arms=4,full_runs=384)))
if __name__=='__main__':main()
