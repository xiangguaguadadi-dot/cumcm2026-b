"""Independent development set; never imports v1 cases or their generator."""
import argparse,importlib.util,json,pathlib,statistics,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from local_env import LocalEnv,InterfaceOnly,make_case
p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--start',type=int,default=81000);p.add_argument('--seeds',type=int,default=6);p.add_argument('--variants',default='r1');p.add_argument('--candidate',default='solver.py');a=p.parse_args()
variants={
'r1':[('baseline',{'visibility_side':False,'visibility_rescue':False}),('side',{'visibility_side':True,'visibility_rescue':False,'visibility_penalty_m':300}),('rescue',{'visibility_side':False,'visibility_rescue':True}),('both100',{'visibility_penalty_m':100}),('both300',{'visibility_penalty_m':300}),('both600',{'visibility_penalty_m':600})],
'validation':[('selected',{})],
'r2':[('r1',{'optical_switch':False}),('optical50',{'optical_switch':True,'optical_radius':50}),('optical100',{'optical_switch':True,'optical_radius':100}),('optical180',{'optical_switch':True,'optical_radius':180}),('optical300',{'optical_switch':True,'optical_radius':300})],
'r3':[('r2',{'optical_order':'snake'}),('nearest',{'optical_order':'nearest'}),('belief',{'optical_order':'belief'})],
'r4':[('r3',{'visibility_quadrature':'vertices','optical_negative_belief':False}),('failure_only',{'visibility_quadrature':'vertices','optical_negative_belief':True}),('area1',{'visibility_quadrature':'area1','optical_negative_belief':False}),('area1_failure',{'visibility_quadrature':'area1','optical_negative_belief':True}),('area3',{'visibility_quadrature':'area3','optical_negative_belief':False}),('area3_failure',{'visibility_quadrature':'area3','optical_negative_belief':True})],
'r5':[('r3',{'segment_recovery_steps':0}),('half1',{'segment_recovery_steps':1}),('half2',{'segment_recovery_steps':2}),('half3',{'segment_recovery_steps':3}),('quarter2',{'segment_recovery_steps':2,'segment_fraction':.25}),('threequarter2',{'segment_recovery_steps':2,'segment_fraction':.75})],
'r6':[('r5',{'mirror_strategy':'none'}),('always',{'mirror_strategy':'always'}),('expected',{'mirror_strategy':'expected'}),('strict',{'mirror_strategy':'strict'})]
}[a.variants]
spec=importlib.util.spec_from_file_location('candidate',ROOT/a.candidate);s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
rows=[];t=time.perf_counter()
for name,conf in variants:
 for scene in ['random','boundary','cluster','min_radius']:
  for noise in ['uniform','positive','negative']:
   for seed in range(a.start,a.start+a.seeds):
    src=make_case(seed,4,scene)
    if all(x.direction is not None for x in src):src[-1].direction=None
    env=LocalEnv(src,seed,noise,keep_log=False);error=None
    t0=time.perf_counter();solver=s.Solver(InterfaceOnly(env),4,**conf)
    try:r=solver.run()
    except Exception as ex:error=repr(ex)
    st=env.stats();rows.append(dict(variant=name,config=conf,scene=scene,noise=noise,seed=seed,complete=st['cleared']==st['n'] and env.exit_reason=='user_exit' and error is None,average=st['average_s'],distance=st['distance_m'],failures=st['clear_failures'],real_seconds=time.perf_counter()-t0,error=error,counters=solver.counters))
 z=[r for r in rows if r['variant']==name];print(name,len(z),sum(r['complete'] for r in z),statistics.mean(r['average'] for r in z),flush=True)
path=ROOT/a.out
if path.exists():raise RuntimeError('Do not overwrite experiments')
path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(dict(purpose='development; seeds disjoint from v1; observation-only deployment',trials=len(variants),cases_per_trial=12*a.seeds,wall_seconds=time.perf_counter()-t,rows=rows),indent=2))
