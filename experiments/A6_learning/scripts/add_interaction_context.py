"""R8: bounded products of already-public observation features in scheduling."""
from pathlib import Path
R=Path(__file__).resolve().parents[3];p=R/'solver.py';s=p.read_text()
old="                   +self.config.get('schedule_boundary',0.0)*boundary)"
new="""                   +self.config.get('schedule_boundary',0.0)*boundary
                   +self.config.get('schedule_uncertain_missing',0.0)*uncertainty*missing_fraction
                   +self.config.get('schedule_uncertain_repeat',0.0)*uncertainty*repeat_fraction)"""
assert old in s;s=s.replace(old,new);p.write_text(s)
