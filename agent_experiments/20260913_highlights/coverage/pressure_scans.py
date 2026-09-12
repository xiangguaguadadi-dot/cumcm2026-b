"""Actual-interface discovery diagnostics, never ranked as complete-task speed."""
import json
import math
from common import HERE, ROOT, dump, sha, load_module, frozen_check, points21, points22


def main():
    out = HERE/'scan_pressure_v1'
    out.mkdir(exist_ok=False)
    frozen = frozen_check()
    envmod = load_module(ROOT/'local_env.py', 'coverage_scan_physics')
    layouts = dict(fixed21=points21(), fixed22=points22(),
                   distance_only_21=[(0.,0.)]+[(1558.8457268119896*math.cos(2*math.pi*k/20),1558.8457268119896*math.sin(2*math.pi*k/20)) for k in range(20)],
                   delete_outer_9=points21()[:9])
    cases=[]
    for aidx in range(24):
        angle=2*math.pi*aidx/24
        for radius in (1800.,1799.999,1750.):
            for offset in (0., math.pi/2-1e-6, math.pi/2, math.pi/2+1e-6, math.pi):
                target=dict(channel=1,x=radius*math.cos(angle),y=radius*math.sin(angle),radius=1000.,direction=angle+offset)
                sources=[target]+[dict(channel=k+2,x=200*math.cos(2*math.pi*k/9),y=200*math.sin(2*math.pi*k/9),radius=1000.,direction=None) for k in range(9)]
                cases.append(dict(case_id=f'CONSTRUCTED-discovery-{len(cases):04d}',mode=4,seed=91370000+len(cases),noise='positive',
                                  target_radius=radius,polar_angle=angle,direction_offset=offset,sources=sources))
    dump(out/'cases.json',cases)
    dump(out/'registration.json',dict(source=frozen,script_sha256=sha(__file__),cases_sha256=sha(out/'cases.json'),
                                      layouts=layouts,worlds=len(cases),scan_executions=len(cases)*len(layouts),
                                      role='constructed source-existence scan fixture; all worlds legal mixed 10-source Q4 but only target channel scanned; no full-task speed claim'))
    rows=[]
    with (out/'rows.jsonl').open('w') as stream:
        for case in cases:
            for name,points in layouts.items():
                env=envmod.LocalEnv([envmod.Source(**s) for s in case['sources']],case['seed'],case['noise'],keep_log=False)
                interface=envmod.InterfaceOnly(env)
                interface.enter()
                observations=[interface.measure(x,y,1)['measure_result'] for x,y in points]
                interface.exit()
                hits=sum(value!='no_signal' for value in observations)
                row=dict(case_id=case['case_id'],layout=name,target_radius=case['target_radius'],polar_angle=case['polar_angle'],
                         direction_offset=case['direction_offset'],source_count=10,target_exists=True,received=hits>0,
                         positive_sites=hits,measurements=len(points),requests=len(points)+2,
                         false_absence_if_layout_assumed_complete=hits==0,measure_results=observations,
                         allowed_for_task_speed_ranking=False)
                stream.write(json.dumps(row,separators=(',',':'))+'\n');rows.append(row)
    grouped={name:dict(fixtures=len(cases),detected=sum(r['received'] for r in rows if r['layout']==name),
                       missed=sum(not r['received'] for r in rows if r['layout']==name),
                       total_requests=sum(r['requests'] for r in rows if r['layout']==name),
                       outward_missed=sum(not r['received'] and r['direction_offset']==0 for r in rows if r['layout']==name)) for name in layouts}
    assert grouped['fixed21']['missed']==grouped['fixed22']['missed']==0
    assert grouped['distance_only_21']['outward_missed']>0 and grouped['delete_outer_9']['outward_missed']>0
    summary=dict(status='pass',label='Constructed scan diagnostics, NOT complete policy tasks or official results',
                 distinct_worlds=len(cases),scan_executions=len(rows),full_policy_executions=0,
                 world_source_count=sum(len(c['sources']) for c in cases),unique_target_sources=len(cases),
                 total_requests=sum(r['requests'] for r in rows),groups=grouped,source_after=frozen_check(),
                 rows_sha256=sha(out/'rows.jsonl'),cases_sha256=sha(out/'cases.json'))
    dump(out/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':main()
