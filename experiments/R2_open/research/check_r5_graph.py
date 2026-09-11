from pathlib import Path
import importlib.util,json,math
OUT=Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('r5check',OUT/'snapshots/r5_development.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
checks=[]
def check(name,passed,detail):
 checks.append(dict(name=name,passed=bool(passed),detail=detail));assert passed,name
h=[(-1.,0.),(1.,0.)];check('already_one_service_region',m._decision_region_graphs(h)==(), 'must signal finite-decision degeneracy and fall back; not certify real P')
h=[(0.,0.),(100.,0.),(200.,0.)];g=m._decision_region_graphs(h)
check('disjoint_all_remaining_zero_progress',abs(m._decision_progress(g,7))<1e-12, 'three separated positions')
check('disjoint_two_survive_two_thirds_cut',abs(m._decision_progress(g,3)-2/3)<1e-12, 'one of three equal pair edges remains')
check('single_hypothesis_finite_goal',m._decision_progress(g,1)==1., 'decision region always contains this finite hypothesis')
check('empty_survivors_not_a_certificate',m._decision_progress(g,0) is None, 'model/sample failure must fallback')
for label,h in [('overlap_line',[(-30.,0.),(0.,0.),(30.,0.)]),('square',[(0.,0.),(30.,0.),(30.,30.),(0.,30.)])]:
 actions=h+[((a[0]+b[0])/2,(a[1]+b[1])/2) for i,a in enumerate(h) for b in h[i+1:] if math.dist(a,b)<=40.]
 regions=[{j for j,z in enumerate(h) if math.dist(z,a)<=20.} for a in actions]
 graph=m._decision_region_graphs(h);limit=(1<<len(h))-1
 for mask in range(1,limit+1):
  survivors={j for j in range(len(h)) if mask&(1<<j)};goal=any(survivors<=r for r in regions);value=m._decision_progress(graph,mask)
  check(f'{label}_mask{mask}_goal_equivalence', (abs(value-1.)<1e-12)==goal,dict(survivors=sorted(survivors),value=value,goal=goal))
  for sub in range(1,mask+1):
   if sub&mask==sub:
    check(f'{label}_mask{mask}_sub{sub}_monotone',m._decision_progress(graph,sub)>=value-1e-12,'ordinary set inclusion only, no adaptive-submodularity claim')
(OUT/'results/r5_graph_checks.json').write_text(json.dumps(dict(checks=checks,passed=len(checks),scope='Deterministic finite-graph invariants, no source-search episodes or random seed'),ensure_ascii=False,indent=2));print(len(checks),'finite graph invariant checks passed')
