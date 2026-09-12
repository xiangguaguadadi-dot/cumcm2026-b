"""R10 adds one geometrically distinct initializer only after R9 fails."""
from pathlib import Path
here = Path(__file__).resolve().parent
hybrid = (here / 'hybrid_cover_component.py').read_text()
adaptive = (here / 'adaptive_cover_component.py').read_text()
body = hybrid[hybrid.index('class A1HybridCoverSpatial'):hybrid.index('        return A1ServiceSpatial')]
body = body.replace('class A1HybridCoverSpatial(A1RotatingCoverSpatial)', 'class A1RotatedMinimaxSpatial(A1HybridCoverSpatial)')
extra = adaptive[adaptive.index('            before_path=None'):adaptive.index('        return A1ServiceSpatial')]
needle = '                proposal=self.points[:];proposal[index]=p\n'
replacement = '''                delta=(math.atan2(p[1],p[0])-math.atan2(old[1],old[0])+math.pi)%(2*math.pi)-math.pi
                if abs(delta)>math.pi/6 or abs(delta)<1e-8:continue
                cc,ss=math.cos(delta),math.sin(delta)
                proposal=self.points[:]
                for j in todo:
                    q=self.points[j]
                    proposal[j]=(cc*q[0]-ss*q[1],ss*q[0]+cc*q[1])
                proposal[index]=p
'''
assert extra.count(needle) == 1
extra = extra.replace(needle, replacement)
extra = extra.replace('points=proposal,minimax_iterations=iterations,', 'points=proposal,minimax_iterations=iterations,pre_rotation=delta,')
extra = extra.replace("self.counters['a1_cover_replacements']=", "self.counters['a1_cover_rotated_minimax']=self.counters.get('a1_cover_rotated_minimax',0)+1\n                self.counters['a1_cover_replacements']=")
body += '            if math.hypot(*p)>=800.:\n' + ''.join('    '+line if line.strip() else line for line in extra.splitlines(True))
body += '''        return A1ServiceSpatial.spatial_next_task(self,todo)

class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        if mode==3:return A1RotatedMinimaxSpatial(env,mode=mode,**merged)
        return _A1_ROTATED_MINIMAX_PARENT(env,mode=mode,**merged)
'''
target = here / 'rotated_minimax_component.py'
assert not target.exists()
target.write_text('"""D3 R10: rotated initialization for constrained minimax fallback."""\n_A1_ROTATED_MINIMAX_PARENT=Solver\n' + body)
