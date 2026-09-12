"""Q4 outer-station radial compensation and circumscribed-arc proposals.

Outer polygon containment alone is insufficient for directional detection.
Every layout still requires the independent nearby convex-hull RF certificate.
This module does not infer a no_signal exclusion disk in Q4.
"""
import copy
import math
try:
    from .compensated_arcs import _negative_points
except ImportError:
    from compensated_arcs import _negative_points


def _outer_ring(snapshot):
    entries, seen = [], set()
    for station in snapshot['stations']:
        point = station['point']
        radius = math.hypot(*point)
        if radius >= 1750.:
            entries.append({'id': station['id'], 'point': point, 'radius': radius, 'angle': math.atan2(point[1], point[0]) % (2 * math.pi), 'mutable': station.get('mutable', True)})
            seen.add(tuple(point))
    channels = snapshot['unknown_channels']
    if not channels:
        return []
    for point in _negative_points(snapshot, channels[0]):
        radius = math.hypot(*point)
        if radius >= 1750. and point not in seen:
            entries.append({'id': None, 'point': point, 'radius': radius, 'angle': math.atan2(point[1], point[0]) % (2 * math.pi), 'mutable': False})
            seen.add(point)
    entries.sort(key=lambda e: e['angle'])
    if len(entries) != 12:
        return []
    gaps = [(entries[(i + 1) % 12]['angle'] - e['angle']) % (2 * math.pi) for i, e in enumerate(entries)]
    return entries if min(gaps) >= math.radians(15) and max(gaps) <= math.radians(45) else []


def _tangent_half_width(radius):
    return math.acos(1800. / radius) - 1e-4 if radius > 1800. else 0.


def propose_directional_compensated(snapshot, base_plan, block_sizes):
    if snapshot['mode'] != 4:
        return []
    ring = _outer_ring(snapshot)
    anchors = [s['anchor'] for s in snapshot.get('source_tasks', []) if s.get('anchor') is not None]
    if not ring or not anchors:
        return []
    plans = []
    for count in block_sizes:
        if count not in (2, 3, 4):
            continue
        for start in range(12):
            block = [ring[(start + k) % 12] for k in range(count)]
            if not all(e['mutable'] for e in block):
                continue
            left, right = ring[(start - 1) % 12], ring[(start + count) % 12]
            left_angle = left['angle']
            span = (right['angle'] - left_angle) % (2 * math.pi)
            old_angles = [left_angle + (e['angle'] - left_angle) % (2 * math.pi) for e in block]
            for pivot in range(count):
                target = min(anchors, key=lambda p: math.dist(p, block[pivot]['point']))
                target_angle = math.atan2(target[1], target[0])
                target_angle += round((old_angles[pivot] - target_angle) / (2 * math.pi)) * 2 * math.pi
                for inward, expansion_factor in ((1., 1.5), (3., 1.5), (5., 1.5), (10., 2.)):
                    radii = [e['radius'] + inward * expansion_factor / (count - 1) for e in block]
                    radii[pivot] = block[pivot]['radius'] - inward
                    widths = [_tangent_half_width(left['radius'])] + [_tangent_half_width(r) for r in radii] + [_tangent_half_width(right['radius'])]
                    caps = [widths[k] + widths[k + 1] for k in range(count + 1)]
                    total = sum(caps)
                    if total <= span:
                        continue
                    cumulative, angles = 0., []
                    for i in range(count):
                        cumulative += caps[i]
                        angles.append(left_angle + cumulative * span / total)
                    desired = old_angles[:]
                    desired[pivot] = target_angle
                    for _ in range(12):
                        for i in range(count):
                            before = left_angle if i == 0 else angles[i - 1]
                            after = left_angle + span if i == count - 1 else angles[i + 1]
                            lower, upper = max(before + 1e-6, after - caps[i + 1]), min(after - 1e-6, before + caps[i])
                            if lower <= upper:
                                angles[i] = max(lower, min(upper, desired[i]))
                    plan = copy.deepcopy(base_plan)
                    stations = {s['id']: s for s in plan['stations']}
                    for entry, radius, angle in zip(block, radii, angles):
                        stations[entry['id']]['point'] = [round(radius * math.cos(angle), 6), round(radius * math.sin(angle), 6)]
                    plan['replaced_ids'] = [e['id'] for e in block]
                    plan['mechanism'] = {'block_size': count, 'attraction': 'directional_outer_compensation', 'pivot_id': block[pivot]['id'], 'pivot_inward_m': inward, 'total_companion_outward_m': inward * expansion_factor}
                    plans.append(plan)
    return plans
