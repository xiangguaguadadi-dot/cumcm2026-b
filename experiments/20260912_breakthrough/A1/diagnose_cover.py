"""Inspect actual replacements/scan evidence on exposed quick cases."""
import importlib.util
import json
import math
import statistics
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
from local_env import LocalEnv,Source,InterfaceOnly
round_id=sys.argv[1]
spec=importlib.util.spec_from_file_location('diagnosed',HERE/'snapshots'/f'{round_id}.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
cases=[c for c in json.loads((ROOT/'evaluation/cases_v1.json').read_text()) if c['mode']==3 and c['quick']]
rows=[]
for case in cases:
    env=LocalEnv([Source(**s) for s in case['sources']],case['seed'],case['noise'],keep_log=True)
    solver=mod.Solver(InterfaceOnly(env),mode=3)
    result=solver.run()
    assert env.successes==len(case['sources']) and env.exit_reason=='user_exit'
    for event in solver.a1_cover_events:
        # Every initially unknown channel really measured the replacement point
        # after the substitution. Near-triggered clears are still real evidence.
        for ch in event['unknown']:
            assert any(r['action']=='measure' and r['request']['channel']==ch and
                       math.dist((r['request']['position']['x'],r['request']['position']['y']),event['new'])<1e-8 and
                       r['response']['virtual_time_s']>event['virtual_time_s'] for r in env.log)
    rows.append(dict(case_id=case['case_id'],average_s=env.stats()['average_s'],counters=solver.counters,
                     events=solver.a1_cover_events,exit_cover=solver.a1_exit_coverage))
out=dict(policy_runs=len(rows),evidence='exposed quick diagnostics, not independent validation',
         replacements=sum(len(r['events']) for r in rows),games_with_replacements=sum(bool(r['events']) for r in rows),
         certificate_cpu_s=sum(r['counters'].get('a1_cover_cpu_s',0.) for r in rows),rows=rows)
if round_id=='r6b':
    out['previous_diagnostic_attempt']=dict(policy_runs=next(i+1 for i,r in enumerate(rows) if r['events']),
        failure='Diagnostic reader expected request.x, but frozen environment records request.position.x; solver unaffected',
        recovered_count='Deterministic replay: first case with a replacement event is the earlier assertion-failure point')
(HERE/'results'/f'{round_id}_cover_diagnostic.json').write_text(json.dumps(out,indent=2))
print({k:v for k,v in out.items() if k!='rows'})
