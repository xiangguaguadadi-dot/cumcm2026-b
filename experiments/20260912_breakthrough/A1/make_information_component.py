"""Generate D2 R4 from the original route, retaining its distance candidates."""
import argparse
import ast
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('--restricted',action='store_true')
args=parser.parse_args()
HERE=Path(__file__).resolve().parent
tree=ast.parse((HERE/'inspection/C7_0_0.py').read_text())
base=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='_sp_Solver')
method=next(n for n in base.body if isinstance(n,ast.FunctionDef) and n.name=='spatial_next_task')
source=ast.unparse(method)
source=source.replace('_sp_enclosing_circle','_Q3._sp_enclosing_circle').replace('_sp_dist','_Q3._sp_dist')
source=source.replace('def improve(route):','def improve(route, fixed_first=False):')
source=source.replace('for i in range(n - 1):','for i in range(int(fixed_first), n - 1):')
old='    best = min(routes, key=lambda r: (length(r), r))'
new='''    parent_route=min(routes,key=lambda r:(length(r),r))
    for first in sorted(parent_route,key=lambda x:(ds[0][x],x))[:6]:
        routes.append(improve([first]+[x for x in parent_route if x!=first],fixed_first=True))
    information={}
    for route in routes:
        first=route[0]
        if first not in information:
            kind,key=tasks[first-1]
            point=self.points[key] if kind=='station' else self._a1_information_stop(key)
            information[first]=self._a1_information_gain(point,key if kind=='source' else None)
    weight=self.config.get('a1_information_weight',0.5)
    best=min(routes,key=lambda r:(length(r)/5.-weight*information[r[0]],r))
    self.counters['a1_information_route_calls']=self.counters.get('a1_information_route_calls',0)+1
    self.counters['a1_information_changed_first']=self.counters.get('a1_information_changed_first',0)+int(best[0]!=parent_route[0])'''
assert old in source
if args.restricted:
    new=new.replace("    for first in sorted(parent_route,key=lambda x:(ds[0][x],x))[:6]:\n        routes.append(improve([first]+[x for x in parent_route if x!=first],fixed_first=True))\n",'')
source=source.replace(old,new)
prefix='''"""D2 R4: score information gathered at the next real service stop in seconds."""
_A1_INFORMATION_PARENT=Solver
class A1InformationSpatial(A1ServiceSpatial):
    def _a1_information_stop(self,ch):
        center,radius=_Q3._sp_enclosing_circle(self.polygons[ch])
        if radius<=self.config.get('clear_trial_radius',100.) or self._a1_progress.get(ch,0)>=3:
            return center
        if len(self.observations[ch])==1:return self.second_point(ch)
        p,deg=self.observations[ch][-1]
        if math.dist(p,center)<25:
            theta=math.radians(deg)+math.pi/2
            return p[0]+35*math.cos(theta),p[1]+35*math.sin(theta)
        return center

    def _a1_information_gain(self,p,exclude):
        gain=0.
        for ch in range(1,21):
            if ch==exclude or ch in self.cleared or not self.observations[ch]:continue
            if min(math.dist(p,q) for q,_ in self.observations[ch])<60.:continue
            center,radius=_Q3._sp_enclosing_circle(self.polygons[ch])
            if radius<=20 or math.dist(p,center)>1500.+radius:continue
            estimate=self._gate_prediction(ch,p)
            if estimate is not None:gain+=max(0.,estimate[1])
        return gain
'''
suffix='''
class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        if mode==3:return A1InformationSpatial(env,mode=mode,**merged)
        return _A1_INFORMATION_PARENT(env,mode=mode,**merged)
'''
out=HERE/('restricted_information_component.py' if args.restricted else 'information_route_component.py')
assert not out.exists()
out.write_text(prefix+'\n'+'\n'.join('    '+line for line in source.splitlines())+'\n'+suffix)
print(out)
