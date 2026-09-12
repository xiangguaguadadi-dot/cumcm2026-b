"""Freeze two independent D3 corrections of the retained partial-station rule."""
from pathlib import Path
here=Path(__file__).resolve().parent
source=(here/'partial_station_component.py').read_text()
damped=source.replace('_A1_PARTIAL_STATION_PARENT','_A1_DAMPED_STATION_PARENT').replace('A1PartialStationSpatial','A1DampedStationSpatial')
needle='        self.points=best\n'
replacement='''        midpoint=((old[0]+best[index][0])/2.,(old[1]+best[index][1])/2.)
        proposal=self.points[:];proposal[index]=midpoint
        self.counters['a1_cover_checks']+=1
        check_start=time.perf_counter()
        safe,radius,vertices=a1_cover_certificate(proposal)
        self.counters['a1_cover_cpu_s']=self.counters.get('a1_cover_cpu_s',0.)+time.perf_counter()-check_start
        if not safe:return task
        best=proposal;saved=distance-math.dist(p,best[index])
        self.points=best
'''
assert damped.count(needle)==1
damped=damped.replace(needle,replacement).replace('partial_incoming_leg=True,','partial_incoming_leg=True,retained_shift_fraction=0.5,')
gated=source.replace('_A1_PARTIAL_STATION_PARENT','_A1_DISCOVERY_STAGE_PARENT').replace('A1PartialStationSpatial','A1DiscoveryStageSpatial')
needle='        task=super().spatial_next_task(todo)\n'
replacement='''        task=super().spatial_next_task(todo)
        if any(self.observations[ch] and ch not in self.cleared for ch in range(1,21)):
            return task
'''
assert gated.count(needle)==1
gated=gated.replace(needle,replacement)
for filename,text in [('damped_station_component.py',damped),('discovery_stage_component.py',gated)]:
    target=here/filename
    assert not target.exists()
    target.write_text(text)
