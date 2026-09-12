"""Evaluator-object/counter tests; no LocalEnv construction or actual calls."""
from copy import deepcopy
import tempfile
import unittest
from .test_pure import public_ready
from ..deploy.state import digest,encode
from ..evaluator.runtime import ForkHandle,seal_handle,sample_handles,BranchClock
from ..evaluator.budget import Budget,BudgetStop


class EvaluatorPureContracts(unittest.TestCase):
    def test_world_and_entire_bundle_binding(self):
        e=public_ready();token=e.token();prepared=e.prepare()
        handle=ForkHandle(token,prepared,{},dict(),0,0.,digest(encode(dict(private={},clock_offsets={}))), 'a'*64,'')
        seal_handle(handle);handle.verify(dict(world_sha256='a'*64))
        with self.assertRaisesRegex(ValueError,'different registered world'):handle.verify(dict(world_sha256='b'*64))
        bad=deepcopy(handle);bad.prepared.choice_id='b'*64
        with self.assertRaisesRegex(ValueError,'bundle integrity'):bad.verify(dict(world_sha256='a'*64))
        bad=deepcopy(handle);bad.token=public_ready(source=True).token();seal_handle(bad)
        with self.assertRaisesRegex(ValueError,'different pre-token'):bad.verify(dict(world_sha256='a'*64))

    def test_registered_public_uniform_sampling(self):
        self.assertEqual(sample_handles(list(range(10))),[0,3,6,9])
        self.assertEqual(sample_handles([3]),[3])
        self.assertEqual(sample_handles([]),[])

    def test_branch_clock_holds_queue_and_preserves_advance(self):
        c=BranchClock(100.);before=c();self.assertEqual(c(),before)
        c.advance(1199.);self.assertEqual(c(),1299.)
        with self.assertRaises(ValueError):c.advance(-1.)

    def test_budget_unknown_is_mutually_exclusive_and_stops(self):
        with tempfile.TemporaryDirectory(prefix='bc_rpi_mock_budget_') as directory:
            b=Budget(directory=directory);b.start('synthetic_counter_only','fixture')
            def mock_failure():raise TimeoutError('No actual environment; counter unit test only')
            with self.assertRaises(TimeoutError):b.call('synthetic',mock_failure,())
            with self.assertRaises(BudgetStop):b.call('synthetic',lambda:dict(accepted=True),())
            row=b.finish(True)
            self.assertFalse(row['success']);self.assertTrue(row['unknown_cost'])
            self.assertEqual((b.data['business_calls'],b.data['accepted_calls'],b.data['rejected_calls'],b.data['unknown_cost_calls']),(1,0,0,1))
            with self.assertRaises(BudgetStop):b.start('not_allowed','fixture')

    def test_budget_proved_local_rejection_separate_from_exception(self):
        with tempfile.TemporaryDirectory(prefix='bc_rpi_mock_budget_') as directory:
            b=Budget(directory=directory);b.start('synthetic_counter_only','fixture')
            def mock_failure():raise ConnectionError('Pure counter fixture, no environment')
            with self.assertRaises(ConnectionError):b.call('synthetic',mock_failure,(),lambda:dict(acceptance='known_no_accept'))
            b.finish(False)
            self.assertEqual((b.data['business_calls'],b.data['accepted_calls'],b.data['rejected_calls'],b.data['unknown_cost_calls']),(1,0,1,0))
            self.assertEqual(b.data['exception_calls'],1)


if __name__=='__main__':unittest.main()
