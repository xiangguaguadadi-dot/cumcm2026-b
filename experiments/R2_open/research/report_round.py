"""Build complete per-round report from all exposed rows, never success-only."""
from pathlib import Path
import argparse,datetime,hashlib,json,statistics
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'experiments/R2_open'
def read(p):return json.loads(Path(p).read_text())
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--round',type=int,required=True);a=p.parse_args();r=a.round
 directory=OUT/f'results/r{r}_exposed';summary=read(directory/'summary.json');rows=read(directory/'case_metrics.json');base=read(ROOT/'experiments/20260911_stage3/baseline/expected_rows.json');index={x['case_id']:x for x in base}
 assert len(rows)==4800==len({x['case_id'] for x in rows}) and all(x['complete'] and not x['error'] and x['exit_reason']=='user_exit' and x['cleared_count']==x['source_count'] for x in rows)
 fields=['mode','group','cleared_count','source_count','cleared_fraction','average_clear_time_s','total_virtual_time_s','complete','exit_reason','error','coverage_certificate','requests','distance_m','clear_failures']
 q4equal=all(all(x[k]==index[x['case_id']][k] for k in fields) for x in rows if x['mode']==4)
 allreg=[];worst=[]
 for x in rows:
  b=index[x['case_id']];d=x['average_clear_time_s']-b['average_clear_time_s']
  if d>1e-8:allreg.append(dict(case_id=x['case_id'],suite=x['exposure_suite'],mode=x['mode'],group=x['group'],source_count=x['source_count'],delta_s_per_source=d,baseline=b['average_clear_time_s'],candidate=x['average_clear_time_s'],clear_failures=x['clear_failures'],baseline_clear_failures=b['clear_failures']))
 for suite in ('combined','v1','previous_final'):
  for mode in (3,4):
   selected=[x for x in rows if x['mode']==mode and (suite=='combined' or x['exposure_suite']==suite)]
   w=max(selected,key=lambda x:x['average_clear_time_s']);reg=[x for x in allreg if x['mode']==mode and (suite=='combined' or x['suite']==suite)];d=max(reg,key=lambda x:x['delta_s_per_source']) if reg else None
   worst.append(dict(suite=suite,mode=mode,worst_case_id=w['case_id'],worst_s_per_source=w['average_clear_time_s'],max_regression=d))
 save(OUT/f'results/r{r}_case_regressions.json',allreg);save(OUT/f'results/r{r}_worst_cases.json',worst)
 agg=[x for x in summary['comparisons_to_S0'] if x['group']=='ALL'];groups=[x for x in summary['comparisons_to_S0'] if x['group']!='ALL' and x['suite']!='combined']
 text=f'# R{r} 完整暴露回归\n\n4800/4800全清、正常退出、零异常；每题30970/30970源清除。数据均为已暴露研发回归，不是新留出或官方成绩。\n\n'
 text+='|批次|题|S0秒/源|候选秒/源|变化|降幅|快/同/慢|\n|---|---|---:|---:|---:|---:|---|\n'
 for x in agg:text+=f"|{x['suite']}|Q{x['mode']}|{x['baseline_mean_s_per_source']:.9f}|{x['candidate_mean_s_per_source']:.9f}|{x['delta_s_per_source']:+.9f}|{100*x['reduction_fraction']:.6f}%|{x['faster']}/{x['equal']}/{x['slower']}|\n"
 text+='\n## 全部48个分批场景\n\n|批次|题|场景|S0|候选|变化秒/源|快/同/慢|\n|---|---|---|---:|---:|---:|---|\n'
 for x in groups:text+=f"|{x['suite']}|Q{x['mode']}|{x['group']}|{x['baseline_mean_s_per_source']:.6f}|{x['candidate_mean_s_per_source']:.6f}|{x['delta_s_per_source']:+.6f}|{x['faster']}/{x['equal']}/{x['slower']}|\n"
 text+='\n## 最差局和最大退步\n\n|批次|题|最差局秒/源|最大退步秒/源|最大退步案例|\n|---|---|---:|---:|---|\n'
 for x in worst:
  d=x['max_regression'];text+=f"|{x['suite']}|Q{x['mode']}|{x['worst_s_per_source']:.6f}|{d['delta_s_per_source'] if d else 0:.6f}|{d['case_id'] if d else '无'}|\n"
 text+=f'\n所有{len(allreg)}条单局退步完整保存，未选择成功子集。Q4在{len(fields)}个任务字段上逐局与S0完全一致：{q4equal}。现实耗时含当前主机负载，S0缓存现实耗时不作计算加速证据。\n'
 (OUT/f'research/r{r}_results.md').write_text(text)
 best=read(OUT/'best.json');combined=[x for x in agg if x['suite']=='combined'];means={str(x['mode']):x['candidate_mean_s_per_source'] for x in combined}
 accepted=all(means[str(m)]<=best[f'q{m}']+1e-10 for m in (3,4)) and any(means[str(m)]<best[f'q{m}']-1e-10 for m in (3,4))
 audit=dict(round=r,accepted=accepted,rows_sha256=sha(directory/'case_metrics.json'),q4_task_fields_equal_S0=q4equal,q4_task_fields=fields,all_complete=True,comparisons=agg,regressions=len(allreg),regressed_groups=[x for x in groups if x['delta_s_per_source']>1e-8],worst=worst)
 save(OUT/f'results/r{r}_delivery_audit.json',audit)
 if accepted:save(OUT/'best.json',dict(label=f'R2_open R{r}',round=r,candidate=str((OUT/f'snapshots/r{r}_solver.py').resolve()),sha256=summary['candidate_sha256'],q3=means['3'],q4=means['4'],exposed_results=str(directory.resolve()),all_complete=True,deployment_dependencies={},control='S0',code_commit='to be recorded after commit',status='validated exposed best; research continues'))
 print(json.dumps(dict(accepted=accepted,means=means,regressed_groups=audit['regressed_groups'],worst=worst),ensure_ascii=False))
if __name__=='__main__':main()
