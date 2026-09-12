"""Rebuild every candidate in memory and verify immutable snapshots byte for byte."""
from pathlib import Path
import ast,hashlib,json
H=Path(__file__).resolve().parent;ROOT=H.parents[1]
core=(ROOT/'experiments/20260912_breakthrough/A1/snapshots/r2.py').read_text()
assert hashlib.sha256(core.encode()).hexdigest()=='ba99196e9b7b61b5af50ba272f545148ed1bed618407d7711051c63b006cba01'
read=lambda x:(H/x).read_text()
tree=ast.parse(read('build.py'));factory=next(n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value.startswith('\nclass Solver:'))
c=read('component.py');method=read('service_method.txt');d={}
for k in (1,2):d[k]=core+'\n'+c.replace('TRIAL_VARIANT = 1','TRIAL_VARIANT = '+str(k))+'\n'+method+factory
two=read('twodisk_component.py');d[3]=core+'\n'+two
fused=two.replace('class TwoDiskSpatial(A1ServiceSpatial):','class TwoDiskSpatial(TrialSpatial):').replace("fail=[t for t in targets if math.dist(center,t)>20.]\n        base=math.dist(self.position,center)/5.+3.+2.*(1.-len(fail)/len(targets))\n        base+=sum(11.+math.dist(center,t)/5. for t in fail)/len(targets)","trial=self.trial_point(ch,center,radius)\n        fail=[t for t in targets if math.dist(trial,t)>20.]\n        base=math.dist(self.position,trial)/5.+3.+2.*(1.-len(fail)/len(targets))\n        base+=sum(11.+math.dist(trial,t)/5. for t in fail)/len(targets)")
d[4]=d[2]+'\n'+fused;d[5]=d[4]+'\n'+read('three_disk_component.py');d[6]=d[5]+'\n'+read('multidisk_component.py');d[7]=d[6]+'\n'+read('orientation_component.py')
d[8]=core+d[6][len(core):].replace('belief_quadrature(poly,81)','belief_quadrature(poly,243)')+'\n'+read('dp_guard_component.py').replace('class GuardedSpatial(OrientationSpatial):','class GuardedSpatial(MultiDiskSpatial):')
d[9]=core+d[8][len(core):].replace('11.','(10.+float(self.channel!=ch))')
d[10]=d[8]+'\n'+read('radio_rollout_component.py');d[11]=d[8]+'\n'+read('failure_sharing_component.py')
rows=[]
for k,s in d.items():
 p=H/'snapshots'/f'r{k}.py';ok=p.read_text()==s;rows.append(dict(round=f'r{k}',bytes=len(s.encode()),sha256=hashlib.sha256(s.encode()).hexdigest(),exact_rebuild=ok));assert ok,(k,'candidate rebuild mismatch')
(H/'results/rebuild_checks.json').write_text(json.dumps(rows,indent=2));print('All',len(rows),'immutable candidates rebuilt byte for byte')
