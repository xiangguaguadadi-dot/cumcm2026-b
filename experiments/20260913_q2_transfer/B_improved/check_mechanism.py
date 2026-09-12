"""Synthetic interface/inclusion checks, no frozen benchmark data."""
from pathlib import Path
import importlib.util,json,math,hashlib,argparse

root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--candidate',default='B1_minimax_costgate.py')
parser.add_argument('--out',default='B1_SYNTHETIC.json')
args=parser.parse_args()
candidate=root/args.candidate
spec=importlib.util.spec_from_file_location('b_candidate',candidate)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
checks=[]
poly=m._G._sp_add_bearing(m._G._sp_initial_polygon(),(0.,0.),0.)
for q in ((450.,60.),(650.,160.),(20.,.1),(409.,532.)):
    upper,lower=m._future_radius_bound(poly,q)
    values=[m._radius(m._wedge(poly,q,-math.pi+2*math.pi*k/1440)) for k in range(1441)]
    checks.append(dict(kind='continuous_upper_vs_dense_reading_grid',point=q,upper=upper,
                       lower=lower,dense_max=max(values),passed=upper+1e-5>=max(values)))
for mode in (3,4):
    s=m.Solver(None,mode=mode)
    s.polygons[1]=poly[:];s.observations[1]=[((0.,0.),0.)]
    before=poly[:]
    q=s.second_point(1)
    checks.append(dict(kind='public_synthetic_second_point',mode=mode,point=q,
                       changed=s.counters.get('b_second_changed',0),
                       passed=s.polygons[1]==before and all(math.isfinite(v) for v in q)))
out=dict(candidate_sha256=hashlib.sha256(candidate.read_bytes()).hexdigest(),checks=checks,
         all_passed=all(c['passed'] for c in checks),benchmark_rows_read=0)
(root/args.out).write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
assert out['all_passed']
