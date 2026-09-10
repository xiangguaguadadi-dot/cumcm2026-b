"""Read-only evidence audit; does not rerun policies or alter frozen cases."""
import ast
import hashlib
import json
import statistics
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
best = json.loads((HERE / 'best.json').read_text())
checks = []

def check(name, ok, **detail):
    checks.append(dict(name=name, passed=bool(ok), **detail))

check('best_equals_snapshot', (ROOT / 'solver.py').read_bytes() == (ROOT / best['snapshot']).read_bytes())
check('best_sha_matches', sha(ROOT / 'solver.py') == best['sha256'], sha256=sha(ROOT / 'solver.py'))
check('manifest_sha_matches', sha(ROOT / 'evaluation/manifest_v1.json') == best['manifest_sha256'])
v = subprocess.run([sys.executable, 'evaluate.py', '--verify-only'], cwd=ROOT, capture_output=True, text=True)
check('all_frozen_files_unchanged', v.returncode == 0, output=v.stdout.strip())
check('no_external_coverage_file', not (ROOT / 'coverage_points.json').exists())
tree = ast.parse((ROOT / 'solver.py').read_text())
attrs = sorted({n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
                and isinstance(n.value, ast.Attribute) and isinstance(n.value.value, ast.Name)
                and n.value.value.id == 'self' and n.value.attr == 'env'})
check('only_four_environment_attributes', attrs == ['clear', 'enter', 'exit', 'measure'], attributes=attrs)
imports = sorted({a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names})
check('standard_library_imports_only', imports == ['json', 'math', 'os', 'time'], imports=imports)
commit_code = subprocess.run(['git', 'show', best['code_commit'] + ':solver.py'], cwd=ROOT, capture_output=True).stdout
check('best_code_commit_matches', hashlib.sha256(commit_code).hexdigest() == best['sha256'], commit=best['code_commit'])
rounds = []
all_rows = {}
for n in range(1, 11):
    snapshot = ROOT / f'experiments/A1_space/snapshots/solver_r{n}.py'
    digest = sha(snapshot)
    for suite, count in [('quick', 120), ('full', 2400)]:
        directory = ROOT / f'results/A1_space_r{n}_{suite}'
        summary = json.loads((directory / 'summary.json').read_text())
        rows = json.loads((directory / 'case_metrics.json').read_text())
        candidate = [r for r in rows if r['variant'] == 'candidate']
        baseline = [r for r in rows if r['variant'] == 'frozen_baseline']
        ids = {(r['case_id'], r['mode']) for r in candidate}
        b_ids = {(r['case_id'], r['mode']) for r in baseline}
        check(f'r{n}_{suite}_hash_rows_complete', summary['candidate_sha256'] == digest
              and len(candidate) == count and len(baseline) == count
              and len(ids) == count and ids == b_ids
              and all(r['complete'] and not r['error'] and r['exit_reason'] == 'user_exit'
                      and r['cleared_count'] == r['source_count'] for r in candidate))
        if suite == 'full':
            all_rows[n] = candidate
            means = {str(q): statistics.mean(r['average_clear_time_s'] for r in candidate if r['mode'] == q) for q in (3, 4)}
            check(f'r{n}_summary_agrees_with_rows', all(abs(means[str(q)] - statistics.mean(
                g['candidate_mean_s_per_source'] for g in summary['groups'] if g['mode'] == q)) < 1e-9 for q in (3, 4)))
            rounds.append(dict(round=n, sha256=digest, means=means, rows=len(candidate)))
r8 = {r['case_id']: r for r in all_rows[8] if r['mode'] == 3}
r10 = {r['case_id']: r for r in all_rows[10] if r['mode'] == 3}
check('r10_q3_equals_r8_every_case', r8.keys() == r10.keys() and all(
    r8[k]['total_virtual_time_s'] == r10[k]['total_virtual_time_s']
    and r8[k]['cleared_count'] == r10[k]['cleared_count'] for k in r8))
check('two_non_improving_rounds', best['best_round'] == 8 and best['candidate_rounds'] == 10
      and best['consecutive_non_improving_full_rounds'] == 2
      and best['status'] == 'complete_empirical_stop')
out = dict(label='A1 final read-only evidence audit; no official simulator run',
           passed=sum(c['passed'] for c in checks), total=len(checks), checks=checks, rounds=rounds)
(HERE / 'final_audit.json').write_text(json.dumps(out, indent=2) + '\n')
(HERE / 'interface_audit.json').write_text(json.dumps(dict(env_attributes=attrs,
    solver_sha256=best['sha256'], frozen_dependencies_modified=False), indent=2) + '\n')
print(f'{out["passed"]}/{out["total"]} audit checks passed')
if out['passed'] != out['total']:
    raise SystemExit(1)
