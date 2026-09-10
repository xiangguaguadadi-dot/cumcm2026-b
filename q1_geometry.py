#!/usr/bin/env python3
"""Question 1: directed-bearing intersection, diameter and enclosing circle.

Pure Python standard library; Python 3.9 or newer. No arbitrary bounding box,
range prior, simulator calls, or third-party dependencies are used.

Usage:
    python q1_geometry.py --self-test
    python q1_geometry.py --demo
    python q1_geometry.py observations.json --output result.json

Input JSON example:
    {"delta_deg": 1.0,
     "observations": [
       {"x": 0, "y": 0, "bearing_deg": 359.5},
       {"x": 100, "y": -100, "bearing_deg": 90}
     ]}

Each observation may instead be a three-element list [x, y, bearing_deg].
The default half-width is the theoretical 1 degree. To account conservatively
for a direction rounded to two decimals, the caller may set 1.005001 degrees.

Public API:
    solve_bearings(observations, delta_deg=1.0, abs_tol=1e-8,
                   parallel_tol=1e-12)
    solve_halfplanes([(a, b, c), ...], ...)  # a*x + b*y <= c

Result keys:
    status: "empty", "unbounded", or "bounded";
    vertices: finite vertices, counterclockwise, without repeated endpoint;
    diameter: None for empty, math.inf for unbounded, finite otherwise;
    mec: None unless bounded, else {center: [x,y], radius: r};
    feasible_point: a numerical feasibility witness, or None;
    recession_direction: a nonzero unboundedness witness, or None;
    dimension: 0/1/2 for a bounded point/segment/polygon, otherwise None;
    numerics: tolerances and warnings.

CLI JSON encodes infinite diameter as the string "Infinity" to remain valid
JSON. For an unbounded set, its finite vertices are NOT a closed boundary.

Numerical scope:
    All half-plane normals are normalized, so abs_tol is in meters.
    Floating-point roundoff is added to each feasibility tolerance.
    Direction tests use parallel_tol, which is dimensionless. Pairs with
    |det| <= parallel_tol are treated as parallel. Nearly parallel bearings,
    huge coordinates or separations comparable to tolerance are ill-conditioned:
    inspect numerics.warnings, vary tolerances, or use exact/high-precision
    predicates before treating a numerical classification as an exact proof.

Complexity for H half-planes and V output vertices:
    Pair intersections and feasibility: O(H^3); hull: O(V log V);
    diameter: O(V^2); minimum enclosing circle: O(V^4) worst-case by exhaustive
    supporting-circle enumeration. This intentionally simple, auditable method
    suits the small number of bearings in this problem. Larger inputs can replace
    these parts with half-plane intersection, rotating calipers and randomized
    incremental minimum-circle algorithms respectively.
"""

import argparse
import json
import math
import sys
from itertools import combinations
from pathlib import Path

MACHINE_EPS = sys.float_info.epsilon


def _number(value, name):
    if isinstance(value, bool):
        raise ValueError(name + " must be a finite number, not a boolean")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(name + " must be a finite number") from exc
    if not math.isfinite(result):
        raise ValueError(name + " must be finite")
    return result


def _unit_direction(angle_deg):
    angle = angle_deg % 360.0
    # Preserve exact axis-aligned boundaries, including 0/360 wraparound.
    cardinal = {0.0: (1.0, 0.0), 90.0: (0.0, 1.0),
                180.0: (-1.0, 0.0), 270.0: (0.0, -1.0)}
    if angle in cardinal:
        return cardinal[angle]
    radians = math.radians(angle)
    return math.cos(radians), math.sin(radians)


def bearing_halfplanes(x, y, bearing_deg, delta_deg=1.0):
    """Return the two forward-wedge inequalities in a*x+b*y<=c form."""
    x = _number(x, "x")
    y = _number(y, "y")
    theta = _number(bearing_deg, "bearing_deg") % 360.0
    delta = _number(delta_deg, "delta_deg")
    if not 0.0 < delta < 90.0:
        raise ValueError("delta_deg must satisfy 0 < delta_deg < 90")
    lo = _unit_direction(theta - delta)
    hi = _unit_direction(theta + delta)
    # cross(lo, p-S)>=0, cross(hi, p-S)<=0: directed, not full lines.
    normals = [(lo[1], -lo[0]), (-hi[1], hi[0])]
    return [(a, b, a*x + b*y) for a, b in normals]


def _roundoff_slack(h, p):
    a, b, c = h
    return 16.0 * MACHINE_EPS * (1.0 + abs(a*p[0]) + abs(b*p[1]) + abs(c))


def _feasible(p, halfplanes, abs_tol):
    return all(a*p[0] + b*p[1] <= c + abs_tol + _roundoff_slack((a,b,c), p)
               for a, b, c in halfplanes)


def _deduplicate(points, abs_tol):
    # The small-instance all-pairs check also merges nonadjacent roundoff copies.
    unique = []
    for p in sorted(points):
        if all(math.dist(p, q) > abs_tol for q in unique):
            unique.append(p)
    return unique


def _cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])


def _orientation_tolerance(a, b, c, abs_tol):
    ux, uy = b[0]-a[0], b[1]-a[1]
    vx, vy = c[0]-a[0], c[1]-a[1]
    return (abs_tol * (math.hypot(ux,uy) + math.hypot(vx,vy))
            + 16*MACHINE_EPS*(1 + abs(ux*vy) + abs(uy*vx)))


def convex_hull(points, abs_tol=1e-8):
    """Monotone chain, retaining only endpoints of a numerical line segment."""
    points = _deduplicate(points, abs_tol)
    if len(points) <= 1:
        return points
    lower = []
    for p in points:
        while (len(lower) >= 2 and _cross(lower[-2], lower[-1], p)
               <= _orientation_tolerance(lower[-2], lower[-1], p, abs_tol)):
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(points):
        while (len(upper) >= 2 and _cross(upper[-2], upper[-1], p)
               <= _orientation_tolerance(upper[-2], upper[-1], p, abs_tol)):
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _circle_three(a, b, c, parallel_tol):
    """Circumcircle using translated coordinates to reduce cancellation."""
    ux, uy = b[0]-a[0], b[1]-a[1]
    vx, vy = c[0]-a[0], c[1]-a[1]
    cross = ux*vy - uy*vx
    scale = math.hypot(ux,uy)*math.hypot(vx,vy)
    if scale == 0.0 or abs(cross) <= parallel_tol*scale:
        return None
    u2, v2 = ux*ux+uy*uy, vx*vx+vy*vy
    ox = (u2*vy - uy*v2)/(2*cross)
    oy = (ux*v2 - u2*vx)/(2*cross)
    center = (a[0]+ox, a[1]+oy)
    radius = math.hypot(ox,oy)
    if not all(math.isfinite(v) for v in (*center, radius)):
        return None
    return center, radius


def minimum_enclosing_circle(points, abs_tol=1e-8, parallel_tol=1e-12):
    """Enumerate all one-, two- and three-point supporting circles.

    Vertices suffice because a disk is convex. Returned radius is recomputed
    against every supplied point, so tolerance cannot leave a point just outside
    the returned disk. The radius differs from the mathematical optimum only
    by the numerical predicate/roundoff accuracy described above.
    """
    points = _deduplicate(points, abs_tol)
    if not points:
        return None
    if len(points) == 1:
        return {"center": list(points[0]), "radius": 0.0}
    mean = (sum(p[0] for p in points)/len(points),
            sum(p[1] for p in points)/len(points))
    best_center = mean
    best_radius = max(math.dist(mean, p) for p in points)

    def consider(center, radius):
        nonlocal best_center, best_radius
        if radius > best_radius + abs_tol:
            return
        actual = max(math.dist(center, p) for p in points)
        rounding = 32*MACHINE_EPS*(1 + abs(center[0]) + abs(center[1]) + radius)
        if actual <= radius + abs_tol + rounding and actual < best_radius:
            best_center, best_radius = center, actual

    for p in points:
        consider(p, 0.0)
    for a, b in combinations(points, 2):
        center = ((a[0]+b[0])/2.0, (a[1]+b[1])/2.0)
        consider(center, math.dist(a,b)/2.0)
    for a, b, c in combinations(points, 3):
        circle = _circle_three(a,b,c,parallel_tol)
        if circle is not None:
            consider(*circle)
    return {"center": list(best_center), "radius": best_radius}


def solve_halfplanes(halfplanes, abs_tol=1e-8, parallel_tol=1e-12):
    """Classify a half-plane intersection and compute its finite geometry."""
    abs_tol = _number(abs_tol, "abs_tol")
    parallel_tol = _number(parallel_tol, "parallel_tol")
    if abs_tol <= 0 or not 0 < parallel_tol < 1:
        raise ValueError("require abs_tol > 0 and 0 < parallel_tol < 1")
    hp = []
    impossible_constant = False
    for row in halfplanes:
        if len(row) != 3:
            raise ValueError("each half-plane must contain [a,b,c]")
        a,b,c = (_number(row[i], "half-plane coefficient") for i in range(3))
        norm = math.hypot(a,b)
        if norm == 0:
            if c < -abs_tol:
                impossible_constant = True
            continue
        hp.append((a/norm,b/norm,c/norm))

    numerics = {"abs_tol_m": abs_tol, "parallel_tol": parallel_tol,
                "near_parallel_pairs": 0, "warnings": []}
    base = {"status": "empty", "vertices": [], "diameter": None,
            "diameter_pair": None, "mec": None, "dimension": None,
            "feasible_point": None, "recession_direction": None,
            "numerics": numerics}
    if impossible_constant:
        return base

    # The minimum-norm point of a nonempty closed polyhedron is supported by
    # zero, one or two independent active constraints in the plane.
    candidates = [(0.0,0.0)]
    candidates.extend((a*c,b*c) for a,b,c in hp)
    intersections = []
    for h1,h2 in combinations(hp,2):
        a,b,c = h1
        d,e,f = h2
        det = a*e-b*d
        if abs(det) <= parallel_tol:
            if det != 0.0:
                numerics["near_parallel_pairs"] += 1
            continue
        p = ((c*e-b*f)/det, (a*f-c*d)/det)
        if all(math.isfinite(v) for v in p):
            candidates.append(p)
            if _feasible(p,hp,abs_tol):
                intersections.append(p)
        else:
            numerics["warnings"].append("Overflow while intersecting boundary lines.")
    if numerics["near_parallel_pairs"]:
        numerics["warnings"].append(
            "Some nearly parallel pairs were treated as parallel; classification "
            "may be ill-conditioned. Recheck with higher precision if material.")

    feasible = [p for p in candidates if _feasible(p,hp,abs_tol)]
    if not feasible:
        return base
    witness = min(feasible, key=lambda p: math.hypot(*p))
    base["feasible_point"] = list(witness)
    hull = convex_hull(intersections,abs_tol)
    base["vertices"] = [list(p) for p in hull]

    # A 2-D nontrivial recession cone contains an axis or an extreme boundary
    # ray. Every checked direction has unit length, hence is nonzero.
    directions = [(1.0,0.0),(-1.0,0.0),(0.0,1.0),(0.0,-1.0)]
    for a,b,_ in hp:
        directions.extend([(b,-a),(-b,a)])
    for direction in directions:
        if all(a*direction[0]+b*direction[1] <= parallel_tol for a,b,_ in hp):
            base.update(status="unbounded",diameter=math.inf,
                        recession_direction=list(direction))
            return base

    if not hull:
        raise ArithmeticError("Bounded set has no numerically recoverable vertices; "
                              "decrease tolerances or use high-precision geometry.")
    if len(hull) == 1:
        diameter, pair, dimension = 0.0, [list(hull[0]),list(hull[0])], 0
    else:
        p,q = max(combinations(hull,2),key=lambda pair:math.dist(*pair))
        diameter, pair = math.dist(p,q), [list(p),list(q)]
        dimension = 1 if len(hull) == 2 else 2
    base.update(status="bounded",diameter=diameter,diameter_pair=pair,
                dimension=dimension,
                mec=minimum_enclosing_circle(hull,abs_tol,parallel_tol))
    return base


def solve_bearings(observations, delta_deg=1.0, abs_tol=1e-8,
                   parallel_tol=1e-12):
    """Solve observations encoded as [x,y,angle] or flat dictionaries."""
    delta_deg = _number(delta_deg,"delta_deg")
    if not 0 < delta_deg < 90:
        raise ValueError("delta_deg must satisfy 0 < delta_deg < 90")
    hp = []
    count = 0
    for obs in observations:
        if isinstance(obs,dict):
            try:
                x,y,theta = obs["x"],obs["y"],obs["bearing_deg"]
            except KeyError as exc:
                raise ValueError("observation needs x, y and bearing_deg") from exc
        else:
            if len(obs) != 3:
                raise ValueError("observation needs [x,y,bearing_deg]")
            x,y,theta = obs
        hp.extend(bearing_halfplanes(x,y,theta,delta_deg))
        count += 1
    result = solve_halfplanes(hp,abs_tol,parallel_tol)
    result["observation_count"] = count
    result["delta_deg"] = delta_deg
    return result


def _json_safe(value):
    if isinstance(value,float) and not math.isfinite(value):
        return "Infinity" if value > 0 else "-Infinity"
    if isinstance(value,dict):
        return {k:_json_safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):
        return [_json_safe(v) for v in value]
    return value


def demo_cases():
    root3 = math.sqrt(3)
    return {
        "empty": [[0,0,0],[-1,0,180]],
        "unbounded_one_bearing": [[0,0,10]],
        "unbounded_parallel_bearings": [[0,0,0],[0,1,0]],
        "single_point": [[0,0,0],[0,0,180]],
        "line_segment": [[0,0,1],[10,0,181]],
        "crosses_zero_degrees": [[0,0,359.5],[100,-100,90]],
        "equilateral_counterexample": [
            [-1100,0,1], [590,-550*root3,121], [570,570*root3,241]],
    }


def self_test():
    cases = demo_cases()
    results = {name:solve_bearings(data) for name,data in cases.items()}
    tests = []
    def check(name,condition):
        if not condition:
            raise AssertionError(name)
        tests.append(name)
    check("empty separated forward wedges",results["empty"]["status"]=="empty")
    for name in ["unbounded_one_bearing","unbounded_parallel_bearings"]:
        r=results[name]
        check(name,r["status"]=="unbounded" and math.isinf(r["diameter"]))
        hp=[h for obs in cases[name] for h in bearing_halfplanes(*obs)]
        check(name+" feasibility witness",_feasible(r["feasible_point"],hp,1e-8))
        d=r["recession_direction"]
        check(name+" recession witness",math.hypot(*d)>0.99 and
              all(a*d[0]+b*d[1]<=1e-12 for a,b,_ in hp))
    r=results["single_point"]
    check("bounded point",r["status"]=="bounded" and r["dimension"]==0
          and r["diameter"]==0 and r["mec"]["radius"]==0)
    r=results["line_segment"]
    check("bounded segment",r["status"]=="bounded" and r["dimension"]==1
          and abs(r["diameter"]-10)<1e-7 and abs(r["mec"]["radius"]-5)<1e-7)
    r=results["crosses_zero_degrees"]
    check("angle wraparound bounded polygon",r["status"]=="bounded"
          and r["dimension"]==2 and r["diameter"]>0)
    shifted=solve_bearings([[x,y,angle+720] for x,y,angle in cases["crosses_zero_degrees"]])
    check("angle periodicity",abs(shifted["diameter"]-r["diameter"])<1e-7)
    r=results["equilateral_counterexample"]
    check("triangle diameter",r["status"]=="bounded" and len(r["vertices"])==3
          and abs(r["diameter"]-40)<1e-7)
    check("triangle minimum circle",abs(r["mec"]["radius"]-40/math.sqrt(3))<1e-7
          and math.dist(r["mec"]["center"],[20,20/math.sqrt(3)])<1e-7)
    check("diameter-40 clearing counterexample",r["mec"]["radius"]>20)
    square=solve_halfplanes([(10,0,10),(-2,0,0),(0,30,30),(0,-0.5,0),(0,0,3)])
    check("half-plane normalization",square["status"]=="bounded" and
          abs(square["diameter"]-math.sqrt(2))<1e-7 and
          abs(square["mec"]["radius"]-math.sqrt(0.5))<1e-7)
    check("impossible constant",solve_halfplanes([(0,0,-1)])["status"]=="empty")
    check("no observations means entire plane",solve_bearings([])["status"]=="unbounded")
    halfplane=solve_halfplanes([(1,0,-5)])
    check("one active constraint finds feasible foot",halfplane["status"]=="unbounded"
          and halfplane["feasible_point"][0]<=-5+1e-8)
    strip=solve_halfplanes([(1,0,2),(-1,0,-1)])
    check("unbounded strip without vertices",strip["status"]=="unbounded"
          and strip["vertices"]==[])
    direct_line=solve_halfplanes([(0,1,0),(0,-1,0)])
    check("unbounded equality line",direct_line["status"]=="unbounded")
    near_parallel=solve_halfplanes([(1,0,1),(1,1e-14,1)])
    check("ill-conditioning warning",near_parallel["numerics"]["near_parallel_pairs"]>0)
    for name,r in list(results.items())+[("square",square)]:
        if r["status"]=="bounded":
            check(name+" actual circle coverage",all(math.dist(v,r["mec"]["center"])
                  <=r["mec"]["radius"]+1e-12 for v in r["vertices"]))
    return {"passed":len(tests),"tests":tests,
            "demonstrations": {name:{"status":r["status"],"dimension":r["dimension"],
              "vertex_count":len(r["vertices"]),"diameter":r["diameter"],"mec":r["mec"]}
              for name,r in results.items()}}


def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input",nargs="?",help="input JSON path; '-' reads standard input")
    parser.add_argument("--delta",type=float,default=None,help="bearing half-width in degrees")
    parser.add_argument("--abs-tol",type=float,default=1e-8,help="positional tolerance, meters")
    parser.add_argument("--parallel-tol",type=float,default=1e-12,help="normalized determinant/direction tolerance")
    parser.add_argument("--output",help="write JSON to this file instead of standard output")
    group=parser.add_mutually_exclusive_group()
    group.add_argument("--self-test",action="store_true")
    group.add_argument("--demo",action="store_true")
    args=parser.parse_args()
    if args.self_test:
        result=self_test()
    elif args.demo:
        result={name:solve_bearings(obs) for name,obs in demo_cases().items()}
    elif args.input:
        raw=sys.stdin.read() if args.input=="-" else Path(args.input).read_text(encoding="utf-8")
        data=json.loads(raw)
        if isinstance(data,dict):
            observations=data["observations"]
            default_delta=data.get("delta_deg",1.0)
        else:
            observations=data
            default_delta=1.0
        result=solve_bearings(observations,args.delta if args.delta is not None else default_delta,
                              args.abs_tol,args.parallel_tol)
    else:
        parser.error("provide an input JSON file, --demo or --self-test")
    encoded=json.dumps(_json_safe(result),ensure_ascii=False,indent=2,allow_nan=False)+"\n"
    if args.output:
        Path(args.output).write_text(encoded,encoding="utf-8")
    else:
        print(encoded,end="")


if __name__=="__main__":
    main()
