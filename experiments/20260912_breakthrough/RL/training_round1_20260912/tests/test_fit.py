"""Synthetic arithmetic/autograd tests, not actual world training."""
import unittest
from ..torch_runtime import configure
torch=configure()
from ..fit import state_loss,world_loss,batch_loss

class EchoScores(torch.nn.Module):
    def __init__(self):super().__init__();self.anchor=torch.nn.Parameter(torch.tensor(0.,dtype=torch.float64))
    def forward(self,features):return features['scores']+self.anchor*0

def state(scores,targets,ref=0):
    return dict(_tensors={'scores':torch.tensor(scores,dtype=torch.float64)},
        _targets=torch.tensor(targets,dtype=torch.float64),targets_normalized=targets,teacher_index=ref)

class FitMathTests(unittest.TestCase):
    def test_normalized_huber_scale_and_gradient(self):
        scores=torch.tensor([0.,0.001],dtype=torch.float64,requires_grad=True)
        loss=state_loss(scores,torch.tensor([0.,0.],dtype=torch.float64),0)
        self.assertAlmostEqual(loss.item(),0.125);loss.backward()
        self.assertAlmostEqual(scores.grad[1].item(),250.)
        self.assertAlmostEqual(scores.grad[0].item(),-250.)

    def test_reference_offset_cancels(self):
        a=state_loss(torch.tensor([0.,0.002],dtype=torch.float64),torch.tensor([0.,0.],dtype=torch.float64),0)
        b=state_loss(torch.tensor([1.,1.002],dtype=torch.float64),torch.tensor([0.,0.],dtype=torch.float64),0)
        self.assertAlmostEqual(a.item(),b.item(),places=10)

    def test_nonreference_actions_equal_within_state(self):
        # Residual normalized magnitudes [1,2] -> Huber [0.5,1.5].
        loss=state_loss(torch.tensor([0.,0.002,0.004],dtype=torch.float64),torch.zeros(3,dtype=torch.float64),0)
        self.assertEqual(loss.item(),1.)

    def test_world_state_action_three_level_mean(self):
        model=EchoScores()
        # World 1: states cost 1 and A0-only zero -> 0.5.
        w1={'states':[state([0.,0.002,0.004],[0.,0.,0.]),state([0.],[0.])]}
        # World 2: one state cost 2.5; worlds equal -> (0.5+2.5)/2=1.5.
        w2={'states':[state([0.,0.006],[0.,0.])]}
        self.assertEqual(world_loss(model,w1).item(),0.5)
        self.assertEqual(batch_loss(model,[w1,w2]).item(),1.5)

    def test_empty_world_still_has_equal_zero_weight(self):
        model=EchoScores();w={'states':[state([0.,0.002],[0.,0.])]}
        loss=batch_loss(model,[w,{'states':[]}]);self.assertEqual(loss.item(),0.25)
        loss.backward();self.assertIsNotNone(model.anchor.grad)

    def test_true_failed_labels_not_dropped(self):
        targets=torch.tensor([0.,-100.],dtype=torch.float64)
        loss=state_loss(torch.zeros(2,dtype=torch.float64),targets,0)
        self.assertEqual(loss.item(),49999.5)

    def test_teacher_not_assumed_index_zero(self):
        a=state_loss(torch.tensor([0.002,0.,0.004],dtype=torch.float64),torch.zeros(3,dtype=torch.float64),1)
        self.assertEqual(a.item(),1.)

    def test_nonfinite_reference_and_shape_rejected(self):
        for scores,targets,ref in [([0.,float('nan')],[0.,0.],0),([0.,1.],[0.,float('inf')],0),
                                   ([0.,1.],[1.,0.],0),([0.,1.],[0.],0),([0.,1.],[0.,0.],2)]:
            with self.assertRaises(ValueError):state_loss(torch.tensor(scores),torch.tensor(targets),ref)

if __name__=='__main__':unittest.main()
