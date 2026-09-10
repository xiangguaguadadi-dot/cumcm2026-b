"""Read stored A2 outputs and source only; never rerun strategies or read cases."""
import ast,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
records=json.loads((OUT/'round_metrics.json').read_text());audits=[]
for rec in records:
    k=rec['round'];path=OUT/f'candidates/r{k}_solver.py';suites={}
    for suite,n in [('quick',120),('full',2400)]:
        folder=ROOT/f'results/A2_information_r{k}_{suite}'
        summary=json.loads((folder/'summary.json').read_text());rows=json.loads((folder/'case_metrics.json').read_text())
        candidate=[r for r in rows if r['variant']=='candidate'];baseline=[r for r in rows if r['variant']=='frozen_baseline']
        ac={(r['mode'],r['case_id']):r for r in candidate};bc={(r['mode'],r['case_id']):r for r in baseline}
        assert len(candidate)==len(baseline)==len(ac)==len(bc)==n and ac.keys()==bc.keys()
        assert summary['candidate_sha256']==sha(path) and summary['all_complete']
        assert all(r['complete'] and not r['error'] and r['exit_reason']=='user_exit' and r['coverage_certificate'] for r in candidate)
        suites[suite]=dict(unique_paired_cases=n,all_complete=True,normal_exit=True,all_coverage_certificates=True,errors=0,sha_matches=True,wall_seconds=summary['wall_seconds'],summary_sha256=sha(folder/'summary.json'),case_metrics_sha256=sha(folder/'case_metrics.json'))
    rules=ROOT/f'results/A2_information_r{k}_rules';nominal=json.loads((rules/'nominal.json').read_text())
    assert nominal['passed']==nominal['total']==79
    unittest=(rules/'unittest.txt').read_text();assert 'Ran 14 tests' in unittest and 'OK' in unittest
    audits.append(dict(round=k,sha256=sha(path),code_commit=rec['code_commit'],suites=suites,nominal_passed=79,unit_tests_passed=14))
best=json.loads((OUT/'best.json').read_text());best_path=ROOT/best['solver_relative_path']
assert sha(ROOT/'solver.py')==sha(best_path)==best['solver_sha256']
assert sha(ROOT/'evaluation/manifest_v1.json')=='431210a6d96e721d23c31698aa389702ea87dcffe8fee6250f71ce6e902be140'
assert not (ROOT/'coverage_points.json').exists() and not (best_path.parent/'coverage_points.json').exists()
tree=ast.parse(best_path.read_text());methods=[]
for n in ast.walk(tree):
    if isinstance(n,ast.Attribute) and isinstance(n.value,ast.Attribute) and isinstance(n.value.value,ast.Name) and n.value.value.id=='self' and n.value.attr=='env':methods.append(n.attr)
assert set(methods)=={'enter','measure','clear','exit'}
audit=dict(rounds=audits,best_round=best['best_round'],strict_best_workspace_match=True,no_adjacent_coverage_json=True,frozen_manifest_sha256=sha(ROOT/'evaluation/manifest_v1.json'),current_best_env_methods=sorted(set(methods)),source_code_commit=best['code_commit'],empirical_stop=best['consecutive_rounds_without_strict_best']==2,not_a_sandbox_proof='AST inventory plus manual source review, not a malicious-code security proof',replayed_strategy_runs=0)
(OUT/'final_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
development=[]
for p in sorted((OUT/'dev').glob('r*.json')):
    d=json.loads(p.read_text())
    if 'rows' not in d:continue
    rows=d['rows'];development.append(dict(file=str(p.relative_to(OUT)),runs=len(rows),baseline_runs=sum(r['variant']=='baseline' for r in rows),candidate_runs=sum(r['variant']=='candidate' for r in rows),baseline_path=d.get('baseline_path','evaluation/baseline_solver.py'),wall_seconds=d.get('elapsed')))
diagnostics=[dict(file=str(p.relative_to(OUT)),attempts=sum(bool(line.strip()) for line in p.read_text().splitlines())) for p in sorted((OUT/'dev').glob('*watchdog*.jsonl'))]
full_n=sum(a['suites']['full']['unique_paired_cases'] for a in audits);quick_n=sum(a['suites']['quick']['unique_paired_cases'] for a in audits)
budget=dict(candidate_full_runs=full_n,candidate_quick_runs=quick_n,evaluation_baseline_runs=0,evaluation_baseline_was_cached=True,development=development,diagnostics=diagnostics,full_wall_seconds=sum(a['suites']['full']['wall_seconds'] for a in audits),quick_wall_seconds=sum(a['suites']['quick']['wall_seconds'] for a in audits),recorded_environment_run_or_attempt_total=full_n+quick_n+sum(d['runs'] for d in development)+sum(d['attempts'] for d in diagnostics),excluded='Rule/geometry checks excluded. R4 original interrupted development ran additional cases with no reliable complete count; total is a recorded lower bound, not all historical calls.')
(OUT/'execution_budget.json').write_text(json.dumps(budget,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(audited_rounds=len(audits),best_round=best['best_round'],recorded_runs=budget['recorded_environment_run_or_attempt_total'],empirical_stop=audit['empirical_stop'])))
