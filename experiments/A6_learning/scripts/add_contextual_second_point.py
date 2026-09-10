"""Round 3 edit: bounded adaptive second-bearing geometry.

At zero contextual weights the geometry equals its input strategy.
"""
from pathlib import Path
root=Path(__file__).resolve().parents[3];path=root/'solver.py';s=path.read_text()
old="        advance = max(30, length * self.config.get('advance_fraction',0.78))\n        lateral = max(45,min(190,length*self.config.get('lateral_fraction',0.20)))\n"
new="""        # Features are current bearing-set geometry, not latent source range.
        range_feature=max(-.5,min(.5,length/1500.0-.5))
        uncertainty_feature=min(1.0,radius/750.0)-.5
        advance_fraction=max(.20,min(.98,self.config.get('advance_fraction',.60)
            +self.config.get('second_range_weight',0.0)*range_feature
            +self.config.get('second_uncertainty_weight',0.0)*uncertainty_feature))
        advance = max(30, length * advance_fraction)
        lateral = max(45,min(190,length*self.config.get('lateral_fraction',0.15)))
"""
assert old in s;s=s.replace(old,new)
old2='dist(q,self.position) + 0.12*min(dist(q,w) for w in self.points)'
new2="dist(q,self.position) + (0.12+self.config.get('second_route_weight',0.0))*min(dist(q,w) for w in self.points)"
assert old2 in s;s=s.replace(old2,new2)
path.write_text(s)
