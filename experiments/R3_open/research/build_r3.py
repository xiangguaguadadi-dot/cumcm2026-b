from pathlib import Path
import ast, json, hashlib, datetime
ROOT=Path(__file__).resolve().parents[3]; OUT=ROOT/'experiments/R3_open'
parent=OUT/'snapshots/r2.py';s=parent.read_text();tree=ast.parse(s)
sp=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='_sp_Solver')
method=next(x for x in sp.body if isinstance(x,ast.FunctionDef) and x.name=='spatial_next_task')
lines=s.splitlines(keepends=True); body=''.join(lines[method.lineno-1:method.end_lineno]).replace('_sp_', '_di_')
marker='    def run(self):';start=s.index('class _di_Solver:'); pos=s.index(marker,start)
s=s[:pos]+body+'\n\n'+s[pos:]
start=s.index('class _di_Solver:');pos=s.index("            if self.config.get('joint_scheduling',False):",s.index(marker,start))
block='''            self.route_successor=None
            route_pending=[c for c in range(1,21) if self.observations[c] and c not in self.cleared]
            # Radius gates center reliability for route order only; no source
            # region or station coverage certificate is removed by this gate.
            spatial_ready=(route_pending and all(_di_enclosing_circle(self.polygons[c])[1]
                <=self.config.get('spatial_ready_radius',100.) for c in route_pending))
            if self.config.get('spatial_route',False) and (spatial_ready or not route_pending):
                kind,key=self.spatial_next_task(todo)
                if kind=='source':
                    self.localize(key)
                else:
                    self.scan_station(key,defer=True)
                    visited.append(key);todo.remove(key)
                if self.config.get('upper_bound_stop',True) and len(self.cleared)>=16:
                    break
                continue
'''
s=s[:pos]+block+s[pos:]
(OUT/'snapshots/r3_development.py').write_text(s)
path=json.loads((OUT/'optimization_path.json').read_text());assert not any(n['id']=='R3_R3' for n in path['nodes'])
node=dict(id='R3_R3',status='registered_before_execution',parents=['R3_R2','A1_space_R8'],hypothesis='Joint station/source tour may reduce Q4 detours when belief centers are reliable; unconstrained center routing may regress on long bearing wedges.',changes=['Port unmodified A1 multistart 2-opt and reinsertion task route into Q4; retain 21 stations, localization, opportunity sensing and 16-channel certificate.'],variants=['R2','naive_global','gated100','gated250'],train_seeds=[43004000,43004011],development_seeds=[43005000,43005011],candidate_development='experiments/R3_open/snapshots/r3_development.py',sha256=hashlib.sha256(s.encode()).hexdigest(),selection_rule='All complete; lowest Q4 development mean; preserve training rankings; no best change without full exposed regression',registered_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
path['nodes'].append(node);(OUT/'optimization_path.json').write_text(json.dumps(path,ensure_ascii=False,indent=2))
with (OUT/'optimization_path.md').open('a') as f:f.write('\n## R3 实验前\n\nA1全局空间路线×当前Q4 R2。比较父R2、无半径门槛、100米及250米门槛；新训练43004000–11、开发43005000–11。源中心仅用于排序，不能充当存在/不存在/光学证书。选择规则为全部完成后开发Q4均值最低，保留训练排序；冻结后再做完整回归。\n')
with (OUT/'idea_log.md').open('a') as f:f.write('\nR3采用A1全局空间排序，检验不确定区域中心代理在Q4下的可靠性门控。B3站点与B1补测可能改变原门控收益，不能假设历史A1效果自动迁移。\n')
src=(OUT/'research/develop_r2.py').read_text();src=src.replace("VARIANTS=[('R1',None,{}),('count','visibility',{'sharing_gain_m':30.,'stop_discovered':True}),('count_ready100','visibility',{'sharing_gain_m':30.,'stop_discovered':True,'discovered_ready_radius':100.})]", "VARIANTS=[('R2',None,{}),('naive_global','visibility',{'spatial_route':True,'spatial_ready_radius':1e9}),('gated100','visibility',{'spatial_route':True,'spatial_ready_radius':100.}),('gated250','visibility',{'spatial_route':True,'spatial_ready_radius':250.})]")
src=src.replace("('r2_'+a.split)","('r3_'+a.split)").replace('43002000','43004000').replace('43003000','43005000').replace("'snapshots/r2_development.py';parents={'R1':OUT/'snapshots/r1.py'}","'snapshots/r3_development.py';parents={'R2':OUT/'snapshots/r2.py'}")
(OUT/'research/develop_r3.py').write_text(src)
print(json.dumps(node,ensure_ascii=False))
