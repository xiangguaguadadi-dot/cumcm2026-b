"""Build immutable bias variants, protecting clear plans while retaining learning."""
import argparse,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--source',default='bias_component_b1.py')
p.add_argument('--config',default='{}');a=p.parse_args();conf=json.loads(a.config)
s=(HERE/a.source).read_text()
s=s.replace('        self.eb_diagnostics=[]','        self.eb_diagnostics=[]\n        self._eb_cover_depth=0')
begin=s.index('    def clear(self,p,ch,certified=False):')
end=s.index('    def measure(self,p,ch):',begin)
block=s[begin:end]
block=block.replace("        near=bool(self.trace and self.trace[-1].get('action')=='measure' and\n            self.trace[-1].get('result')=='near' and self.trace[-1].get('channel')==ch)\n        bias=self._eb_bias()", "        protected=self._eb_cover_depth or getattr(self,'_protected_clear_plan',False)\n        bias=None if protected else self._eb_bias()")
block=block.replace('        ok=super().clear(p,ch,certified=certified)\n        if ok:self._eb_learn(ch,tuple(p),near)', '''        trace_start=len(self.trace)
        ok=super().clear(p,ch,certified=certified)
        if ok:
            # Learn from the actual public action ledger, including protected
            # coverage clears and a parent implementation that changes p.
            completed=next((i for i in range(len(self.trace)-1,trace_start-1,-1)
                if self.trace[i].get('action')=='clear' and self.trace[i].get('channel')==ch
                and self.trace[i].get('result')=='success'),None)
            if completed is not None:
                action=self.trace[completed];actual=(action['x'],action['y'])
                previous=self.trace[completed-1] if completed else {}
                near=(previous.get('action')=='measure' and previous.get('channel')==ch
                    and previous.get('result')=='near'
                    and math.dist(actual,(previous['x'],previous['y']))<1e-7)
                self._eb_learn(ch,actual,near)''')
cover='''    def cover_polygon(self,ch):
        self._eb_cover_depth+=1
        self._eb_redirect=None
        try:return super().cover_polygon(ch)
        finally:self._eb_cover_depth-=1

'''
s=s[:begin]+cover+block+s[end:]
s=s.replace('        if redirect and redirect[0]==ch', "        if not self._eb_cover_depth and not getattr(self,'_protected_clear_plan',False) and redirect and redirect[0]==ch")
component=HERE/f'bias_component_{a.name}.py';assert not component.exists();component.write_text(s)
helpers=(HERE/'point_component.py').read_text().split('class ObservationResidualDirectional')[0]
source=(HERE/'snapshots/baseline.py').read_text()+'\n'+helpers+'\n'+s+'\nOPTIMIZED_CONFIGS[4].update('+repr(conf)+')\n'
path=HERE/'snapshots'/f'{a.name}.py';assert not path.exists();path.write_text(source)
(HERE/f'{a.name}_registration.json').write_text(json.dumps(dict(name=a.name,config=conf,
    candidate_sha256=hashlib.sha256(source.encode()).hexdigest(),component_sha256=hashlib.sha256(s.encode()).hexdigest(),
    component=component.name,parent_source=a.source,direction='Q4 shared error online calibration',
    safety_change='Protected clear and redirect coordinates retained; success learning retained from actual public clear ledger.',
    evidence='No action-performance equivalence asserted for the earlier b1_guard that dropped protected clear learning.',
    inputs='Public bearings and actual successful clear/near disks only; no exact source truth',
    gate='all-clear quick, development, full and paired exposed 4800 for retained'),indent=2))
print(path)
