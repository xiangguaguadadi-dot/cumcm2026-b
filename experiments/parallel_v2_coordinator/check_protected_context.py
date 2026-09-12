"""Regression diagnostic for coverage-point rewrites; evaluator code only."""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from local_env import InterfaceOnly,LocalEnv,Source


def run(path,case,intervention=False):
    spec=importlib.util.spec_from_file_location('review_candidate',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    env=LocalEnv([Source(**s) for s in case['sources']],case['seed'],case['noise'],keep_log=False)
    solver=module.Solver(InterfaceOnly(env),mode=case['mode'],**module.OPTIMIZED_CONFIGS[case['mode']])
    original_cover,original_clear=solver.cover_polygon,solver.clear
    depth=[0]
    events=[]

    def cover(ch):
        depth[0]+=1
        previous_style=solver.config.get('a3_style')
        if intervention:
            solver.config['a3_style']='off'
            solver._a3_redirect=None
        try:
            return original_cover(ch)
        finally:
            if intervention:
                solver.config['a3_style']=previous_style
                solver._a3_redirect=None
            depth[0]-=1

    def clear(p,ch,certified=False):
        before=len(solver.trace)
        protected=bool(depth[0] or getattr(solver,'_protected_clear_plan',False))
        try:
            return original_clear(p,ch,certified=certified)
        finally:
            actual=[r for r in solver.trace[before:] if r['action']=='clear' and r['channel']==ch]
            if actual:
                first=actual[0]
                events.append(dict(in_cover_polygon=bool(depth[0]),protected_clear_plan=protected,
                                   channel=ch,requested_point=list(p),
                                   executed_point=[first['x'],first['y']],result=first['result'],
                                   moved_by_residual_m=math.dist(p,(first['x'],first['y']))))

    solver.cover_polygon=cover
    solver.clear=clear
    error=None
    try:
        solver.run()
    except Exception as exception:
        error=f'{type(exception).__name__}: {exception}'
    stats=env.stats()
    return dict(case_id=case['case_id'],intervention=intervention,error=error,
                complete=error is None and stats['cleared']==stats['n'] and env.exit_reason=='user_exit',
                cleared=stats['cleared'],sources=stats['n'],total_virtual_time_s=stats['time_s'],
                cover_coordinate_rewrites=[e for e in events if e['protected_clear_plan'] and e['moved_by_residual_m']>1e-7],
                events=events)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--show-intervention',action='store_true')
    args=parser.parse_args()
    assert not args.out.exists()
    case=next(c for c in json.loads((ROOT/'evaluation/cases_v1.json').read_text())
              if c['case_id']=='LOCAL-v1-q4-cell50_shared_field-5030')
    rows=[run(args.candidate,case)]
    if args.show_intervention:
        rows.append(run(args.candidate,case,True))
    else:
        assert rows[0]['complete'] and not rows[0]['cover_coordinate_rewrites'], rows[0]
    args.out.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps([{k:v for k,v in r.items() if k!='events'} for r in rows],ensure_ascii=False))
