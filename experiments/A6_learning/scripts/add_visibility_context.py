"""Extended round architecture: RF observation history features, zero by default."""
from pathlib import Path
root=Path(__file__).resolve().parents[3];path=root/'solver.py';s=path.read_text()
old="""        log_scale=(self.config.get('schedule_uncertainty',0.0)*uncertainty
                   +self.config.get('schedule_density',0.0)*density
                   +self.config.get('schedule_station_gain',0.0)*station_gain)
"""
new="""        # Missing RF is a cost feature only: it never deletes feasible sources
        # or certifies an unscanned channel absent.
        observed=len(self.observations[ch])
        missing=len(self.no_signal_points[ch])
        missing_fraction=missing/max(1,observed+missing)
        repeat_fraction=min(1.0,max(0,observed-1)/2.0)
        workload=len(estimates)/16.0
        log_scale=(self.config.get('schedule_uncertainty',0.0)*uncertainty
                   +self.config.get('schedule_density',0.0)*density
                   +self.config.get('schedule_station_gain',0.0)*station_gain
                   +self.config.get('schedule_missing',0.0)*missing_fraction
                   +self.config.get('schedule_repeat',0.0)*repeat_fraction
                   +self.config.get('schedule_workload',0.0)*workload)
"""
assert old in s;s=s.replace(old,new);path.write_text(s)
