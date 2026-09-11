"""Read-only call profiling around the unchanged frozen rule entry points."""
from pathlib import Path
import contextlib
import io
import json
import runpy
import sys
import time

ROOT=Path('/Users/t/ai project/数学建模2026/代码')
OUT=ROOT/'experiments/20260911_rl_execution/core/regression_v1'
TARGET=str((ROOT/'local_env.py').resolve())

def profile_entry(label,argv,module=None,path=None):
    counts={a:{'attempts':0,'accepted':0,'rejected':0,'exception_or_no_response':0} for a in ('enter','measure','clear','exit')}
    def profile(frame,event,arg):
        if frame.f_code.co_filename!=TARGET or frame.f_code.co_name not in counts:return
        row=counts[frame.f_code.co_name]
        if event=='call':row['attempts']+=1
        elif event=='return':
            if isinstance(arg,dict):
                if arg.get('accepted') is True:row['accepted']+=1
                else:row['rejected']+=1
            else:row['exception_or_no_response']+=1
    stdout=io.StringIO();stderr=io.StringIO();previous=sys.getprofile();old_argv=sys.argv[:]
    started=time.perf_counter();exit_code=0
    try:
        sys.argv=argv;sys.setprofile(profile)
        with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
            try:
                if module:runpy.run_module(module,run_name='__main__',alter_sys=True)
                else:runpy.run_path(str(path),run_name='__main__')
            except SystemExit as e:exit_code=e.code or 0
    finally:
        sys.setprofile(previous);sys.argv=old_argv
    wall=time.perf_counter()-started
    (OUT/(label+'.stdout.txt')).write_text(stdout.getvalue())
    (OUT/(label+'.stderr.txt')).write_text(stderr.getvalue())
    record={'label':label,'argv':argv,'exit_code':exit_code,'wall_time_s':wall,
       'interface_calls':counts,'total_attempts':sum(x['attempts'] for x in counts.values()),
       'accepted_business_requests':sum(x['accepted'] for x in counts.values()),
       'measurement_scope':'sys.setprofile observes original LocalEnv function call/return; no method or file mutation',
       'synthetic_rule_checks_not_new_worlds':True}
    (OUT/(label+'.execution.json')).write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record),flush=True)
    if exit_code:raise SystemExit(exit_code)
    return record

if __name__=='__main__':
    sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
    profile_entry('rules',['python','discover','-s','tests','-v'],module='unittest')
    profile_entry('nominal',['tests/check_nominal.py','--package',str(ROOT),'--out',str(OUT/'nominal.json')],path=ROOT/'tests/check_nominal.py')
