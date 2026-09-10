import json,statistics,hashlib,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[2];exp=root/'experiments/A3_coordination';r=int(sys.argv[1]);directory=root/f'results/A3_coordination_r{r}_full'
s=json.loads((directory/'summary.json').read_text());rows=json.loads((directory/'case_metrics.json').read_text())
metric={str(m):dict(mean_s_per_source=statistics.mean(x['average_clear_time_s'] for x in rows if x['mode']==m and x['variant']=='candidate'),full_clear_count=sum(x['complete'] for x in rows if x['mode']==m and x['variant']=='candidate'),cases=1200,baseline_mean_s_per_source=statistics.mean(x['average_clear_time_s'] for x in rows if x['mode']==m and x['variant']=='frozen_baseline')) for m in (3,4)}
for z in metric.values():z['reduction_fraction']=1-z['mean_s_per_source']/z['baseline_mean_s_per_source']
regress=[dict(mode=g['mode'],group=g['group'],baseline=g.get('baseline_mean_s_per_source'),candidate=g.get('candidate_mean_s_per_source'),reduction=g.get('reduction_fraction')) for g in s['groups'] if g.get('reduction_fraction',0)<0]
summary=dict(round=r,sha256=s['candidate_sha256'],all_complete=s['all_complete'],metrics=metric,regressions=regress,full_path=str(directory.relative_to(root)),full_wall_seconds=s['wall_seconds'])
(exp/f'r{r}_analysis.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
