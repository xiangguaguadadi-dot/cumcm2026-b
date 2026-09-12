"""Pure geometry tests: no environment or evaluation data is instantiated."""
import copy
import math
import unittest
from experiments.jointplan_v1.geometry import certify_points, replay_certificate, propose, verify, snapshot_hash
from experiments.jointplan_v1.geometry.continuous import quantize_points


def q3_points(radius=1124.):
    return [(0., 0.)] + [(radius * math.cos(i * math.pi / 3), radius * math.sin(i * math.pi / 3)) for i in range(6)]


def q4_points():
    return [(0., 0.)] + [(999 * math.cos(i * math.pi / 4), 999 * math.sin(i * math.pi / 4)) for i in range(8)] + [(1864 * math.cos(i * math.pi / 6), 1864 * math.sin(i * math.pi / 6)) for i in range(12)]


def snapshot():
    ps = q3_points()
    return {'mode': 3, 'position': [0., 0.], 'channel': 1, 'history_version': 20, 'parent_sha256': 'synthetic', 'history': [{'action': 'measure', 'point': [0., 0.], 'channel': c, 'result': 'no_signal'} for c in range(1, 21)], 'unknown_channels': list(range(10, 21)), 'stations': [{'id': i, 'point': list(p), 'channels': list(range(10, 21)), 'mutable': True} for i, p in enumerate(ps) if i > 0], 'source_tasks': [{'channel': i + 1, 'anchor': [p[0] * 1.35, p[1] * 1.35]} for i, p in enumerate(ps[1:])]}


class GeometryTests(unittest.TestCase):
    def test_q3_full_continuous_certificate_and_replay(self):
        points = q3_points()
        proof = certify_points(3, points, keep_leaves=True)
        self.assertEqual(proof['status'], 'certified')
        self.assertTrue(replay_certificate(3, points, proof))

    def test_q4_full_continuous_certificate_and_replay(self):
        points = q4_points()
        proof = certify_points(4, points, keep_leaves=True)
        self.assertEqual(proof['status'], 'certified')
        self.assertTrue(replay_certificate(4, points, proof))

    def test_radius_coverage_does_not_certify_q4(self):
        self.assertEqual(certify_points(4, q3_points())['status'], 'counterexample')

    def test_missing_station_detects_real_continuous_hole(self):
        self.assertEqual(certify_points(3, q3_points()[:-1])['status'], 'counterexample')

    def test_no_margin_boundary_returns_unknown(self):
        # Four cardinal points at exactly R around origin do not permit a strict
        # robust origin leaf, and unrelated holes do not manufacture a proof.
        result = certify_points(4, [(1000., 0.), (-1000., 0.), (0., 1000.), (0., -1000.)], max_depth=0)
        self.assertEqual(result['status'], 'unknown')

    def test_computation_limit_never_certifies(self):
        self.assertEqual(certify_points(3, q3_points(), max_nodes=1)['status'], 'unknown')

    def test_omitted_leaf_and_duplicate_leaf_rejected(self):
        ps = q3_points()
        proof = certify_points(3, ps, keep_leaves=True)
        bad = copy.deepcopy(proof)
        bad['leaves'].pop()
        self.assertFalse(replay_certificate(3, ps, bad))
        bad = copy.deepcopy(proof)
        bad['leaves'].append(bad['leaves'][0])
        self.assertFalse(replay_certificate(3, ps, bad))

    def test_moved_points_invalidate_prior_proof(self):
        ps = q3_points()
        proof = certify_points(3, ps, keep_leaves=True)
        ps[1] = (1125., 0.)
        self.assertFalse(replay_certificate(3, ps, proof))

    def test_past_action_channels_are_not_free(self):
        s = snapshot()
        p = {'snapshot_hash': snapshot_hash(s), 'parent_sha256': s['parent_sha256'], 'history_version': s['history_version'], 'stations': copy.deepcopy(s['stations'])}
        p['stations'][0]['channels'].remove(10)
        self.assertEqual(verify(s, p)['status'], 'counterexample')

    def test_stale_snapshot_rejected(self):
        s = snapshot()
        plans = propose(s, {'max_seconds': 2, 'block_sizes': [2], 'max_plans': 1})
        self.assertTrue(plans)
        s['position'][0] = 1.
        self.assertEqual(verify(s, plans[0])['reason'], 'stale_snapshot')

    def test_two_three_four_joint_moves_are_executable_and_certified(self):
        for count in (2, 3, 4):
            s = snapshot()
            plans = propose(s, {'max_seconds': 2, 'block_sizes': [count], 'max_plans': 1})
            self.assertTrue(plans)
            self.assertEqual(len(plans[0]['replaced_ids']), count)
            self.assertGreater(plans[0]['proxy_gain_s'], 0.)
            self.assertEqual(verify(s, plans[0])['status'], 'certified')
            self.assertEqual(s, snapshot(), 'propose must not mutate public history')

    def test_integer_quantization_bound(self):
        for x in (-2000000., -1.2345, -.00049, 0., .00049, 1.2345, 2000000.):
            p = quantize_points([(x, -x)])[0]
            self.assertLessEqual(abs(p[0] / 1024 - x), .5 / 1024)


if __name__ == '__main__':
    unittest.main()
