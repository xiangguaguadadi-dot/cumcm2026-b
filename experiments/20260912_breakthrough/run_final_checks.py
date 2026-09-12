"""Persist local rule and synthetic-contract checks, separately from task runs."""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
p=argparse.ArgumentParser()
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
a.out.mkdir(parents=True,exist_ok=False)
commands=[
    ('frozen_rules',['-m','unittest','discover','-s','tests','-v']),
    ('frozen_hashes',['evaluate.py','--verify-only']),
    ('nominal_79',['tests/check_nominal.py','--package','.', '--out',str(a.out.resolve()/'nominal.json')]),
    ('exact_geometric_witnesses',[str(HERE/'test_geometric_counterexamples.py')]),
    ('rl_synthetic_contracts',[str(HERE/'RL/test_contracts.py')]),
    ('packaging_synthetic_contracts',[str(HERE/'test_final_packaging.py')]),
]
results=[]
for name,args in commands:
    command=[sys.executable,'-S','-B',*args]
    start=time.perf_counter()
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
    log=a.out/(name+'.log')
    log.write_text(result.stdout+result.stderr)
    results.append(dict(name=name,command=command,returncode=result.returncode,
        wall_s=time.perf_counter()-start,log=str(log),
        log_sha256=hashlib.sha256(log.read_bytes()).hexdigest()))
    print(name,result.returncode,result.stdout,result.stderr)
summary=dict(status='pass' if all(r['returncode']==0 for r in results) else 'fail',
    evidence='Rule checks and synthetic research fixtures only; not solver full-game results',
    results=results,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    checked_source_sha256={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [ROOT/'evaluation/manifest_v1.json',HERE/'RL/test_contracts.py',
                     HERE/'RL/implementation_spec.md',HERE/'RL/PROPOSAL.md',
                     HERE/'test_geometric_counterexamples.py',HERE/'verify_geometric_counterexamples.py',
                     HERE/'test_final_packaging.py',HERE/'build_final.py',HERE/'verify_dispatch_traces.py']})
(a.out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
assert summary['status']=='pass'
