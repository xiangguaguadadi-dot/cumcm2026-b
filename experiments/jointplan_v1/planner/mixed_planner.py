"""Deterministic full mixed-route proxy, with explicit paid action branches.

This is a planning approximation, never a coverage or clearing certificate.
It prices every remaining discovery scan in the all-negative branch, plus
all currently known source services and their failed-trial continuation.
Additional sources discovered online invalidate the prediction and trigger
replanning. Prediction errors are retained against actual full-task suffixes.
"""
import math


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _atoms(task):
    polygon = task["polygon"]
    center = task["anchor"]
    if not polygon:
        return [center]
    # Deterministic quadrature inside a convex public feasible polygon.
    stride = max(1, len(polygon) // 8)
    points = [center] + [[center[0] + .65 * (p[0] - center[0]),
                          center[1] + .65 * (p[1] - center[1])]
                         for p in polygon[::stride]][:8]
    return points


def _certified_proxy(start, center, radius, successor):
    margin = max(0., 20. - radius - 1e-6)
    if _dist(start, center) <= margin:
        return start
    candidates = [center]
    for target in [start, successor] if successor is not None else [start]:
        distance = _dist(target, center)
        if distance > 0:
            candidates.append([center[0] + margin * (target[0] - center[0]) / distance,
                               center[1] + margin * (target[1] - center[1]) / distance])
    return min(candidates, key=lambda p: _dist(start, p) + (_dist(p, successor) if successor else 0.))


def _source_service(task, starts, channel, successor, mode):
    """Weighted endpoint branches, including failed clear and near clear fees."""
    center, radius, ch = task["anchor"], task["radius"], task["channel"]
    samples = _atoms(task)
    cost = move = measures = clears = switches = 0.
    ends = []
    for start, weight in starts:
        if radius <= 20.:
            q = _certified_proxy(start, center, radius, successor)
            d = _dist(start, q) / 5.
            cost += weight * (d + 5.)
            move += weight * d
            clears += weight
            ends.append((q, weight))
            continue
        for target in samples:
            w = weight / len(samples)
            pos = start
            branch = dsum = nm = nc = ns = 0.
            # The parent currently tries an optical point inside this scale.
            if radius <= 100. or task.get("service_progress", 0) >= 3:
                d = _dist(pos, center) / 5.
                branch += d + 3.
                dsum += d
                nc += 1
                pos = center
                if _dist(center, target) <= 20.:
                    branch += 2.
                else:
                    # Failure branch: a paid same-location measurement, then
                    # follow-up localization and actual successful optical clear.
                    branch += 5. + (channel != ch)
                    nm += 1
                    ns += channel != ch
                    d = max(0., _dist(pos, target) - 19.) / 5.
                    branch += d + 5.
                    dsum += d
                    nc += 1
                    pos = target
                    if mode == 4:
                        # Directional no_signal may demand an extra paid
                        # probe; model is deliberately recorded as approximate.
                        branch += 3.
                        nm += .5
            else:
                observed = task.get("observations", [])
                p = observed[-1]["point"] if observed else start
                deg = observed[-1]["bearing_deg"] if observed else math.degrees(math.atan2(center[1] - p[1], center[0] - p[0]))
                angle = math.radians(deg)
                u = (math.cos(angle), math.sin(angle))
                length = max(0., (center[0] - p[0]) * u[0] + (center[1] - p[1]) * u[1])
                advance = max(30., .6 * length)
                lateral = max(45., min(190., .15 * length))
                probes = [[p[0] + advance * u[0] - sign * lateral * u[1],
                           p[1] + advance * u[1] + sign * lateral * u[0]] for sign in (-1, 1)]
                # One common action for the shared public history. Quadrature
                # targets influence outcomes, never a separate first action.
                probe = min(probes, key=lambda q: _dist(pos, q) + _dist(q, center)
                            + (.12 * _dist(q, successor) if successor else 0.))
                d = _dist(pos, probe) / 5.
                branch += d + 5. + (channel != ch)
                dsum += d
                nm += 1
                ns += channel != ch
                d = max(0., _dist(probe, target) - 19.) / 5.
                branch += d + 5.
                dsum += d
                nc += 1
                pos = target
                if mode == 4:
                    branch += 6.
                    nm += 1
            cost += w * branch
            move += w * dsum
            measures += w * nm
            clears += w * nc
            switches += w * ns
            ends.append((pos, w))
    # Keep the endpoint uncertainty across the next route edge. Bound growth
    # by merging identical public quadrature target coordinates.
    merged = {}
    for p, w in ends:
        key = tuple(p)
        merged[key] = merged.get(key, 0.) + w
    return cost, list(merged.items()), ch if measures else channel, {
        "movement_s": move, "measures": measures, "clear_attempts": clears,
        "switches": switches, "service_s": cost - move}


def task_map(snapshot, stations=None):
    stations = snapshot["stations"] if stations is None else stations
    tasks = {("station", s["id"]): dict(s, kind="station", anchor=s["point"])
             for s in stations if s["channels"]}
    tasks.update({("source", s["channel"]): dict(s, kind="source") for s in snapshot["source_tasks"]})
    return tasks


def route_cost(snapshot, route, tasks=None):
    tasks = task_map(snapshot) if tasks is None else tasks
    starts = [(snapshot["position"], 1.)]
    channel = snapshot["channel"]
    total = 0.
    breakdown = {"movement_s": 0., "measures": 0., "clear_attempts": 0., "switches": 0., "service_s": 0.}
    for index, key in enumerate(route):
        task = tasks[key]
        successor = tasks[route[index + 1]]["anchor"] if index + 1 < len(route) else None
        if key[0] == "source":
            cost, starts, channel, part = _source_service(task, starts, channel, successor, snapshot["mode"])
        else:
            p = task["point"]
            channels = sorted(task["channels"])
            if channel in channels:
                channels.remove(channel)
                channels.insert(0, channel)
            move = sum(w * _dist(start, p) / 5. for start, w in starts)
            switches = 0
            for ch in channels:
                switches += ch != channel
                channel = ch
            service = 5. * len(channels) + switches
            cost = move + service
            part = {"movement_s": move, "measures": len(channels), "clear_attempts": 0.,
                    "switches": switches, "service_s": service}
            starts = [(p, 1.)]
        total += cost
        for k in breakdown:
            breakdown[k] += part[k]
    return {"total_s": total, "breakdown": breakdown, "modeled_tail": "all_remaining_scans_and_current_source_services",
            "additional_discovery": "invalidates_prediction_and_replans", "endpoint_model": "public_polygon_quadrature"}


def choose(snapshot, stations=None, options=None):
    """Complete route neighborhood including paid scans and uncertain service exits."""
    options = options or {}
    tasks = task_map(snapshot, stations)
    keys = sorted(tasks)
    if not keys:
        return None
    remaining = set(keys)
    greedy = []
    previous = snapshot["position"]
    while remaining:
        key = min(remaining, key=lambda k: (_dist(previous, tasks[k]["anchor"]), k))
        greedy.append(key)
        previous = tasks[key]["anchor"]
        remaining.remove(key)
    distance_cost = lambda route: _dist(snapshot["position"], tasks[route[0]]["anchor"]) + sum(
        _dist(tasks[a]["anchor"], tasks[b]["anchor"]) for a, b in zip(route, route[1:]))
    routes = [greedy, keys, keys[::-1]]
    # Only candidate generation uses the cheap distance proxy. Final route
    # choice always includes every modeled action, switch and service branch.
    for start in list(routes):
        route = start[:]
        for _ in range(12):
            current = distance_cost(route)
            alternatives = [route[:i] + route[i:j + 1][::-1] + route[j + 1:]
                            for i in range(len(route) - 1) for j in range(i + 1, len(route))]
            best = min(alternatives, key=distance_cost, default=route)
            if distance_cost(best) >= current - 1e-6:
                break
            route = best
        routes.append(route)
    shortest = min(routes, key=distance_cost)
    # Explicitly insert either station or source service at the front, retaining
    # all other obligations. This expands beyond a fixed current-source score.
    for key in shortest[: min(6, len(shortest))]:
        routes.append([key] + [k for k in shortest if k != key])
    parent_action = options.get("parent_action")
    if parent_action is not None and tuple(parent_action) in tasks:
        key = tuple(parent_action)
        routes.append([key] + [k for k in shortest if k != key])
    unique = {tuple(route): route for route in routes}
    scored = [(route_cost(snapshot, route, tasks), route) for route in unique.values()]
    cost, route = min(scored, key=lambda row: (row[0]["total_s"], row[1]))
    parent = next((c for c, r in scored if r[0] == tuple(parent_action)), None) if parent_action else None
    return {"next_action": {"kind": route[0][0], "key": route[0][1]},
            "route": [list(k) for k in route], "route_successor": tasks[route[1]]["anchor"] if len(route) > 1 else None,
            "cost": cost, "parent_first_cost": parent,
            "candidate_routes": len(scored), "snapshot_hash": snapshot["snapshot_hash"]}
