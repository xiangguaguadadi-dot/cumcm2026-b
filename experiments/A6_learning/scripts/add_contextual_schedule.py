"""Round 2 architecture edit; zero feature weights recover baseline scheduling."""
from pathlib import Path
root=Path(__file__).resolve().parents[3];path=root/'solver.py'
s=path.read_text()
marker='    def run(self):\n'
method='''    def learned_source_cost(self,ch,estimates,index):
        """Only public observation-derived geometry; no source truth or labels.

        Exponential scaling stays positive.  At zero feature weights this is
        exactly the original distance times source_priority score.
        """
        center,radius=estimates[ch]
        distance=dist(self.position,center)
        uncertainty=min(1.0,radius/750.0)
        others=[c for c in estimates if c!=ch]
        density=(sum(math.exp(-dist(center,estimates[c][0])/400.0) for c in others)
                 /max(1,len(others)))
        station_gain=0.0
        if index is not None:
            station=self.points[index]
            station_gain=max(-1.0,min(1.0,(dist(center,station)-dist(self.position,station))/1800.0))
        log_scale=(self.config.get('schedule_uncertainty',0.0)*uncertainty
                   +self.config.get('schedule_density',0.0)*density
                   +self.config.get('schedule_station_gain',0.0)*station_gain)
        return distance*self.config.get('source_priority',1.0)*math.exp(max(-4.0,min(4.0,log_scale)))

'''
assert marker in s;s=s.replace(marker,method+marker)
old='''                    ch=min(pending,key=lambda c:dist(self.position,enclosing_circle(self.polygons[c])[0]))
                    target=enclosing_circle(self.polygons[ch])[0]
                    source_cost=dist(self.position,target)*self.config.get('source_priority',1.0)
'''
new='''                    estimates={c:enclosing_circle(self.polygons[c]) for c in pending}
                    ch=min(pending,key=lambda c:self.learned_source_cost(c,estimates,index))
                    source_cost=self.learned_source_cost(ch,estimates,index)
'''
assert old in s;s=s.replace(old,new)
path.write_text(s)
