"""Registered development and component-wiring check; no held-out claims."""
import ast
import hashlib
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
import evaluate
from local_env import Source

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def valid(r):
    return r.get('complete') and r.get('exit_reason') == 'user_exit' and not r.get('error') and r.get('cleared_count') == r.get('source_count')

def main():
    evaluate.verify()
    out = HERE / 'development_r1'
    out.mkdir(exist_ok=False)
    generator = ROOT / 'evaluation/generate_cases.py'
    parsed = ast.parse(generator.read_text())
    fn = next(n for n in parsed.body if isinstance(n, ast.FunctionDef) and n.name == 'sources')
    groups = ast.literal_eval(next(n.value for n in parsed.body if isinstance(n, ast.Assign)
                                   and any(isinstance(t, ast.Name) and t.id == 'groups' for t in n.targets)))
    scope = dict(Source=Source, random=random, math=math)
    exec(compile(ast.Module(body=[fn], type_ignores=[]), '<frozen-sources>', 'exec'), scope)
    seeds = list(range(47000000, 47000008))
    prior = json.loads((ROOT / 'experiments/20260911_stage3/seed_exclusions.json').read_text())['seeds']
    assert not set(seeds).intersection(prior)
    cases = []
    for group, scenario, noise in groups:
        for seed in seeds:
            sources = scope['sources'](seed, 4, scenario)
            assert 10 <= len(sources) <= 16
            assert len({s.channel for s in sources}) == len(sources)
            assert any(s.direction is None for s in sources) and any(s.direction is not None for s in sources)
            values = [vars(s) for s in sources]
            cases.append(dict(case_id=f'DEV-C1-r1-q4-{group}-{seed}', mode=4,
                              group=group, noise=noise, seed=seed, sources=values))
    registry = json.loads((HERE / 'candidate_registry.json').read_text())
    registry = {'S1': {'file': '../baseline/S1.py', 'sha256': sha(HERE.parent / 'baseline/S1.py')}, **registry}
    save(out / 'registration.json', dict(seeds=seeds, cases=len(cases), candidates=registry,
         generator_sha256=sha(generator), selection='All normal and clear, then lower all-case mean; compare each parent.',
         role='new development reused for two component-switch checks; not holdout'))
    save(out / 'cases.json', cases)
    save(HERE / 'used_seeds.json', dict(range=[47000000, 48000000], rounds=[dict(seeds=seeds, cases=96)]))
    summaries, raw = [], {}
    for name, meta in registry.items():
        path = (HERE / meta['file']).resolve()
        assert sha(path) == meta['sha256']
        begin = time.perf_counter()
        rows = evaluate.run_cases(cases, path, False)
        wall = time.perf_counter() - begin
        assert sha(path) == meta['sha256']
        save(out / (name + '_rows.json'), rows)
        raw[name] = rows
        good = all(valid(r) for r in rows)
        result = dict(candidate=name, actual_runs=len(rows), complete=sum(bool(valid(r)) for r in rows),
                      all_complete=good, source_count=sum(r['source_count'] for r in rows), wall_seconds=wall)
        if good:
            result.update(mean_s_per_source=statistics.mean(r['average_clear_time_s'] for r in rows),
                          mean_movement_s_per_source=statistics.mean(r['distance_m']/5/r['source_count'] for r in rows),
                          mean_requests=statistics.mean(r['requests'] for r in rows))
        summaries.append(result)
        save(out / 'summary.json', summaries)
        print(json.dumps(result), flush=True)
    equality = {}
    fields = ('case_id', 'complete', 'exit_reason', 'error', 'source_count', 'cleared_count',
              'total_virtual_time_s', 'distance_m', 'requests', 'clear_failures')
    for name, parent in [('C1_gate_off', 'E1_R1'), ('C1_route_off', 'E2_station')]:
        mismatches = [a['case_id'] for a, b in zip(raw[name], raw[parent])
                      if any(a.get(k) != b.get(k) for k in fields)]
        equality[name] = dict(parent=parent, cases=len(raw[name]), mismatches=mismatches,
                              statement='Behavior equality on this development set only.')
    save(out / 'wiring_checks.json', equality)
    save(HERE / 'execution_budget.json', dict(development_actual_runs=sum(x['actual_runs'] for x in summaries),
          development_unique_cases=len(cases), development_unique_seeds=len(seeds),
          wiring_check_cases_reused=2*len(cases), regression_actual_runs=0,
          wall_seconds=sum(x['wall_seconds'] for x in summaries)))
    evaluate.verify()
    assert all(not x['mismatches'] for x in equality.values())

if __name__ == '__main__':
    main()
