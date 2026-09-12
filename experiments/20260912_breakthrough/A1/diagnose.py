"""Recompute legal C7 action costs on the already exposed Q3 quick cases."""
import collections
import importlib.util
import json
import math
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from local_env import LocalEnv, Source, InterfaceOnly
import evaluate

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def main():
    evaluate.verify()
    c7 = load(ROOT / 'experiments/20260911_stage4/combination/geometry_fusions/C7_both.py', 'c7')
    cases = [c for c in json.loads((ROOT/'evaluation/cases_v1.json').read_text()) if c['mode']==3 and c['quick']]
    out = HERE/'diagnostic_q3_quick'
    out.mkdir(exist_ok=False)
    totals=collections.defaultdict(lambda: collections.Counter())
    rows=[]
    with (out/'actions.jsonl').open('w') as stream:
        for case in cases:
            env=LocalEnv([Source(**s) for s in case['sources']],case['seed'],case['noise'],keep_log=True)
            solver=c7.Solver(InterfaceOnly(env),mode=3)
            stack=[]
            actions=[]
            for name in ('scan_station','localize','share_observations','rescue_bearing','cover_polygon'):
                original=getattr(solver,name)
                def wrap(*args,_name=name,_original=original,**kwargs):
                    stack.append(_name)
                    try:return _original(*args,**kwargs)
                    finally:stack.pop()
                setattr(solver,name,wrap)
            for name in ('measure','clear'):
                original=getattr(solver,name)
                def action(p,ch,*args,_name=name,_original=original,**kwargs):
                    before=len(env.log)
                    was_known=bool(solver.observations[ch]) or ch in solver.cleared
                    prev=solver.position
                    t0=solver.virtual_time
                    context=stack[:]
                    answer=_original(p,ch,*args,**kwargs)
                    direct=env.log[before]
                    cost=direct['response']['virtual_time_s']-t0
                    distance=math.dist(prev,p)
                    category=('sharing' if 'share_observations' in context else
                              'station_known' if 'scan_station' in context and was_known else
                              'station_unknown' if 'scan_station' in context else
                              'rescue' if 'rescue_bearing' in context else
                              'cover' if 'cover_polygon' in context else 'localize')
                    rec=dict(case_id=case['case_id'],action=_name,channel=ch,category=category,context=context,
                             cost_s=cost,distance_m=distance,was_known=was_known,request=direct['request'],response=direct['response'])
                    actions.append(rec)
                    totals[category].update(actions=1,cost_s=cost,distance_m=distance,move_s=distance/5.,other_s=cost-distance/5.)
                    return answer
                setattr(solver,name,action)
            result=solver.run()
            assert env.successes==len(case['sources']) and env.exit_reason=='user_exit'
            assert abs(sum(a['cost_s'] for a in actions)-env.virtual_time_s)<1e-5
            for action in actions:stream.write(json.dumps(action)+'\n')
            row=dict(case_id=case['case_id'],mode=3,group=case['group'],sources=len(case['sources']),
                     average_s=env.virtual_time_s/len(case['sources']),total_s=env.virtual_time_s,
                     complete=True,counters=result['counters'])
            rows.append(row)
            print(case['case_id'],round(row['average_s'],3),flush=True)
    summary=dict(cases=len(cases),mean_s_per_source=statistics.mean(r['average_s'] for r in rows),
                 category_totals=dict(totals),rows=rows)
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(dict(totals),indent=2))
    evaluate.verify()

if __name__=='__main__':main()
