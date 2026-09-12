"""Pure protocol fixtures: these are not local-world solver evaluations."""
import importlib.util
import math
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "candidate_disabled.py"
spec = importlib.util.spec_from_file_location("adapter", PATH)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class SyntheticProtocol:
    def __init__(self, near=False):
        self.near = near
        self.p = (0., 0.)
        self.channel = 1
        self.us = 0
        self.calls = []

    def _result(self, action, args, fixed, **fields):
        if args:
            p = args[:2]
            self.us += round((math.dist(self.p, p) / 5. + fixed) * 1e6)
            self.p = p
        self.calls.append((action, args, self.us, fields))
        return dict(accepted=True, virtual_time_s=self.us / 1e6, **fields)

    def enter(self):
        return self._result("enter", (), 0., remaining_real_duration_s=1200.)

    def exit(self):
        return self._result("exit", (), 0., exit_reason="user_exit")

    def measure(self, x, y, ch):
        fixed = 5. + (ch != self.channel)
        self.channel = ch
        return self._result("measure", (x, y, ch), fixed,
                            measure_result="near" if self.near and ch <= 16 else "no_signal")

    def clear(self, x, y, ch):
        return self._result("clear", (x, y, ch), 5., clear_result="success")


class AdapterTests(unittest.TestCase):
    def test_exact_requests_and_virtual_time_on_synthetic_protocol(self):
        for mode in (3, 4):
            for near in (False, True):
                with self.subTest(mode=mode, near=near):
                    old_env, new_env = SyntheticProtocol(near), SyntheticProtocol(near)
                    old = adapter._PARENT.Solver(old_env, mode=mode)
                    new = adapter.Solver(new_env, mode=mode)
                    r0, r1 = old.run(), new.run()
                    self.assertEqual(old_env.calls, new_env.calls)
                    self.assertEqual(old.trace, new.trace)
                    self.assertEqual(old.counters, new.counters)
                    self.assertEqual(old.scanned, new.scanned)
                    self.assertEqual(r0["virtual_time_s"], r1["virtual_time_s"])
                    self.assertTrue(new.jointplan_snapshots)
                    for snap in new.jointplan_snapshots:
                        self.assertEqual(snap["snapshot_hash"], adapter.public_hash(snap))
                        self.assertNotIn("env", snap)
                    if near:
                        self.assertEqual(sum(x[0] == "clear" for x in new_env.calls), 16)

    def test_hash_ignores_real_deadline_but_binds_actual_geometry(self):
        s = {"position": [0., 0.], "remaining_real_s": 1., "deadline_monotonic": 2.}
        t = dict(s, remaining_real_s=9., deadline_monotonic=10.)
        self.assertEqual(adapter.public_hash(s), adapter.public_hash(t))
        self.assertNotEqual(adapter.public_hash(s), adapter.public_hash(dict(t, position=[1., 0.])))


if __name__ == "__main__":
    unittest.main()
