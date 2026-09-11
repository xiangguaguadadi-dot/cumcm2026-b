from pathlib import Path
import json,sys,importlib.util,time
P=Path(__file__).resolve().parents[1];ROOT=P.parents[1];sys.path.insert(0,str(ROOT))
from local_env import Source,LocalEnv,InterfaceOnly
path=P/'snapshots/r3_fixed.py';spec=importlib.util.spec_from_file_location('joint',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
cases=json.loads((P/'development/r3_joint/cases.json').read_text());chosen=[c for c in cases if c['seed']==44000036]
rows=[];started=time.perf_counter()
for c in chosen:
    env=LocalEnv([Source(**s)for s in c['sources']],c['seed'],c['noise'],keep_log=False)
    solver=m.Solver(InterfaceOnly(env),mode=c['mode'],**m.OPTIMIZED_CONFIGS[c['mode']]);result=solver.run()
    rows.append(dict(case_id=c['case_id'],mode=c['mode'],stats=env.stats(),counters=solver.counters))
report=dict(label='24 already-used development cases; repeated instrumentation, not new performance evidence',rows=rows,wall_seconds=time.perf_counter()-started)
(P/'research/joint_diagnostic.json').write_text(json.dumps(report,indent=2))
for mode in (3,4):
    a=[x for x in rows if x['mode']==mode];calls=sum(x['counters'].get('joint_route_calls',0)for x in a);count=sum(x['counters'].get('joint_certified_regions',0)for x in a);saving=sum(x['counters'].get('joint_proxy_saved_m',0)for x in a)
    print(dict(mode=mode,cases=len(a),route_calls=calls,certified_regions=count,regions_per_call=count/calls,proxy_saving_m_per_case=saving/len(a)))
