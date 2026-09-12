"""Detached public-observation trace audit: first quick case of every mode/group.

Only the evaluator loads scenario data. The strategy receives InterfaceOnly,
and all hooks below read strategy-visible observations, polygons and action logs.
No true source coordinates or antenna types are recorded in the diagnostic.
"""
from pathlib import Path
import argparse,importlib.util,json,math,hashlib,sys,time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
from local_env import LocalEnv,Source,InterfaceOnly
import evaluate

parser=argparse.ArgumentParser()
parser.add_argument('--candidate',required=True)
parser.add_argument('--out',required=True)
args=parser.parse_args()
candidate=HERE/args.candidate
out=HERE/args.out;out.mkdir(parents=True,exist_ok=False)
digest=hashlib.sha256(candidate.read_bytes()).hexdigest()
evaluate.verify()
cases=json.loads((ROOT/'evaluation/cases_v1.json').read_text())
selected={}
for c in cases:
    if c['quick']:selected.setdefault((c['mode'],c['group']),c)
selected=list(selected.values())
(out/'registration.json').write_text(json.dumps(dict(candidate_sha256=digest,
    selection='first case in each of all 24 mode/group cells from the predetermined quick set',
    actual_runs_planned=len(selected),case_ids=[c['case_id'] for c in selected],
    hook_scope='public strategy state only; no decisions changed',data_role='exposed diagnostic reruns'),indent=2)+'\n')
spec=importlib.util.spec_from_file_location('diagnosed_candidate',candidate)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
records=[]
start=time.perf_counter()
for case in selected:
    env=LocalEnv([Source(**x) for x in case['sources']],case['seed'],case['noise'],keep_log=False)
    s=m.Solver(InterfaceOnly(env),mode=case['mode'])
    original=s.second_point;decisions=[]
    def intercepted(ch):
        pos=s.position
        parent=super(m._Lookahead,s).second_point(ch)
        trace_start=len(s.trace)
        chosen=original(ch)
        cache=s._b_cache.get(ch)
        def estimates(q):
            if not cache or tuple(q) not in cache[2]:return None
            future,visibility,radii=cache[2][tuple(q)]
            return dict(full_next_measure_clear_proxy_s=math.dist(pos,q)/5.+5.+future,
                        visibility_proxy=visibility,worst_radius_upper_m=radii[0] if radii else None,
                        worst_radius_lower_m=radii[1] if radii else None)
        decisions.append(dict(channel=ch,trace_index=trace_start,position=pos,
            observation_count=len(s.observations[ch]),parent=parent,chosen=chosen,
            changed=math.dist(parent,chosen)>1e-5,parent_estimates=estimates(parent),chosen_estimates=estimates(chosen)))
        return chosen
    s.second_point=intercepted
    result=s.run();stats=env.stats()
    executed={}
    for d in decisions:
        first=next((i for i in range(d['trace_index'],len(s.trace))
                    if s.trace[i].get('channel')==d['channel']),None)
        if first is None:continue
        a=s.trace[first]
        if a['action']!='measure' or math.dist(d['chosen'],(a['x'],a['y']))>1e-5:continue
        d['executed_trace_index']=first
        if first in executed:continue
        end=next((i for i in range(first+1,len(s.trace)) if s.trace[i]['action']=='clear'
                  and s.trace[i]['channel']==d['channel'] and s.trace[i]['result']=='success'),len(s.trace)-1)
        tail=s.trace[first+1:end+1]
        p=d['chosen'];distance=0.
        for event in tail:
            q=(event['x'],event['y']);distance+=math.dist(p,q);p=q
        executed[first]=dict(channel=d['channel'],changed=d['changed'],second_measure_result=a['result'],
            before=d['parent_estimates'],after=d['chosen_estimates'],
            subsequent_scope='all intervening global actions until this channel clears',
            subsequent_global_movement_m=distance,
            subsequent_channel_measures=sum(x['action']=='measure' and x['channel']==d['channel'] for x in tail),
            subsequent_channel_clears=sum(x['action']=='clear' and x['channel']==d['channel'] for x in tail),
            subsequent_elapsed_virtual_s=s.trace[end]['virtual_time_s']-a['virtual_time_s'])
    record=dict(case_id=case['case_id'],mode=case['mode'],group=case['group'],
        complete=stats['cleared']==stats['n'] and env.exit_reason=='user_exit',
        total_virtual_time_s=stats['time_s'],cleared_count=stats['cleared'],distance_m=stats['distance_m'],
        clear_failures=stats['clear_failures'],second_point_calls=len(decisions),
        changed_calls=sum(d['changed'] for d in decisions),decisions=decisions,
        executed_second_points=list(executed.values()),public_trace=s.trace)
    records.append(record)
    print(case['mode'],case['group'],record['second_point_calls'],record['changed_calls'],flush=True)
evaluate.verify()
assert hashlib.sha256(candidate.read_bytes()).hexdigest()==digest
summary=[]
for mode in (3,4):
    rows=[r for r in records if r['mode']==mode]
    actual=[x for r in rows for x in r['executed_second_points']]
    changed=[x for x in actual if x['changed']]
    summary.append(dict(mode=mode,cases=len(rows),all_complete=all(r['complete'] for r in rows),
        second_point_calls=sum(r['second_point_calls'] for r in rows),changed_calls=sum(r['changed_calls'] for r in rows),
        executed_second_points=len(actual),executed_changed_points=len(changed),
        changed_outcomes={k:sum(x['second_measure_result']==k for x in changed) for k in ('direction','no_signal','near')},
        changed_mean_old_radius_upper=sum(x['before']['worst_radius_upper_m'] for x in changed)/len(changed) if changed else None,
        changed_mean_new_radius_upper=sum(x['after']['worst_radius_upper_m'] for x in changed)/len(changed) if changed else None,
        changed_mean_old_full_cost_proxy=sum(x['before']['full_next_measure_clear_proxy_s'] for x in changed)/len(changed) if changed else None,
        changed_mean_new_full_cost_proxy=sum(x['after']['full_next_measure_clear_proxy_s'] for x in changed)/len(changed) if changed else None,
        all_after_channel_measures=sum(x['subsequent_channel_measures'] for x in actual),
        all_after_channel_clears=sum(x['subsequent_channel_clears'] for x in actual)))
(out/'public_diagnostics.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
(out/'summary.json').write_text(json.dumps(dict(candidate_sha256=digest,actual_runs=len(records),
    wall_seconds=time.perf_counter()-start,summaries=summary),ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
