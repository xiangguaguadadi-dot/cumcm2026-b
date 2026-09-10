"""Validate recorded artifacts without rerunning or tuning any candidate."""
import json,hashlib,statistics,ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];EXP=ROOT/'experiments/A3_coordination'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checks=[]
def check(value,name):
 assert value,name
 checks.append(name)
manifest=json.loads((ROOT/'evaluation/manifest_v1.json').read_text())
check(all(sha(ROOT/p)==h for p,h in manifest['sha256'].items()),'all frozen evaluation files unchanged')
for r in (1,2,3):
 snapshot=EXP/f'snapshots/r{r}_solver.py';ast.parse(snapshot.read_text())
 for suite,n in (('quick',120),('full',2400)):
  d=ROOT/f'results/A3_coordination_r{r}_{suite}'
  s=json.loads((d/'summary.json').read_text());rows=json.loads((d/'case_metrics.json').read_text());c=[x for x in rows if x['variant']=='candidate']
  check(s['candidate_sha256']==sha(snapshot),f'r{r} {suite} solver provenance')
  check(s['all_complete'] and len(c)==n and all(x['complete'] and not x['error'] and x['exit_reason']=='user_exit' for x in c),f'r{r} {suite} all completed normally')
  if suite=='full':
   a=json.loads((EXP/f'r{r}_analysis.json').read_text())
   for m in (3,4):
    mean=statistics.mean(x['average_clear_time_s'] for x in c if x['mode']==m)
    check(abs(mean-a['metrics'][str(m)]['mean_s_per_source'])<1e-10,f'r{r} Q{m} recomputed mean')
 nom=json.loads((EXP/f'research/r{r}_nominal.json').read_text())
 check(nom['passed']==nom['total']==79,f'r{r} nominal 79/79')
 check('Ran 14 tests' in (EXP/f'research/r{r}_tests.txt').read_text() and (EXP/f'research/r{r}_tests.txt').read_text().endswith('OK\n'),f'r{r} rules 14/14')
b=json.loads((EXP/'best.json').read_text())
check(b['best_round']==2 and b['candidate_rounds']==3,'best and stopping round')
check(sha(ROOT/'solver.py')==sha(ROOT/b['solver_relative_path'])==b['solver_sha256'],'working solver equals best snapshot')
l=json.loads((EXP/'literature.json').read_text())
check(len(l['items'])==10 and len({x['id'] for x in l['items']})==10,'10 unique literature records')
check(sum(x['tier']=='core' for x in l['items'])==5,'5 core and 5 extended')
check(all(x['url'].startswith('https://arxiv.org/abs/') and x['read_range'] and x['inspiration'] and x['implementation_level'] for x in l['items']),'literature source/read/inspiration/code trace fields')
check(not b['dependencies'] and not b['trained_weights'] and not (ROOT/'coverage_points.json').exists(),'no untracked solver module/weight/config dependency')
output=dict(passed=len(checks),checks=checks)
(EXP/'artifact_validation.json').write_text(json.dumps(output,ensure_ascii=False,indent=2));print(json.dumps(output,ensure_ascii=False,indent=2))
