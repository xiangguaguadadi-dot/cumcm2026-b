"""Mechanical R9 component assembly, preserving R7 first and R8 fallback."""
from pathlib import Path

here = Path(__file__).resolve().parent
rotation = (here / 'rotating_cover_component.py').read_text()
adaptive = (here / 'adaptive_cover_component.py').read_text()
helpers = adaptive[adaptive.index('def a1_voronoi_cells'):adaptive.index('class A1AdaptiveCoverSpatial')]
rotation_body = rotation[rotation.index('            for index in sorted'):rotation.index('        return A1ServiceSpatial')]
adaptive_body = adaptive[adaptive.index('            before_path=None'):adaptive.index('        return A1ServiceSpatial')]
prefix = '''"""D3 R9: original R7 certified rotation, then bounded minimax fallback."""
_A1_HYBRID_COVER_PARENT=Solver
'''
body = '''class A1HybridCoverSpatial(A1RotatingCoverSpatial):
    def spatial_next_task(self,todo):
        p=self.position
        eligible=(todo and 0 not in todo and self.virtual_time<180000. and
                  self._a1_last_cover_stop!=p and
                  not any(math.dist(p,self.points[i])<1e-5 for i in range(len(self.points)) if i not in todo))
        if eligible:
            self._a1_last_cover_stop=p
'''
body += rotation_body
body += '            if math.hypot(*p)>=800.:\n'
body += ''.join('    '+line if line.strip() else line for line in adaptive_body.splitlines(True))
body += '''        return A1ServiceSpatial.spatial_next_task(self,todo)

class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        if mode==3:return A1HybridCoverSpatial(env,mode=mode,**merged)
        return _A1_HYBRID_COVER_PARENT(env,mode=mode,**merged)
'''
target = here / 'hybrid_cover_component.py'
assert not target.exists()
target.write_text(prefix + helpers + body)
