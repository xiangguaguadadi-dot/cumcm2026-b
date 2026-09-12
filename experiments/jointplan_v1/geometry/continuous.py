"""Integer conservative continuous discovery certificates (standard library).

A grid is used to partition a continuum, never to assert that point samples
cover it. Every retained square is proved covered, or the answer is unknown.
Q4 uses a nearby-station convex hull sufficient condition for every direction.
Station coordinates are exact binary input floats; their rational rounding to
1/1024 m has Euclidean error < 1/1024 m. Radius and hull margins are 2/1024 m.
"""
import hashlib
import json
import math
import time

SCALE = 1024
EXTENT = 2048 * SCALE
DOMAIN2 = (1800 * SCALE) ** 2
RADIUS = 1000 * SCALE - 2
MARGIN = 2


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _quantize(x):
    if isinstance(x, bool) or not math.isfinite(x) or abs(x) > 2000000:
        raise ValueError('invalid coordinate')
    n, d = float(x).as_integer_ratio()
    return (2 * n * SCALE + d) // (2 * d)


def quantize_points(points):
    return sorted(set((_quantize(p[0]), _quantize(p[1])) for p in points))


def _cross(a, b, p):
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def hull(points):
    ps = sorted(set(points))
    if len(ps) < 3:
        return ps
    low, high = [], []
    for p in ps:
        while len(low) >= 2 and _cross(low[-2], low[-1], p) <= 0:
            low.pop()
        low.append(p)
    for p in reversed(ps):
        while len(high) >= 2 and _cross(high[-2], high[-1], p) <= 0:
            high.pop()
        high.append(p)
    return low[:-1] + high[:-1]


def _inside_hull(poly, corners, margin=MARGIN):
    if len(poly) < 3:
        return False
    for a, b in zip(poly, poly[1:] + poly[:1]):
        bound = margin * (abs(b[0] - a[0]) + abs(b[1] - a[1]))
        if any(_cross(a, b, p) < bound for p in corners):
            return False
    return True


def _outside(x, y, h):
    dx, dy = max(0, abs(x) - h), max(0, abs(y) - h)
    return dx * dx + dy * dy > DOMAIN2


def _support(mode, points, x, y, h):
    near = [p for p in points if (abs(p[0] - x) + h) ** 2 + (abs(p[1] - y) + h) ** 2 <= RADIUS ** 2]
    if mode == 3:
        return near[:1]
    corners = [(x - h, y - h), (x - h, y + h), (x + h, y - h), (x + h, y + h)]
    poly = hull(near)
    return poly if _inside_hull(poly, corners) else []


def _counterexample(mode, points, x, y):
    # Counterexamples are diagnostic unless the failure has a strict robust
    # margin to all radius / half-plane boundaries. Return only robust ones.
    if x * x + y * y > DOMAIN2:
        return None
    if mode == 3:
        if all((p[0] - x) ** 2 + (p[1] - y) ** 2 > (1000 * SCALE + 2) ** 2 for p in points):
            return {'point': [x / SCALE, y / SCALE]}
        return None
    near = [p for p in points if (p[0] - x) ** 2 + (p[1] - y) ** 2 <= (1000 * SCALE + 2) ** 2]
    if not near:
        return {'point': [x / SCALE, y / SCALE], 'direction': [1, 0]}
    # Find an emission normal pointing strictly away from every nearby station.
    vectors = [(p[0] - x, p[1] - y) for p in near]
    for a, b in zip(hull(near), hull(near)[1:] + hull(near)[:1]):
        nx, ny = b[1] - a[1], a[0] - b[0]
        if nx == ny == 0:
            continue
        if all(nx * vx + ny * vy < -2 * (abs(nx) + abs(ny)) for vx, vy in vectors):
            return {'point': [x / SCALE, y / SCALE], 'direction': [nx, ny]}
    for vx, vy in vectors:
        nx, ny = -vx, -vy
        if all(nx * u + ny * v < -2 * (abs(nx) + abs(ny)) for u, v in vectors):
            return {'point': [x / SCALE, y / SCALE], 'direction': [nx, ny]}
    return None


def certify_points(mode, coordinates, max_depth=18, max_nodes=60000, deadline=None, keep_leaves=False):
    if mode not in (3, 4):
        raise ValueError('mode must be 3 or 4')
    started = time.perf_counter()
    points = quantize_points(coordinates)
    stack = [(0, 0, EXTENT, 0)]
    count = 0
    leaves = []
    supports = set()
    max_used_depth = 0
    while stack:
        x, y, h, depth = stack.pop()
        count += 1
        if count > max_nodes or (deadline is not None and count % 32 == 0 and time.perf_counter() > deadline):
            return {'status': 'unknown', 'reason': 'computation_limit', 'nodes': count, 'seconds': time.perf_counter() - started}
        if _outside(x, y, h):
            if keep_leaves:
                leaves.append([x, y, h, []])
            continue
        support = _support(mode, points, x, y, h)
        if support:
            max_used_depth = max(max_used_depth, depth)
            supports.update(support)
            if keep_leaves:
                leaves.append([x, y, h, [list(p) for p in support]])
            continue
        counterexample = _counterexample(mode, points, x, y)
        if counterexample is not None:
            return {'status': 'counterexample', 'witness': counterexample, 'nodes': count, 'seconds': time.perf_counter() - started}
        if depth >= max_depth or h < 2:
            return {'status': 'unknown', 'reason': 'boundary_or_degenerate', 'cell': [x, y, h], 'nodes': count, 'seconds': time.perf_counter() - started}
        half = h // 2
        stack.extend((x + dx * half, y + dy * half, half, depth + 1) for dx, dy in ((-1, -1), (-1, 1), (1, -1), (1, 1)))
    result = {'status': 'certified', 'method': 'integer_square_cover' if mode == 3 else 'integer_near_hull_cover', 'mode': mode, 'quantized_points_hash': canonical_hash(points), 'nodes': count, 'max_depth': max_used_depth, 'support_points': [list(p) for p in sorted(supports)], 'seconds': time.perf_counter() - started, 'scale': SCALE, 'radial_margin_units': 2, 'hull_margin_units': 2}
    if keep_leaves:
        result['leaves'] = leaves
    return result


def replay_certificate(mode, coordinates, proof):
    """Check retained leaves, supports, and exact dyadic partition independently."""
    if proof.get('status') != 'certified' or proof.get('mode') != mode:
        return False
    points = quantize_points(coordinates)
    if proof.get('quantized_points_hash') != canonical_hash(points):
        return False
    allowed = set(points)
    leaves = proof.get('leaves')
    if not leaves:
        return False
    boxes = {}
    for x, y, h, support in leaves:
        if any(type(v) is not int for v in (x, y, h)) or h < 1 or h & (h - 1):
            return False
        if abs(x) + h > EXTENT or abs(y) + h > EXTENT:
            return False
        key = (x, y, h)
        if key in boxes:
            return False
        boxes[key] = True
        if _outside(x, y, h):
            continue
        ss = [tuple(p) for p in support]
        if not ss or not set(ss).issubset(allowed) or not _support(mode, ss, x, y, h):
            return False
    # Merge sibling squares bottom up. This proves exact partition, disjointness,
    # root coverage and no omitted fringe without trusting summed area alone.
    while boxes != {(0, 0, EXTENT): True}:
        small = min(k[2] for k in boxes)
        if small >= EXTENT:
            return False
        keys = [k for k in boxes if k[2] == small]
        parents = set()
        for x, y, h in keys:
            period = 4 * h
            px = ((x + EXTENT) // period) * period - EXTENT + 2 * h
            py = ((y + EXTENT) // period) * period - EXTENT + 2 * h
            parents.add((px, py, 2 * h))
        for px, py, ph in parents:
            children = [(px + dx * small, py + dy * small, small) for dx, dy in ((-1, -1), (-1, 1), (1, -1), (1, 1))]
            if not all(k in boxes for k in children) or (px, py, ph) in boxes:
                return False
            for k in children:
                del boxes[k]
            boxes[px, py, ph] = True
    return True
