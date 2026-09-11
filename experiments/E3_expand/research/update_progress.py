from pathlib import Path
import json,hashlib
OUT=Path(__file__).resolve().parent.parent
def read(p):return json.loads((OUT/p).read_text())
def sha(p):return hashlib.sha256((OUT/p).read_bytes()).hexdigest()
rounds=[dict(id='E3_R1',mechanism='paid unknown-channel initialization',status='rejected_full',parent='S1',development='results/r1_development',extra_development='results/r2_development',snapshot='snapshots/r1.py',full='results/r1_exposed',source='ISER2013'),dict(id='E3_R2',mechanism='joint information side score',status='rejected_development; existing mechanism recheck',parent='S1; same family as A3_coordination_R3',development='results/r2_development',snapshot='snapshots/r2_development.py',source='ATL2020; not TD3 reproduction'),dict(id='E3_R3',mechanism='convex-footprint no-signal exclusion',status='retained_component_S1; current-common-best integration not run here',parent='S1',development='results/r3_development',extra_development='results/r3_extended_development',snapshot='snapshots/r3.py',full='results/r3_exposed',source='independent task-specific geometric derivation, motivated by bounded-set sensing')]
for r in rounds:
 r['sha256']=sha(r['snapshot'])
 if 'full' in r:
  s=read(r['full']+'/summary.json');r['full_all_complete']=s['all_complete'];r['full_comparisons']=[v for v in s['comparisons_to_S1'] if v['group']=='ALL'];r['wall_s']=s['wall_seconds_new_runs']
(OUT/'optimization_path.json').write_text(json.dumps(rounds,ensure_ascii=False,indent=2))
best=read('results/r3_exposed/summary.json');means={str(x['mode']):x['candidate_mean_s_per_source'] for x in best['comparisons_to_S1'] if x['suite']=='combined' and x['group']=='ALL'}
(OUT/'best.json').write_text(json.dumps(dict(status='retained_E3_component_against_S1; not yet compared with common C1',snapshot='snapshots/r3.py',sha256=sha('snapshots/r3.py'),dependencies='snapshots/r1_dependencies.json',results='results/r3_exposed',all_complete=True,means_s_per_source=means),indent=2))
dev=[read('results/'+name+'/budget.json') for name in ['r1_development','r2_development','r3_development','r3_extended_development']]
budget=dict(development_environment_runs=sum(x['actual_runs'] for x in dev),development_distinct_cases=288,development_distinct_seeds=24,quick_candidate_runs=240,full_candidate_runs=9600,full_distinct_cases=4800,actual_environment_runs=sum(x['actual_runs'] for x in dev)+240+9600,actual_S1_development_runs=288,cache_comparison_rows=9600,cache_rows_are_not_new_executions=True,geometry_fixture_checks=8000,geometry_fixtures_are_not_strategy_episodes=True,development_wall_s=sum(x['wall_s'] for x in dev),full_wall_s=sum(x['wall_s'] for x in rounds if 'wall_s' in x),state='ongoing; add subsequent attempts')
(OUT/'execution_budget.json').write_text(json.dumps(budget,indent=2))
lines=['# E3 扩展研究与实测进展','','当前独立保留组件为R3：在固定S1上，Q4从473.897493降至473.620439秒/源（0.05846%），4800案例全部正常清除；Q3逐局保持S1。它尚未与主协调最新C1完成融合对照，因此不称共同最佳。','', '## 已完成机制实验','', '|轮次|机制|开发结果|完整暴露回归|决定|','|---|---|---|---|---|','|R1|未知频道共享初始化|两批96新Q4小幅改善；600m密集补测退步|Q4 475.131767，较S1慢0.26045%；4800全清|拒绝|','|R2|第二测点跨目标信息收益|三权重均微退步；已有A3_R3方向的S1复测|未跑full|拒绝|','|R3|凸接收域no_signal排除|96新Q4微改善；近距离锥扩展反而退步|Q4 473.620439；两批同向改善；4800全清|保留独立组件，交协调融合|','', '## R3为什么不排除真实源','', '圆盘与半圆盘接收域均为凸集，包含真实源s及所有曾收到direction的接收位置p1、p2。因此，若q返回no_signal，它不可能位于conv{s,p1,p2}中。将q=αs+βp1+γp2重排（α>0，非负且和为1），得到禁区s=q+(β/α)(q-p1)+(γ/α)(q-p2)。非共线时这是两个半平面的交；它的补集是两片半平面的并。分别裁剪原可靠多边形，再取两片并集的凸包，仍覆盖全部可行真源。共线退化跳过；边界保留微米级裕量。','', '只用最后8正点与24负点限制成本；漏掉旧约束只减少收紧程度，不让不可靠点变成清除证书。hypothetical visibility cache随多边形刷新；最终clear仍沿用所有顶点20m条件与完整覆盖退出。这里的负观测楔形是本项目推导，未冒称指定论文原算法或定理。','', '## 完整性、退步与边界','']
for r in rounds:
 if 'full' not in r:continue
 s=read(r['full']+'/summary.json');c=[x for x in s['comparisons_to_S1'] if x['suite']=='combined' and x['group']=='ALL' and x['mode']==4][0]
 regress=[x for x in s['comparisons_to_S1'] if x['suite']=='combined' and x['mode']==4 and x['group']!='ALL' and x['delta_s_per_source']>1e-8]
 lines.append(f"- {r['id']}：Q4 2400局（30970源）全部清；快/同/慢={c['faster']}/{c['equal']}/{c['slower']}。场景均值退步："+'；'.join(f"{x['group']} +{x['delta_s_per_source']:.6f}秒/源" for x in regress)+'。')
lines+=['','完整比较包括每题2400局；full4800为既有暴露研发案例，quick是其子集，没有增加留出，也没有Windows官方测试。现实耗时只反映本机执行，不与历史缓存作速度排名。',f"本阶段目前实际环境执行{budget['actual_environment_runs']}次，其中开发{budget['development_environment_runs']}、quick240、完整候选9600；开发仅288不同案例、24不同seed，不能把执行次数叫独立样本。8000几何夹具仅检查公式性质，不是8000求解任务。",'', '## 阅读与下一步','', '指定8条论文与2条引用扩展已落[literature.json](literature.json)和[阅读简报](RESEARCH_BRIEF.md)，严格注明实际页码、版本与访问缺口。共享初始化和跨目标动作收益已经做实测；随机有限集的动态生灭/数据关联在本题缺少对应问题，暂不搬入求解器。后续继续恢复有界传感器选择原文，并探索真正不同且有行动含义的机制。']
(OUT/'report.md').write_text('\n'.join(lines)+'\n')
(OUT/'resume.md').write_text('''# E3当前续作状态

工作树work/stage4/E3_expand；仅写experiments/E3_expand；分支experiments/20260911-stage4/e3_expand。
已完成R1共享未知频道初始化（4800全清但Q4退步0.26045%，拒绝）；R2跨频道第二测点收益（旧A3R3机制当前父法复测，三个权重均开发负，未full）；R3凸接收域no_signal排除（新推导），4800全清、Q4 473.620439 vs S1 473.897493，Q3逐局不变，已告root准备融合C1。
R3基础snapshot snapshots/r3.py SHA7d113e5262d52eaca7e0287ea062e3221b0cadf33340f3536b2b1adbe8f7ec27；依赖stage4baseline三文件，snapshots/r1_dependencies.json已登记。
R3 extended带1000m近距离锥，96开发退步，保留源码与负结果但不晋级。
开发已用seed46000000–46000023，下一46000024；实际环境执行11088，budget脚本可重算；无新增holdout。
研究8条用户线索+2扩展紧凑账本literature.json/RESEARCH_BRIEF，生成脚本research/build_literature.py；共享初始化15页、ATL16页已全文读；其余关键章节实际范围已记录，未冒称全文。
ICRA2013原作者链接404，SemanticScholar检索到UMN开放库bitstream，但download返回HTML挑战。当前正在下载author thesis链接和UMN server API content（exec sessions36165、4157，需poll仅一次确认完毕）。原ICRA2013 cache/icra2013.pdf是HTML，不可当论文；readmanifest需记录。
所有正文缓存research/cache由本目录.gitignore排除；不提交PDF/全文/网页缓存。已读AGENTS/README/协议/技能，root协调允许旧研究与方法交流；后续只读work/stage4/COORDINATION.md和自身resume定位状态，不用旧root_coordination_status。
继续：保存并push首批实现/结果/说明；继续源核实与新机制实测，不把仅一小组件提升当完成整个研究。
''')
print(budget)
