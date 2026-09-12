"""Persist rule-check evidence without modifying the frozen test suite."""
import json
import subprocess
import sys
import time
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
round_id=sys.argv[1]
out=HERE/'results'/f'{round_id}_rules'
out.mkdir(exist_ok=False)
records=[]
for name,args in [('unit',['-m','unittest','discover','-s','tests','-v']),
                  ('manifest',['evaluate.py','--verify-only']),
                  ('nominal',['tests/check_nominal.py','--package','.', '--out',str(out/'nominal.json')])]:
    command=[sys.executable,'-S','-B',*args]
    start=time.perf_counter()
    result=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
    elapsed=time.perf_counter()-start
    (out/f'{name}.stdout.txt').write_text(result.stdout)
    (out/f'{name}.stderr.txt').write_text(result.stderr)
    records.append(dict(name=name,command=command,returncode=result.returncode,wall_s=elapsed))
    print(name,result.returncode,round(elapsed,3),result.stdout,result.stderr)
(out/'execution.json').write_text(json.dumps(records,indent=2))
assert all(r['returncode']==0 for r in records)
