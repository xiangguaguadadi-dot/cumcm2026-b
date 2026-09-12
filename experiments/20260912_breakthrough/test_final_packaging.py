"""Synthetic packaging/trace guards only; no solver or environment tasks."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load('final_builder_test', HERE / 'build_final.py')
traces = load('final_trace_test', HERE / 'verify_dispatch_traces.py')


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cumcm-packaging-test-')
        self.root = Path(self.temp.name).resolve()
        self.parents = []
        for name in ('A1', 'A2'):
            directory = self.root / name
            directory.mkdir()
            path = directory / 'fake.py'
            path.write_text(
                'BASELINE_CONFIG={"base":1}\n'
                'OPTIMIZED_CONFIGS={3:{"a":3},4:{"a":4}}\n'
                f'TAG={name!r}\n'
                'def Solver(env,mode=3,**config):return TAG,env,mode,config\n'
            )
            self.parents.append(path)
        self.out = self.root / 'output' / 'combined.py'

    def tearDown(self):
        self.temp.cleanup()

    def build(self, bad_hash=False):
        args = ['build_final.py', '--q3', str(self.parents[0]),
                '--q3-sha', 'bad' if bad_hash else builder.sha(self.parents[0]),
                '--q4', str(self.parents[1]), '--q4-sha', builder.sha(self.parents[1]),
                '--out', str(self.out)]
        with patch.object(builder, 'HERE', self.root), patch.object(sys, 'argv', args), \
                patch('builtins.print'):
            builder.main()

    def test_dispatch_preserves_mode_env_and_overrides(self):
        self.build()
        mod = load('synthetic_final_dispatch', self.out)
        for mode, name in ((3, 'A1'), (4, 'A2')):
            env = object()
            self.assertEqual(mod.Solver(env, mode, a=19), (name, env, mode, {'a': 19}))
        with self.assertRaises(ValueError):
            mod.Solver(None, mode=2)

    def test_parent_namespaces_and_config_are_independent(self):
        self.build()
        mod = load('synthetic_final_isolation', self.out)
        mod._FINAL_Q3.TAG = 'changed'
        mod.OPTIMIZED_CONFIGS[3]['a'] = 99
        self.assertEqual(mod._FINAL_Q4.TAG, 'A2')
        self.assertEqual(mod._FINAL_Q3.OPTIMIZED_CONFIGS[3]['a'], 3)

    def test_manifest_binds_exact_source_and_output(self):
        self.build()
        manifest = json.loads(self.out.with_suffix('.build.json').read_text())
        self.assertEqual(manifest['candidate_sha256'], builder.sha(self.out))
        self.assertEqual(manifest['q3_sha256'], builder.sha(self.parents[0]))
        self.assertEqual(manifest['q4_sha256'], builder.sha(self.parents[1]))
        self.assertEqual(manifest['external_deployment_dependencies'], [])
        self.assertEqual(manifest['validation_status'], 'not yet executed')

    def test_wrong_parent_hash_rejected_before_output(self):
        with self.assertRaises(AssertionError):
            self.build(bad_hash=True)
        self.assertFalse(self.out.exists())

    def test_existing_output_not_overwritten(self):
        self.build()
        before = self.out.read_bytes()
        with self.assertRaises(AssertionError):
            self.build()
        self.assertEqual(before, self.out.read_bytes())

    def test_sidecar_rejected_at_build_and_import(self):
        self.out.parent.mkdir()
        sidecar = self.out.parent / 'coverage_points.json'
        sidecar.write_text('[]')
        with self.assertRaises(AssertionError):
            self.build()
        sidecar.unlink()
        self.build()
        sidecar.write_text('[]')
        with self.assertRaisesRegex(RuntimeError, 'coverage_points'):
            load('synthetic_final_sidecar', self.out)


class TraceTests(unittest.TestCase):
    def test_rejected_attempt_is_recorded(self):
        class Backend:
            def measure(self, **kwargs):
                raise ValueError('synthetic rejection')
        recorder = traces.RecordingInterface(Backend())
        with self.assertRaises(ValueError):
            recorder.measure(1, 2, 3)
        self.assertEqual(len(recorder.calls), 1)
        self.assertEqual(recorder.calls[0]['request'], {'x': 1, 'y': 2, 'channel': 3})
        self.assertEqual(recorder.calls[0]['error'], 'ValueError: synthetic rejection')

    def test_only_two_machine_clock_fields_are_ignored(self):
        def row(virtual=5, real=1):
            return {'action': 'measure', 'request': {'channel': 1}, 'error': None,
                    'response': {'real_timestamp_ms': real,
                                 'remaining_real_duration_s': 1200 - real,
                                 'elapsed_virtual_time_s': virtual, 'status': 'no_signal'}}
        self.assertEqual(traces.canonical_trace([row(real=1)]),
                         traces.canonical_trace([row(real=2)]))
        self.assertNotEqual(traces.canonical_trace([row(virtual=5)]),
                            traces.canonical_trace([row(virtual=6)]))


if __name__ == '__main__':
    unittest.main(verbosity=2)
