"""Persist exact command outputs for existing unchanged rule/physics suites."""
import hashlib,json,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
out=HERE/'checks';out.mkdir(exist_ok=True)
commands=[['-m','unittest','discover','-s','tests','-v'],['evaluate.py','--verify-only'],
 ['tests/check_nominal.py','--package','.', '--out',str(out/'nominal_79.json')]]
records=[]
for i,cmd in enumerate(commands):
    call=[sys.executable,'-S','-B']+cmd;start=time.perf_counter()
    result=subprocess.run(call,cwd=ROOT,capture_output=True,text=True)
    (out/f'check_{i}.log').write_text(result.stdout+result.stderr)
    records.append(dict(command=call,returncode=result.returncode,wall_s=time.perf_counter()-start))
    assert result.returncode==0
records.append(dict(note='Rule/nominal tests validate frozen environment, not universal candidate correctness',
    candidates={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob('R*.py')},
    environment_manifest_sha256=hashlib.sha256((ROOT/'evaluation/manifest_v1.json').read_bytes()).hexdigest()))
(out/'checks_manifest.json').write_text(json.dumps(records,indent=2)+'\n')
print(json.dumps(records))
