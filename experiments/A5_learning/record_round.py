"""Record a completed frozen outer round and the current best, without editing evaluation."""
import argparse,hashlib,json,statistics
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1]
p=argparse.ArgumentParser();p.add_argument('--round',type=int,required=True);p.add_argument('--note',required=True);a=p.parse_args();n=a.round
full_path=ROOT/f'results/A5_learning_r{n}_full';quick_path=ROOT/f'results/A5_learning_r{n}_quick'
full=json.loads((full_path/'summary.json').read_text());quick=json.loads((quick_path/'summary.json').read_text());rows=json.loads((full_path/'case_metrics.json').read_text())
metrics={}
for mode in (3,4):
 z=[x for x in rows if x['mode']==mode and x['variant']=='candidate'];b=[x for x in rows if x['mode']==mode and x['variant']=='frozen_baseline']
 metrics[str(mode)]=dict(mean_s_per_source=statistics.mean(x['average_clear_time_s'] for x in z) if all(x['complete'] for x in z) else None,
                       baseline_mean_s_per_source=statistics.mean(x['average_clear_time_s'] for x in b),complete=sum(x['complete'] for x in z),total=len(z),
                       errors=sum(bool(x['error']) for x in z),max_runtime_s=max(x['program_runtime_s'] for x in z))
record=dict(round=n,solver_path=f'experiments/A5_learning/snapshots/r{n}_solver.py',solver_sha256=full['candidate_sha256'],
            full_results_path=str(full_path.relative_to(ROOT)),quick_results_path=str(quick_path.relative_to(ROOT)),
            full_wall_s=full['wall_seconds'],quick_wall_s=quick['wall_seconds'],quick_all_complete=quick['all_complete'],full_all_complete=full['all_complete'],metrics=metrics,
            regressions=[g for g in full['groups'] if g.get('reduction_fraction',0)<0],note=a.note)
best=json.loads((P/'best.json').read_text());improves=full['all_complete'] and all(metrics[k]['mean_s_per_source']<=best['metrics'][k]['mean_s_per_source']+1e-9 for k in metrics) and any(metrics[k]['mean_s_per_source']<best['metrics'][k]['mean_s_per_source']-1e-9 for k in metrics)
record['improves_current_best']=improves
if improves:
 best.update(round=n,solver_path=record['solver_path'],solver_sha256=record['solver_sha256'],full_results_path=record['full_results_path'],metrics=metrics,code_commit=None,status='full验证两题均不退步；等待记录包含代码的Git提交')
best['rounds_completed']=n;record['current_best_round']=best['round'];record['current_best_sha256']=best['solver_sha256']
if not improves:best['status']=f'R{n} full未同时优于当前最佳；最佳保持R{best["round"]}'
(P/'best.json').write_text(json.dumps(best,ensure_ascii=False,indent=2))
rp=P/'round_summaries.json';records=json.loads(rp.read_text()) if rp.exists() else []
if any(x['round']==n for x in records):raise RuntimeError('Round already recorded')
records.append(record);rp.write_text(json.dumps(records,ensure_ascii=False,indent=2))
with (P/'iteration_log.md').open('a') as f:
 f.write(f'\n### R{n} full完成\n\n候选SHA256 `{record["solver_sha256"]}`；2400局完整状态 `{full["all_complete"]}`，评测耗时 {full["wall_seconds"]:.3f}s。\n\n')
 for m,z in metrics.items():f.write(f'- Q{m}：{z["complete"]}/{z["total"]}全清，均值 {z["mean_s_per_source"]} 秒/源，基线 {z["baseline_mean_s_per_source"]}。\n')
 f.write(f'\n判断：{a.note}。当前最佳 R{best["round"]}，SHA256 `{best["solver_sha256"]}`。\n\n结果：`{record["full_results_path"]}`；所有退步场景见 report.md 和 round_summaries.json。\n')
print(json.dumps(record,ensure_ascii=False,indent=2))
