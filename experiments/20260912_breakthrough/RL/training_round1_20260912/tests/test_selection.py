import unittest
from ..selection import float32,predicted_choice,gated_choice
from ..policy import Policy
from ..calibration_math import world_residual,margin_from_worlds

class SelectionTests(unittest.TestCase):
    def test_float32_difference_and_hash_tie(self):
        ids=['a'*64,'b'*64,'c'*64];scores=[float32(.1),float32(.1),float32(.09)]
        c=predicted_choice(ids,ids[2],scores)
        self.assertEqual(c['candidate_id'],ids[0]);self.assertEqual(c['gains'][0],float32(scores[0]-scores[2]))

    def test_teacher_reference_may_be_any_index(self):
        ids=['a'*64,'b'*64];c=predicted_choice(ids,ids[1],[float32(.01),0.])
        self.assertEqual((c['teacher_index'],c['candidate_id']),(1,ids[0]))

    def test_gate_strict_equal_boundary_is_teacher(self):
        ids=['a'*64,'b'*64];gain=float32(1/1024);margin=gain-0.0005
        c=gated_choice(ids,ids[0],[0.,gain],margin)
        self.assertEqual(c['strict_threshold'],gain);self.assertEqual(c['selected_id'],ids[0])
        self.assertEqual(gated_choice(ids,ids[0],[0.,gain],0.)['selected_id'],ids[1])

    def test_invalid_scores_ids_and_margins(self):
        ids=['a'*64,'b'*64]
        for scores in ([0.,float('nan')],[0.,float('inf')],[0.],[0.,.1]):
            with self.assertRaises(ValueError):predicted_choice(ids,ids[0],scores)
        with self.assertRaises(ValueError):predicted_choice(ids,'c'*64,[0.,0.])
        for margin in (-1.,float('nan'),float('inf')):
            with self.assertRaises(ValueError):Policy(None,margin)

class CalibrationTests(unittest.TestCase):
    def states(self,value):return [dict(candidate_id='b',teacher_id='a',predicted_gain=value,realized_gain=0.)]

    def test_world_max_not_average(self):
        states=self.states(0.002)+self.states(0.02)
        self.assertEqual(world_residual(states),0.02)

    def test_24_world_nearest_rank_22(self):
        rows=[dict(world_id=str(i),status='complete',states=self.states(i/1000),world_max_optimistic_residual=i/1000) for i in range(24)]
        q=margin_from_worlds(rows,[str(i) for i in range(24)])
        self.assertEqual((q['nearest_rank'],q['margin']),(22,0.021))

    def test_negative_margin_clamped_to_zero(self):
        rows=[dict(world_id=str(i),status='complete',states=self.states(-0.01),world_max_optimistic_residual=-0.01) for i in range(24)]
        self.assertEqual(margin_from_worlds(rows,[str(i) for i in range(24)])['margin'],0.)

    def test_A0_residual_exact_zero(self):
        state=dict(candidate_id='a',teacher_id='a',predicted_gain=0.,realized_gain=0.)
        self.assertEqual(world_residual([state]),0.)
        state['predicted_gain']=.001
        with self.assertRaises(ValueError):world_residual([state])

    def test_incomplete_empty_duplicate_and_nonfinite_rejected(self):
        with self.assertRaises(ValueError):world_residual([])
        with self.assertRaises(ValueError):world_residual(self.states(float('nan')))
        rows=[dict(world_id=str(i),status='complete',states=self.states(0.),world_max_optimistic_residual=0.) for i in range(24)]
        with self.assertRaises(ValueError):margin_from_worlds(rows[:-1],[str(i) for i in range(24)])
        rows[-1]=dict(rows[0])
        with self.assertRaises(ValueError):margin_from_worlds(rows,[str(i) for i in range(24)])

if __name__=='__main__':unittest.main()
