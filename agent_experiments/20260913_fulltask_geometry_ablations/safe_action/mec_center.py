"""Single-factor B3 ablation: use the MEC center for certified one-clear states."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "最佳方法/代码/solver.py"
EXPECTED_SOURCE_SHA256 = "e6a0666d644ceaa1d7ae69f19042b9ca022379f3e5a57d927e52bcf1a09360bd"

assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == EXPECTED_SOURCE_SHA256
_spec = importlib.util.spec_from_file_location("safe_action_center_frozen_b3", SOURCE)
_B3 = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_B3)

OPTIMIZED_CONFIGS = {k: dict(v) for k, v in _B3.OPTIMIZED_CONFIGS.items()}
BASELINE_CONFIG = dict(_B3.BASELINE_CONFIG)
ARM = "mec_center"
_original = _B3._G._LensSpatial.route_clear_point


def _mec_only_for_certified_single_clear(self, center, radius, original):
    ch = getattr(self, "_active_target", None)
    poly = self.polygons.get(ch) if ch is not None else None
    if radius <= 20.0 + 1e-9 and poly:
        q = tuple(center)
        maximum = max(_B3._G._sp_dist(q, v) for v in poly)
        self.safe_action_audit = getattr(self, "safe_action_audit", [])
        self.safe_action_audit.append({
            "arm": ARM, "channel": ch, "vertices": len(poly),
            "mec_center": list(center), "mec_radius_m": radius,
            "position_before": list(self.position),
            "route_successor": list(self.route_successor) if getattr(self, "route_successor", None) is not None else None,
            "parent_inner_disk_point": list(original), "selected_point": list(q),
            "maximum_vertex_distance_m": maximum,
            "selected_point_certified": maximum <= 20.0 + 1e-8,
            "distance_from_mec_center_m": 0.0,
        })
        return q
    return _original(self, center, radius, original)


_B3._G._LensSpatial.route_clear_point = _mec_only_for_certified_single_clear


class Solver:
    def __new__(cls, env, mode=3, **config):
        return _B3.Solver(env, mode=mode, **config)

