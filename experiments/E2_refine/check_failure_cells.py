from pathlib import Path
import importlib.util,json,types
P=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('e2_cell_candidate',P/'snapshots/r3_failure_cells.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
f=m.FailureDirectional._e2_cell_excluded
s=types.SimpleNamespace(config={'e2_failure_cells':True},_e2_failed_clear={1:[]},counters={})
square=[(-12.5,-12.5),(12.5,-12.5),(12.5,12.5),(-12.5,12.5)];origin=(0.,0.);u=(1.,0.);v=(0.,1.)
checks=[]
for name,shape,failed,expected in [('no_failed_disk',square,[],False),('whole_cell_inside',square,[(0.,0.)],True),('center_inside_far_corner_outside',square,[(10.,0.)],False),('boundary_not_strictly_excluded',[(20.,0.)],[(0.,0.)],False),('strict_margin_inside',[(19.999998,0.)],[(0.,0.)],True)]:
 s._e2_failed_clear[1]=failed;got=f(s,shape,origin,u,v,1);assert got==expected,(name,got);checks.append(dict(name=name,expected=expected,actual=got,passed=True))
(P/'results/r3_cell_certificate_checks.json').write_text(json.dumps(dict(purpose='Targeted geometric safety cases, no environment strategy episodes',checks=checks),indent=2)+'\n')
print(len(checks),'passed')
