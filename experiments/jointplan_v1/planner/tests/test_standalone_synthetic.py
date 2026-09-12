"""Build/source/hash tests and pure synthetic protocol equivalence only."""
import builtins
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from test_adapter_synthetic import SyntheticProtocol

FILE = Path(__file__).resolve().parents[1] / "build_standalone.py"
spec = importlib.util.spec_from_file_location("builder", FILE)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
REPO = FILE.parents[3]
GEOMETRY = REPO.parent / "geometry/experiments/jointplan_v1/geometry"
if not GEOMETRY.is_dir():
    GEOMETRY = REPO / "experiments/jointplan_v1/geometry"


class StandaloneTests(unittest.TestCase):
    def test_bundle_import_and_synthetic_run_without_file_or_filesystem(self):
        code, manifest = builder.build_sources(REPO, entry="joint", geometry_dir=GEOMETRY,
            config={"3": {"jointplan_intervention_limit": 0}, "4": {"jointplan_intervention_limit": 0}})
        self.assertEqual(builder.sha256(code), manifest["standalone_sha256"])
        scope = {"__name__": "standalone_without_file_attribute"}
        def forbidden(*args, **kwargs):
            raise AssertionError("Standalone attempted filesystem access")
        with patch.object(builtins, "open", forbidden), patch.object(Path, "read_text", forbidden), \
             patch.object(Path, "resolve", forbidden), patch.object(os.path, "exists", forbidden):
            exec(compile(code, "<standalone-in-memory>", "exec"), scope)
            for mode in (3, 4):
                env = SyntheticProtocol(near=True)
                result = scope["Solver"](env, mode=mode).run()
                self.assertEqual(result["cleared_count"], 16)
                self.assertTrue(result["completion_certified"])
                self.assertEqual(sum(c[0] == "enter" for c in env.calls), 1)
            geometry = scope["_JP_LOAD"]("geometry")
            parent = scope["_JP_LOAD"]("parent")
            points = parent.Solver(object(), mode=3).points
            proof = geometry.certify_points(3, points)
            self.assertEqual(proof["status"], "certified")

    def test_disabled_bundle_matches_parent_all_negative_trace(self):
        code, _ = builder.build_sources(REPO, entry="disabled", geometry_dir=GEOMETRY)
        scope = {"__name__": "bundle_disabled_test"}
        exec(compile(code, "<bundle-disabled-test>", "exec"), scope)
        for mode in (3, 4):
            e0, e1 = SyntheticProtocol(), SyntheticProtocol()
            scope["_JP_LOAD"]("parent").Solver(e0, mode=mode).run()
            scope["Solver"](e1, mode=mode).run()
            self.assertEqual(e0.calls, e1.calls)

    def test_replay_data_is_not_a_normal_embedded_actor_default(self):
        with self.assertRaises(ValueError):
            builder.build_sources(REPO, geometry_dir=GEOMETRY,
                config={"3": {"jointplan_replay": {"snapshot_hash": "exposed-prefix"}}})

    def test_source_tampering_is_detected_before_runtime(self):
        code, manifest = builder.build_sources(REPO, geometry_dir=GEOMETRY)
        manifest_sha = manifest["embedded_sha256"]["mixed"]
        code = code.replace(manifest_sha, "0" * 64)
        with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
            exec(compile(code, "<tampered-bundle>", "exec"), {"__name__": "tampered_bundle"})

    @unittest.skipUnless((GEOMETRY / "compensated_engine.py").is_file(), "Optional compensated provider unavailable")
    def test_fixed_alternate_geometry_provider_is_fully_embedded(self):
        code, manifest = builder.build_sources(REPO, geometry_dir=GEOMETRY,
                                               geometry_provider="compensated_engine")
        self.assertIn("compensated_engine", manifest["geometry_load_order"])
        self.assertIn("compensated_arcs", manifest["geometry_load_order"])
        scope = {"__name__": "alternate_geometry_bundle"}
        exec(compile(code, "<alternate-geometry>", "exec"), scope)
        provider = scope["_JP_LOAD"]("geometry")
        self.assertTrue(provider.propose.__module__.endswith(".compensated_engine"))
        self.assertTrue(callable(provider.verify))


if __name__ == "__main__":
    unittest.main()
