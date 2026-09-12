import concurrent.futures
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'core'))
from budget import Budget, BudgetStop
from runner import Recorder, CallLimit, journal_counts, canonical

LIMITS=dict(call_limit=40,confirmation_reserve=10,execution_limit=20,workers=2,per_run_call_cap=10,wall_seconds=20)
class Accounting(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'b.sqlite';self.b=Budget(self.path,LIMITS)
    def reserve(self,i='a',phase='P0'):
        return self.b.reserve(i,phase,'batch','case','sha')
    def settle(self,i,n=2,unknown=0):
        self.b.finish(i,dict(attempts=n,accepted=n-unknown,rejected=0,unknown=unknown,known_error=0),'r')
    def test_limits_immutable(self):
        with self.assertRaises(ValueError):Budget(self.path,dict(LIMITS,call_limit=100))
    def test_atomic_worker_limit(self):
        def reserve(i):
            try:self.reserve(str(i));return True
            except BudgetStop:return False
        with concurrent.futures.ThreadPoolExecutor(8) as pool:
            self.assertEqual(sum(pool.map(reserve,range(8))),2)
    def test_reservations_return_only_unused(self):
        self.reserve();self.settle('a',10);self.reserve('b');self.settle('b',10);self.reserve('c')
        with self.assertRaises(BudgetStop):self.reserve('d')
        self.settle('c',10)
        with self.assertRaises(BudgetStop):self.reserve('e')
        self.reserve('f','P3')
    def test_unknown_blocks_next(self):
        self.reserve();self.settle('a',2,1)
        with self.assertRaises(BudgetStop):self.reserve('b')
    def test_duplicate_settlement(self):
        self.reserve();self.settle('a')
        with self.assertRaises(ValueError):self.settle('a')
    def test_settle_cap(self):
        self.reserve()
        with self.assertRaises(ValueError):self.settle('a',11)
    def test_counts_partition(self):
        self.reserve()
        with self.assertRaises(AssertionError):self.b.finish('a',dict(attempts=1,accepted=2,rejected=0,unknown=0,known_error=0),'r')
    def test_clock_starts_at_call(self):
        with patch('budget.time.time',return_value=100):self.reserve();self.b.first_call('a')
        self.settle('a')
        with patch('budget.time.time',return_value=121):
            with self.assertRaises(BudgetStop):self.reserve('b')
    def test_snapshot(self):
        self.reserve();self.settle('a',3)
        self.assertEqual(self.b.snapshot()['settled_calls']['accepted'],3)
    def test_partial_outcome_is_unknown(self):
        p=Path(self.tmp.name)/'j';p.write_text('{"event":"attempt","seq":0}\n')
        self.assertEqual(journal_counts(p)['unknown'],1)
    def test_truncated_record_is_unknown(self):
        p=Path(self.tmp.name)/'j';p.write_text('{"event":')
        self.assertEqual(journal_counts(p)['unknown'],1)
    def test_duplicate_rejected(self):
        p=Path(self.tmp.name)/'j';p.write_text('{"event":"attempt","seq":0}\n'*2)
        with self.assertRaises(ValueError):journal_counts(p)
    def test_orphan_rejected(self):
        p=Path(self.tmp.name)/'j';p.write_text('{"event":"outcome","seq":0}\n')
        with self.assertRaises(ValueError):journal_counts(p)

class Fake:
    measures=clear_attempts=successes=_virtual_us=0
    started=finished=False
    def __init__(self,kind='ok'):self.log=[];self.kind=kind
    def enter(self):
        if self.kind=='known':raise ValueError('bad input')
        if self.kind=='mutating':self.measures+=1;raise ValueError('after accept')
        if self.kind=='rejected':return dict(accepted=False)
        self.started=True;return dict(accepted=True)
class FakeBudget:
    def first_call(self,x):pass
class Recording(unittest.TestCase):
    def rec(self,kind='ok',cap=2):return Recorder(Fake(kind),io.StringIO(),FakeBudget(),'r',cap)
    def test_accept_and_cap(self):
        r=self.rec(cap=1);r.call('enter')
        with self.assertRaises(CallLimit):r.call('enter')
        self.assertEqual(r.counts['attempts'],1)
    def test_known_error(self):
        r=self.rec('known')
        with self.assertRaises(ValueError):r.call('enter')
        self.assertEqual(r.counts['known_error'],1)
    def test_mutating_error_unknown_no_fallback(self):
        r=self.rec('mutating')
        with self.assertRaises(ValueError):r.call('enter')
        with self.assertRaises(CallLimit):r.call('enter')
        self.assertEqual(r.counts['unknown'],1);self.assertEqual(r.counts['attempts'],1)
    def test_rejected(self):
        r=self.rec('rejected');r.call('enter');self.assertEqual(r.counts['rejected'],1)
    def test_sets_serialized(self):self.assertEqual(json.loads(canonical({'x':{1,2}})),{'x':[1,2]})
if __name__=='__main__':unittest.main()
