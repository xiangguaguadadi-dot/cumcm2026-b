"""Explicit stage dependency sets, not every mutable Python file in the round."""
from __future__ import annotations
import sys
from .common import ROOT,RL,REPO,BASE,WORLD_SOURCE,WORLD_PIN,load,save_new,sha
from implementation.evaluator.source_archive import archive_sources

COLLECTION_FILES=('__init__.py','common.py','budget.py','register.py','freeze.py','collect.py',
                  'tests/__init__.py','tests/test_budget.py','tests/test_collection.py')

def check_base():
    old=load(BASE/'results/g1_v1/source_freeze.json')
    differences=[name for name,expected in old['files'].items() if sha(REPO/name)!=expected]
    if differences:raise RuntimeError('Accepted G0/G1 base changed: '+repr(differences))
    if sha(WORLD_SOURCE)!=WORLD_PIN:raise RuntimeError('Frozen world generator changed')
    return old

def collection_sources():
    old=check_base();paths={REPO/name for name in old['files']}
    paths.update(ROOT/name for name in COLLECTION_FILES);paths.add(WORLD_SOURCE)
    return dict(schema='bc-rpi-round1-collection-source-freeze-v1',python_executable=sys.executable,
        python_version=sys.version,no_site=sys.flags.no_site,
        accepted_base_deploy_sha256=old['deploy_implementation_sha256'],
        files={str(p.relative_to(REPO)):sha(p) for p in sorted(paths)},
        mutable_unexecuted_modules_excluded='features/model/fit/actor/calibration/development; none is imported or run during collection')

def verify_sources(freeze):
    check_base()
    for name,expected in freeze['files'].items():
        if sha(REPO/name)!=expected:raise RuntimeError('Stage-frozen dependency changed: '+name)

def prepare(directory):
    directory=ROOT/directory
    if directory.exists():raise FileExistsError('Use a fresh immutable preflight directory')
    directory.mkdir(parents=True)
    registration=load(ROOT/'registration.json')
    for key,name in [('manifest_sha256','world_manifest.json'),('novelty_sha256','novelty_audit.json'),
                     ('plan_sha256','EXECUTION_PLAN.md'),('compatibility_sha256','compatibility_registration.json')]:
        if sha(ROOT/name)!=registration[key]:raise RuntimeError('Registered input changed: '+name)
    import io,unittest
    output=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromNames([
        'training_round1_20260912.tests.test_budget','training_round1_20260912.tests.test_collection'])
    tests=unittest.TextTestRunner(stream=output,verbosity=2).run(suite)
    save_new(directory/'pure_tests.json',dict(tests=tests.testsRun,success=tests.wasSuccessful(),
        actual_environment_calls=0,neural_training_runs=0,log=output.getvalue()))
    if not tests.wasSuccessful():raise RuntimeError('Round budget pure preflight failed')
    freeze=collection_sources();save_new(directory/'source_freeze.json',freeze)
    save_new(directory/'source_archive.json',archive_sources(freeze,directory/'sources.zip'))
    inputs=[ROOT/name for name in ('registration.json','world_manifest.json','novelty_audit.json',
        'compatibility_registration.json','EXECUTION_PLAN.md')]
    inputs+=[RL/'PROPOSAL.md',RL/'implementation_spec.md',RL.parent/'RL_EXECUTION_RESULT.json',
             BASE/'execution_status.json',BASE/'results/g1_v1/source_freeze.json',directory/'pure_tests.json']
    hashes={str(p.relative_to(REPO)):sha(p) for p in inputs}
    save_new(directory/'input_freeze.json',dict(schema='bc-rpi-round1-collection-input-freeze-v1',files=hashes))
    save_new(directory/'input_archive.json',archive_sources(dict(files=hashes),directory/'inputs.zip'))
    verify_sources(freeze)
    print({'preflight':str(directory),'pure_tests':tests.testsRun,'sources':len(freeze['files']),
           'source_freeze_sha256':sha(directory/'source_freeze.json'),'actual_calls':0})

def verify_inputs(directory):
    for name,expected in load(directory/'input_freeze.json')['files'].items():
        if sha(REPO/name)!=expected:raise RuntimeError('Frozen collection input changed: '+name)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True)
    prepare(parser.parse_args().out)
