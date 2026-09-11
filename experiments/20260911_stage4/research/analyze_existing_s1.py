"""Research diagnosis from existing S1 records, zero new policy executions."""
from pathlib import Path
import json,math,statistics
P=Path(__file__).resolve().parent.parent
rows=json.loads((P/'baseline/expected_rows.json').read_text())
cases=json.loads((P/'exposed_cases.json').read_text())
def relaxed_mst(c):
    points=[(0.,0.,0.)]+[(s['x'],s['y'],20.) for s in c['sources']]
    n=len(points);used=[False]*n;best=[float('inf')]*n;best[0]=0.;total=0.
    for _ in points:
        i=min((j for j in range(n) if not used[j]),key=lambda j:best[j]);used[i]=True;total+=best[i]
        x,y,r=points[i]
        for j,(a,b,s) in enumerate(points):
            if not used[j]:best[j]=min(best[j],max(0.,math.hypot(x-a,y-b)-r-s))
    return total/5/len(c['sources'])+5.
floors={c['case_id']:relaxed_mst(c) for c in cases}
result=[]
for mode in (3,4):
    for group in ['ALL']+sorted({r['group'] for r in rows}):
        part=[r for r in rows if r['mode']==mode and (group=='ALL' or r['group']==group)]
        cost=statistics.mean(r['average_clear_time_s'] for r in part);moving=statistics.mean(r['distance_m']/5/r['source_count'] for r in part)
        result.append(dict(mode=mode,group=group,cases=len(part),mean_s_per_source=cost,movement_s_per_source=moving,other_s_per_source=cost-moving,movement_fraction=moving/cost,mean_requests_per_case=statistics.mean(r['requests'] for r in part),mean_failed_clear_per_case=statistics.mean(r['clear_failures'] for r in part),relaxed_omniscient_MST_lower_bound_s_per_source=statistics.mean(floors[r['case_id']] for r in part)))
answer=dict(data_role='Existing 4800 exposed S1 records; no new source-search execution',actual_policy_executions=0,cells=result,lower_bound_meaning='Optimistic physical floor only: a minimum spanning tree of pairwise distances between known 20m service disks, connected to the origin, plus mandatory 5s per successful clear. Ignores discovery, observations, unknown geometry, failed clear, and a single globally consistent service-point choice. MST with independent edgewise disk distances is a relaxation, not an achievable route or promised reduction.',proof='Any actual trajectory from origin visiting every source service disk induces a spanning path through chosen service points. Every path edge is at least max(center distance minus endpoint service radii,0). MST over these edge lower bounds is no longer than that path. Add 5 seconds for every successful clear; unmodeled nonnegative costs may only raise actual time.')
(P/'research/existing_s1_cost_diagnosis.json').write_text(json.dumps(answer,ensure_ascii=False,indent=2)+'\n')
for r in result:
    if r['group']=='ALL':print(json.dumps(r))
