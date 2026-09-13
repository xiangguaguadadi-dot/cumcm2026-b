"""Constructed implementation stress for conservative failed-clear disk exclusion."""
import hashlib, importlib.util, json, math, random, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[2] / "最佳方法/代码/solver.py"


def load():
    spec = importlib.util.spec_from_file_location("failed_clear_geometry", SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    dummy = module.Solver(None, mode=3)
    return dummy._exclude_observed_disks.__func__.__globals__["_geo_outside_disk_hull"]


def contains(poly, point, tol=1e-6):
    values = []
    for a, b in zip(poly, poly[1:] + poly[:1]):
        d = math.dist(a, b)
        if d > 1e-9:
            values.append(((b[0]-a[0])*(point[1]-a[1])-(b[1]-a[1])*(point[0]-a[0]))/d)
    return bool(poly) and (not values or all(v >= -tol for v in values) or all(v <= tol for v in values))


def area(poly):
    return abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(poly,poly[1:]+poly[:1])))/2


def main():
    outside = load()
    rng = random.Random(2026091312)
    rows = []
    for index in range(2000):
        sides = 3 + index % 14
        radius = 25 + (index % 17) * 8
        center = (rng.uniform(-200, 200), rng.uniform(-200, 200))
        angles = sorted(rng.uniform(0, 2*math.pi) for _ in range(sides))
        poly = [(center[0] + radius*(.65+.35*rng.random())*math.cos(a),
                 center[1] + radius*(.65+.35*rng.random())*math.sin(a)) for a in angles]
        # Reuse the implementation's hull so the declared prior is convex.
        hull = outside.__globals__["_geo_convex_hull"](poly)
        if len(hull) < 3:
            continue
        # The centroid lies in the convex hull. Pick a failed point >20 m away.
        source = (sum(p[0] for p in hull)/len(hull), sum(p[1] for p in hull)/len(hull))
        bearing = rng.uniform(0, 2*math.pi)
        failed = (source[0] + (20.0001 + rng.random()*80)*math.cos(bearing),
                  source[1] + (20.0001 + rng.random()*80)*math.sin(bearing))
        after = outside(hull, failed, 20.0-1e-6)
        row = {"fixture": index, "vertices_before": len(hull), "vertices_after": len(after),
               "source_distance_m": math.dist(source, failed), "source_inside_before": contains(hull, source),
               "source_inside_after": contains(after, source), "area_before_m2": area(hull),
               "area_after_m2": area(after) if after else 0.0}
        rows.append(row)
    failures = [r for r in rows if not r["source_inside_before"] or not r["source_inside_after"]]
    output = {"status": "pass" if not failures else "fail", "fixtures": len(rows),
              "true_source_exclusions": len(failures),
              "effective_shrinks": sum(r["area_after_m2"] < r["area_before_m2"]-1e-8 for r in rows),
              "minimum_failed_distance_m": min(r["source_distance_m"] for r in rows),
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "boundary": "Constructed numeric implementation stress; the physical validity follows separately from clear failure implying distance >20 m."}
    (HERE/"geometry_stress_rows.jsonl").write_text("".join(json.dumps(r,separators=(",",":"))+"\n" for r in rows))
    (HERE/"geometry_stress_summary.json").write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(output,ensure_ascii=False))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
