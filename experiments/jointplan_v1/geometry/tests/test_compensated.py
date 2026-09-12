import unittest
from experiments.jointplan_v1.geometry.tests.test_geometry import snapshot
from experiments.jointplan_v1.geometry.compensated_arcs import propose_compensated
from experiments.jointplan_v1.geometry.engine import _base_plan, verify


class CompensatedArcTests(unittest.TestCase):
    def test_inward_and_outward_stations_are_jointly_certifiable(self):
        s = snapshot()
        s['source_tasks'] = [{'channel': 1, 'anchor': [850., 0.]}]
        base = _base_plan(s)
        for count in (2, 3, 4):
            plans = propose_compensated(s, base, [count])
            self.assertTrue(plans)
            certified = []
            for plan in plans:
                if verify(s, plan)['status'] == 'certified':
                    certified.append(plan)
            self.assertTrue(certified)
            self.assertTrue(all(len(p['replaced_ids']) == count for p in certified))
            self.assertEqual(s['stations'], base['stations'])

    def test_no_nonpublic_station_reconstruction(self):
        s = snapshot()
        s['stations'].pop()
        self.assertEqual(propose_compensated(s, _base_plan(s), [2]), [])

    def test_q4_does_not_use_circle_arc_shortcut(self):
        s = snapshot()
        s['mode'] = 4
        self.assertEqual(propose_compensated(s, _base_plan(s), [2]), [])


if __name__ == '__main__':
    unittest.main()
