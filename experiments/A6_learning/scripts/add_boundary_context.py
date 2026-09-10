"""Public feasible-center proximity to known arena edge; no scenario labels."""
from pathlib import Path
R=Path(__file__).resolve().parents[3];p=R/'solver.py';s=p.read_text()
old="        workload=len(estimates)/16.0\n        log_scale=("
new="        workload=len(estimates)/16.0\n        boundary=max(0.0,min(1.0,(math.hypot(center[0],center[1])-1350.0)/450.0))\n        log_scale=("
assert old in s;s=s.replace(old,new)
old="                   +self.config.get('schedule_workload',0.0)*workload)"
new="                   +self.config.get('schedule_workload',0.0)*workload\n                   +self.config.get('schedule_boundary',0.0)*boundary)"
assert old in s;s=s.replace(old,new);p.write_text(s)
