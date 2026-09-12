"""Run unchanged frozen rule tests; record every actual LocalEnv fixture call."""
from pathlib import Path
import gzip
import importlib.util
import io
import json
import sys
import time
import unittest
import uuid
from runner import Budget, Recorder, canonical, dump, digest, verify_manifest, CAMPAIGN, REPO
sys.path.insert(0,str(REPO))
import local_env


def main():
    verify_manifest()
    out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False)
    budget=Budget(CAMPAIGN/'execution.sqlite')
    original=local_env.LocalEnv
    current=None;records=[]
    hashes={str(p):digest(p) for p in (Path(__file__).resolve(),Path(__file__).with_name('runner.py'),Path(__file__).with_name('budget.py'),REPO/'local_env.py',REPO/'tests/test_rules.py',REPO/'tests/test_metrics.py')}
    def settle():
        nonlocal current
        if current is None:return
        env,rec,stream,run_id,active=current
        active[0]=False
        raw=stream.getvalue().encode();journal=out/(run_id+'.journal.jsonl.gz')
        journal.write_bytes(gzip.compress(raw,mtime=0))
        payload=dict(kind='frozen_rule_fixture',run_id=run_id,calls=rec.counts,stats=env.stats(),exit_reason=env.exit_reason,source_files=hashes)
        path=out/(run_id+'.json');dump(path,payload)
        budget.finish(run_id,rec.counts,path);records.append(payload);current=None
    class Target:
        def __init__(self,env):
            self.env=env;self.originals={n:getattr(env,n) for n in ('enter','measure','clear','exit')}
        def __getattr__(self,k):return self.originals[k] if k in self.originals else getattr(self.env,k)
    def factory(*args,**kwargs):
        nonlocal current
        settle()
        run_id='rules_'+uuid.uuid4().hex
        cap=budget.reserve(run_id,'P0',str(out.relative_to(CAMPAIGN)),'frozen_fixture',hashes[str(REPO/'tests/test_rules.py')])
        env=original(*args,**kwargs);target=Target(env);stream=io.StringIO()
        rec=Recorder(target,stream,budget,run_id,cap);active=[True]
        def call(name,*a,**kw):
            if not active[0]:raise RuntimeError('Frozen test reused an already settled fixture')
            return rec.call(name,*a,**kw)
        for name in ('enter','measure','clear','exit'):
            setattr(env,name,lambda *a,_name=name,**kw:call(_name,*a,**kw))
        current=(env,rec,stream,run_id,active);return env
    local_env.LocalEnv=factory
    log=io.StringIO()
    try:
        suite=unittest.defaultTestLoader.discover(str(REPO/'tests'),pattern='test_*.py')
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    finally:
        settle();local_env.LocalEnv=original
    (out/'unittest.txt').write_text(log.getvalue())
    summary=dict(passed=result.wasSuccessful(),tests=result.testsRun,fixtures=len(records),counts={k:sum(r['calls'][k] for r in records) for k in ('attempts','accepted','rejected','known_error','unknown')},source_files=hashes)
    verify_manifest();dump(out/'summary.json',summary);dump(CAMPAIGN/'execution_status.json',budget.snapshot());print(canonical(summary))
    if not result.wasSuccessful():raise SystemExit(1)
if __name__=='__main__':main()
