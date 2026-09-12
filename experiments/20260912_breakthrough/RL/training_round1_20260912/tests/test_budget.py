from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from ..budget import Budget,BudgetStop
from ..common import LIMITS

class BudgetTests(unittest.TestCase):
    def make(self,limits=None):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        now=[1000000000.]
        b=Budget(directory=tmp.name,now=lambda:now[0],monotonic=lambda:now[0],
                 limits=limits,resource_probe=lambda:(100,100))
        b.set_phase('labels');return b,now

    def test_new_clock_independent_of_old_campaign(self):
        b,now=self.make();self.assertEqual(b.data['campaign_start_epoch'],1000000000.)
        now[0]+=21599;b.start('a','full');b.finish(True)
        now[0]+=1
        with self.assertRaises(BudgetStop):b.start('b','suffix')

    def test_total_reserve_rejects_before_run_start(self):
        limits=deepcopy(LIMITS);limits['business_calls']=15845;b,_=self.make(limits)
        with self.assertRaises(BudgetStop):b.start('a','full')
        self.assertEqual(b.data['executions_started'],0)

    def test_phase_reserve_independent_of_other_stage_surplus(self):
        limits=deepcopy(LIMITS);limits['phase_calls']['labels']=15845;b,_=self.make(limits)
        with self.assertRaises(BudgetStop):b.start('a','full')
        b.set_phase('development');b.start('a','full');b.finish(True)

    def test_exact_reserve_then_actual_partition(self):
        limits=deepcopy(LIMITS);limits['phase_calls']['labels']=15846;b,_=self.make(limits)
        b.start('a','full');b.call('enter',lambda:{'accepted':True},());b.finish(True)
        self.assertEqual(b.data['business_calls'],1);self.assertEqual(b.data['phase_calls']['labels'],1)
        with self.assertRaises(BudgetStop):b.start('b','suffix')

    def test_unknown_acceptance_never_becomes_zero_or_retries(self):
        b,_=self.make();b.start('a','full')
        def lost():raise TimeoutError('response lost')
        with self.assertRaises(TimeoutError):b.call('measure',lost,())
        with self.assertRaises(BudgetStop):b.call('exit',lambda:{'accepted':True},())
        b.finish(False)
        self.assertEqual((b.data['business_calls'],b.data['unknown_cost_calls'],b.data['rejected_calls']),(1,1,0))
        with self.assertRaises(BudgetStop):b.start('b','full')

    def test_proven_rejection_is_distinct(self):
        b,_=self.make();b.start('a','fixture')
        def rejected():raise ValueError('not accepted')
        with self.assertRaises(ValueError):b.call('enter',rejected,(),lambda:{'acceptance':'known_no_accept'})
        b.finish(False);b.start('b','full');b.finish(True)
        self.assertEqual((b.data['rejected_calls'],b.data['unknown_cost_calls']),(1,0))

    def test_run_id_not_repeated_and_phase_not_changed_midrun(self):
        b,_=self.make();b.start('a','full')
        with self.assertRaises(BudgetStop):b.set_phase('calibration')
        b.finish(True)
        with self.assertRaises(BudgetStop):b.start('a','full')

    def test_journal_unsettled_blocks_even_if_status_tampered(self):
        b,_=self.make();b.start('a','full');b.data['current_run']=None;b.save()
        with self.assertRaises(BudgetStop):Budget(directory=b.directory,resource_probe=lambda:(100,100))

    def test_compatibility_maximum_24(self):
        b,_=self.make();b.set_phase('compatibility')
        for i in range(24):b.start(str(i),'fixture');b.finish(True)
        with self.assertRaises(BudgetStop):b.start('over','fixture')

    def test_resources_and_hard_execution_count(self):
        b,_=self.make();b.resource_probe=lambda:(LIMITS['rss_bytes']+1,100)
        with self.assertRaises(BudgetStop):b.start('rss','full')
        b.resource_probe=lambda:(100,LIMITS['raw_bytes'])
        with self.assertRaises(BudgetStop):b.start('data','full')
        b.resource_probe=lambda:(100,100);b.data['executions_started']=LIMITS['executions']
        with self.assertRaises(BudgetStop):b.start('executions','full')

    def test_no_unregistered_call(self):
        b,_=self.make()
        with self.assertRaises(RuntimeError):b.call('enter',lambda:{'accepted':True},())
        self.assertEqual(b.data['business_calls'],0)

if __name__=='__main__':unittest.main()
