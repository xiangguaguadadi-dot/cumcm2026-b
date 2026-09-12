"""Independent binary64-as-rational coverage verification.

The witness generator for the new 22-point artifact may be reused. No generator
or prior verifier is used to decide whether either certificate passes here.
"""
import argparse
import json
import math
import time
from common import HERE, ROOT, PARENT, CERT, NoActions, dump, sha, load_module, frozen_check, points21, points22


def integer_hull(points):
    points = sorted(set(points))
    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lower, upper = [], []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1]+upper[:-1]


def verify(data, path, leaf_path):
    start = time.perf_counter()
    assert data['certified'] and not data['failed']
    ratios = [[float(v).as_integer_ratio() for v in p] for p in data['points']]
    denominator = max(d for p in ratios for _, d in p)
    assert denominator & (denominator-1) == 0
    assert all(denominator % d == 0 for p in ratios for _, d in p)
    points = [tuple(n*(denominator//d) for n, d in p) for p in ratios]
    assert len(points) == len(set(points))
    leaves = data['leaves']
    keys = {(d, i, j) for d, i, j, _ in leaves}
    assert len(keys) == len(leaves) == data['leaf_count']
    maximum_depth = max(d for d, i, j in keys)
    area_numerator = sum(4**(maximum_depth-d) for d, i, j in keys)
    assert area_numerator == 4**maximum_depth
    for d, i, j in keys:
        assert 0 <= i < 2**d and 0 <= j < 2**d
        for k in range(d):
            assert (k, i//2**(d-k), j//2**(d-k)) not in keys
    covered = outside = 0
    min_range_slack = min_hull_slack = math.inf
    with leaf_path.open('w') as out:
        for d, i, j, kind in leaves:
            scale = 2**d
            unit = denominator*scale
            x = (-1800*scale+3600*i)*denominator
            y = (-1800*scale+3600*j)*denominator
            width = 3600*denominator
            corners = [(x, y), (x+width, y), (x+width, y+width), (x, y+width)]
            if kind == 'outside':
                nx = x if x > 0 else x+width if x+width < 0 else 0
                ny = y if y > 0 else y+width if y+width < 0 else 0
                assert nx*nx+ny*ny > (1800*unit)**2
                outside += 1
                row = dict(depth=d, ix=i, iy=j, kind='outside', exact_pass=True)
            else:
                assert isinstance(kind, list) and len(set(kind)) == len(kind) >= 3
                assert all(type(k) is int and 0 <= k < len(points) for k in kind)
                witnesses = [(points[k][0]*scale, points[k][1]*scale) for k in kind]
                hull = integer_hull(witnesses)
                assert len(hull) >= 3
                max_d2 = max((p[0]-q[0])**2+(p[1]-q[1])**2 for p in witnesses for q in corners)
                assert max_d2 < (1000*unit)**2
                range_slack = 1000-math.sqrt(max_d2)/unit
                min_range_slack = min(min_range_slack, range_slack)
                local_hull_slack = math.inf
                for a, b in zip(hull, hull[1:]+hull[:1]):
                    dx, dy = b[0]-a[0], b[1]-a[1]
                    cross = min(dx*(q[1]-a[1])-dy*(q[0]-a[0]) for q in corners)
                    assert cross >= 0
                    local_hull_slack = min(local_hull_slack, cross/math.hypot(dx, dy)/unit)
                min_hull_slack = min(min_hull_slack, local_hull_slack)
                covered += 1
                row = dict(depth=d, ix=i, iy=j, kind='covered', exact_pass=True,
                           witness_indices=kind, range_slack_m_approx=range_slack,
                           hull_slack_m_approx=local_hull_slack)
            out.write(json.dumps(row, separators=(',', ':'))+'\n')
    return dict(status='pass', certificate=str(path.relative_to(ROOT)), certificate_sha256=sha(path),
                station_count=len(points), leaf_count=len(leaves), covered_leaves=covered, outside_leaves=outside,
                maximum_depth=maximum_depth, coordinate_basis='actual IEEE-754 float.as_integer_ratio',
                common_denominator=denominator, exact_integer_checks=True,
                partition_prefix_free=True, partition_full_area=True, rebuilt_witness_convex_hulls=True,
                min_range_slack_m_approx=min_range_slack, min_hull_slack_m_approx=min_hull_slack,
                leaf_checks_sha256=sha(leaf_path), wall_s=time.perf_counter()-start,
                guarantee='Every point of the 1800 m disk lies in the convex hull of sites <1000 m away; every closed emission half-plane contains one such site.',
                boundary='Certifies these fixed binary64 site coordinates under the physical model. Does not certify runtime, official interface, or arbitrary rotated floating points.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='certificate_checks_v1')
    args = parser.parse_args()
    out = HERE/args.out
    out.mkdir(exist_ok=False)
    frozen = frozen_check()
    parent = load_module(PARENT, 'coverage_certificate_parent')
    actual = parent.Solver(NoActions(), mode=4)
    assert actual.points == points21() and not actual.trace
    data21 = json.loads(CERT.read_text())
    first = verify(data21, CERT, out/'21_leaf_checks.jsonl')
    first['current_b3_initial_coordinates_exactly_equal'] = True
    first['construction_environment_actions'] = 0
    dump(out/'21_result.json', first)
    print(json.dumps(dict(stage='21_verified', **{k:first[k] for k in ('station_count','leaf_count','covered_leaves','outside_leaves','common_denominator')})), flush=True)
    # Generation supplies a witness, not acceptance. The same independent integer checker accepts it below.
    generator_path = ROOT/'experiments/B3/research/certify_geometry.py'
    generator = load_module(generator_path, 'coverage_witness_generator_only')
    data22 = generator.certify([list(p) for p in points22()], maxdepth=17)
    path22 = out/'22_certificate.json'
    dump(path22, data22)
    assert data22['certified'] and not data22['failed']
    second = verify(data22, path22, out/'22_leaf_checks.jsonl')
    second['witness_generator_sha256'] = sha(generator_path)
    second['generator_did_not_decide_acceptance'] = True
    r = 999.5
    second['ideal_22_point_triangulation'] = dict(triangles=28, max_edge_m=r,
                                                outer_inradius_m=2*r*math.cos(math.pi/7),
                                                note='Explanation of old construction; acceptance above independently certifies actual binary64 sites.')
    dump(out/'22_result.json', second)
    frozen_after = frozen_check()
    dump(out/'summary.json', dict(status='pass', source_before=frozen, source_after=frozen_after,
                                  verifier_sha256=sha(__file__), certificates={'fixed21':first,'fixed22':second},
                                  environment_policy_worlds_executed=0))
    print(json.dumps(dict(stage='complete', fixed21_leaves=first['leaf_count'], fixed22_leaves=second['leaf_count'])), flush=True)


if __name__ == '__main__':
    main()
