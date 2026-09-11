"""Behavioral checks: candidate permutation, masking and feature isolation."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import torch
from shared import CandidateNetwork,batch_snapshots

def fixture():
    return dict(global_features=[i/16 for i in range(16)],
                channel_features=[[i/20,j/12]+[0.0]*10 for i,j in zip(range(20),range(20))],
                candidate_features=[[i/3,j/16]+[0.0]*14 for i,j in zip(range(3),range(3))],
                valid_mask=[True,False,True], teacher_index=2, candidate_ids=['a','b','c'])

class SharedBehavior(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(5)
        torch.set_num_threads(1)
        self.model=CandidateNetwork().eval()

    def test_candidate_permutation_equivariance(self):
        s=fixture();scores,v=self.model(**batch_snapshots([s]))
        p=[2,0,1];permuted=copy.deepcopy(s)
        for field in ('candidate_features','valid_mask','candidate_ids'):
            permuted[field]=[s[field][i] for i in p]
        s2,v2=self.model(**batch_snapshots([permuted]))
        torch.testing.assert_close(s2,scores[:,p])
        torch.testing.assert_close(v2,v)

    def test_privileged_or_teacher_metadata_not_tensor_inputs(self):
        a=fixture();b=copy.deepcopy(a)
        b.update(teacher_index=0,true_N=16,seed=9999,source_truth='must not be read')
        ba,bb=batch_snapshots([a]),batch_snapshots([b])
        for key in ba: torch.testing.assert_close(ba[key],bb[key])

    def test_invalid_probability_and_padding_are_zero(self):
        a=fixture();b=copy.deepcopy(a)
        b['candidate_features']=b['candidate_features'][:1];b['valid_mask']=[True]
        scores,_=self.model(**batch_snapshots([a,b]))
        p=torch.softmax(scores,-1)
        self.assertEqual(p[0,1].item(),0.)
        self.assertEqual(p[1,1:].sum().item(),0.)
        self.assertEqual(p[1,0].item(),1.)

    def test_all_masked_is_explicit_error(self):
        s=fixture();s['valid_mask']=[False]*3
        with self.assertRaises(ValueError):batch_snapshots([s])
        s['valid_mask']=[True,2,False]
        with self.assertRaises(ValueError):batch_snapshots([s])

    def test_valid_masked_loss_backpropagates_finite_gradients(self):
        batch=batch_snapshots([fixture()]);scores,v=self.model(**batch)
        loss=-torch.log_softmax(scores,-1)[0,2]+v.square().mean()
        loss.backward()
        grads=[p.grad for p in self.model.parameters() if p.grad is not None]
        self.assertTrue(grads and all(torch.isfinite(g).all() for g in grads))

if __name__=='__main__':unittest.main()
