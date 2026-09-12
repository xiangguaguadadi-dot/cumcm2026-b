"""Create new frozen guarded candidates; original experiment snapshots stay untouched."""
from pathlib import Path
HERE=Path(__file__).resolve().parent
s=(HERE/'snapshots/finite_r3.py').read_text()
needle='''class FiniteOpticalBase(HexDirectional):
    belief_quadrature=_Q3._DecisionSpatial.belief_quadrature'''
replacement='''class FiniteOpticalBase(HexDirectional):
    def _execute_protected_plan(self,ch,plan):
        previous=getattr(self,'_protected_clear_plan',False)
        self._protected_clear_plan=True
        try:
            for i,q in enumerate(plan):
                if self.clear(q,ch,certified=i==len(plan)-1):return
        finally:
            self._protected_clear_plan=previous
    belief_quadrature=_Q3._DecisionSpatial.belief_quadrature'''
assert s.count(needle)==1;s=s.replace(needle,replacement)
needle='''        (q1, q2) = plan
        if self.clear(q1, ch):
            return
        self.clear(q2, ch, certified=True)'''
assert s.count(needle)==1;s=s.replace(needle,'''        return self._execute_protected_plan(ch,plan)''')
needle='''        for (i, q) in enumerate(plan):
            if self.clear(q, ch, certified=i == len(plan) - 1):
                return'''
assert s.count(needle)==1;s=s.replace(needle,'''        return self._execute_protected_plan(ch,plan)''')
(HERE/'snapshots/finite_r3_guarded.py').write_text(s)
for name,penalty in [('finite_r4',5.),('finite_r5',15.)]:
 needle='''        plans = []''';assert s.count(needle)==3
 v=s.replace(needle,f'''        base += {penalty}*(1.-self.predicted_visibility(ch,center))*len(fail)/len(targets)
        plans = []''')
 (HERE/'snapshots'/f'{name}.py').write_text(v)
v=s.replace('20.0 < radius <= 100.0','20.0 < radius <= 145.0').replace('for count in (4, 5, 6):','for count in (4, 5, 6, 7, 8):')
assert v!=s;(HERE/'snapshots/finite_r6.py').write_text(v)
