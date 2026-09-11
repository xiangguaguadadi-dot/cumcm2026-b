"""Deterministic regression for planning cache state; not an environment run."""
from pathlib import Path
import importlib.util,json
OUT=Path(__file__).resolve().parents[1]
p=OUT/'snapshots/r5_development.py';s=importlib.util.spec_from_file_location('cache_check',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
x=object.__new__(m._GraphSpatial)
x.polygons={1:[(1190.,-5.),(1210.,-5.),(1210.,5.),(1190.,5.)]}
x.observations={1:[((0.,0.),0.)]};x.no_signal_points={1:[]};x.failed_clear_points={1:[]}
x.planning_hypotheses=lambda ch:[(1200.,0.),(1195.,1.)]
a=x._belief_plan(1);x.observations[1].append(((-100.,0.),0.));b=x._belief_plan(1)
assert a[1][0][0]==1200. and b[1][0][0]==1300. and a!=b
(OUT/'results/r5_cache_check.json').write_text(json.dumps(dict(passed=True,same_polygon=True,old_positive_radius_lower=a[1][0][0],new_positive_radius_lower=b[1][0][0],expected_change=100,source='deterministic planning-state probe; no source-search episode or new random seed'),indent=2))
print('Positive-observation cache invalidation verified')
