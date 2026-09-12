"""Q3 joint radial compensation plus boundary-arc reassignment.

This is only a proposal grammar. Its trigonometric calculations are NOT a
coverage certificate; every output must pass the separate integer whole-domain
verifier before any action. It reads detached public history only.
"""
import copy
import math


def _negative_points(snapshot, channel):
    points = []
    for row in snapshot.get('history', []):
        request, response = row.get('request', row), row.get('response', row)
        if (row.get('action') == 'measure' and request.get('channel') == channel
                and response.get('measure_result', response.get('result')) == 'no_signal'
                and response.get('accepted', True) is True):
            points.append(tuple(request['point']) if 'point' in request else (request['x'], request['y']))
    return points


def _half_width(radius):
    # For source radial coordinate t in [1000,1800], distance squared to a
    # station is convex in t. Satisfying both endpoint circles is sufficient.
    values = [(t * t + radius * radius - 1000. * 1000.) / (2 * t * radius) for t in (1000., 1800.)]
    if max(values) >= 1.:
        return 0.
    return min(math.acos(max(-1., v)) for v in values) - 1e-4


def _ring(snapshot):
    future = {s['id']: s for s in snapshot['stations']}
    entries = []
    seen = set()
    for station in future.values():
        point = station['point']
        radius = math.hypot(*point)
        if radius > 850.:
            entries.append({'id': station['id'], 'point': point, 'radius': radius, 'angle': math.atan2(point[1], point[0]) % (2 * math.pi), 'mutable': station.get('mutable', True)})
            seen.add(tuple(point))
    channels = snapshot['unknown_channels']
    if not channels:
        return []
    for point in _negative_points(snapshot, channels[0]):
        radius = math.hypot(*point)
        if radius > 850. and point not in seen:
            entries.append({'id': None, 'point': point, 'radius': radius, 'angle': math.atan2(point[1], point[0]) % (2 * math.pi), 'mutable': False})
            seen.add(point)
    entries.sort(key=lambda e: e['angle'])
    if len(entries) != 6:
        return []
    gaps = [(entries[(i + 1) % 6]['angle'] - e['angle']) % (2 * math.pi) for i, e in enumerate(entries)]
    if min(gaps) < math.radians(30) or max(gaps) > math.radians(90):
        return []
    return entries


def propose_compensated(snapshot, base_plan, block_sizes):
    if snapshot['mode'] != 3:
        return []
    ring = _ring(snapshot)
    if not ring:
        return []
    anchors = [s['anchor'] for s in snapshot.get('source_tasks', []) if s.get('anchor') is not None]
    if not anchors:
        return []
    proposals = []
    for count in block_sizes:
        if count not in (2, 3, 4):
            continue
        for start in range(6):
            block = [ring[(start + k) % 6] for k in range(count)]
            if not all(e['mutable'] for e in block):
                continue
            left, right = ring[(start - 1) % 6], ring[(start + count) % 6]
            left_angle = left['angle']
            span = (right['angle'] - left_angle) % (2 * math.pi)
            old_angles = [left_angle + (e['angle'] - left_angle) % (2 * math.pi) for e in block]
            for pivot in range(count):
                target = min(anchors, key=lambda p: math.dist(p, block[pivot]['point']))
                if math.hypot(*target) >= block[pivot]['radius']:
                    continue
                for shrink, expansion in ((.90, 375.), (.95, 200.), (.98, 100.)):
                    radii = [min(1497., e['radius'] + expansion / max(1, count - 1)) for e in block]
                    radii[pivot] = max(900., block[pivot]['radius'] * shrink)
                    widths = [_half_width(left['radius'])] + [_half_width(r) for r in radii] + [_half_width(right['radius'])]
                    caps = [widths[i] + widths[i + 1] for i in range(count + 1)]
                    total = sum(caps)
                    if total < span + 1e-7:
                        continue
                    # Start with a feasible allocation of the whole angular span.
                    angles, cumulative = [], 0.
                    for i in range(count):
                        cumulative += caps[i]
                        angles.append(left_angle + cumulative * span / total)
                    desired = old_angles[:]
                    target_angle = math.atan2(target[1], target[0])
                    target_angle += round((old_angles[pivot] - target_angle) / (2 * math.pi)) * 2 * math.pi
                    desired[pivot] = target_angle
                    for _ in range(12):
                        for i in range(count):
                            before = left_angle if i == 0 else angles[i - 1]
                            after = left_angle + span if i == count - 1 else angles[i + 1]
                            lower = max(before + 1e-6, after - caps[i + 1])
                            upper = min(after - 1e-6, before + caps[i])
                            if lower <= upper:
                                angles[i] = max(lower, min(upper, desired[i]))
                    plan = copy.deepcopy(base_plan)
                    stations = {s['id']: s for s in plan['stations']}
                    for entry, radius, angle in zip(block, radii, angles):
                        stations[entry['id']]['point'] = [round(radius * math.cos(angle), 6), round(radius * math.sin(angle), 6)]
                    plan['replaced_ids'] = [e['id'] for e in block]
                    plan['mechanism'] = {'block_size': count, 'attraction': 'compensated_boundary_arcs', 'pivot_id': block[pivot]['id'], 'pivot_radial_fraction': shrink, 'companion_expansion_total_m': expansion, 'half_arc_widths_deg': [math.degrees(w) for w in widths[1:-1]]}
                    proposals.append(plan)
    return proposals
