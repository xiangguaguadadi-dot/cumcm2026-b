"""Synthetic terminal classification; no LocalEnv instance or actual call."""
from copy import deepcopy
import unittest
from ..collect import IncompleteOutcome,classify_outcome,terminal_cost

def result():
    return dict(success=True,normal_exit=True,true_terminal_n=10,cleared=10,
        modeled_full_virtual_us=1_000_000_000,episode={'error':None},environment_log=[
            dict(action='exit',request={},response=dict(accepted=True,exit_reason='user_exit'))])

class ClassificationTests(unittest.TestCase):
    def test_normal_complete_success(self):
        self.assertEqual(classify_outcome(result()),'normal_complete_success')
        self.assertEqual(terminal_cost(result()),0.1)

    def test_true_normal_terminal_failure_gets_penalty(self):
        r=result();r.update(success=False,cleared=9)
        self.assertEqual(classify_outcome(r),'proven_normal_exit_incomplete_clear_failure')
        self.assertEqual(terminal_cost(r),100.1)

    def test_resource_failure_cannot_become_training_penalty(self):
        for message in ('MemoryError:','BudgetStop: Hard bound','OSError: disk full','IOError: write failed'):
            r=result();r.update(success=False,normal_exit=False);r['episode']['error']=message
            with self.assertRaises(IncompleteOutcome) as context:terminal_cost(r)
            self.assertEqual(context.exception.kind,'resource')

    def test_unproven_real_timeout_is_incomplete_not_invented_terminal(self):
        r=result();r.update(success=False,normal_exit=False,cleared=3)
        r['episode']['error']='InterfaceFailure: local time limit closed the interface'
        with self.assertRaises(IncompleteOutcome):terminal_cost(r)

    def test_unknown_acceptance_blocks_even_success_flag(self):
        with self.assertRaises(IncompleteOutcome):classify_outcome(result(),True)

    def test_ledger_mismatch_blocks_success(self):
        r=result();r['ledger_error']='mismatch'
        with self.assertRaises(IncompleteOutcome):terminal_cost(r)

    def test_missing_or_unaccepted_exit_not_terminal_proof(self):
        for modify in ('empty','unaccepted','wrong_reason','flag_false'):
            r=result()
            if modify=='empty':r['environment_log']=[]
            elif modify=='unaccepted':r['environment_log'][-1]['response']['accepted']=False
            elif modify=='wrong_reason':r['environment_log'][-1]['response']['exit_reason']='unknown'
            else:r['normal_exit']=False
            with self.assertRaises(IncompleteOutcome):terminal_cost(r)

    def test_flags_and_denominator_consistent(self):
        for changes in ({'true_terminal_n':0},{'cleared':11},{'success':False},{'cleared':9}):
            r=result();r.update(changes)
            with self.assertRaises(IncompleteOutcome):terminal_cost(r)

    def test_prefix_normalized_once(self):
        self.assertEqual(terminal_cost(result(),500_000_000),0.05)
        with self.assertRaises(ValueError):terminal_cost(result(),1_000_000_001)

if __name__=='__main__':unittest.main()
