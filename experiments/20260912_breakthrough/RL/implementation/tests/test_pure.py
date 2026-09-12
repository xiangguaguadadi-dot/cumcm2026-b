"""Pure public-state/negative tests. No LocalEnv import and no business calls."""
from copy import deepcopy
from dataclasses import replace
import math
from pathlib import Path
import tempfile
import unittest
from ..deploy import operations,vendor
from ..deploy.engine import Engine,CandidateWorker
from ..deploy.state import (ResumeToken,controller_state,encode,decode,digest,
                           validate_controller_state,validate_engine_state)


def public_ready(mode=4,source=False):
    """Explicitly synthetic public state; it is not an actual entered episode."""
    e=Engine(vendor.NoCalls(),mode,clock=lambda:10.)
    e.api.started=True;e.api.started_at=10.;e.api.deadline=1210.
    e.s.deadline=1205.;e.state['boundary_phase']='READY_PREPARE'
    if source:
        e.s.observations[1]=[((0.,0.),0.)]
        e.s.polygons[1]=[(900.,-15.),(1000.,-15.),(1000.,15.),(900.,15.)]
        e.s.trace=[dict(action='measure',x=0.,y=0.,channel=1,result='direction',svd_deg=0.,virtual_time_s=5.)]
        e.s.virtual_time=e.api.virtual_time=5.
        e.state['todo']=set()
        e.api.positive_observations={(1,0.,0.,'direction')}
    return e


def resign(token,**fields):
    changed=replace(token,**fields)
    raw=changed.to_json();raw.pop('integrity_sha256')
    return replace(changed,integrity_sha256=digest(raw))


class PublicStateContracts(unittest.TestCase):
    def test_lossless_typed_json(self):
        data={1:(-0.,float('inf'),{1,2}), 'tuple_key':{(1,2):[3.]}}
        self.assertEqual(encode(decode(encode(data))),encode(data))

    def test_initial_controller_schemas(self):
        for mode in (3,4):validate_controller_state(controller_state(public_ready(mode).s))

    def test_no_public_unknown_fields(self):
        s=controller_state(public_ready().s)
        for field in ('seed','N','source_config','previous_reward'):
            bad=deepcopy(s);bad[field]=1
            with self.assertRaises(ValueError):validate_controller_state(bad)
        bad=deepcopy(s);bad['counters']['previous_reward']=1.
        with self.assertRaises(ValueError):validate_controller_state(bad)
        bad=controller_state(public_ready(source=True).s);bad['trace'][0]['source_truth']=1
        with self.assertRaises(ValueError):validate_controller_state(bad)

    def test_engine_unknown_slot_rejected(self):
        state=deepcopy(public_ready().state)
        for slot in (True,-1,3,float('nan'),'2'):
            state['interventions_remaining']=slot
            with self.assertRaises(ValueError):validate_engine_state(state)
        state=deepcopy(public_ready().state);state['previous_reward']=1
        with self.assertRaises(ValueError):validate_engine_state(state)

    def test_detached_prepare_no_side_effect_or_requests(self):
        for source in (False,True):
            e=public_ready(source=source);before=e.pre_hash()
            e.prepare()
            self.assertEqual(before,e.pre_hash())

    def test_commit_once_and_transactional_rejection(self):
        e=public_ready();p=e.prepare();before=e.pre_hash()
        bad=deepcopy(p);bad.common_patch['position']=(12.,13.)
        with self.assertRaises(ValueError):e.compare_and_commit(bad)
        self.assertEqual(before,e.pre_hash())
        e.compare_and_commit(p)
        with self.assertRaises(ValueError):e.compare_and_commit(p)

    def test_token_roundtrip_no_enter(self):
        e=public_ready();token=ResumeToken.from_json(e.token().to_json())
        resumed=Engine.restore(vendor.NoCalls(),token,clock=lambda:20.)
        self.assertEqual(resumed.pre_hash(),e.pre_hash())
        self.assertEqual(resumed.api.deadline,1220.)

    def test_token_full_integrity_clock_tamper(self):
        token=public_ready().token()
        bad=replace(token,clock_offsets={**token.clock_offsets,'interface_deadline_remaining_s':2400.})
        with self.assertRaisesRegex(ValueError,'integrity'):Engine.restore(vendor.NoCalls(),bad)
        bad=resign(token,clock_offsets={**token.clock_offsets,'interface_deadline_remaining_s':2400.})
        with self.assertRaisesRegex(ValueError,'original entered window'):Engine.restore(vendor.NoCalls(),bad)

    def test_token_prefix_denominator_even_if_resigned(self):
        token=public_ready().token()
        for fields in ({'accepted_event_count':1},{'prefix_virtual_us':1}):
            with self.assertRaisesRegex(ValueError,'denominator'):Engine.restore(vendor.NoCalls(),resign(token,**fields))

    def test_token_bad_clock_and_dependency(self):
        token=public_ready().token()
        for value in (float('nan'),None):
            bad=resign(token,clock_offsets={**token.clock_offsets,'task_elapsed_real_s':value}) if value is None else None
            if bad is None:
                with self.assertRaises(ValueError):resign(token,clock_offsets={**token.clock_offsets,'task_elapsed_real_s':value})
            else:
                with self.assertRaises(ValueError):Engine.restore(vendor.NoCalls(),bad)
        with self.assertRaisesRegex(ValueError,'dependency'):Engine.restore(vendor.NoCalls(),resign(token,implementation_sha256='0'*64))

    def test_candidate_process_exact_dimensions_and_stability(self):
        e=public_ready(source=True);p=e.prepare();before=e.pre_hash()
        worker=CandidateWorker()
        try:
            e.worker=worker;e.expand(p)
            self.assertTrue(p.choices['eligible'],p.choices['rejections'])
            request=dict(controller=p.public_controller,engine=p.public_engine,meta=p.meta)
            twice=worker.generate(request)
            self.assertEqual(twice,p.choices)
            self.assertEqual(e.pre_hash(),before)
            f=twice['features']
            self.assertEqual(len(f['global_features']),20)
            self.assertEqual([len(x) for x in f['channels']],[12]*20)
            self.assertEqual([len(x) for x in f['polygon']],[2]*32)
            self.assertTrue(all(len(x)==14 for x in f['actions']+f['active_events']))
            # Global domain center (0,0), unlike active feasible polygon center.
            self.assertEqual(f['global_features'][10:12],[0.,0.])
            self.assertNotEqual(f['global_features'][10:12],f['global_features'][17:19])
        finally:worker.close()

    def test_generator_error_retains_teacher(self):
        class FailingWorker:
            def generate(self,_):raise ValueError('synthetic bad feature schema')
        e=public_ready(source=True);e.worker=FailingWorker();p=e.prepare();tid=p.choices['teacher_id']
        e.expand(p)
        self.assertEqual(p.choices['candidate_ids'],[tid])
        self.assertIn('generator_error',p.choices['rejections'][0])

    def test_recursive_candidate_metadata_whitelist(self):
        p=public_ready(source=True).prepare()
        for field,value in [('route_successor',{'source_truth':16}),('controller_patch_hash',{'seed':314159})]:
            request=dict(controller=p.public_controller,engine=p.public_engine,meta=deepcopy(p.meta))
            request['meta'][field]=value
            with self.assertRaises(ValueError):operations.generate(request)
        request=dict(controller=p.public_controller,engine=p.public_engine,meta=deepcopy(p.meta))
        request['meta']['teacher_task']['key']=True
        with self.assertRaises(ValueError):operations.generate(request)

    def test_unknown_backend_cannot_be_retried_or_fallback(self):
        from ..deploy.interface import PublicLedger
        class MockTimeout:
            def __init__(self):self.calls=0
            def enter(self):
                self.calls+=1
                raise TimeoutError('Synthetic accepted-response-lost fixture')
            measure=clear=exit=enter
        backend=MockTimeout();api=PublicLedger(backend,clock=lambda:10.)
        for _ in range(2):
            with self.assertRaises(vendor.InterfaceFailure):api.enter()
        self.assertEqual(backend.calls,1)
        self.assertIsNotNone(api.unknown_backend_failure)

    def test_coordinate_rules(self):
        self.assertEqual(operations.coordinate(-0.),'0.0000000')
        self.assertEqual(operations.coordinate(1.23456785),'1.2345678')
        with self.assertRaises(ValueError):operations.coordinate(float('inf'))

    def test_worker_import_boundary_static(self):
        import ast
        root=Path(__file__).resolve().parents[1]/'deploy'
        for path in root.glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node,ast.Import):names=[a.name for a in node.names]
                elif isinstance(node,ast.ImportFrom):names=[node.module or '']
                else:continue
                self.assertFalse(any(any(part in n.split('.') for part in ('local_env','evaluator','train','evaluation')) for n in names),(path,names))


if __name__=='__main__':unittest.main()
