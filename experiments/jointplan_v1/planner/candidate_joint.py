"""Certified future-station commits plus natural-unit mixed scheduling.

All executed actions remain in the live parent state. Failed/unknown final
coverage verification triggers a fully paid original-layout completion from
that state; no re-enter, clock reset, or historical-coordinate rollback exists.
"""
import ast
import copy
import importlib.util
import math
from pathlib import Path
import sys
import time
import types


def _load(name, path, package=False):
    spec = importlib.util.spec_from_file_location(name, path,
        submodule_search_locations=[str(path.parent)] if package else None)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_DIR = Path(__file__).resolve().parent
_D = _load("jointplan_disabled_adapter", _DIR / "candidate_disabled.py")
_M = _load("jointplan_mixed_planner", _DIR / "mixed_planner.py")
OPTIMIZED_CONFIGS = {mode: dict(config, jointplan_geometry=True, jointplan_mixed=True,
                               jointplan_intervention_limit=2, jointplan_boundary_visited=[1, 3])
                     for mode, config in _D.OPTIMIZED_CONFIGS.items()}
BASELINE_CONFIG = dict(_D.BASELINE_CONFIG)
_RUN_CACHE = {}
_GEOMETRY = None


def _geometry(self):
    provider = self.jointplan_options.get("jointplan_geometry_provider")
    if provider is not None:
        return provider
    global _GEOMETRY
    if _GEOMETRY is None:
        _GEOMETRY = _load("jointplan_geometry", _DIR.parent / "geometry/__init__.py", package=True)
    return _GEOMETRY


def _joint_run(original):
    wanted = original.__qualname__.split(".")[0]
    def run_code(module_code):
        klass = next(c for c in module_code.co_consts if isinstance(c, types.CodeType) and c.co_name == wanted)
        return next(c for c in klass.co_consts if isinstance(c, types.CodeType) and c.co_name == "run")
    for source in _D._embedded_sources(_D._SOURCE):
        tree = ast.parse(source)
        for klass in tree.body:
            if not isinstance(klass, ast.ClassDef) or klass.name != wanted:
                continue
            method = next(x for x in klass.body if isinstance(x, ast.FunctionDef) and x.name == "run")
            if run_code(compile(tree, "<jointplan-run-match>", "exec")).co_code != original.__code__.co_code:
                continue
            outer = next(x for x in method.body if isinstance(x, ast.While))
            outer.body.insert(0, ast.parse("if self._jp_boundary(todo, visited):\n    continue").body[0])
            index = next(i for i, x in enumerate(method.body) if isinstance(x, ast.Assign)
                         and any(isinstance(t, ast.Name) and t.id == "unresolved" for t in x.targets))
            method.body.insert(index, ast.parse("self._jp_finish(todo, visited)").body[0])
            certificate = next(x for x in method.body if isinstance(x, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "geometric_certificate" for t in x.targets))
            certificate.value = ast.Call(func=ast.Attribute(value=ast.Name(id="self", ctx=ast.Load()),
                attr="_jp_certificate", ctx=ast.Load()), args=[ast.Name(id="unresolved", ctx=ast.Load()),
                certificate.value], keywords=[])
            code = run_code(compile(ast.fix_missing_locations(tree), "<jointplan-enabled-run>", "exec"))
            return types.FunctionType(code, original.__globals__, "run", original.__defaults__, original.__closure__)
    raise RuntimeError("Could not match frozen parent run for enabled planner")


def _snapshot(self, todo, visited):
    snapshot = _D.snapshot_from_solver(self, todo, visited)
    if self._jp_geometry_active:
        for station in snapshot["stations"]:
            allowed = self._jp_channels.get(station["id"], list(snapshot["unknown_channels"]))
            station["channels"] = [c for c in allowed if c in snapshot["unknown_channels"]]
        snapshot["pending_stations"] = copy.deepcopy(snapshot["stations"])
    snapshot["snapshot_hash"] = _D.public_hash(snapshot)
    return snapshot


def _base_plan(snapshot, stations=None):
    return {"snapshot_hash": snapshot["snapshot_hash"], "parent_sha256": _D.PARENT_SHA256,
            "history_version": snapshot["history_version"],
            "stations": copy.deepcopy(snapshot["stations"] if stations is None else stations),
            "replaced_ids": [], "route_station_ids": list(snapshot["route_station_ids"])}


def _commit(self, snapshot, plan, todo):
    # Bind all pending real coordinates/history; verify is independently called
    # even when propose returned a certificate.
    checked = _geometry(self).verify(snapshot, plan,
        deadline=time.perf_counter() + self.jointplan_options.get("jointplan_verify_seconds", 2.))
    if checked.get("status") != "certified":
        return checked
    current = {s["id"]: s for s in snapshot["stations"]}
    if set(current) != {s["id"] for s in plan["stations"]}:
        return {"status": "unknown", "reason": "pending_station_ids_changed"}
    prepared = []
    for station in plan["stations"]:
        old = current[station["id"]]
        p = tuple(map(float, station["point"]))
        if len(p) != 2 or not all(math.isfinite(v) for v in p):
            return {"status": "unknown", "reason": "invalid_coordinate"}
        if p != tuple(old["point"]) and not old["mutable"]:
            return {"status": "unknown", "reason": "attempt_to_move_executed_station"}
        if station["id"] not in todo:
            return {"status": "unknown", "reason": "station_already_executed"}
        prepared.append((station["id"], p, sorted(set(station["channels"]))))
    # No actual history, position, channel, deadline, or paid cost is modified.
    for index, p, channels in prepared:
        self.points[index] = p
        self._jp_channels[index] = channels
    self._jp_geometry_active = True
    self._jp_last_certificate = checked
    return checked


def _scan(self, index, defer=False):
    if not self._jp_geometry_active or index not in self._jp_channels:
        return self._jp_parent_scan(index, defer=defer)
    p = self.points[index]
    unknown = [c for c in self._jp_channels[index]
               if c not in self.cleared and not self.observations[c]]
    if self.channel in unknown:
        unknown.remove(self.channel)
        unknown.insert(0, self.channel)
    self.counters["scan_stations"] += 1
    for ch in unknown:
        self.measure(p, ch)  # parent near -> clear and protected clear behavior remain intact
        self.scanned[ch].add(index)  # approximate parent route bookkeeping only
    # Preserve the frozen parent's paid station retest gates for known sources.
    for ch in range(1, 21):
        if ch in self.cleared or not self.observations[ch]:
            continue
        if any(math.dist(p, old) < 1e-5 for old, _ in self.observations[ch]):
            continue
        if self.mode == 4:
            take = self._e2_gate(ch, p, "station")
            if take:
                self.counters["e2_station_retests"] = self.counters.get("e2_station_retests", 0) + 1
        else:
            enclosing = self.run.__globals__["_sp_enclosing_circle"]
            center, radius = enclosing(self.polygons[ch])
            if math.dist(center, p) > 1500. + radius:
                continue
            self.counters["a1_station_considered"] = self.counters.get("a1_station_considered", 0) + 1
            prediction = self._gate_prediction(ch, p) if radius > 20. else (0., -1.)
            take = prediction is None or prediction[1] > 0.
            key = "a1_station_taken" if take else "a1_station_skipped"
            self.counters[key] = self.counters.get(key, 0) + 1
        if take:
            self.measure(p, ch)
    if not defer:
        pending = [c for c in range(1, 21) if self.observations[c] and c not in self.cleared]
        for ch in pending:
            while ch not in self.cleared:
                self.localize(ch)


def _boundary(self, todo, visited):
    snapshot = _snapshot(self, todo, visited)
    if self.jointplan_options.get("jointplan_capture_snapshots", True):
        self.jointplan_snapshots.append(snapshot)
    if self._jp_base_points is None and visited:
        # The original origin-triggered rotation/adaptive ring has now finished.
        self._jp_base_points = [tuple(p) for p in self.points]
    if len(self.cleared) >= 16:
        todo.clear()
        return True
    if self._jp_geometry_active:
        retired = [i for i in todo if not any(c not in self.cleared and not self.observations[c]
                                              for c in self._jp_channels.get(i, range(1, 21)))]
        for i in retired:
            todo.remove(i)
            self._jp_retired.append(i)
        if retired:
            return True
    options = self.jointplan_options
    allowed_visited = options.get("jointplan_boundary_visited", [1, 3])
    replay = options.get("jointplan_replay")
    prefix = replay.get("snapshot_hash") if replay else options.get("jointplan_prefix_hash")
    eligible = bool(visited) and self._jp_generation_attempts < options.get("jointplan_intervention_limit", 2)
    eligible &= (snapshot["snapshot_hash"] == prefix) if prefix else len(visited) in allowed_visited
    eligible &= snapshot["snapshot_hash"] not in self._jp_attempted
    if not prefix:
        eligible &= len(visited) not in self._jp_attempted_visited
    if not eligible:
        return False
    self._jp_attempted.add(snapshot["snapshot_hash"])
    self._jp_attempted_visited.add(len(visited))
    self._jp_generation_attempts += 1
    if replay:
        self._jp_replay_status = "matched_preparation"
    started = time.perf_counter()
    decision = {"snapshot_hash": snapshot["snapshot_hash"], "history_version": snapshot["history_version"],
                "virtual_time_before_s": self.virtual_time, "geometry_requested": bool(options.get("jointplan_geometry", True))}
    try:
        plans = [copy.deepcopy(replay["plan"])] if replay else (_geometry(self).propose(
            snapshot, options.get("jointplan_geometry_options")) if options.get("jointplan_geometry", True) else [])
        decision["generated_plans"] = len(plans)
        selected_plan = None
        selected = _M.choose(snapshot) if options.get("jointplan_mixed", True) else None
        baseline_cost = _M.choose(snapshot)
        rank = 0 if replay else options.get("jointplan_candidate_rank")
        if plans and rank is not None:
            if 0 <= rank < len(plans):
                selected_plan = plans[rank]
                selected = _M.choose(snapshot, selected_plan["stations"])
        elif plans:
            alternatives = [(_M.choose(snapshot, p["stations"]), p) for p in plans]
            alternatives = [(s, p) for s, p in alternatives if s is not None]
            if alternatives:
                choice, plan = min(alternatives, key=lambda pair: (pair[0]["cost"]["total_s"], pair[1].get("plan_id", "")))
                if baseline_cost is None or choice["cost"]["total_s"] < baseline_cost["cost"]["total_s"] - options.get("jointplan_minimum_gain_s", 0.):
                    selected, selected_plan = choice, plan
        if selected_plan is not None:
            checked = _commit(self, snapshot, selected_plan, todo)
            decision["commit_certificate"] = checked
            if checked.get("status") != "certified":
                if replay:
                    self._jp_replay_status = "matched_but_certificate_rejected"
                selected_plan = None
                selected = _M.choose(snapshot) if options.get("jointplan_mixed", True) and not replay else None
            else:
                decision["plan"] = copy.deepcopy(selected_plan)
        if selected is None:
            decision["status"] = "no_admissible_plan"
            self.jointplan_decisions.append(decision)
            return False
    except Exception as error:
        # This catch surrounds pure preparation only. Protocol exceptions from
        # any real accepted/unknown operation below are never swallowed/retried.
        decision.update(status="planning_error_before_action", error=repr(error))
        if replay:
            self._jp_replay_status = "matched_but_preparation_failed"
        self.jointplan_decisions.append(decision)
        return False
    decision.update(status="execute", selection=selected, planning_seconds=time.perf_counter() - started)
    self.jointplan_decisions.append(decision)
    self._jp_interventions += 1
    if replay:
        self._jp_replay_status = "committed_once"
    if selected_plan is not None and (not options.get("jointplan_mixed", True) or
                                      (replay and replay.get("scheduler", "parent") == "parent")):
        decision["status"] = "commit_parent_schedule"
        return False
    self.route_successor = tuple(selected["route_successor"]) if selected["route_successor"] is not None else None
    action = selected["next_action"]
    if action["kind"] == "station":
        index = action["key"]
        self.scan_station(index, defer=True)
        visited.append(index)
        todo.remove(index)
    else:
        self.localize(action["key"])
    decision["virtual_time_after_unit_s"] = self.virtual_time
    decision["actual_unit_cost_s"] = self.virtual_time - decision["virtual_time_before_s"]
    return True


def _finish(self, todo, visited):
    if not self._jp_geometry_active or len(self.cleared) >= 16:
        return
    snapshot = _snapshot(self, set(), visited)
    checked = _geometry(self).verify(snapshot, _base_plan(snapshot),
        deadline=time.perf_counter() + self.jointplan_options.get("jointplan_verify_seconds", 2.))
    self._jp_final_certificate = checked
    if checked.get("status") == "certified":
        return
    # A safe and deliberately complete continuation: append original certified
    # sites as new obligations, preserving every past action and live state.
    self.counters["jointplan_paid_coverage_fallbacks"] = self.counters.get("jointplan_paid_coverage_fallbacks", 0) + 1
    original = self._jp_base_points or [tuple(p) for p in self.points]
    for p in original:
        index = len(self.points)
        self.points.append(p)
        self._jp_parent_scan(index, defer=True)
        visited.append(index)
    enclosing = self.run.__globals__.get("_sp_enclosing_circle", self.run.__globals__.get("_di_enclosing_circle"))
    while any(self.observations[c] and c not in self.cleared for c in range(1, 21)):
        pending = [c for c in range(1, 21) if self.observations[c] and c not in self.cleared]
        ch = min(pending, key=lambda c: math.dist(self.position, enclosing(self.polygons[c])[0]))
        self.localize(ch)
    unresolved = [c for c in range(1, 21) if c not in self.cleared]
    self._jp_fallback_complete = all(not self.observations[c] and all(
        any(math.dist(p, q) < 1e-7 for q in self.no_signal_points[c]) for p in original) for c in unresolved)
    if not self._jp_fallback_complete and len(self.cleared) < 16:
        raise RuntimeError("Paid original-layout fallback lacks actual channel evidence")


def _certificate(self, unresolved, parent_certificate):
    if not self._jp_geometry_active:
        return parent_certificate
    return bool(self._jp_fallback_complete or (self._jp_final_certificate.get("status") == "certified"
                and all(not self.observations[c] for c in unresolved)))


def _diagnostics(self):
    result = _D._diagnostics(self)
    result["kind"] = "jointplan_mixed_and_certified_geometry"
    result["decisions"] = copy.deepcopy(self.jointplan_decisions)
    for decision in result["decisions"]:
        decision["actual_remaining_s"] = self.virtual_time - decision["virtual_time_before_s"]
        if "selection" in decision:
            decision["predicted_minus_actual_remaining_s"] = decision["selection"]["cost"]["total_s"] - decision["actual_remaining_s"]
    result["retired_station_ids"] = list(self._jp_retired)
    result["final_geometry_certificate"] = copy.deepcopy(self._jp_final_certificate)
    result["paid_original_fallback_complete"] = self._jp_fallback_complete
    result["generation_attempts"] = self._jp_generation_attempts
    result["interventions"] = self._jp_interventions
    result["replay_status"] = self._jp_replay_status
    result["replay_requested_hash"] = self.jointplan_options.get("jointplan_replay", {}).get("snapshot_hash")
    return result


class Solver:
    def __new__(cls, env, mode=3, **config):
        merged = {**OPTIMIZED_CONFIGS[mode], **config}
        options = {k: v for k, v in merged.items() if k.startswith("jointplan_")}
        clean = {k: v for k, v in merged.items() if not k.startswith("jointplan_")}
        ledger = _D.PublicLedgerEnv(env)
        solver = _D._PARENT.Solver(ledger, mode=mode, **clean)
        original = solver.run.__func__
        if original not in _RUN_CACHE:
            _RUN_CACHE[original] = _joint_run(original)
        solver._jp_parent_scan = solver.scan_station
        solver.run = types.MethodType(_RUN_CACHE[original], solver)
        solver.scan_station = types.MethodType(_scan, solver)
        solver._jp_boundary = types.MethodType(_boundary, solver)
        solver._jp_finish = types.MethodType(_finish, solver)
        solver._jp_certificate = types.MethodType(_certificate, solver)
        solver.jointplan_diagnostics = types.MethodType(_diagnostics, solver)
        solver.jointplan_options = options
        solver.jointplan_snapshots, solver.jointplan_decisions = [], []
        solver._jp_channels, solver._jp_final_certificate = {}, {}
        solver._jp_interventions = 0
        solver._jp_generation_attempts = 0
        solver._jp_replay_status = "not_matched" if options.get("jointplan_replay") else "not_requested"
        solver._jp_geometry_active = solver._jp_fallback_complete = False
        solver._jp_base_points = None
        solver._jp_retired, solver._jp_attempted, solver._jp_attempted_visited = [], set(), set()
        return solver
