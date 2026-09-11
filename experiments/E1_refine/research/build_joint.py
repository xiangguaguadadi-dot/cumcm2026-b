from pathlib import Path
import ast,json,hashlib
P=Path(__file__).resolve().parents[1];ROOT=P.parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source=(P/'parents/S1_Q4.py').read_text(); tree=ast.parse(source)
cls=next(x for x in tree.body if isinstance(x,ast.ClassDef)and any(isinstance(m,ast.FunctionDef)and m.name=='spatial_next_task' and m.lineno>1000 for m in x.body))
method=next(m for m in cls.body if isinstance(m,ast.FunctionDef)and m.name=='spatial_next_task')
code='\n'.join(source.splitlines()[method.lineno-1:method.end_lineno])
code=code.replace('        tasks=',"        if self.config.get('joint_clear_style','off')=='off':return super().spatial_next_task(todo)\n        self._joint_clear_target=None\n        geom=_P3 if self.mode==3 else _P4\n        circle=geom._sp_enclosing_circle if self.mode==3 else geom._di_enclosing_circle\n        tasks=",1).replace('_di_enclosing_circle','circle').replace('geom.circle','geom._di_enclosing_circle').replace('_di_dist','math.dist')
code=code.replace("        self.route_successor=positions[best[1]] if len(best)>1 else None\n        return tasks[best[0]-1]",'''        certified={x:tasks[x-1][1] for x in best if tasks[x-1][0]=='source'
                   and 0<len(self.polygons[tasks[x-1][1]])<=32
                   and circle(self.polygons[tasks[x-1][1]])[1]<20.-1e-6}
        self.counters['joint_route_calls']=self.counters.get('joint_route_calls',0)+1
        self.counters['joint_certified_regions']=self.counters.get('joint_certified_regions',0)+len(certified)
        def refine(route):
            points={x:positions[x] for x in route}
            if not certified:return points,length(route)
            def cost():return math.dist(self.position,points[route[0]])+sum(math.dist(points[a],points[b])for a,b in zip(route,route[1:]))
            before=cost()
            for sweep in range(3):
                prior=cost()
                order=range(len(route)) if sweep%2==0 else range(len(route)-1,-1,-1)
                for i in order:
                    x=route[i]
                    if x not in certified:continue
                    prev=self.position if i==0 else points[route[i-1]]
                    nxt=points[route[i+1]] if i+1<len(route) else None
                    poly=self.polygons[certified[x]]
                    q=geom._lens_route_point(poly,prev,nxt,points[x])
                    if all(math.dist(q,v)<=20.-1e-8 for v in poly):points[x]=q
                if prior-cost()<1e-5:break
            after=cost()
            assert after<=before+1e-6
            return points,after
        points,score=refine(best)
        if self.config.get('joint_clear_style')=='reorder':
            options=[(score,best,points)]
            for route in routes:
                if route==best:continue
                q,value=refine(route);options.append((value,route,q))
            score,best,points=min(options,key=lambda z:(z[0],z[1]))
        self.counters['joint_proxy_saved_m']=self.counters.get('joint_proxy_saved_m',0.)+length(best)-score
        self.route_successor=points[best[1]] if len(best)>1 else None
        if best[0] in certified:self._joint_clear_target=(certified[best[0]],points[best[0]])
        return tasks[best[0]-1]''')
component='''# E1 R3: coordinate descent of all certified clear regions on a full open tour.
class JointMixin:
'''+code+'''
    def route_clear_point(self,center,radius,original):
        fallback=super().route_clear_point(center,radius,original)
        item=getattr(self,'_joint_clear_target',None)
        if item is None or item[0]!=self._active_target or radius>20:return fallback
        q=item[1];poly=self.polygons[self._active_target]
        if not poly or any(math.dist(q,v)>20.-1e-8 for v in poly):return fallback
        target=getattr(self,'route_successor',None)
        cost=lambda p:math.dist(self.position,p)+(math.dist(p,target)if target is not None else 0.)
        return min((fallback,q),key=lambda p:(cost(p),p))

class JointSpatial(JointMixin,_P3._LensSpatial):pass
class JointDirectional(JointMixin,_P4._LensDirectional):pass
'''
(P/'research/joint_component.py').write_text(component)
def build(name,style):
    header='"""Self-contained E1 joint clear route candidate."""\nimport math,types\n'
    for label,path in [('_P3',P/'parents/S1_Q3.py'),('_P4',P/'parents/S1_Q4.py')]:
        header+=f'{label}=types.ModuleType({label!r})\n{label}.__file__=__file__\nexec(compile({path.read_text()!r},__file__+{label!r},"exec"),{label}.__dict__)\n'
    footer=f'''\nOPTIMIZED_CONFIGS={{3:dict(_P3.OPTIMIZED_CONFIGS[3],joint_clear_style={style!r}),4:dict(_P4.OPTIMIZED_CONFIGS[4],joint_clear_style={style!r})}}
BASELINE_CONFIG=dict(_P3.BASELINE_CONFIG)
class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={{**OPTIMIZED_CONFIGS[mode],**config}}
        return (JointSpatial if mode==3 else JointDirectional)(env,mode=mode,**merged)
'''
    path=P/'snapshots'/f'{name}.py';path.write_text(header+component+footer)
    return dict(name=name,file=str(path.relative_to(ROOT)),sha256=sha(path),config=dict(joint_clear_style=style))
items=[build('r3_parent','off'),build('r3_fixed','fixed'),build('r3_reorder','reorder')]
(P/'research/r3_candidates.json').write_text(json.dumps(items,indent=2))
