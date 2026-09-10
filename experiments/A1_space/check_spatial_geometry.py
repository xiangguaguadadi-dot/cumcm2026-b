"""Candidate-specific spatial checks, separate from the frozen rule suite."""
import argparse,importlib.util,json,math,random
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--out',required=True);a=p.parse_args()
s=importlib.util.spec_from_file_location('spatial_candidate',a.candidate);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Silent:
 def measure(self,x,y,c):return {'accepted':True,'measure_result':'no_signal','virtual_time_s':0}
checks=[]
def check(name,ok,**extra):checks.append(dict(name=name,passed=bool(ok),**extra))
# Convexity in source radius implies these endpoint bounds suffice continuously.
for rr in (1124.0,1800*math.cos(math.pi/6)):
 values=[math.sqrt(r*r+rr*rr-2*r*rr*math.cos(math.pi/6)) for r in (1000.,1800.)]
 check('continuous_cover_endpoints_'+str(rr),max(values)<1000,distances=values)
x=m.Solver(Silent(),3);before=x.points[:];x.scanned[1].add(2);x.scan_station(0,True)
check('no_relabel_after_nonorigin_scan',x.points==before)
x=m.Solver(Silent(),3);x.scan_station(0,True)
check('silent_origin_can_select_outer_ring',abs(m.dist(x.points[1],(0,0))-1800*math.cos(math.pi/6))<1e-8)
if hasattr(x,'route_clear_point'):
 rng=random.Random(928631);max_excess=-1e9;max_cost_increase=-1e9
 for i in range(1000):
  c=(rng.uniform(-1800,1800),rng.uniform(-1800,1800));r=rng.uniform(0,19.999)
  x.position=(rng.uniform(-2000,2000),rng.uniform(-2000,2000));x.route_successor=(rng.uniform(-2000,2000),rng.uniform(-2000,2000));margin=20-r-1e-6;d=m.dist(x.position,c)
  old=x.position if d<=margin else (c[0]+margin*(x.position[0]-c[0])/d,c[1]+margin*(x.position[1]-c[1])/d)
  q=x.route_clear_point(c,r,old);max_excess=max(max_excess,m.dist(q,c)+r-20)
  cost=lambda t:m.dist(x.position,t)+m.dist(t,x.route_successor)
  max_cost_increase=max(max_cost_increase,cost(q)-cost(old))
 check('1000_feasible_clear_disks',max_excess<0,max_excess_m=max_excess)
 check('1000_forecast_cost_nonincrease',max_cost_increase<=1e-7,max_increase_m=max_cost_increase)
check('env_calls_only_public',all('.env.'+v not in Path(a.candidate).read_text() for v in ('_sources','seed','stats','error')))
out=dict(passed=sum(c['passed'] for c in checks),total=len(checks),checks=checks);Path(a.out).write_text(json.dumps(out,indent=2));print(out)
if not all(c['passed'] for c in checks):raise SystemExit(1)
