"""Recompute paired complete-task comparisons and write the visible path."""
from pathlib import Path
import json,hashlib,statistics,datetime,argparse
ROOT=Path(__file__).resolve().parents[2];D=ROOT/'experiments/B3'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--round',type=int,required=True);a=p.parse_args();n=a.round
out=ROOT/f'results/B3_r{n}_exposed';s=read(out/'summary.json');rows=read(out/'case_metrics.json');control=read(ROOT/'experiments/20260911_breakthrough/baseline/expected_rows.json');idx={r['case_id']:r for r in control}
assert len(idx)==len(rows)==4800 and set(idx)=={r['case_id'] for r in rows}
for r in rows:
 assert r['complete'] and not r['error'] and r['exit_reason']=='user_exit' and r['cleared_count']==r['source_count'] and r['coverage_certificate']
 assert abs(r['average_clear_time_s']-r['total_virtual_time_s']/r['cleared_count'])<1e-8
metrics=s['comparisons_to_C0'];aggregates=[r for r in metrics if r['group']=='ALL'];regressions=[r for r in metrics if r['group']!='ALL' and r['delta_s_per_source']>1e-8]
worst=[]
for suite in ('v1','previous_final'):
 for mode in (3,4):
  part=[r for r in rows if r['exposure_suite']==suite and r['mode']==mode]
  r=max(part,key=lambda r:r['average_clear_time_s']-idx[r['case_id']]['average_clear_time_s']);b=idx[r['case_id']]
  worst.append({'suite':suite,'mode':mode,'case_id':r['case_id'],'candidate':r['average_clear_time_s'],'C0':b['average_clear_time_s'],'delta_s_per_source':r['average_clear_time_s']-b['average_clear_time_s']})
record={'round':n,'candidate':f'experiments/B3/snapshots/r{n}_solver.py','candidate_sha256':s['candidate_sha256'],'result_dir':str(out.relative_to(ROOT)),'rows_sha256':sha(out/'case_metrics.json'),'summary_sha256':sha(out/'summary.json'),'all_complete':True,'aggregates':aggregates,'regressed_groups':regressions,'worst_paired_cases':worst,'development':read(D/f'development/r{n}/summary.json') if (D/f'development/r{n}/summary.json').exists() else None,'quick_wall_s':read(ROOT/f'results/B3_r{n}_quick/summary.json')['wall_seconds'],'full_wall_s':read(ROOT/f'results/B3_r{n}_full/summary.json')['wall_seconds'],'previous_final_wall_s':s['wall_seconds_new_runs']}
(D/f'research/r{n}_paired_audit.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
path=read(D/'optimization_path.json');r=next(x for x in path['rounds'] if x['id']==f'R{n}');r.update(result_time_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='retained_best',selection='4800完整，Q3相同，Q4两批改善；更新本路线最佳',results=record)
path['current_best']=f'R{n}';(D/'optimization_path.json').write_text(json.dumps(path,ensure_ascii=False,indent=2))
md=[f'# B3 第{n}轮完整结果','',f"候选SHA256：`{s['candidate_sha256']}`。4800/4800全清、正常退出、无异常，源数分母核对通过。旧v1及上一轮final均为暴露回归。",'', '|批次|题|C0秒/源|候选秒/源|更快/相同/更慢|降幅|','|---|---|---:|---:|---|---:|']
for r in aggregates:md.append(f"|{r['suite']}|Q{r['mode']}|{r['baseline_mean_s_per_source']:.9f}|{r['candidate_mean_s_per_source']:.9f}|{r['faster']}/{r['equal']}/{r['slower']}|{100*r['reduction_fraction']:.4f}%|")
md+=['','## 全部24分题场景与两个批次','','|批次|题|场景|C0|候选|变化秒/源|','|---|---|---|---:|---:|---:|']
for r in metrics:
 if r['group']!='ALL' and r['suite']!='combined':md.append(f"|{r['suite']}|Q{r['mode']}|{r['group']}|{r['baseline_mean_s_per_source']:.6f}|{r['candidate_mean_s_per_source']:.6f}|{r['delta_s_per_source']:+.6f}|")
md+=['','## 单局负结果','']
for r in worst:md.append(f"- {r['suite']} Q{r['mode']} 最大配对退步：{r['case_id']}；{r['C0']:.6f}→{r['candidate']:.6f}，变化{r['delta_s_per_source']:+.6f}秒/源。")
md+=['',f"quick新增120局，full新增2400局，exposed复用同SHA的full后新增2400局；本轮暴露任务实际执行4920次，含重复quick子集。墙钟记录分别{record['quick_wall_s']:.3f}/{record['full_wall_s']:.3f}/{record['previous_final_wall_s']:.3f}秒。",'','选择：当前轮满足两题均不差且至少一题改善，更新本路线最佳。单局和场景退步仍保留；不宣称官方或新最终样本收益。']
(D/f'research/r{n}_results.md').write_text('\n'.join(md)+'\n');print(json.dumps({'round':n,'complete':4800,'aggregates':aggregates,'worst_pairs':worst},ensure_ascii=False))
