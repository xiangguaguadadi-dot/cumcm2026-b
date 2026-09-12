"""Independent exact-rational negative witnesses for proposed Q4 site sets.

This proves only that listed finite layouts fail, never that every layout of the
same cardinality fails. No solver is executed and no source truth is supplied to
any online policy. The enlarged near radius makes the witness conservative.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from fractions import Fraction as F
from pathlib import Path


def point(p):
    return tuple(F(str(x)) for x in p)


def cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def hull(points):
    points = sorted(set(points))
    if len(points) <= 1:
        return points
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


def witness(q, stations):
    if q[0]*q[0]+q[1]*q[1] > F(1800)**2:
        return None
    near = [s for s in stations if sum((x-y)**2 for x,y in zip(s,q)) <= F('1000.0000001')**2]
    poly = hull(near)
    normals = []
    if len(poly) >= 3:
        for a,b in zip(poly, poly[1:]+poly[:1]):
            if cross(a,b,q) < 0:
                normals.append((b[1]-a[1], a[0]-b[0]))
    elif len(poly) == 2:
        a,b = poly
        d = (b[0]-a[0], b[1]-a[1])
        normals.extend([(d[1],-d[0]),(-d[1],d[0]),d,(-d[0],-d[1])])
        for s in poly:
            normals.append((q[0]-s[0],q[1]-s[1]))
    elif poly:
        normals.append((q[0]-poly[0][0], q[1]-poly[0][1]))
    else:
        normals.append((F(1),F(0)))
    for n in normals:
        n2 = n[0]*n[0]+n[1]*n[1]
        if not n2:
            continue
        dots = [sum(n[i]*(s[i]-q[i]) for i in range(2)) for s in near]
        # Strictly behind an emission half-plane, at least 1e-7m projection.
        if all(v < 0 and v*v > F('0.0000001')**2*n2 for v in dots):
            return dict(point_exact=[str(x) for x in q],
                        point_approx=[float(x) for x in q],
                        normal_exact=[str(x) for x in n],
                        near_station_count=len(near),
                        strict_projection_margin_m_approx=(
                            min(-float(v) for v in dots)/math.sqrt(float(n2)) if dots else None),
                        exact_domain_check=True, exact_closed_enlarged_radius_check=True,
                        exact_strict_halfplane_check=True)
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--records', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    assert not a.out.exists(), 'Preserve existing review'
    records = json.loads(a.records.read_text())
    verified, unresolved = [], []
    for index, record in enumerate(records):
        stations = [point(s) for s in record['sites']]
        found = None
        for raw in record.get('failures', []):
            q = point(raw)
            # Also try an explicitly interior point: a boundary trig sample can
            # round outside the domain. The revised point is a new witness.
            for shrink in [F(1), F('0.999999999')]:
                candidate = tuple(x*shrink for x in q)
                found = witness(candidate, stations)
                if found:
                    found['sample_shrink_exact'] = str(shrink)
                    break
            if found:
                break
        if found:
            verified.append(dict(layout_index=index, witness=found))
        else:
            unresolved.append(index)
    report = dict(status='all_listed_layouts_have_exact_counterexamples' if not unresolved else 'unresolved_layouts',
                  layouts=len(records), verified_counterexamples=len(verified), unresolved=unresolved,
                  records_sha256=hashlib.sha256(a.records.read_bytes()).hexdigest(),
                  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  method='Finite decimal station and point coordinates interpreted as exact rationals; closed radius enlarged by 1e-7m; explicit strictly separating emission normal',
                  limitation='Only listed finite layouts; not a lower bound on number of sites, not an algorithm trial or official result',
                  witnesses=verified)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'witnesses'}))


if __name__ == '__main__':
    main()
