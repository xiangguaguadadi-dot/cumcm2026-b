"""Recompute all metrics from raw v1 rows; never used by Solver."""
import pathlib,json,statistics,hashlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2];P=ROOT/'experiments/A4_directional'

def mode_stats(rows,mode,variant='candidate'):
 z=[r for r in rows if r['mode']==mode and r['variant']==variant];rt=sorted(r['program_runtime_s'] for r in z)
 return dict(cases=len(z),complete=sum(r['complete'] for r in z),normal_exit=sum(r['exit_reason']=='user_exit' for r in z),errors=sum(r['error'] is not None for r in z),cleared_sources=sum(r['cleared_count'] for r in z),total_sources=sum(r['source_count'] for r in z),mean_s_per_source=statistics.mean(r['average_clear_time_s'] for r in z),worst_s_per_source=max(r['average_clear_time_s'] for r in z),max_virtual_s=max(r['total_virtual_time_s'] for r in z),mean_real_s=statistics.mean(rt),p95_real_s=rt[int(.95*(len(rt)-1))],p99_real_s=rt[int(.99*(len(rt)-1))],max_real_s=max(rt),mean_requests=statistics.mean(r['requests'] for r in z),mean_distance_m=statistics.mean(r['distance_m'] for r in z),mean_clear_failures=statistics.mean(r['clear_failures'] for r in z))
rounds=[];best=None;bestrows=None;streak=0
for path in sorted((P/'results').glob('r*_full'),key=lambda p:int(p.name.split('_')[0][1:])):
 n=int(path.name.split('_')[0][1:]);rows=json.loads((path/'case_metrics.json').read_text());summ=json.loads((path/'summary.json').read_text());stats={str(m):mode_stats(rows,m) for m in [3,4]}
 if bestrows is None:bestrows=[dict(r,variant='candidate') for r in rows if r['variant']=='frozen_baseline']
 previous_best=best if best else 0;prior={str(m):mode_stats(bestrows,m) for m in [3,4]}
 valid=all(x['complete']==x['cases'] and not x['errors'] for x in stats.values())
 improved=valid and all(stats[str(m)]['mean_s_per_source']<=prior[str(m)]['mean_s_per_source']+1e-8 for m in [3,4]) and any(stats[str(m)]['mean_s_per_source']<prior[str(m)]['mean_s_per_source']-1e-8 for m in [3,4])
 prev_index={(r['case_id'],r['mode']):r for r in bestrows};paired={}
 for m in [3,4]:
  deltas=[r['average_clear_time_s']-prev_index[(r['case_id'],m)]['average_clear_time_s'] for r in rows if r['mode']==m and r['variant']=='candidate']
  paired[str(m)]=dict(improved=sum(d<-1e-8 for d in deltas),worsened=sum(d>1e-8 for d in deltas),tied=sum(abs(d)<=1e-8 for d in deltas),mean_change=statistics.mean(deltas))
 groups=[]
 for g in summ['groups']:
  m=g['mode'];name=g['group'];pr=statistics.mean(r['average_clear_time_s'] for r in bestrows if r['mode']==m and r['group']==name)
  groups.append(dict(mode=m,group=name,baseline=g.get('baseline_mean_s_per_source'),candidate=g.get('candidate_mean_s_per_source'),previous_best=pr,change_vs_previous_best=g.get('candidate_mean_s_per_source',pr)-pr,reduction_vs_baseline=g.get('reduction_fraction'),complete=g['candidate_complete']))
 if improved:best=n;bestrows=[r for r in rows if r['variant']=='candidate'];streak=0
 elif n>=4:streak+=1
 dev=json.loads((P/f'results/r{n}_development.json').read_text());val=json.loads((P/f'results/r{n}_dev_validation.json').read_text());quick=json.loads((P/f'results/r{n}_quick/case_metrics.json').read_text());cand=P/f'candidates/r{n}_solver.py'
 rounds.append(dict(round=n,candidate_sha256=hashlib.sha256(cand.read_bytes()).hexdigest(),code_commit=subprocess.check_output(['git','log','-1','--format=%H','--',str(cand.relative_to(ROOT))],cwd=ROOT,text=True).strip(),metrics=stats,quick={str(m):mode_stats(quick,m) for m in [3,4]},full_wall_seconds=summ['wall_seconds'],previous_best_round=previous_best,refreshed_best=improved,best_round_after=best,extension_no_improvement_streak=streak,paired_vs_previous_best=paired,groups=groups,development=dict(config_trials=dev['trials'],case_runs=len(dev['rows']),seeds=sorted(set(r['seed'] for r in dev['rows'])),validation_case_runs=len(val['rows']),validation_seeds=sorted(set(r['seed'] for r in val['rows']))),results_path=str(path.relative_to(ROOT))))
result=dict(label='LOCAL-v1 fixed regression; not official, not blind holdout',rounds=rounds,total_rounds=len(rounds),best_round=best,extension_no_improvement_streak=streak,actual_candidate_regression_runs=2520*len(rounds),development_and_validation_runs=sum(r['development']['case_runs']+r['development']['validation_case_runs'] for r in rounds),total_full_wall_seconds=sum(r['full_wall_seconds'] for r in rounds))
(P/'comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='rounds'},ensure_ascii=False))
