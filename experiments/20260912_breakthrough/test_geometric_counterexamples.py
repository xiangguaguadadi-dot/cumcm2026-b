"""Synthetic tests of the independent reviewer, not solver evaluations."""
import unittest

from verify_geometric_counterexamples import point, witness


class WitnessTests(unittest.TestCase):
    def test_convex_interior_has_no_negative_witness(self):
        self.assertIsNone(witness(point((0,0)), [point(x) for x in [(-1,-1),(1,-1),(1,1),(-1,1)]]))

    def test_collinear_closed_halfplanes_include_boundary(self):
        self.assertIsNone(witness(point((0,0)), [point((-1,0)),point((1,0))]))

    def test_closed_receive_boundary_is_retained(self):
        self.assertIsNone(witness(point((0,0)), [point((-1000,0)),point((1000,0))]))

    def test_coincident_station_always_detects(self):
        self.assertIsNone(witness(point((0,0)), [point((0,0))]))

    def test_strictly_separated_point_has_witness(self):
        result = witness(point((0,1)), [point((-1,0)),point((1,0))])
        self.assertTrue(result['exact_strict_halfplane_check'])
        self.assertGreater(result['strict_projection_margin_m_approx'],0)

    def test_outside_domain_is_not_counterexample(self):
        self.assertIsNone(witness(point(('1800.000001',0)), []))


if __name__ == '__main__':
    unittest.main()
