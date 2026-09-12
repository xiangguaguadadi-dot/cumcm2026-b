"""Deterministic geometric calculations, independent of simulator/evaluation data."""
import json
import math
from pathlib import Path

D = math.pi / 180
L = 1500.0
R = 1000.0


def geometric_formula(r, alpha, x, y):
    """Original range/intersection-angle form, for numeric algebra cross-check."""
    gx, gy = r * math.cos(alpha), r * math.sin(alpha)
    vx, vy = gx - x, gy - y
    d = math.hypot(vx, vy)
    ca = (math.cos(alpha) * vx + math.sin(alpha) * vy) / d
    sa = abs(math.cos(alpha) * vy - math.sin(alpha) * vx) / d
    if sa < 1e-15:
        return math.inf
    return 2 * D * math.sqrt(r*r + d*d + 2*r*d*abs(ca)) / sa


def endpoints(x, y):
    return max(geometric_formula(L, a, x, y) for a in (-D, D))


def candidate(b):
    phi_unconstrained = math.acos(3 * L * b * math.cos(D) / (2*L*L+b*b))
    phi_max = math.acos(b / (2*R)) - D
    phi = min(phi_unconstrained, phi_max)
    x, y = b * math.cos(phi), b * math.sin(phi)
    return dict(b=b, x=x, y=y, phi_deg=math.degrees(phi),
                Dlin_worst=endpoints(x, y), time_s=b/5+5,
                safety_slack=2*R*(x*math.cos(D)-y*math.sin(D))-b*b)


rows = [candidate(b) for b in (100., 300., 500., math.sqrt(450000), 800., 1000.)]
checks = []
for row in rows:
    b, x, y = row['b'], row['x'], row['y']
    sampled_max = max(geometric_formula(5.01+(L-5.01)*i/300, -D+2*D*j/80, x, y)
                      for i in range(301) for j in range(81))
    phimax = math.acos(b/(2*R))-D
    grid = [(endpoints(b*math.cos(p), b*math.sin(p)), math.degrees(p))
            for p in (D+1e-8+(phimax-D-1e-8)*i/10000 for i in range(10001))]
    grid_best = min(grid)
    checks.append(dict(b=b, sampled_range_angle_max=sampled_max,
                       analytic_endpoint_max=row['Dlin_worst'],
                       grid_best_D=grid_best[0], grid_best_phi_deg=grid_best[1],
                       analytic_D_minus_grid_best=row['Dlin_worst']-grid_best[0]))

old = endpoints(600,300)
d = 41.
numbers = dict(rows=rows, old_default=dict(x=600, y=300, Dlin_worst=old),
               same_budget_linear_reduction_fraction=1-rows[3]['Dlin_worst']/old,
               conservative_three_disk_domain_radial_lower_bound=(L*L-R*R)*math.sin(2*D)/(R+L*math.sin(2*D)),
               max_angular_separation_41m_deg=math.degrees(math.atan(d*R/math.sqrt((L*L-R*R)*((L-d)**2-R*R)))),
               sampled_corroboration=checks,
               evidence='Exact analytic results apply to the explicitly linearized strip model only. Grid checks are numerical corroboration, not exact-wedge validation.')
out = Path(__file__).with_name('geometry_numbers.json')
out.write_text(json.dumps(numbers, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(numbers, ensure_ascii=False, indent=2))
