"""Explicit immutable source/input archives for stages after raw collection."""
from __future__ import annotations
import argparse
import sys
from .common import ROOT,REPO,load,save_new,sha
from .freeze import check_base,verify_sources,COLLECTION_FILES
from implementation.evaluator.source_archive import archive_sources

STAGE_FILES={
    'fit':('features.py','model.py','fit.py','export_fit.py','torch_runtime.py'),
    'calibration':('features.py','model.py','torch_runtime.py','selection.py','calibration_math.py',
        'actor_worker.py','inference_worker.py','calibrate.py'),
    'evaluation':('features.py','model.py','torch_runtime.py','selection.py','calibration_math.py',
        'actor_worker.py','inference_worker.py','policy.py','calibrate.py','evaluate_round.py'),
}
STAGE_TESTS={
    'fit':('test_features.py','test_model.py','test_fit.py'),
    'calibration':('test_features.py','test_model.py','test_selection.py','test_stage_contracts.py'),
    'evaluation':('test_features.py','test_model.py','test_selection.py','test_policy_mocks.py','test_stage_contracts.py'),
}

def sources(stage):
    if stage not in STAGE_FILES:raise ValueError('Unknown round stage')
    old=check_base();paths={REPO/name for name in old['files']}
    paths.update(ROOT/name for name in COLLECTION_FILES)
    paths.update(ROOT/name for name in STAGE_FILES[stage]);paths.add(ROOT/'stage_freeze.py')
    if stage=='evaluation':paths.add(ROOT.parent.parent/'A2/BEST_R2.py')
    paths.update(ROOT/'tests'/name for name in STAGE_TESTS[stage])
    # test_selection exercises fixed-margin Policy construction as a pure test.
    if stage=='calibration':paths.add(ROOT/'policy.py')
    return dict(schema='bc-rpi-round1-stage-source-freeze-v1',stage=stage,
        python_executable=sys.executable,python_version=sys.version,no_site=sys.flags.no_site,
        accepted_base_deploy_sha256=old['deploy_implementation_sha256'],
        files={str(p.relative_to(REPO)):sha(p) for p in sorted(paths)},
        excluded_modules='Only explicitly listed executed dependencies plus current pure tests are pinned.')

def prepare(stage,out,inputs):
    out=(ROOT/out).resolve();out.relative_to(ROOT)
    if out.exists():raise FileExistsError('Use a fresh immutable stage preflight')
    out.mkdir(parents=True)
    import io,unittest
    from .torch_runtime import configure
    configure();stream=io.StringIO()
    test_names=('test_budget.py','test_collection.py')+STAGE_TESTS[stage]
    modules=['training_round1_20260912.tests.'+name[:-3] for name in test_names]
    suite=unittest.defaultTestLoader.loadTestsFromNames(modules)
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    save_new(out/'pure_tests.json',dict(stage=stage,tests=result.testsRun,success=result.wasSuccessful(),
        modules=modules,actual_environment_executions=0,actual_business_calls=0,
        campaign_training_runs=0,optimizer_updates=0,log=stream.getvalue()))
    if not result.wasSuccessful():raise RuntimeError('Stage pure preflight failed; archive preserved without execution')
    freeze=sources(stage);save_new(out/'source_freeze.json',freeze)
    save_new(out/'source_archive.json',archive_sources(freeze,out/'sources.zip'))
    paths=[]
    for name in inputs:
        path=(ROOT/name).resolve();path.relative_to(REPO)
        if path.is_dir():paths.extend(p for p in path.rglob('*') if p.is_file())
        else:paths.append(path)
    if not paths:raise ValueError('Stage must bind actual immutable inputs')
    paths.append(out/'pure_tests.json')
    input_manifest=dict(schema='bc-rpi-round1-stage-input-freeze-v1',stage=stage,
        files={str(p.relative_to(REPO)):sha(p) for p in sorted(set(paths))})
    save_new(out/'input_freeze.json',input_manifest)
    save_new(out/'input_archive.json',archive_sources(input_manifest,out/'inputs.zip'))
    verify_sources(freeze)
    print(dict(stage=stage,source_freeze_sha256=sha(out/'source_freeze.json'),
        input_freeze_sha256=sha(out/'input_freeze.json'),sources=len(freeze['files']),inputs=len(paths)))

def required_paths(names):
    paths=set()
    for name in names:
        path=(ROOT/name).resolve();path.relative_to(REPO)
        if path.is_dir():paths.update(p for p in path.rglob('*') if p.is_file())
        else:paths.add(path)
    return {str(p.relative_to(REPO)) for p in paths}

def verify_stage_sources(source,stage):
    if source.get('schema')!='bc-rpi-round1-stage-source-freeze-v1' or source.get('stage')!=stage:
        raise ValueError('Wrong stage source schema/identity')
    expected=set(sources(stage)['files'])
    if set(source['files'])!=expected:raise ValueError('Stage source dependency set incomplete or unexpected')
    verify_sources(source)

def verify_stage_inputs(manifest,stage,required):
    if manifest.get('schema')!='bc-rpi-round1-stage-input-freeze-v1' or manifest.get('stage')!=stage:
        raise ValueError('Wrong stage input schema/identity')
    missing=required_paths(required)-set(manifest['files'])
    if missing:raise ValueError('Required actual stage inputs absent from freeze: '+repr(sorted(missing)))
    for name,expected in manifest['files'].items():
        path=(REPO/name).resolve();path.relative_to(REPO)
        if sha(path)!=expected:raise RuntimeError('Frozen stage input changed: '+name)

def verify_preflight(directory,acceptance,flag,*,stage,required):
    directory=(ROOT/directory).resolve();directory.relative_to(ROOT)
    if acceptance.get(flag) is not True:raise RuntimeError('Coordinator stage acceptance required')
    if acceptance.get('source_freeze_sha256')!=sha(directory/'source_freeze.json'):
        raise RuntimeError('Accepted stage source identity differs')
    if acceptance.get('input_freeze_sha256')!=sha(directory/'input_freeze.json'):
        raise RuntimeError('Accepted stage input identity differs')
    source=load(directory/'source_freeze.json');verify_stage_sources(source,stage)
    inputs=load(directory/'input_freeze.json');verify_stage_inputs(inputs,stage,required)
    return source,inputs

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=STAGE_FILES,required=True)
    p.add_argument('--out',required=True);p.add_argument('--input',action='append',required=True)
    a=p.parse_args();prepare(a.stage,a.out,a.input)
