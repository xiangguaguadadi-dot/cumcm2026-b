import json,statistics,hashlib,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[2];home=root/'experiments/A2_information'
lines=['# A2 实验迭代日志','', '固定评测：LOCAL-v1；quick 是 full 子集，不是独立留出集。完整成功才比较虚拟时间。原版共同最佳 Q3 306.3004342181635、Q4 570.8833714439976 秒/源。','']
records=[]
best_round=0;fail_count=0
best_values={'3':306.3004342181635,'4':570.8833714439976};best_groups=None
for k in range(1,100):
 p=root/f'results/A2_information_r{k}_full'
 if not (p/'summary.json').exists():continue
 s=json.loads((p/'summary.json').read_text());rows=json.loads((p/'case_metrics.json').read_text());z={}
 for m in [3,4]:
  a=[r for r in rows if r['mode']==m and r['variant']=='candidate'];b=[r for r in rows if r['mode']==m and r['variant']=='frozen_baseline']
  ca=statistics.mean(r['average_clear_time_s'] for r in a);ba=statistics.mean(r['average_clear_time_s'] for r in b)
  z[str(m)]={'mean_s_per_source':ca,'baseline_mean_s_per_source':ba,'reduction_percent':100*(1-ca/ba),'complete':sum(r['complete'] for r in a),'cases':len(a),'errors':sum(bool(r['error']) for r in a),'mean_distance_m':statistics.mean(r['distance_m'] for r in a),'mean_clear_failures':statistics.mean(r['clear_failures'] for r in a)}
 previous_best=best_round
 if best_groups is None:best_groups={(g['mode'],g['group']):g['baseline_mean_s_per_source'] for g in s['groups']}
 group_regressions=[dict(mode=g['mode'],group=g['group'],previous_mean=best_groups[(g['mode'],g['group'])],candidate_mean=g['candidate_mean_s_per_source'],increase_s_per_source=g['candidate_mean_s_per_source']-best_groups[(g['mode'],g['group'])]) for g in s['groups'] if g['candidate_mean_s_per_source']>best_groups[(g['mode'],g['group'])]+1e-10]
 improved=s['all_complete'] and all(z[m]['mean_s_per_source']<=best_values[m]+1e-12 for m in best_values) and any(z[m]['mean_s_per_source']<best_values[m]-1e-12 for m in best_values)
 if improved:
  best_round=k;fail_count=0;best_values={m:z[m]['mean_s_per_source'] for m in z};best_groups={(g['mode'],g['group']):g['candidate_mean_s_per_source'] for g in s['groups']}
 else:fail_count+=1
 best_path=home/f'candidates/r{best_round}_solver.py' if best_round else root/'evaluation/baseline_solver.py'
 code_commit=subprocess.check_output(['git','log','-1','--format=%H','--',f'experiments/A2_information/candidates/r{k}_solver.py'],cwd=root,text=True).strip()
 rec=dict(round=k,sha256=s['candidate_sha256'],code_commit=code_commit,wall_seconds=s['wall_seconds'],metrics=z,all_complete=s['all_complete'],result=str(p.relative_to(root)),previous_best_round=previous_best,strict_best_refreshed=improved,best_round_after=best_round,best_sha256_after=hashlib.sha256(best_path.read_bytes()).hexdigest(),consecutive_not_improved_after=fail_count,regressions_vs_previous_best=group_regressions)
 records.append(rec)
 lines+= [f'## 第 {k} 轮','',f'- 候选：`experiments/A2_information/candidates/r{k}_solver.py`；SHA256 `{s["candidate_sha256"]}`。',f'- full 结果：`{p.relative_to(root)}`；实际运行 {s["wall_seconds"]:.3f} 秒；完整通过：{s["all_complete"]}。',f'- 规则记录：`results/A2_information_r{k}_rules/`；quick：`results/A2_information_r{k}_quick/`。','', '| 题目 | 全清 | 秒/源 | 对基准减少 |','|---|---:|---:|---:|']
 for m,v in z.items():lines.append(f'| Q{m} | {v["complete"]}/{v["cases"]} | {v["mean_s_per_source"]:.8f} | {v["reduction_percent"]:.4f}% |')
 lines+=['','逐场景退步（负减少率；不隐藏）：','']
 for g in s['groups']:
  if g.get('reduction_fraction',0)<0:lines.append(f'- Q{g["mode"]} `{g["group"]}`：增加 {-g["reduction_fraction"]*100:.4f}%。')
 if not any(g.get('reduction_fraction',0)<0 for g in s['groups']):lines.append('- 无；24个题目/场景均值均未比冻结基准退步。')
 lines+=['',f'相对本轮进入时共同最佳（R{previous_best}；R0指冻结基准）的场景退步：','']
 for g in group_regressions:lines.append(f'- Q{g["mode"]} `{g["group"]}`：{g["previous_mean"]:.8f} → {g["candidate_mean"]:.8f} 秒/源，增加 {g["increase_s_per_source"]:.8f}。')
 if not group_regressions:lines.append('- 无。')
 if k==1:lines+=['','第一轮结论：Q3 改善而 Q4 退步，保留为非支配候选，共同最佳仍为原版。没有以合并指标把取舍说成全面改善。第一轮开发检查 `dev/r1_preliminary.json`：各题24局；Q3 337.1310 vs 341.0363，Q4 766.1990 vs 712.8780。仅试一个规划器，没有隐藏参数扫描。']
 if k==2:lines+=['','第二轮结论：Q3持平第一轮，Q4由578.9624下降到574.8171，但仍比基准慢0.6891%。第二轮支配第一轮这个取舍候选；共同最佳仍为原版，非支配集为原版和第二轮。quick的Q4虽略胜基准，full未支持该改善，不能用quick替代full。开发集910100–910109每题60局也保留，未做参数扫描。开发数据中boundary/min_radius的第四问可能全定向，属于比题设混合更强的压力场景，不能冒充官方分布。']
 if k==3:lines+=['','第三轮结论：Q3 299.76540283、Q4 570.73731319，两题均低于基准且均低于第二轮，2400局全清，因此当前共同最佳更新为第三轮。Q4收益仅0.0256%，必须视为很小的本地改进，等待独立新样本检验。第三轮启用Q3主动观测、Q4回退原版测点，两题使用全顶点最近认证清除。几何505项检查通过。']
 if k==4:lines+=['','第四轮结论：Q3大幅改善，但Q4比第三轮略慢，故为取舍，未刷新严格共同最佳（仍R3）。完整v1的2400局都成功并正常退出。独立压力开发初次运行因过久在nearest_certified_clear内手动中断，未保存完整开发均值；随后用5秒/局的诊断看门狗完整记录120局，部分全定向边界案例顶点数达数千乃至上万，触发诊断限时。这个5秒阈值不是官方1200秒时限，不把它等同于官方超时，但该复杂度风险使R4不可直接部署。详见dev/r4_watchdog.jsonl及development_interrupt.json。后续R5修复计算复杂度，没有进行隐式参数扫描。']
 if k==5:lines+=['','第五轮结论：Q3 290.85380296、Q4 570.73731319，分别减少5.0430%和0.0256%；2400局全清，刷新严格共同最佳为第五轮（支配R3）。R4的Q3均值仅比R5少0.000024秒/源，而其计算风险明显；保留R4原始数字，不把R5说成在每个小数位都支配R4。计算退化重放120局全部完成，最高49顶点，最长0.0514秒，5秒诊断超时由5个降为0。']
 if k==6:lines+=['','第六轮结论：Q3 286.01852917、Q4 570.73731319；2400局全清，无异常。Q3进一步改善、Q4与第五轮严格相同，因此当前共同最佳为R6，连续未刷新计数归零。无信号排除仅在Q3启用，完整几何证明与独立点验证留存。']
 if k==7:lines+=['','第七轮结论：Q3 286.01274518、Q4 570.73731319，2400局全清。Q3只比R6快0.00578399秒/源，Q4逐局相同，按预定严格共同最佳口径更新R7并将未刷新计数归零；不把这一极小回归差异描述为显著或稳健改善。新增planning_hypotheses只影响排序；有限提案为空退回原假想点，不改变正确性。']
 if k==8:lines+=['','第八轮结论：Q3 285.86670335、Q4 568.44941153；2400局全清。光学失败信息使两题均值均改善，刷新最佳R8，未刷新计数归零；仍需单列场景退步。全局覆盖与格点兜底未修改。']
 if k==9:lines+=['','第九轮结论：Q3 285.95192367、Q4 568.40397853，2400局全清。相对R8，Q3慢0.08522032秒/源而Q4快0.04543300秒/源，是非支配取舍，严格共同最佳仍为R8；连续未刷新计数1。后续R10由干净上下文仅从本路线自身材料接续设计。']
 if k==10:lines+=['','第十轮采用接收上界一致的预测后验：predicted_polygon通过已有add_bearing(...,tighten=False)加入24个1500m外切半平面，只影响动作排序。独立开发910900–910909每题60局与R8逐局任务指标一致，1000个合成几何组合全部保持合法目标，52个预测外包发生收紧。full2400局全部清除且与R8逐局秒/源完全一致，未刷新最佳；连续R9/R10未刷新计数2，达到经验停止。没有进一步扫面数或候选参数。编码前解析排除了“中心光学失败后跳过检测”想法，没有把它算作运行候选。']
 lines+=['',f'本轮源码提交：`{code_commit or "未提交"}`。全测异常数：Q3={z["3"]["errors"]}，Q4={z["4"]["errors"]}。共同最佳更新：{improved}；本轮后为R{best_round}，SHA256 `{rec["best_sha256_after"]}`；连续未刷新计数{fail_count}。']
 lines+=['']
(home/'iteration_log.md').write_text('\n'.join(lines)+'\n');(home/'round_metrics.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
