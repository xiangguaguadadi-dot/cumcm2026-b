"""Replay every exposed Q3 world to audit real replacement and exit evidence."""
import argparse
import hashlib
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from local_env import LocalEnv, Source, InterfaceOnly
import evaluate

p = argparse.ArgumentParser()
p.add_argument('--round', required=True)
a = p.parse_args()
candidate = HERE / 'snapshots' / (a.round + '.py')
target = HERE / 'results' / (a.round + '_all_q3_cover_diagnostic.json')
assert not target.exists()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
candidate_sha = sha(candidate)
evaluate.verify()
case_path = ROOT / 'experiments/20260911_stage4/exposed_cases.json'
manifest = json.loads((ROOT / 'experiments/20260911_stage4/exposure_manifest.json').read_text())
assert sha(case_path) == manifest['cases_sha256']
cases = [c for c in json.loads(case_path.read_text()) if c['mode'] == 3]
refs = {r['case_id']: r for r in json.loads((HERE / 'results' / (a.round + '_exposed') / 'case_metrics.json').read_text()) if r['mode'] == 3}
assert len(cases) == len(refs) == 2400
spec = importlib.util.spec_from_file_location('final_cover_candidate', candidate)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
rows = []
start = time.perf_counter()
for case in cases:
    env = LocalEnv([Source(**s) for s in case['sources']], case['seed'], case['noise'], keep_log=True)
    solver = mod.Solver(InterfaceOnly(env), mode=3)
    result = solver.run()
    assert env.successes == len(case['sources']) and env.exit_reason == 'user_exit'
    assert abs(env.virtual_time_s - refs[case['case_id']]['total_virtual_time_s']) < 1e-8
    measurements = [r for r in env.log if r['action'] == 'measure']
    real_negatives = {(r['request']['channel'], r['request']['position']['x'], r['request']['position']['y'])
                      for r in measurements if r['response'].get('measure_result') == 'no_signal'}
    for event in solver.a1_cover_events:
        safe, radius, vertices = mod.a1_cover_certificate(event['points'])
        assert safe and radius <= 999.999
        for ch in event['unknown']:
            assert any(r['request']['channel'] == ch and
                       math.dist((r['request']['position']['x'], r['request']['position']['y']), event['new']) < 1e-8 and
                       r['response']['virtual_time_s'] > event['virtual_time_s'] for r in measurements)
    for certificate in solver.a1_exit_coverage:
        ch = certificate['channel']
        assert all((ch, x, y) in real_negatives for x, y in certificate['points'])
        assert mod.a1_cover_certificate(certificate['points'])[0]
    request_count = solver.counters['measure'] + solver.counters['clear_attempts'] + 2
    assert request_count == refs[case['case_id']]['requests']
    rows.append(dict(case_id=case['case_id'], exposure_suite=case['exposure_suite'], group=case['group'],
        average_s=env.virtual_time_s / env.successes, counters=solver.counters, events=solver.a1_cover_events,
        exit_channels_certified=len(solver.a1_exit_coverage), requests=request_count,
        all_real_measurement_and_exit_checks=True))
    if len(rows) % 400 == 0:
        print('audited Q3', len(rows), flush=True)
output = dict(round=a.round, candidate_sha256=candidate_sha, cases_sha256=sha(case_path),
    policy_runs=len(rows), requests=sum(r['requests'] for r in rows),
    games_with_events=sum(bool(r['events']) for r in rows), replacements=sum(len(r['events']) for r in rows),
    certificate_cpu_s=sum(r['counters'].get('a1_cover_cpu_s', 0.) for r in rows),
    wall_s=time.perf_counter()-start, all_complete=True, exactly_matches_saved_virtual_time_and_requests=True,
    evidence='2400 repeated exposed Q3 games; real measurements and negative evidence checked against action logs; not new worlds, not official, not independent geometry implementation',
    rows=rows)
assert sha(candidate) == candidate_sha
evaluate.verify()
target.write_text(json.dumps(output, indent=2))
print(json.dumps({k: v for k, v in output.items() if k != 'rows'}, indent=2))
