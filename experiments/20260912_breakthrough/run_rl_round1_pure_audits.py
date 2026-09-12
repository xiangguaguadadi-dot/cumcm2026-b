#!/usr/bin/env python3
"""Run only synthetic contracts and frozen-file checks; no real fit or world."""
import argparse
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from audit_rl_execution import require,sha256

ROOT=Path(__file__).resolve().parent

def run():
    sys.path.insert(0,str(ROOT/'RL'))
    from training_round1_20260912.torch_runtime import configure
    configure()
    top=['test_audit_training_records','test_audit_training_labels','test_audit_fitted_models',
         'test_audit_calibration','test_audit_public_fit','test_audit_round_compatibility']
    package=[p.stem for p in sorted((ROOT/'RL/training_round1_20260912/tests').glob('test_*.py'))]
    groups=[('independent_auditors',top),('implementation_contracts',[
        'training_round1_20260912.tests.'+name for name in package])]
    results=[];sources={}
    for label,names in groups:
        stream=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromNames(names)
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        require(result.wasSuccessful(),'Pure suite failed: '+label+'\n'+stream.getvalue())
        results.append(dict(group=label,tests=result.testsRun,success=True,log=stream.getvalue()))
        for name in names:
            path=Path(sys.modules[name].__file__).resolve();sources[str(path)]=sha256(path)
    from audit_development import self_test
    statistics=self_test();sources[str(ROOT/'audit_development.py')]=sha256(ROOT/'audit_development.py')
    frozen=subprocess.run([sys.executable,'-S','-B','evaluate.py','--verify-only'],cwd=ROOT.parents[1],
        text=True,capture_output=True,check=False)
    require(frozen.returncode==0 and 'Frozen v1 hashes verified' in frozen.stdout,'Original evaluation hashes changed')
    require(all(sha256(p)==s for p,s in sources.items()),'Test source changed during verification')
    return dict(schema='bc-rpi-r1-final-pure-verification-v1',status='all_selected_pure_checks_passed',
        unittest_tests=sum(r['tests'] for r in results),groups=results,statistics_self_test=statistics,
        original_frozen_evaluation_check=dict(exit_code=frozen.returncode,stdout=frozen.stdout,stderr=frozen.stderr),
        source_sha256=sources,runner_sha256=sha256(__file__),actual_environment_executions=0,
        actual_campaign_optimizer_updates=0,
        evidence_limits=['Synthetic tensor gradients are not fitted campaign models or environment results.',
            'Real label/fit/calibration/compatibility/development acceptance is recorded separately.'])

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    require(not a.out.exists(),'Preserve previous test artifact');value=run()
    a.out.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:value[k] for k in ('status','unittest_tests','actual_environment_executions','actual_campaign_optimizer_updates')},indent=2))
