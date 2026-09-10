"""Execute required checks and exactly one quick/full run for a frozen A6 candidate."""
import argparse,json,subprocess,sys
from pathlib import Path
B=Path(__file__).resolve().parents[1];R=B.parents[1]
p=argparse.ArgumentParser();p.add_argument('--round',type=int,required=True);a=p.parse_args();n=a.round
snapshot=B/'snapshots'/f'r{n}_solver.py'
assert snapshot.read_bytes()==(R/'solver.py').read_bytes()
def run(args,log=None):
 return subprocess.run([sys.executable,*map(str,args)],cwd=R,stdout=log,stderr=subprocess.STDOUT,check=True)
with (B/f'r{n}_rules.log').open('x') as log:
 run(['-m','unittest','discover','-s','tests','-v'],log)
 run(['tests/check_nominal.py','--package','.', '--out',B/f'r{n}_nominal.json'],log)
 run(['evaluate.py','--verify-only'],log)
with (B/f'r{n}_boundary_audit.json').open('x') as log:
 run([B/'scripts/audit_policy.py',snapshot],log)
for suite in ['quick','full']:
 out=R/'results'/f'A6_learning_r{n}_{suite}'
 with (B/f'r{n}_{suite}.log').open('x') as log:
  run(['evaluate.py','--suite',suite,'--candidate',snapshot,'--out',out],log)
 summary=json.loads((out/'summary.json').read_text())
 run([B/'scripts/record_round.py','--round',n,'--suite',suite])
 if not summary['all_complete']:raise SystemExit(f'{suite} did not fully complete; retained evidence')
run([B/'scripts/update_best.py','--round',n])
