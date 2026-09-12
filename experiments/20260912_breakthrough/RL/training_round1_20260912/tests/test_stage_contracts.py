"""Synthetic stage/IPC/cache tests: no simulator, process spawn or optimizer."""
from copy import deepcopy
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from .. import calibrate,stage_freeze
from ..calibration_math import world_residual
from ..common import digest,sha
from ..inference_worker import InferenceWorker
from ..selection import float32
from ..policy import Policy

class InputFreezeTests(unittest.TestCase):
    def test_required_input_must_be_member_and_same_hash(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();path=root/'input.json';path.write_text('{"a":1}')
            manifest=dict(schema='bc-rpi-round1-stage-input-freeze-v1',stage='calibration',files={'input.json':sha(path)})
            with patch.object(stage_freeze,'ROOT',root),patch.object(stage_freeze,'REPO',root):
                stage_freeze.verify_stage_inputs(manifest,'calibration',['input.json'])
                with self.assertRaises(ValueError):stage_freeze.verify_stage_inputs(manifest,'evaluation',['input.json'])
                with self.assertRaises(ValueError):stage_freeze.verify_stage_inputs(dict(manifest,files={}), 'calibration',['input.json'])
                path.write_text('{"a":2}')
                with self.assertRaises(RuntimeError):stage_freeze.verify_stage_inputs(manifest,'calibration',['input.json'])

    def test_source_schema_stage_and_dependency_set_are_strict(self):
        source=dict(schema='bc-rpi-round1-stage-source-freeze-v1',stage='fit',files={'one':'1','two':'2'})
        with patch.object(stage_freeze,'sources',return_value=dict(files=source['files'])),patch.object(stage_freeze,'verify_sources') as verify:
            stage_freeze.verify_stage_sources(source,'fit');verify.assert_called_once_with(source)
            for bad in (dict(source,stage='evaluation'),dict(source,schema='other'),dict(source,files={'one':'1'})):
                with self.assertRaises(ValueError):stage_freeze.verify_stage_sources(bad,'fit')

    def test_required_directory_includes_all_actual_members(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();(root/'data').mkdir();(root/'data'/'one').write_text('x');(root/'data'/'two').write_text('y')
            with patch.object(stage_freeze,'ROOT',root),patch.object(stage_freeze,'REPO',root):
                self.assertEqual(stage_freeze.required_paths(['data']),{'data/one','data/two'})

class IPCFailureTests(unittest.TestCase):
    def test_frozen_candidate_memory_error_does_not_become_normal_teacher(self):
        teacher='a'*64;worker=SimpleNamespace(disabled=False,checkpoint_sha='c'*64)
        policy=Policy(worker,0.)
        prepared=SimpleNamespace(choices={'teacher_id':teacher,'rejections':['generator_error:ValueError:MemoryError: fixture']},
            choice_id='choice',meta={'teacher_task':{'kind':'source','key':4}},prepare_wall_s=.1)
        engine=SimpleNamespace(s=SimpleNamespace(mode=4),state={'interventions_remaining':2,'forced_teacher_channels':set()},
            expand=lambda p:None)
        with self.assertRaises(MemoryError):policy.select(engine,prepared)
        self.assertEqual(len(policy.decisions),1)
        self.assertFalse(policy.decisions[0]['model_scored'])
        self.assertIn('MemoryError',policy.decisions[0]['rejection'])

    def worker(self,response):
        worker=InferenceWorker.__new__(InferenceWorker);worker.disabled=False;worker.sequence=0;worker.checkpoint_sha='c'*64
        worker.process=SimpleNamespace(stdin=io.StringIO());worker.disable=Mock()
        worker._readline=Mock(return_value=json.dumps(dict(response,request_id='1')))
        return worker

    def test_remote_memory_error_is_not_silent_teacher_protocol_failure(self):
        worker=self.worker(dict(ok=False,error_type='MemoryError',resource_failure=True,error='MemoryError: fixture'))
        with patch('training_round1_20260912.inference_worker.validate_snapshot'):
            with self.assertRaises(MemoryError):worker.score({})
        worker.disable.assert_called_once()

    def test_normal_remote_error_disables_worker_and_stays_value_error(self):
        worker=self.worker(dict(ok=False,error_type='ValueError',resource_failure=False,error='ValueError: fixture'))
        with patch('training_round1_20260912.inference_worker.validate_snapshot'):
            with self.assertRaises(ValueError):worker.score({})
        worker.disable.assert_called_once()

    def test_request_identity_checked_before_score(self):
        worker=self.worker(dict(ok=True));worker._readline.return_value=json.dumps(dict(request_id='wrong',ok=True))
        with patch('training_round1_20260912.inference_worker.validate_snapshot'):
            with self.assertRaises(ValueError):worker.score({})
        worker.disable.assert_called_once()

    def test_finite_operands_overflow_residual_is_rejected(self):
        state=dict(candidate_id='b',teacher_id='a',predicted_gain=1e308,realized_gain=-1e308)
        with self.assertRaises(ValueError):world_residual([state])

class FakeHandle:
    def __init__(self):
        self.source_index=0;self.bundle_integrity_sha256='bundle';self.private_integrity_sha256='private'
        self.prepared=SimpleNamespace(choice_id='choice',meta={'teacher_task':{'kind':'source','key':4}},
            choices={'candidate_ids':['a'*64,'b'*64]},to_json=lambda:dict(choice='public'))
        self.token=SimpleNamespace(prefix_virtual_us=10,interface_public_state={'events':[]},to_json=lambda:dict(token='public'))
    def verify(self,world):
        if world['world_sha256']!='worldsha':raise ValueError('Wrong fake world')
    def to_json(self):return dict(fake_handle=True)

class CalibrationCacheTests(unittest.TestCase):
    def test_cache_identity_changes_for_all_material_semantics(self):
        world=dict(world_id='world',world_sha256='worldsha');handle=FakeHandle();action='a'*64
        baseline=calibrate.cache_identity(world,handle,action,'pi','source')['key_sha256']
        variants=[calibrate.cache_identity(world,handle,'b'*64,'pi','source'),
            calibrate.cache_identity(world,handle,action,'pi2','source'),
            calibrate.cache_identity(world,handle,action,'pi','source2')]
        handle.bundle_integrity_sha256='new-bundle';variants.append(calibrate.cache_identity(world,handle,action,'pi','source'))
        self.assertTrue(all(v['key_sha256']!=baseline for v in variants))
        with self.assertRaises(ValueError):calibrate.cache_identity(world,handle,'c'*64,'pi','source')

    def test_all_seed_choices_frozen_before_unique_action_union_runs(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();out=root/'out';world=dict(world_id='world',world_sha256='worldsha',index=0,group='group')
            models=[];workers={};order=[];teacher='a'*64;alternative='b'*64
            for seed in (912101,912102,912103):
                path=root/f'{seed}.pt';path.write_text(str(seed));models.append(dict(seed=seed,path=path.name,sha256=sha(path),epoch=5))
                def score(snapshot,seed=seed):
                    order.append(('predict',seed))
                    return dict(scores=[0.,float32(.01)] if seed!=912103 else [0.,float32(-.01)],
                        roundtrip_wall_s=0.,forward_wall_s=0.,tensor_build_wall_s=0.)
                workers[seed]=SimpleNamespace(score=score)
            budget=SimpleNamespace(data={'business_calls':100,'executions_started':1})
            recorder=SimpleNamespace(budget=budget,freeze={})
            recorder.record=lambda result,w,family,**metadata:dict(run_id=result['run_id'],path='mock',**metadata)
            handle=FakeHandle();baseline=dict(run_id='rollin',success=True,true_terminal_n=10)
            def suffix(w,b,run_id,h,action_id,**kwargs):
                before=json.loads((out/'worlds/w000/s00/selection_before_labels.json').read_text())
                self.assertEqual(len(before['selected_by_seed']),3)
                self.assertEqual(before['calls_at_selection_freeze'],100)
                self.assertEqual(before['executions_at_selection_freeze'],1)
                self.assertEqual(order[:3],[('predict',s) for s in (912101,912102,912103)])
                order.append(('suffix',action_id));b.data['business_calls']+=1;b.data['executions_started']+=1
                return dict(run_id=run_id,success=True,cost=.2 if action_id==teacher else .19),[]
            with patch.object(calibrate,'ROOT',root),patch.object(calibrate,'run_full',return_value=(baseline,[handle])),\
                patch.object(calibrate,'run_suffix',side_effect=suffix),patch.object(calibrate,'expand_handle'),\
                patch.object(calibrate,'build_snapshot',return_value=dict(candidate_ids=[teacher,alternative],teacher_id=teacher)),\
                patch.object(calibrate,'decode',side_effect=lambda value:value),patch.object(calibrate,'verify_sources'),\
                patch.object(calibrate,'verify_replay',return_value=dict(exact=True)),\
                patch.object(calibrate,'terminal_cost',side_effect=lambda result,prefix=0:result['cost']):
                rows=calibrate.world_calibration(world,out,recorder,None,workers,models,'pi','source')
            self.assertEqual(len(rows),3)
            self.assertEqual([x for x in order if x[0]=='suffix'],[('suffix',teacher),('suffix',alternative)])
            first,second,third=[r['states'][0] for r in rows]
            self.assertEqual(first['selected_origin_run_id'],second['selected_origin_run_id'])
            self.assertEqual(first['selected_cache_key_sha256'],second['selected_cache_key_sha256'])
            self.assertEqual(third['selected_origin_run_id'],third['reference_origin_run_id'])
            self.assertEqual(third['realized_gain'],0.)
            self.assertEqual(budget.data['business_calls'],102)
            labels=json.loads((out/'worlds/w000/s00/complete_labels.json').read_text())
            self.assertEqual(len(labels['unique_action_outcomes']),2)
            self.assertEqual(sum(len(r['consumers']) for r in labels['unique_action_outcomes']),6)

if __name__=='__main__':unittest.main()
