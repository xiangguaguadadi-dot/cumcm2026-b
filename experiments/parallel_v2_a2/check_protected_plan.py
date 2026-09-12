"""Safety integration check: each plan clear is protected; nested state restores."""
import importlib.util,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('protected',HERE/'snapshots/finite_r3_guarded.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
checks=0
for initial in (False,True):
 for raises in (False,True):
  s=m.MultiDiskSpatial(None,mode=4,**m.OPTIMIZED_CONFIGS[4]);s._protected_clear_plan=initial;calls=[]
  def clear(p,ch,certified=False):
   assert s._protected_clear_plan is True
   calls.append((p,ch,certified))
   if raises:raise ValueError('injected guarded execution failure')
   return certified
  s.clear=clear
  try:s._execute_protected_plan(7,[(1,2),(3,4),(5,6)])
  except ValueError:assert raises
  assert s._protected_clear_plan==initial
  if not raises:assert [c[2] for c in calls]==[False,False,True]
  checks+=1
out={'nested_initial_states_and_exception_paths':checks,'all_passed':True,'guard':'_protected_clear_plan'}
(HERE/'results/protected_plan_checks.json').write_text(json.dumps(out,indent=2)+'\n');print(out)
