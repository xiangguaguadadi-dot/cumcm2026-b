from pathlib import Path
import ast,json,hashlib
P=Path(__file__).resolve().parents[1];ROOT=P.parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source=(P/'parents/S1_Q4.py').read_text();tree=ast.parse(source)
method=next(m for x in tree.body if isinstance(x,ast.ClassDef) for m in x.body if isinstance(m,ast.FunctionDef)and m.name=='spatial_next_task'and m.lineno>1000)
code='\n'.join(source.splitlines()[method.lineno-1:method.end_lineno])
code=code.replace('        tasks=',"        geom=_P3 if self.mode==3 else _P4\n        circle=geom._sp_enclosing_circle if self.mode==3 else geom._di_enclosing_circle\n        tasks=",1).replace('_di_enclosing_circle','circle').replace('geom.circle','geom._di_enclosing_circle').replace('_di_dist','math.dist')
code=code.replace('        ds=[[math.dist(a,b) for b in positions] for a in positions]', '''        entries=[[b for b in positions]for a in positions]
        old_position=self.position
        try:
            for j,(kind,ch) in enumerate(tasks,1):
                if kind!='source' or len(self.observations[ch])!=1:continue
                center,radius=circle(self.polygons[ch])
                if radius<=self.config.get('clear_trial_radius',100.):continue
                for i,prev in enumerate(positions):
                    if i==j:continue
                    # Predict the unchanged parent's first sensing location
                    # from the preceding block's center-valued exit forecast.
                    self.position=prev
                    entries[i][j]=self.second_point(ch)
        finally:self.position=old_position
        ds=[[math.dist(a,entries[i][j])+math.dist(entries[i][j],b) for j,b in enumerate(positions)]for i,a in enumerate(positions)]''')
code=code.replace('                best=None;delta=0.','''                best=None;delta=0.
                reverse_prefix=[0.]
                for a,b in zip(route,route[1:]):reverse_prefix.append(reverse_prefix[-1]+ds[b][a]-ds[a][b])''',1)
code=code.replace('                        change=ds[before][b]-ds[before][a]','                        change=ds[before][b]-ds[before][a]+reverse_prefix[j]-reverse_prefix[i]',1)
code=code.replace("        self.route_successor=positions[best[1]] if len(best)>1 else None", "        self.route_successor=entries[best[0]][best[1]] if len(best)>1 else None\n        self.counters['service_block_calls']=self.counters.get('service_block_calls',0)+1")
component='# E1 R4: directed entry/service/exit task blocks; predictions only.\nclass ServiceBlockMixin:\n'+code+'\nclass BlockSpatial(ServiceBlockMixin,_P3._LensSpatial):pass\nclass BlockDirectional(ServiceBlockMixin,_P4._LensDirectional):pass\n'
(P/'research/service_block_component.py').write_text(component)
header='"""Self-contained E1 directed service block candidate."""\nimport math,types\n'
for label,path in [('_P3',P/'parents/S1_Q3.py'),('_P4',P/'parents/S1_Q4.py')]:
    header+=f'{label}=types.ModuleType({label!r})\n{label}.__file__=__file__\nexec(compile({path.read_text()!r},__file__+{label!r},"exec"),{label}.__dict__)\n'
footer='''\nOPTIMIZED_CONFIGS={3:dict(_P3.OPTIMIZED_CONFIGS[3]),4:dict(_P4.OPTIMIZED_CONFIGS[4])}
BASELINE_CONFIG=dict(_P3.BASELINE_CONFIG)
class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        return (BlockSpatial if mode==3 else BlockDirectional)(env,mode=mode,**merged)
'''
path=P/'snapshots/r4_blocks.py';path.write_text(header+component+footer)
items=[json.loads((P/'research/r3_candidates.json').read_text())[0],json.loads((P/'research/r1_candidates.json').read_text())[1],dict(name='r4_blocks',file=str(path.relative_to(ROOT)),sha256=sha(path),config={})]
(P/'research/r4_candidates.json').write_text(json.dumps(items,indent=2))
