"""Public-history joint future-station and paid-channel proposals.

This module neither imports an environment nor reads case/seed files. All cost
estimates are fixed-state route proxies; only complete external replay measures
real performance. Every emitted alternative has a continuous certificate.
"""
import copy
import itertools
import math
import time
try:
    from .continuous import canonical_hash, certify_points
except ImportError:
    from continuous import canonical_hash, certify_points

VERSION = 'jointplan-geometry-v1'


def snapshot_hash(snapshot):
    return canonical_hash({k: v for k, v in snapshot.items() if k not in ('snapshot_hash', 'remaining_real_s', 'deadline_monotonic')})


def _channels(station):
    return sorted(set(station.get('channels', [])))


def _past_points(snapshot, channel):
    result = []
    for row in snapshot.get('history', []):
        request, response = row.get('request', row), row.get('response', row)
        if (row.get('action') == 'measure' and request.get('channel') == channel
                and response.get('measure_result', response.get('result')) == 'no_signal'
                and response.get('accepted', True) is True):
            result.append(tuple(request['point']) if 'point' in request else (request['x'], request['y']))
    return result


def _validate(snapshot, plan):
    if plan.get('snapshot_hash') != snapshot_hash(snapshot):
        return 'stale_snapshot'
    if plan.get('parent_sha256') != snapshot.get('parent_sha256') or plan.get('history_version') != snapshot.get('history_version'):
        return 'stale_parent_or_history'
    originals = {s['id']: s for s in snapshot['stations']}
    proposed = {s['id']: s for s in plan['stations']}
    if len(proposed) != len(plan['stations']) or set(proposed) != set(originals):
        return 'station_id_mismatch'
    for key, station in proposed.items():
        old = originals[key]
        if old.get('mutable', True) is False and station != old:
            return 'immutable_station_changed'
        if any(type(c) is not int or c not in range(1, 21) for c in station.get('channels', [])):
            return 'invalid_paid_channel'
        if len(station.get('point', [])) != 2 or not all(math.isfinite(p) and abs(p) <= 2000000 for p in station['point']):
            return 'invalid_coordinate'
    return None


def verify(snapshot, plan, deadline=None, keep_leaves=False):
    error = _validate(snapshot, plan)
    if error:
        return {'status': 'unknown', 'reason': error}
    cache, proofs = {}, {}
    for channel in sorted(snapshot['unknown_channels']):
        points = _past_points(snapshot, channel) + [tuple(s['point']) for s in plan['stations'] if channel in _channels(s)]
        key = tuple(sorted(set(points)))
        if key not in cache:
            cache[key] = certify_points(snapshot['mode'], points, deadline=deadline, keep_leaves=keep_leaves)
        result = cache[key]
        proofs[str(channel)] = result
        if result['status'] != 'certified':
            return {'status': result['status'], 'channel': channel, 'reason': result.get('reason'), 'witness': result.get('witness'), 'proofs': proofs}
    return {'status': 'certified', 'version': VERSION, 'snapshot_hash': plan['snapshot_hash'], 'plan_points_hash': canonical_hash(plan['stations']), 'unique_point_sets': len(cache), 'proofs': proofs}


def _source_anchors(snapshot):
    result = []
    for task in snapshot.get('source_tasks', []):
        anchor = task.get('anchor', task.get('point'))
        if anchor is None and task.get('polygon'):
            ps = task['polygon']
            anchor = [sum(p[k] for p in ps) / len(ps) for k in (0, 1)]
        if anchor is not None:
            result.append((('source', task['channel']), tuple(anchor)))
    return result


def _route(snapshot, stations):
    tasks = [(('station', s['id']), tuple(s['point'])) for s in stations if _channels(s)] + _source_anchors(snapshot)
    if not tasks:
        return [], 0.
    coords = {key: value for key, value in tasks}
    remain = set(coords)
    order, position = [], tuple(snapshot['position'])
    while remain:
        key = min(remain, key=lambda k: (math.dist(position, coords[k]), str(k)))
        order.append(key)
        position = coords[key]
        remain.remove(key)
    def distance(route):
        last, cost = tuple(snapshot['position']), 0.
        for key in route:
            cost += math.dist(last, coords[key])
            last = coords[key]
        return cost
    best = distance(order)
    for _ in range(3):
        changed = False
        for i in range(len(order)):
            for j in range(i + 1, len(order)):
                route = order[:i] + list(reversed(order[i:j + 1])) + order[j + 1:]
                value = distance(route)
                if value < best - 1e-8:
                    best, order, changed = value, route, True
        if not changed:
            break
    return order, best


def proxy_cost(snapshot, stations):
    order, movement = _route(snapshot, stations)
    assigned = {s['id']: _channels(s) for s in stations}
    channel, measures, switches = snapshot.get('channel', 1), 0, 0
    for kind, key in order:
        if kind != 'station':
            continue
        channels = assigned[key][:]
        if channel in channels:
            channels.remove(channel)
            channels.insert(0, channel)
        for c in channels:
            measures += 1
            switches += int(c != channel)
            channel = c
    # Known-source fixed clear fees do not change across station layouts. Source
    # localization/retests and stochastic discoveries remain unmodeled, explicit.
    return {'total_s': movement / 5 + 5 * measures + switches, 'movement_m': movement, 'measure_count': measures, 'switch_count': switches, 'route': [list(k) for k in order], 'cost_scope': 'fixed_state_route_plus_paid_unknown_measures_only'}


def _base_plan(snapshot):
    return {'version': VERSION, 'snapshot_hash': snapshot_hash(snapshot), 'parent_sha256': snapshot.get('parent_sha256'), 'history_version': snapshot.get('history_version'), 'stations': copy.deepcopy(snapshot['stations']), 'replaced_ids': [], 'removed_channel_actions': [], 'fallback_id': 'continue_from_real_public_history', 'invalidated_by': ['new_observation', 'new_clear', 'different_position_or_channel']}


def _roundpoint(point):
    return [round(float(p), 6) for p in point]


def _interpolate(a, b, f, max_move):
    distance = math.dist(a, b)
    f = min(f, max_move / max(distance, 1e-9))
    return _roundpoint([a[k] + f * (b[k] - a[k]) for k in (0, 1)])


def propose(snapshot, options=None):
    options = {**snapshot.get('geometry_options', {}), **(options or {})}
    started = time.perf_counter()
    deadline = started + float(options.get('max_seconds', 1.5 if snapshot['mode'] == 4 else .25))
    max_plans = int(options.get('max_plans', 6))
    base = _base_plan(snapshot)
    base_cost = proxy_cost(snapshot, base['stations'])
    mutable = {s['id']: s for s in base['stations'] if s.get('mutable', True) and _channels(s)}
    order = [key for kind, key in base_cost['route'] if kind == 'station' and key in mutable]
    anchors = _source_anchors(snapshot)
    candidates = []
    block_sizes = options.get('block_sizes', [2])
    # Move a block toward several public service tasks together. Repositioning
    # can profit even when its scan-only path is longer, because sources already
    # have to be served. Include radial and route-smoothing alternatives.
    for count in block_sizes:
        if count not in (2, 3, 4) or count > len(order):
            continue
        for start in range(len(order) - count + 1):
            keys = order[start:start + count]
            for attraction, step in (('source', 80.), ('source', 200.), ('source', 450.), ('radial_in', 50.), ('radial_out', 150.), ('smooth', 80.)):
                plan = copy.deepcopy(base)
                points = {s['id']: s for s in plan['stations']}
                for index, key in enumerate(keys):
                    original = mutable[key]['point']
                    if attraction == 'source':
                        if not anchors:
                            continue
                        target = min(anchors, key=lambda task: math.dist(original, task[1]))[1]
                    elif attraction == 'radial_in':
                        target = (0., 0.)
                    elif attraction == 'radial_out':
                        target = (2 * original[0], 2 * original[1])
                    else:
                        previous = mutable[order[start + index - 1]]['point'] if start + index else snapshot['position']
                        following = mutable[order[start + index + 1]]['point'] if start + index + 1 < len(order) else previous
                        target = [(previous[k] + following[k]) / 2 for k in (0, 1)]
                    points[key]['point'] = _interpolate(original, target, 1., step)
                changed = [key for key in keys if points[key]['point'] != mutable[key]['point']]
                if len(changed) < 2:
                    continue
                plan['replaced_ids'] = changed
                plan['mechanism'] = {'block_size': count, 'attraction': attraction, 'step_m': step}
                plan['proxy'] = proxy_cost(snapshot, plan['stations'])
                plan['proxy_gain_s'] = base_cost['total_s'] - plan['proxy']['total_s']
                candidates.append(plan)
    # Preferred complete proxy first; finite enumeration is deterministic and
    # candidate ranking never observes later true environment responses.
    candidates.sort(key=lambda p: (-p['proxy_gain_s'], canonical_hash(p['stations'])))
    emitted, seen, attempts, statuses = [], set(), 0, {}
    for plan in candidates:
        if time.perf_counter() >= deadline or len(emitted) >= max_plans:
            break
        key = canonical_hash(plan['stations'])
        if key in seen:
            continue
        seen.add(key)
        if plan['proxy_gain_s'] <= float(options.get('minimum_proxy_gain_s', 0.)):
            continue
        attempts += 1
        cert = verify(snapshot, plan, deadline=deadline)
        statuses[cert['status']] = statuses.get(cert['status'], 0) + 1
        if cert['status'] != 'certified':
            continue
        # Paid assignment optimization: only delete a real future channel action
        # after its whole remaining continuous obligation is independently met.
        if options.get('prune_channels', True):
            groups = {}
            for ch in snapshot['unknown_channels']:
                group = (tuple(sorted(set(_past_points(snapshot, ch)))), tuple(s['id'] for s in plan['stations'] if ch in _channels(s)))
                groups.setdefault(group, []).append(ch)
            for channels in groups.values():
                for station in reversed(plan['stations']):
                    if time.perf_counter() >= deadline:
                        break
                    if not station.get('mutable', True) or channels[0] not in _channels(station):
                        continue
                    previous = station['channels'][:]
                    station['channels'] = [c for c in previous if c not in channels]
                    checked = verify(snapshot, plan, deadline=deadline)
                    if checked['status'] == 'certified':
                        plan['removed_channel_actions'].extend([[station['id'], c] for c in channels if c in previous])
                        cert = checked
                    else:
                        station['channels'] = previous
        plan['certificate'] = cert
        plan['proxy'] = proxy_cost(snapshot, plan['stations'])
        plan['proxy_gain_s'] = base_cost['total_s'] - plan['proxy']['total_s']
        plan['route_station_ids'] = [key for kind, key in plan['proxy']['route'] if kind == 'station']
        plan['generation'] = {'seconds': time.perf_counter() - started, 'attempts': attempts, 'statuses': dict(statuses), 'proposed_candidates': len(candidates)}
        emitted.append(plan)
    return emitted
