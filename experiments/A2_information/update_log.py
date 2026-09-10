import json,statistics,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[2];home=root/'experiments/A2_information'
lines=['# A2 实验迭代日志','', '固定评测：LOCAL-v1；quick 是 full 子集，不是独立留出集。完整成功才比较虚拟时间。原版共同最佳 Q3 306.3004342181635、Q4 570.8833714439976 秒/源。','']
records=[]
for k in [1,2,3,4,5]:
 p=root/f'results/A2_information_r{k}_full'
 if not p.exists():continue
 s=json.loads((p/'summary.json').read_text());rows=json.loads((p/'case_metrics.json').read_text());z={}
 for m in [3,4]:
  a=[r for r in rows if r['mode']==m and r['variant']=='candidate'];b=[r for r in rows if r['mode']==m and r['variant']=='frozen_baseline']
  ca=statistics.mean(r['average_clear_time_s'] for r in a);ba=statistics.mean(r['average_clear_time_s'] for r in b)
  z[str(m)]={'mean_s_per_source':ca,'baseline_mean_s_per_source':ba,'reduction_percent':100*(1-ca/ba),'complete':sum(r['complete'] for r in a),'cases':len(a),'errors':sum(bool(r['error']) for r in a),'mean_distance_m':statistics.mean(r['distance_m'] for r in a),'mean_clear_failures':statistics.mean(r['clear_failures'] for r in a)}
 rec=dict(round=k,sha256=s['candidate_sha256'],wall_seconds=s['wall_seconds'],metrics=z,all_complete=s['all_complete'],result=str(p.relative_to(root)))
 records.append(rec)
 lines+= [f'## 第 {k} 轮','',f'- 候选：`experiments/A2_information/candidates/r{k}_solver.py`；SHA256 `{s["candidate_sha256"]}`。',f'- full 结果：`{p.relative_to(root)}`；实际运行 {s["wall_seconds"]:.3f} 秒；完整通过：{s["all_complete"]}。',f'- 规则记录：`results/A2_information_r{k}_rules/`；quick：`results/A2_information_r{k}_quick/`。','', '| 题目 | 全清 | 秒/源 | 对基准减少 |','|---|---:|---:|---:|']
 for m,v in z.items():lines.append(f'| Q{m} | {v["complete"]}/{v["cases"]} | {v["mean_s_per_source"]:.8f} | {v["reduction_percent"]:.4f}% |')
 lines+=['','逐场景退步（负减少率；不隐藏）：','']
 for g in s['groups']:
  if g.get('reduction_fraction',0)<0:lines.append(f'- Q{g["mode"]} `{g["group"]}`：增加 {-g["reduction_fraction"]*100:.4f}%。')
 if k==1:lines+=['','第一轮结论：Q3 改善而 Q4 退步，保留为非支配候选，共同最佳仍为原版。没有以合并指标把取舍说成全面改善。第一轮开发检查 `dev/r1_preliminary.json`：各题24局；Q3 337.1310 vs 341.0363，Q4 766.1990 vs 712.8780。仅试一个规划器，没有隐藏参数扫描。']
 if k==2:lines+=['','第二轮结论：Q3持平第一轮，Q4由578.9624下降到574.8171，但仍比基准慢0.6891%。第二轮支配第一轮这个取舍候选；共同最佳仍为原版，非支配集为原版和第二轮。quick的Q4虽略胜基准，full未支持该改善，不能用quick替代full。开发集910100–910109每题60局也保留，未做参数扫描。开发数据中boundary/min_radius的第四问可能全定向，属于比题设混合更强的压力场景，不能冒充官方分布。']
 if k==3:lines+=['','第三轮结论：Q3 299.76540283、Q4 570.73731319，两题均低于基准且均低于第二轮，2400局全清，因此当前共同最佳更新为第三轮。Q4收益仅0.0256%，必须视为很小的本地改进，等待独立新样本检验。第三轮启用Q3主动观测、Q4回退原版测点，两题使用全顶点最近认证清除。几何505项检查通过。']
 if k==4:lines+=['','第四轮结论：Q3大幅改善，但Q4比第三轮略慢，故为取舍，未刷新严格共同最佳（仍R3）。完整v1的2400局都成功并正常退出。独立压力开发初次运行因过久在nearest_certified_clear内手动中断，未保存完整开发均值；随后用5秒/局的诊断看门狗完整记录120局，部分全定向边界案例顶点数达数千乃至上万，触发诊断限时。这个5秒阈值不是官方1200秒时限，不把它等同于官方超时，但该复杂度风险使R4不可直接部署。详见dev/r4_watchdog.jsonl及development_interrupt.json。下一轮回到可控制复杂度的设计，不进行隐式参数扫描。']
 if k==5:lines+=['','第五轮结论：Q3 290.85380296、Q4 570.73731319，分别减少5.0430%和0.0256%；2400局全清，刷新严格共同最佳为第五轮（支配R3）。R4的Q3均值仅比R5少0.000024秒/源，而其计算风险明显；保留R4原始数字，不把R5说成在每个小数位都支配R4。计算退化重放120局全部完成，最高49顶点，最长0.0514秒，5秒诊断超时由5个降为0。']
 lines+=['']
(home/'iteration_log.md').write_text('\n'.join(lines)+'\n');(home/'round_metrics.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
