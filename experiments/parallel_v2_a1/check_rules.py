from pathlib import Path
import subprocess,time,json,sys,ast
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
r=sys.argv[1];out=HERE/'results'/f'r{r}_rules';out.mkdir(exist_ok=False)
records=[]
for name,args in [('unit',['-m','unittest','discover','-s','tests','-v']),('manifest',['evaluate.py','--verify-only']),('nominal',['tests/check_nominal.py','--package','.', '--out',str(out/'nominal.json')])]:
 st=time.perf_counter();p=subprocess.run([sys.executable,'-S','-B',*args],cwd=ROOT,capture_output=True,text=True)
 (out/(name+'.stdout.txt')).write_text(p.stdout);(out/(name+'.stderr.txt')).write_text(p.stderr)
 records.append(dict(name=name,returncode=p.returncode,wall_s=time.perf_counter()-st));assert p.returncode==0
ast.parse((HERE/'snapshots'/f'r{r}.py').read_text())
(out/'execution.json').write_text(json.dumps(records,indent=2));print(records)
