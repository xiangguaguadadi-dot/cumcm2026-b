"""Pure synthetic negative controls for checkpoint-ledger and weighting audit."""
from copy import deepcopy
import sys
import unittest

import audit_fitted_models as audit


def fixture():
    ids = [f'fit_{i:02d}' for i in range(24)]
    journal = []
    for seed in audit.SEEDS:
        journal.append(dict(seed=seed,event='fit_start',epochs=20,expected_updates=60,fit_worlds=24,fit_val_worlds=12))
        for epoch in range(1,21):
            for batch in range(3):
                journal.append(dict(seed=seed,event='optimizer_update',epoch=epoch,update=(epoch-1)*3+batch+1,
                    batch_worlds=8,fit_world_ids=ids[batch*8:(batch+1)*8],loss=.1,gradient_norm_before_clip=.2))
            if epoch in (5,10,20): journal.append(dict(seed=seed,event='checkpoint_saved',epoch=epoch))
        journal.append(dict(seed=seed,event='fit_finish',status='complete',updates=60))
    return ids,journal


class UpdateAuditTests(unittest.TestCase):
    def reject(self, change):
        ids,rows=fixture();change(rows)
        with self.assertRaises((AssertionError,ValueError,KeyError)):
            audit.audit_update_order(rows,ids)

    def test_three_complete_initializations(self):
        ids,rows=fixture();out=audit.audit_update_order(rows,ids)
        self.assertEqual(set(out),set(audit.SEEDS));self.assertEqual(sum(v['updates'] for v in out.values()),180)

    def test_missing_update(self): self.reject(lambda rows: rows.pop(1))
    def test_duplicate_update(self): self.reject(lambda rows: rows.insert(2,deepcopy(rows[1])))
    def test_fit_val_cannot_enter_gradient(self): self.reject(lambda rows: rows[1]['fit_world_ids'].__setitem__(0,'fit_val_00'))
    def test_repeated_world_cannot_replace_another(self): self.reject(lambda rows: rows[1]['fit_world_ids'].__setitem__(0,'fit_01'))
    def test_drop_eight_world_batch(self): self.reject(lambda rows: rows[1].__setitem__('batch_worlds',7))
    def test_nan_gradient(self): self.reject(lambda rows: rows[1].__setitem__('gradient_norm_before_clip',float('nan')))
    def test_negative_loss(self): self.reject(lambda rows: rows[1].__setitem__('loss',-1))
    def test_no_completion(self): self.reject(lambda rows: rows.pop())
    def test_extra_checkpoint(self):
        def change(rows): rows.insert(-1,dict(seed=audit.SEEDS[-1],event='checkpoint_saved',epoch=15))
        self.reject(change)

    def test_extra_seed(self):
        self.reject(lambda rows: rows.append(dict(seed=999,event='fit_start')))

    def test_extra_event(self):
        self.reject(lambda rows: rows.insert(-1,dict(seed=audit.SEEDS[-1],event='unknown')))

    def test_epochs_cannot_be_reordered_while_updates_stay_contiguous(self):
        def change(rows):
            updates=[r for r in rows if r['seed']==audit.SEEDS[0] and r['event']=='optimizer_update']
            for row in updates[:3]: row['epoch']=2
            for row in updates[3:6]: row['epoch']=1
        self.reject(change)

    def test_checkpoint_cannot_precede_its_updates(self):
        def change(rows):
            i=next(i for i,r in enumerate(rows) if r['event']=='checkpoint_saved')
            rows.insert(1,rows.pop(i))
        self.reject(change)

    def test_seeds_cannot_be_interleaved(self):
        def change(rows):
            first=[r for r in rows if r['seed']==audit.SEEDS[0]]
            second=[r for r in rows if r['seed']==audit.SEEDS[1]]
            third=[r for r in rows if r['seed']==audit.SEEDS[2]]
            rows[:]=[r for pair in zip(first,second) for r in pair]+third
        self.reject(change)


class WeightingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.append('/Users/t/Documents/Codex/2026-09-10/new-chat/work/rl_execution_runtime/venv/lib/python3.12/site-packages')
        import torch
        cls.torch=torch

    def state(self, values, index=0):
        # This echo callable is not a real model, and no optimization is run.
        raw={k:[] for k in audit.TENSOR_KEYS};raw['global_features']=values;raw['active_mask']=[True]
        return dict(state_index=index,snapshot=dict(features=raw,candidate_ids=[str(i) for i in range(len(values))]),
                    targets_normalized=[0.]*len(values),teacher_index=0)

    def test_nested_equal_weights_include_teacher_only_and_empty_world(self):
        worlds=[dict(world_id='w1',role='fit_val',states=[self.state([0.,.002,.004]),self.state([0.],1)]),
                dict(world_id='w2',role='fit_val',states=[self.state([0.,.006])]),
                dict(world_id='w3',role='fit_val',states=[])]
        loss,rows=audit.nested_huber(self.torch,lambda x:x['global_features'],worlds)
        self.assertAlmostEqual(loss,1.,places=6)
        self.assertAlmostEqual(rows[0]['loss'],.5,places=6)
        self.assertEqual(rows[2]['loss'],0.)

    def test_failure_penalty_remains_in_loss(self):
        state=self.state([0.,0.]);state['targets_normalized']=[0.,-100.]
        loss,_=audit.nested_huber(self.torch,lambda x:x['global_features'],[dict(world_id='w',role='fit_val',states=[state])])
        self.assertAlmostEqual(loss,49999.5,places=2)


if __name__=='__main__':unittest.main()
