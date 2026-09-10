"""Summarize paired results without dropping failures or combining Q3/Q4."""
import argparse,json,statistics,hashlib,subprocess
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];ROOT=BASE.parents[1]
p=argparse.ArgumentParser();p.add_argument('--round',type=int,required=True);p.add_argument('--suite',default='full');a=p.parse_args()
out=ROOT/'results'/f'A6_learning_r{a.round}_{a.suite}'
s=json.loads((out/'summary.json').read_text());rows=json.loads((out/'case_metrics.json').read_text())
summary={}
for mode in [3,4]:
 z=[r for r in rows if r['mode']==mode and r['variant']=='candidate']
 b=[r for r in rows if r['mode']==mode and r['variant']=='frozen_baseline']
 summary[mode]=dict(complete=sum(r['complete'] for r in z),cases=len(z),mean_s=statistics.mean(r['average_clear_time_s'] for r in z),baseline_mean_s=statistics.mean(r['average_clear_time_s'] for r in b),errors=[r for r in z if not r['complete']],max_runtime_s=max(r['program_runtime_s'] for r in z),mean_runtime_s=statistics.mean(r['program_runtime_s'] for r in z),worst_s=max(r['average_clear_time_s'] for r in z))
regressions=[g for g in s['groups'] if g.get('reduction_fraction',0)<0]
record=dict(round=a.round,suite=a.suite,candidate_sha256=s['candidate_sha256'],all_complete=s['all_complete'],wall_seconds=s['wall_seconds'],modes=summary,regressions_vs_baseline=regressions,result_path=str(out.relative_to(ROOT)),groups=s['groups'])
path=BASE/f'r{a.round}_{a.suite}_aggregate.json';path.write_text(json.dumps(record,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in record.items() if k not in ('groups','regressions_vs_baseline')},ensure_ascii=False,indent=2))
