"""Action-contract fixtures; no world performance or coverage theorem claimed."""
import importlib.util,json,sys
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
name=sys.argv[1] if len(sys.argv)>1 else 'b1_safe'
spec=importlib.util.spec_from_file_location('bias_safety',HERE/'snapshots'/f'{name}.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
records=[]
for protected,depth,actual,near_point,success in [
    (True,0,(10.,12.),None,True),(False,1,(10.,12.),None,True),
    (False,0,(99.,98.),None,True),(True,0,(10.,12.),(10.,12.),True),
    (True,0,(10.,12.),(9.,12.),True),(True,0,(10.,12.),None,False)]:
    s=m.Solver(object(),mode=4);s._protected_clear_plan=protected;s._eb_cover_depth=depth
    calls=[];learned=[];s._eb_learn=lambda *args:learned.append(args)
    s._eb_bias=lambda:None
    if near_point:
        s.trace.append(dict(action='measure',channel=1,result='near',x=near_point[0],y=near_point[1]))
    def parent_clear(self,p,ch,certified=False):
        calls.append(tuple(p))
        self.trace.append(dict(action='clear',channel=ch,result='success' if success else 'fail',x=actual[0],y=actual[1]))
        return success
    with patch.object(m._A3_ORIGINAL_Q4,'clear',parent_clear):
        assert s.clear((10.,12.),1) is success
    assert calls==[(10.,12.)]
    assert learned==([(1,actual,near_point==actual)] if success else [])
    records.append(dict(protected=protected,cover_depth=depth,actual=actual,near_point=near_point,success=success,passed=True))

s=m.Solver(object(),mode=4);events=[]
def parent_cover(self,ch):
    events.append((self._eb_cover_depth,self._eb_redirect))
    assert self._eb_cover_depth==1 and self._eb_redirect is None
    raise ValueError('fixture')
s._eb_redirect=(1,(1.,2.),(3.,4.))
with patch.object(m._A3_ORIGINAL_Q4,'cover_polygon',parent_cover):
    try:s.cover_polygon(1)
    except ValueError:pass
assert s._eb_cover_depth==0 and events==[(1,None)]
records.append(dict(kind='cover_context_restored_on_failure',passed=True))
for protected,expected in [(True,(1.,2.)),(False,(3.,4.))]:
    s=m.Solver(object(),mode=4);s._protected_clear_plan=protected
    s._eb_redirect=(1,(1.,2.),(3.,4.));called=[]
    def parent_measure(self,p,ch):called.append(tuple(p));return 'fixture'
    with patch.object(m._A3_ORIGINAL_Q4,'measure',parent_measure):s.measure((1.,2.),1)
    assert called==[expected] and s._eb_redirect is None
    records.append(dict(kind='measure_redirect',protected=protected,passed=True))
out=HERE/'results'/f'{name}_safety.json';assert not out.exists()
out.write_text(json.dumps(dict(candidate=name,fixtures=records,all_passed=True),indent=2))
print(json.dumps(dict(candidate=name,fixtures=len(records),all_passed=True)))
