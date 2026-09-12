"""Mechanically specialize the already-read C7 route to next-service endpoints."""
import ast
from pathlib import Path

HERE=Path(__file__).resolve().parent
tree=ast.parse((HERE/'inspection/C7_0_0.py').read_text())
base=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='_sp_Solver')
method=next(n for n in base.body if isinstance(n,ast.FunctionDef) and n.name=='spatial_next_task')

class Rewrite(ast.NodeTransformer):
    def visit_Subscript(self,node):
        if ast.unparse(node)=='_sp_enclosing_circle(self.polygons[k])[0]':
            return ast.parse('self._a1_route_point(k)',mode='eval').body
        return self.generic_visit(node)
    def visit_Name(self,node):
        if node.id=='_sp_dist':return ast.Attribute(value=ast.Name(id='_Q3',ctx=ast.Load()),attr='_sp_dist',ctx=node.ctx)
        return node

method=Rewrite().visit(method)
ast.fix_missing_locations(method)
prefix='''"""D2 R3: align route proxies with the endpoint of the actual next service round."""
_A1_SERVICE_PARENT=Solver
class A1EntrySpatial(A1ServiceSpatial):
    def _a1_route_point(self,ch):
        center,radius=_Q3._sp_enclosing_circle(self.polygons[ch])
        if radius<=self.config.get('clear_trial_radius',100.) or self._a1_progress.get(ch,0)>=3:
            return center
        if len(self.observations[ch])==1:
            return self.second_point(ch)
        p,deg=self.observations[ch][-1]
        if math.dist(p,center)<25:
            theta=math.radians(deg)+math.pi/2
            return p[0]+35*math.cos(theta),p[1]+35*math.sin(theta)
        return center
'''
suffix='''
class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        if mode==3:return A1EntrySpatial(env,mode=mode,**merged)
        return _A1_SERVICE_PARENT(env,mode=mode,**merged)
'''
out=HERE/'entry_route_component.py'
assert not out.exists()
out.write_text(prefix+'\n'+'\n'.join('    '+line for line in ast.unparse(method).splitlines())+'\n'+suffix)
print(out)
