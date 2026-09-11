from pathlib import Path
import argparse,json,datetime,hashlib,statistics
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'experiments/B2'
p=argparse.ArgumentParser();p.add_argument('round',type=int);p.add_argument('--decision',required=True);p.add_argument('--reason',required=True);a=p.parse_args();r=a.round
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
s=json.loads((BASE/f'results/r{r}_exposed/summary.json').read_text());rows=json.loads((BASE/f'results/r{r}_exposed/case_metrics.json').read_text());c0=json.loads((ROOT/'experiments/20260911_breakthrough/baseline/expected_rows.json').read_text());index={x['case_id']:x for x in c0}
allg=[x for x in s['comparisons_to_C0'] if x['group']=='ALL']
regress=[dict(row=x,control=index[x['case_id']],delta=x['average_clear_time_s']-index[x['case_id']]['average_clear_time_s']) for x in rows if x['average_clear_time_s']>index[x['case_id']]['average_clear_time_s']+1e-8];regress.sort(key=lambda x:x['delta'],reverse=True)
(BASE/f'results/r{r}_regressions.json').write_text(json.dumps(regress,ensure_ascii=False,indent=2))
record={'round':r,'candidate':f'snapshots/r{r}.py','sha256':s['candidate_sha256'],'dependencies':json.loads((BASE/'dependencies.json').read_text()),'code_commit':'pending','decision':a.decision,'reason':a.reason,'complete':s['all_complete'],'four_batches':[x for x in allg if x['suite']!='combined'],'combined':[x for x in allg if x['suite']=='combined'],'comparisons_to_previous':s.get('comparisons_to_previous'),'full_path':f'results/r{r}_full','exposed_path':f'results/r{r}_exposed','summary_sha256':sha(BASE/f'results/r{r}_exposed/summary.json'),'rows_sha256':sha(BASE/f'results/r{r}_exposed/case_metrics.json'),'max_regressions':regress[:10]}
registry=BASE/'rounds.json';history=json.loads(registry.read_text()) if registry.exists() else [];history.append(record);registry.write_text(json.dumps(history,ensure_ascii=False,indent=2))
if a.decision=='accepted':
 (BASE/'best.json').write_text(json.dumps(dict(agent='B2',best_round=r,**record,all_rounds='rounds.json',status='continuing'),ensure_ascii=False,indent=2))
lines=[f'## R{r}：{a.decision}',f'\n{a.reason}\n',f'- 候选：[r{r}.py](snapshots/r{r}.py)，SHA256 `{s["candidate_sha256"]}`。',f'- 全部4800局完整：{s["all_complete"]}；四批次指标如下，均为已暴露回归。','\n|批次|题|C0秒/源|候选秒/源|差值|快/同/慢|','|---|---|---:|---:|---:|---|']
for x in allg:lines.append(f'|{x["suite"]}|Q{x["mode"]}|{x["baseline_mean_s_per_source"]:.9f}|{x["candidate_mean_s_per_source"]:.9f}|{x["delta_s_per_source"]:+.9f}|{x["faster"]}/{x["equal"]}/{x["slower"]}|')
lines+=['\n四个分批/分题的所有场景：','\n|批次|题|场景|C0|候选|差值秒/源|','|---|---|---|---:|---:|---:|']
for x in s['comparisons_to_C0']:
 if x['suite']!='combined' and x['group']!='ALL':lines.append(f'|{x["suite"]}|Q{x["mode"]}|{x["group"]}|{x["baseline_mean_s_per_source"]:.6f}|{x["candidate_mean_s_per_source"]:.6f}|{x["delta_s_per_source"]:+.6f}|')
lines+=['\n全部单局退步保存在[r'+str(r)+'_regressions.json](results/r'+str(r)+'_regressions.json)，原始4800行完整保留；最大退步前五局：']
for z in regress[:5]:lines.append(f'- {z["row"]["case_id"]}：+{z["delta"]:.6f} 秒/源。')
lines+=['\n\n']
with (BASE/'iteration_log.md').open('a') as f:f.write('\n'.join(lines))
o=json.loads((BASE/'optimization_path.json').read_text());o['events'].append(dict(id=f'R{r}_result',time=datetime.datetime.now(datetime.timezone.utc).isoformat(),sha256=s['candidate_sha256'],result=f'results/r{r}_exposed/summary.json',decision=a.decision,reason=a.reason,metrics=allg,regressions=f'results/r{r}_regressions.json',execution_budget={'quick':120,'full':2400,'previous_final_new_runs':2400,'development':f'development/r{r}/summary.json'}));
if a.decision=='accepted':o['best']=f'R{r}'
(BASE/'optimization_path.json').write_text(json.dumps(o,ensure_ascii=False,indent=2))
with (BASE/'optimization_path.md').open('a') as f:f.write(f'\n- **R{r}实验后**：{a.reason} 候选[r{r}](snapshots/r{r}.py)；[完整结果](results/r{r}_exposed/summary.json)、[单局退步](results/r{r}_regressions.json)。决策：{a.decision}。\n')
print(json.dumps({'round':r,'decision':a.decision,'metrics':allg},ensure_ascii=False))
