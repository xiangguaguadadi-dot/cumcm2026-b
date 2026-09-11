from pathlib import Path
import ast,json,hashlib,datetime
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'experiments/R3_open'
s=(OUT/'snapshots/r3.py').read_text();lines=s.splitlines(keepends=True);tree=ast.parse(s)
sp=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='_sp_Solver')
m=next(x for x in sp.body if isinstance(x,ast.FunctionDef) and x.name=='route_clear_point')
method=''.join(lines[m.lineno-1:m.end_lineno]).replace('_sp_','_di_')
start=s.index('class _di_Solver:');pos=s.index('    def localize(self,ch):',start)
s=s[:pos]+method+'\n\n'+s[pos:]
start=s.index('class _di_Solver:');pos=s.index('                if self.clear(clear_point,ch,certified=radius<=20):',start)
block="                if radius<=20 and self.config.get('route_clear',False):\n                    clear_point=self.route_clear_point(center,radius,clear_point)\n"
s=s[:pos]+block+s[pos:];(OUT/'snapshots/r4_development.py').write_text(s)
p=json.loads((OUT/'optimization_path.json').read_text());assert not any(n['id']=='R3_R4' for n in p['nodes']);node=dict(id='R3_R4',status='registered_before_execution',parents=['R3_R3','A1_space_R8'],hypothesis='Use now-available joint-route successor to select a shorter certified clear location; altered arrivals may change future supplemental observations.',changes=['Transfer A1 route_clear_point into Q4; optimize only inside radius 20-r certified disk, keep old candidate as comparison.'],variants=['R3','route_clear'],train_seeds=[43006000,43006011],development_seeds=[43007000,43007011],candidate_development='experiments/R3_open/snapshots/r4_development.py',sha256=hashlib.sha256(s.encode()).hexdigest(),selection_rule='All complete; lower Q4 development mean than R3, then freeze for full regression; record training ranking',registered_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());p['nodes'].append(node);(OUT/'optimization_path.json').write_text(json.dumps(p,ensure_ascii=False,indent=2))
with (OUT/'optimization_path.md').open('a') as f:f.write('\n## R4实验前\n\n当前R3已给出route_successor，移植A1安全清除圆盘内的entry+exit代理最优化；仅半径<=20生效。父R3与route_clear两臂，新训练43006000–11/开发43007000–11；全部完成且开发更快后冻结。未来补测因落点变化而变，不可由局部代理不增推出完整任务不增。\n')
src=(OUT/'research/develop_r3.py').read_text();left=src.index("VARIANTS=[('R2'");right=src.index('\ndef main():',left);src=src[:left]+"VARIANTS=[('R3',None,{}),('route_clear','visibility',{'route_clear':True})]"+src[right:];src=src.replace("('r3_'+a.split)","('r4_'+a.split)").replace('43004000','43006000').replace('43005000','43007000').replace("'snapshots/r3_development.py';parents={'R2':OUT/'snapshots/r2.py'}","'snapshots/r4_development.py';parents={'R3':OUT/'snapshots/r3.py'}")
(OUT/'research/develop_r4.py').write_text(src);print(node)
