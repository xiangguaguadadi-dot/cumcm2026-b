"""Independent arithmetic and witness audit of the Q2 research artifacts."""
import json
import math
from pathlib import Path

BASE = Path(__file__).resolve().parent
data = json.loads((BASE / "numerical/results.json").read_text())
bounds = json.loads((BASE / "numerical/continuous_bounds.json").read_text())
delta = math.pi / 180
rows = []

def minimum_distance_to_polygon(origin, poly):
    result = float("inf")
    for a, b in zip(poly, poly[1:] + poly[:1]):
        vx, vy = b[0] - a[0], b[1] - a[1]
        length2 = vx * vx + vy * vy
        t = 0 if length2 == 0 else max(0, min(1, ((origin[0]-a[0])*vx + (origin[1]-a[1])*vy)/length2))
        result = min(result, math.dist(origin, (a[0]+t*vx, a[1]+t*vy)))
    return result

for bound in bounds["rows"]:
    r = next(r for r in data["audits"] if r["name"] == bound["name"] and r["narc"] == 128 and not r["outer"])
    q, pair = r["q"], r["pair"]
    z = math.radians(r["bearing_deg"])
    first_errors = [abs(math.atan2(p[1], p[0])) for p in pair]
    second_errors = [abs(math.remainder(math.atan2(p[1]-q[1], p[0]-q[0])-z, 2*math.pi)) for p in pair]
    prior_ranges = [math.hypot(*p) for p in pair]
    second_ranges = [math.dist(q, p) for p in pair]
    safe_margin = min(1e6, 2000*(q[0]*math.cos(delta)-abs(q[1])*math.sin(delta))) - math.hypot(*q)**2
    diameter = math.dist(*pair)
    checks = {
        "safe_region": safe_margin >= -1e-7,
        "first_ranges": all(5 < d <= 1500+1e-8 for d in prior_ranges),
        "second_ranges": all(5 < d <= 1500+1e-8 for d in second_ranges),
        "first_errors": max(first_errors) <= delta+1e-10,
        "second_errors": max(second_errors) <= delta+1e-10,
        "diameter_reproduced": abs(diameter-bound["diameter_lower_witness"]) <= 1e-8,
        "enclosure_not_below_witness": bound["radius_upper_cover"] >= diameter/2,
    }
    assert all(checks.values()), (r["name"], checks)
    rows.append({
        "name": r["name"], "q": q, "checks": checks,
        "witness_pair": pair, "witness_distance_m": diameter,
        "first_ranges_m": prior_ranges, "second_ranges_m": second_ranges,
        "first_bearing_errors_deg": [x/delta for x in first_errors],
        "second_bearing_errors_deg": [x/delta for x in second_errors],
        "posterior_distance_to_first_m": minimum_distance_to_polygon((0,0),r["polygon"]),
        "posterior_distance_to_second_m": minimum_distance_to_polygon(q,r["polygon"]),
    })

old = bounds["rows"][0]
reductions = []
for new in bounds["rows"][1:]:
    reductions.append({
        "name": new["name"],
        "nominal_reduction_percent": 100*(1-new["radius_lower_pair_bound"]/old["radius_lower_pair_bound"]),
        "reduction_interval_percent": [
            100*(1-new["radius_upper_cover"]/old["radius_lower_pair_bound"]),
            100*(1-new["radius_lower_pair_bound"]/old["radius_upper_cover"]),
        ],
        "extra_movement_seconds": (math.hypot(*new["q"])-math.hypot(*old["q"]))/5,
    })

result = {"all_witness_checks_passed": True, "rows": rows, "reductions": reductions,
          "evidence": "Constructed mathematical scenario; ordinary double precision; no official simulator or continuous global point-optimality claim."}
(BASE / "AUDIT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
print(json.dumps({"all_witness_checks_passed": True, "reductions": reductions},ensure_ascii=False,indent=2))
