"""Final provenance and paired-row audit; never imported by the online solver."""
import ast
import hashlib
import json
import pathlib
import statistics

ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'experiments/A4_directional'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
best = json.loads((P/'best.json').read_text())
candidate = ROOT/best['best_solver_relative']
manifest = json.loads((ROOT/'evaluation/manifest_v1.json').read_text())
checks = {name: sha(ROOT/name) == digest for name, digest in manifest['sha256'].items()}
assert all(checks.values())
assert sha(candidate) == best['solver_sha256'] == sha(ROOT/'solver.py')
source = candidate.read_text()
tree = ast.parse(source)
imports = sorted({n.name for s in ast.walk(tree) if isinstance(s, ast.Import) for n in s.names})
assert imports == ['json', 'math', 'os', 'time']
env_attributes = sorted({n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
    and isinstance(n.value, ast.Attribute) and isinstance(n.value.value, ast.Name)
    and n.value.value.id == 'self' and n.value.attr == 'env'})
assert env_attributes == ['clear', 'enter', 'exit', 'measure']
assert not any(isinstance(n, ast.ImportFrom) for n in ast.walk(tree))
rows = json.loads((ROOT/best['full_results_relative']/'case_metrics.json').read_text())
summary = json.loads((ROOT/best['full_results_relative']/'summary.json').read_text())
assert summary['candidate_sha256'] == sha(candidate)
assert summary['manifest_sha256'] == sha(ROOT/'evaluation/manifest_v1.json')
by_variant = {}
for variant in ['candidate', 'frozen_baseline']:
    subset = [r for r in rows if r['variant'] == variant]
    index = {(r['case_id'], r['mode']): r for r in subset}
    assert len(subset) == len(index) == 2400
    assert all(r['complete'] and r['exit_reason'] == 'user_exit' and r['error'] is None for r in subset)
    by_variant[variant] = index
assert by_variant['candidate'].keys() == by_variant['frozen_baseline'].keys()
paired = {}
for mode in [3, 4]:
    deltas = [r['average_clear_time_s']-by_variant['frozen_baseline'][k]['average_clear_time_s']
              for k, r in by_variant['candidate'].items() if r['mode'] == mode]
    paired[str(mode)] = dict(total=len(deltas), improved=sum(x < -1e-8 for x in deltas),
        worsened=sum(x > 1e-8 for x in deltas), tied=sum(abs(x) <= 1e-8 for x in deltas),
        mean_change_seconds_per_source=statistics.mean(deltas))
assert paired['3']['tied'] == 1200
round_integrity = []
for number in range(1, 9):
    snap = P/f'candidates/r{number}_solver.py'
    result_dir = P/f'results/r{number}_full'
    result_summary = json.loads((result_dir/'summary.json').read_text())
    run_rows = json.loads((result_dir/'case_metrics.json').read_text())
    actual = [r for r in run_rows if r['variant'] == 'candidate']
    assert len(actual) == len({(r['case_id'], r['mode']) for r in actual}) == 2400
    assert all(r['complete'] and r['exit_reason'] == 'user_exit' and r['error'] is None for r in actual)
    assert result_summary['candidate_sha256'] == sha(snap)
    assert result_summary['manifest_sha256'] == sha(ROOT/'evaluation/manifest_v1.json')
    assert all(r['average_clear_time_s'] == by_variant['frozen_baseline'][(r['case_id'],3)]['average_clear_time_s'] for r in actual if r['mode'] == 3)
    round_integrity.append(dict(round=number, snapshot_matches_result=True, full_complete_normal_no_error=2400, q3_exactly_baseline=True))
output = dict(label='LOCAL-v1 final provenance and raw-row audit; no official replay',
    passed=True, best_round=best['best_round'], candidate_sha256=sha(candidate),
    manifest_sha256=sha(ROOT/'evaluation/manifest_v1.json'), frozen_file_checks=checks,
    best_matches_deployed_solver=True, declared_imports=imports, direct_env_attributes=env_attributes,
    policy_read_boundary='Manual source review plus AST inventory: only four env methods; the sole file input is optional coverage_points.json, checked against the analytic geometric certificate. No case IDs, test labels, truth, or cached metrics are imported by policy.',
    paired_rows=paired, candidate_runs=2400, complete_normal_no_error=2400, all_rounds_integrity=round_integrity,
    finite_sample_boundary='AST inventory is not a security proof; complete local regression is not an all-environment or official guarantee.')
(P/'results/final_audit.json').write_text(json.dumps(output, ensure_ascii=False, indent=2))
print(json.dumps(output, ensure_ascii=False, indent=2))
