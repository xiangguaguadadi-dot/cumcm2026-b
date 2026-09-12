"""Public-history adapter for the frozen fusion_r5 solver.

The only modification to the frozen run method is a call at the top of its
outer scheduling loop.  The disabled boundary function records data and never
selects, suppresses, or executes an environment action.
"""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import time
import types

PARENT_SHA256 = "0bda4f711b9e9716739af8aedf456cb1eeefb47d8ba3ed230ca682c8450a96ea"
_ROOT = Path(__file__).resolve().parents[3]
_PARENT_PATH = _ROOT / "experiments/parallel_v2_coordinator/fusion_r5.py"
_SOURCE = _PARENT_PATH.read_text(encoding="utf-8")
if hashlib.sha256(_SOURCE.encode()).hexdigest() != PARENT_SHA256:
    raise RuntimeError("Frozen parent SHA256 mismatch")
_spec = importlib.util.spec_from_file_location("jointplan_frozen_parent", _PARENT_PATH)
_PARENT = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_PARENT)
OPTIMIZED_CONFIGS = {mode: dict(config) for mode, config in _PARENT.OPTIMIZED_CONFIGS.items()}
BASELINE_CONFIG = dict(_PARENT.BASELINE_CONFIG)


def public_hash(value):
    """Stable physical/history hash; wall-clock deadline is explicitly excluded."""
    value = {k: v for k, v in value.items() if k not in
             {"snapshot_hash", "remaining_real_s", "deadline_monotonic"}}
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


class PublicLedgerEnv:
    """Records only the public four-method protocol; no env introspection."""
    _FIELDS = {"accepted", "action", "duration_s", "virtual_time_s", "measure_result",
               "svd_deg", "clear_result", "exit_reason", "max_virtual_duration_s",
               "max_real_duration_s", "remaining_real_duration_s", "error", "message"}

    def __init__(self, env):
        self._env = env
        self.history = []

    def _call(self, action, args):
        result = getattr(self._env, action)(*args)
        request = {} if not args else {"point": [float(args[0]), float(args[1])],
                                      "channel": int(args[2])}
        # Real-time values are retained for review but normalized in the hash.
        response = {k: copy.deepcopy(v) for k, v in result.items() if k in self._FIELDS}
        self.history.append({"action": action, "request": request, "response": response})
        return result

    def enter(self):
        return self._call("enter", ())

    def measure(self, x, y, channel):
        return self._call("measure", (x, y, channel))

    def clear(self, x, y, channel):
        return self._call("clear", (x, y, channel))

    def exit(self):
        return self._call("exit", ())


def _embedded_sources(source):
    yield source
    for node in ast.walk(ast.parse(source)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "compile" and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            yield from _embedded_sources(node.args[0].value)


def _hooked_run(original):
    """Find the exact frozen run AST, then insert a natural-boundary hook."""
    wanted = original.__qualname__.split(".")[0]
    def run_code(module_code):
        klass = next(c for c in module_code.co_consts if isinstance(c, types.CodeType) and c.co_name == wanted)
        return next(c for c in klass.co_consts if isinstance(c, types.CodeType) and c.co_name == "run")
    for source in _embedded_sources(_SOURCE):
        tree = ast.parse(source)
        for klass in tree.body:
            if not isinstance(klass, ast.ClassDef) or klass.name != wanted:
                continue
            for method in klass.body:
                if not isinstance(method, ast.FunctionDef) or method.name != "run":
                    continue
                # Compile the full module for its exact symbol context, but
                # never execute it. Reuse the frozen function globals below.
                code = run_code(compile(tree, "<jointplan-run-match>", "exec"))
                if code.co_code != original.__code__.co_code:
                    continue
                outer = next(x for x in method.body if isinstance(x, ast.While))
                hook = ast.parse("self._jp_boundary(todo, visited)").body[0]
                outer.body.insert(0, hook)
                code = run_code(compile(ast.fix_missing_locations(tree), "<jointplan-natural-boundary>", "exec"))
                return types.FunctionType(code, original.__globals__, "run", original.__defaults__, original.__closure__)
    raise RuntimeError("Could not match frozen parent run function")


def snapshot_from_solver(solver, todo, visited):
    """Detached JSON state containing only actual public observations."""
    history = copy.deepcopy(solver.env.history)
    # The accepted deadline remains separately available to the actor; it is
    # excluded here so identical observations have a reproducible prefix hash.
    for row in history:
        row["response"].pop("remaining_real_duration_s", None)
    unknown = [c for c in range(1, 21) if c not in solver.cleared and not solver.observations[c]]
    stations = [{"id": i, "point": list(solver.points[i]), "channels": list(unknown),
                 "mutable": i in todo and i != 0} for i in sorted(todo)]
    failed = getattr(solver, "failed_clear_points", getattr(solver, "_e2_failed_clear", {}))
    enclosing = solver.run.__globals__.get("_sp_enclosing_circle", solver.run.__globals__.get("_di_enclosing_circle"))
    tasks = []
    for ch in range(1, 21):
        if ch in solver.cleared or not solver.observations[ch]:
            continue
        center, radius = enclosing(solver.polygons[ch])
        tasks.append({"channel": ch, "polygon": [list(p) for p in solver.polygons[ch]],
                      "anchor": list(center), "radius": radius,
                      "observations": [{"point": list(p), "bearing_deg": deg}
                                       for p, deg in solver.observations[ch]],
                      "service_progress": getattr(solver, "_a1_progress", getattr(solver, "_e2_progress", {})).get(ch, 0)})
    snapshot = {"schema_version": 1, "mode": solver.mode, "position": list(solver.position),
                "channel": solver.channel, "history_version": len(history), "history": history,
                "parent_sha256": PARENT_SHA256, "unknown_channels": unknown,
                "cleared_channels": sorted(solver.cleared),
                "negative_points": {str(c): [list(p) for p in solver.no_signal_points[c]] for c in range(1, 21)},
                "failed_clear_points": {str(c): [list(p) for p in failed.get(c, [])] for c in range(1, 21)},
                "stations": stations, "pending_stations": stations,
                "route_station_ids": sorted(todo), "visited_station_ids": list(visited),
                "source_tasks": tasks, "virtual_time_s": solver.virtual_time,
                "remaining_virtual_s": max(0., 360000. - solver.virtual_time),
                "deadline_monotonic": solver.deadline,
                "remaining_real_s": max(0., solver.deadline - time.monotonic()) if solver.deadline else None,
                "protected_plan_active": bool(getattr(solver, "_protected_clear_plan", False)),
                "route_successor": list(solver.route_successor) if getattr(solver, "route_successor", None) is not None else None}
    snapshot["snapshot_hash"] = public_hash(snapshot)
    return snapshot


def _disabled_boundary(self, todo, visited):
    snapshot = snapshot_from_solver(self, todo, visited)
    self.jointplan_snapshots.append(snapshot)
    callback = self.jointplan_options.get("jointplan_snapshot_callback")
    if callback is not None:
        callback(copy.deepcopy(snapshot))


_RUN_CACHE = {}


class Solver:
    def __new__(cls, env, mode=3, **config):
        options = {k: v for k, v in config.items() if k.startswith("jointplan_")}
        clean = {k: v for k, v in config.items() if not k.startswith("jointplan_")}
        ledger = PublicLedgerEnv(env)
        solver = _PARENT.Solver(ledger, mode=mode, **clean)
        original = solver.run.__func__
        if original not in _RUN_CACHE:
            _RUN_CACHE[original] = _hooked_run(original)
        solver.run = types.MethodType(_RUN_CACHE[original], solver)
        solver._jp_boundary = types.MethodType(_disabled_boundary, solver)
        solver.jointplan_options = options
        solver.jointplan_snapshots = []
        return solver
