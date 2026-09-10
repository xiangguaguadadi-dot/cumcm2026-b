"""Recompute the Chinese report tables from retained raw experiment evidence."""
from pathlib import Path
import json,statistics,hashlib,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
L=json.loads((HERE/'literature.json').read_text());best=json.loads((HERE/'best.json').read_text())
rounds=[]
for p in sorted((ROOT/'results').glob('A1_space_r*_full/summary.json'),key=lambda p:int(p.parent.name.split('_r')[-1].split('_')[0])):
 n=int(p.parent.name.split('_r')[-1].split('_')[0]);s=json.loads(p.read_text());rows=json.loads((p.parent/'case_metrics.json').read_text())
 m={q:statistics.mean(x['average_clear_time_s'] for x in rows if x['mode']==q and x['variant']=='candidate') for q in (3,4)}
 base={q:statistics.mean(x['average_clear_time_s'] for x in rows if x['mode']==q and x['variant']=='frozen_baseline') for q in (3,4)}
 rounds.append(dict(n=n,summary=s,rows=rows,m=m,base=base,path=str(p.parent.relative_to(ROOT))))
b=next(x for x in rounds if x['n']==best['best_round']);out=[]
def line(s=''):out.append(s)
line('# A1 阶段实验报告：全局空间搜索与移动成本')
line('\n研究及实验日期：2026-09-11。路线独立工作树：`'+str(ROOT)+'`。')
line(f'\n当前选择 R{b["n"]}：第三问 **{b["m"][3]:.6f} 秒/源**，第四问 **{b["m"][4]:.6f} 秒/源**；相对冻结原版分别降低 **{100*(1-b["m"][3]/b["base"][3]):.4f}%** 和 **{100*(1-b["m"][4]/b["base"][4]):.4f}%**。每题 1200/1200 局全清、正常退出，无异常。这是本地固定回归结果，不是官方模拟器成绩。')
line('\n**状态：按主Agent要求暂存释放并发名额；已完成7轮，当前最佳R6，连续未刷新计数1，尚未收敛。恢复后从R8继续，详见resume.md。**')
line('\n## 1. 问题与原版分析')
line('\n目标是总虚拟耗时/清除数，在确保全部清除的前提下尽量小。虚拟耗时包含移动/5、每次检测5秒、切换频道1秒、光学定位3秒、成功清除2秒。算法不能看真实源数、源坐标、案例ID和随机种子；正式环境20分钟现实限制仍适用。')
line('\n原版已具备：有界误差多边形、最小包围圆、启发式试清、定向丢信号恢复、有限光学格点兜底、Q3七站/Q4二十二站连续覆盖证书、已知最多16源的停止条件，以及三起点2-opt站点路线。A1没有把这些既有模块重新署名成新成果。主要缺口是覆盖点偏外、站点与待清源的全局行程缺少统一安排、区域中心代理与最终服务位置不一致。')
for q in (3,4):
 for variant,label in [('frozen_baseline','原版'),('candidate','最佳')]:
  z=[x for x in b['rows'] if x['mode']==q and x['variant']==variant]
  move=statistics.mean(x['distance_m']/5/x['cleared_count'] for x in z);total=statistics.mean(x['average_clear_time_s'] for x in z)
  line(f'\n- Q{q} {label}：每源移动时间均值 {move:.3f} 秒，占每局秒/源均值的 {100*move/total:.2f}%；总秒/源 {total:.3f}。这是真实本地动作记录分解，不是静态路径推算。')
line('\n## 2. 到底调研了哪些文献')
line(f'\n共保留 {L["counts"]["total"]} 篇一手作者论文；{L["counts"]["core_section_read"]} 篇阅读了下表列明的关键正文/证明/实验章节，{L["counts"]["discovery"]} 篇为摘要与身份发现级。**没有把下载等同于通读全文，也没有声称这些文献均已复现。** 逐条结构化记录、原文散列和采用边界见 [literature.json](literature.json)。')
line('\n检索族包括：离散停点与覆盖采样、连续割草与见证集、旅行商邻域、在线发现/绕行、GP信息路径、跨片区服务成本、多机能耗、学习集中搜索。范围为能帮助本题空间决策的方法谱系，不是整个机器人规划领域的穷尽综述。使用 arXiv 作者页面与正文，沿正文引用扩展竞争路线。常规web搜索两次连接失败，Google直连超时；继承代理下下载SSL失败，随后使用直连成功下载9篇正文。访问失败没有被写成已读。')
line('\n查询词：'+ '；'.join('`'+q+'`' for q in L['queries'])+'。')
line('\n### 2.1 身份、版本与实际阅读范围')
line('\n| ID | 题名、作者、初稿年份 | 原文版本 | 实际阅读范围 |\n|---|---|---|---|')
for p in L['papers']:
 authors='; '.join(p['authors']);line(f'| {p["id"]} | [{p["title"]}]({p["pdf_url"]})；{authors}；{p["first_submission"][:4]} | {p["version"]}，更新 {p["last_submission"]} | {p["read"]} |')
line('\n### 2.2 文献 → 启发 → 实现 → 实验的追溯表')
line('\n| 文献 | 核心机制与本题启发 | 是否进入代码 / 函数 / 轮次 | 未采用部分与理由 |\n|---|---|---|---|')
for p in L['papers']:
 line(f'| {p["id"]} | {p["mechanism"]} **启发：**{p["inspiration"]} | {p["implementation"]} | {p["reason"]} |')
line('\n### 2.3 核心正文的证据和边界')
for p in L['papers']:
 if p['tier']=='core_sections':line(f'\n**[{p["title"]}]({p["pdf_url"]})**\n\n{p["evidence"]} 本题迁移边界：{p["limitations"]}')
line('\n### 2.4 方法分类树')
line('\n- 覆盖约束 → 离散停点/采样密度 → He等；连续覆盖/见证集 → Fekete等。\n- 服务路径 → 邻域访问/几何命中集 → Dumitrescu–Tóth；均匀圆盘中心绕行界 → Bercea；片区入出点与TSP精修 → Plessen。\n- 在线决策 → 发现后绕行 → Maini等；局部集中探索/学习 → Matloob等。\n- 信息与覆盖 → 显式GP不确定性约束/联合选点路由 → Jakkala等。\n- 任务成本 → 能耗与速度/多机分配 → Datsko等。\n\n每篇论文在主树只出现一次；交叉启发在上表说明。')
line('\n## 3. 方案与实际实现')
line('\n- R1：自创解析覆盖环。把Q3六个环站由1558.845727米压到1124米，原点保持；原定位器不变。启发来自覆盖约束和采样成本分离，数值与证明由本实验推导，非论文现成结果。\n- R2：自创开放空间路线。将未访问认证站和待清源估计中心放入同一开放路线，三起点2-opt，每次执行一个任务后重规划。受在线发现后服务思路启发，未复现JUMP/SNAKE的曲率运动模型。\n- R3：原点20频道全无信号时，在任何外站访问前选外环，否则内环；Q4回退原版，公开保留R2的负结果。\n- R4：Q4只有在全部待清区域半径不超过原有100米试清尺度时才启用全局路线；加入显式换环索引不变量。\n- R5：在半径20−r的认证可清除邻域内近似优化进入+离开距离，使用直线交盘和角度网格/黄金分割，保留旧点候选并复核可行性。\n- R6：确定性单节点重插与2-opt组合，保留旧路线；R7：清除段执行既定顺序、扫描站后才重规划，结果退步并回退到R6。所有候选都保存快照，R7未混入当前最佳solver。')
line('\n“论文启发”不意味着因果归功。真实改变的是上述具体函数；文献中未实现的GP、强化学习、命中集、SOCP、Dubins和能耗模型不承担本题效果解释。R1的覆盖环、R3的无信号分支、R4的就绪条件、R5的认证盘内近似均为本实验设计，原论文只提供相关问题建模视角。')
line('\n## 4. 完整性与停止证明')
line('\nQ3：r≤1000的源由原点覆盖。r∈[1000,1800]的源与某一环站极角差≤π/6。站半径为a时，距离平方不超过 f(r)=r²+a²−2ra cos(π/6)。f关于r凸，故只需检查区间端点。a=1124时端点距离562.628556、999.545300米；a=1558.845727时854.400375、900米，均小于1000。两个环都对连续圆域有效；无信号选择哪个环只影响效率。原点无信号只推出源距原点>1000，不能推出全在最边缘；偏心聚簇的退步说明这种信息局限。')
line('\n换环前现在显式要求所有频道scanned中没有非0站，避免旧索引匹配新坐标。Q4维持原七边形三角剖分覆盖点。每个空间路线包含全部未访问站和已观测未清源；每次外层动作消费一个站，或通过原有限定位/光学兜底清掉一个源，所以外层任务最多22+16=38，不会只重规划而不推进。clear/measure的时间限制守卫和180000秒切换光学覆盖保留。')
line('\nR5：已知真实源g∈B(c,r)，选点p∈B(c,20−r−10⁻⁶)，则|p−g|≤|p−c|+|c−g|<20。数值优化复核盘内可行性。1000组随机几何检查全部通过只是实现辅助检查，连续可靠性来自三角不等式。有限本地案例全清不替代解析覆盖证明。路径优化没有扩大原定位区域、增加必访站点或改变光学格点覆盖；完整预算边界分析见 [plan.md](plan.md)。')
line('\n## 5. 实验协议、预算与可复现性')
line('\n固定评测 LOCAL-v1 的环境、评测脚本、规则、案例和基准保持冻结。每轮先既有单测、冻结散列、79项正常规则，再quick120局，再full2400局；基准取已校验缓存。quick是full的子集；5000–5099固定回归已知，不当作新留出。未按案例ID或测试组在线决策。训练/开发只用重新生成的62000系列，后续验证用63000、64000、65000等明确不同系列，逐个JSON保留。没有下载模型权重，没有训练大模型或用真值教师。')
line('\n首次开发辅助函数在Q4边缘/原点簇压力场景产生全定向数据，不符合题目混合条件；该批保留为 `r2_development_invalid_mixture.json`，排除出有效证据。修改仅在A1新开发生成脚本中让最后一个源保持全向，所有候选和基准比较均重新运行；冻结生成器和固定案例没有修改。')
line('\n原用户预算每Agent最多三轮，之后用户因R2→R3持续改善追加授权。停止按主Agent给定的连续两轮full未刷新当前最佳执行；该规则只代表这组有限设计空间的经验停止，不是证明算法或研究方向已经全局收敛。')
line('\n| 轮次 | Q3秒/源 | 比原版减少 | Q4秒/源 | 比原版减少 | 全清局数 | full现实秒 |\n|---|---:|---:|---:|---:|---:|---:|')
line(f'| 原版 | {b["base"][3]:.6f} | — | {b["base"][4]:.6f} | — | 2400/2400 | 历史缓存，不比较现实速度 |')
for x in rounds:
 line(f'| R{x["n"]} | {x["m"][3]:.6f} | {100*(1-x["m"][3]/x["base"][3]):.4f}% | {x["m"][4]:.6f} | {100*(1-x["m"][4]/x["base"][4]):.4f}% | {sum(z["complete"] for z in x["rows"] if z["variant"]=="candidate")}/2400 | {x["summary"]["wall_seconds"]:.3f} |')
line('\n所有清除率都保留逐局清除个数/真实源数，真实源数仅在评测层计算。全局均值按每局秒/源再平均，不能把跨局总时间除跨局总源数替代，也不是官方公开的跨案例总分。')
line('\n### 各轮失败和场景退步')
line('\n| 轮次 | 问题 | 相比原版退步的场景（负数表示时间降低量为负） |\n|---|---|---|')
for x in rounds:
 for q in (3,4):
  bad=[g for g in x['summary']['groups'] if g['mode']==q and g.get('reduction_fraction',0)<-1e-12]
  line(f'| R{x["n"]} | Q{q} | '+('；'.join(g['group']+f' {100*g["reduction_fraction"]:.4f}%' for g in bad) or '无')+' |')
line('\n所有轮次的异常/不完整行仍在 `case_metrics.json`；若有任何不完整局，不对成功子集做耗时排名。这里列出的全量候选都通过完整性检查；性能退步也完整保留，没有只选表现最好的场景报告。')
line('\n## 6. 当前最佳版本每场景结果')
line('\n| 题目 | 场景 | 原版秒/源 | 最佳秒/源 | 时间减少 | 全清 |\n|---|---|---:|---:|---:|---:|')
for g in b['summary']['groups']:
 line(f'| Q{g["mode"]} | {g["group"]} | {g["baseline_mean_s_per_source"]:.6f} | {g["candidate_mean_s_per_source"]:.6f} | {100*g["reduction_fraction"]:.4f}% | {g["candidate_complete"]}/{g["cases"]} |')
line('\n开发集表现与固定回归不完全一致，尤其Q4中心代理和Q3偏心聚簇。这不构成官方分布泛化证据。统一新样本验证由主Agent在六路完成后执行，不把其结果返回A1继续调参。')
line('\n## 7. 证据文件与运行')
line(f'\n- 当前最佳：`{best["solver_relative_path"]}`，快照 `{best["snapshot"]}`。\n- SHA256：`{best["sha256"]}`。\n- 实现提交：`{best["code_commit"]}`。\n- 全量结果：[{b["path"]}/summary.json](../../{b["path"]}/summary.json)，逐局原始结果同目录。\n- 版本与依赖：[best.json](best.json)；逐轮判断：[iteration_log.md](iteration_log.md)；方案和证明：[plan.md](plan.md)。\n- 逐篇文献：[literature.json](literature.json)；身份元数据与正文散列：`research/source_metadata.json`。原论文PDF、HTML和提取文本仅保留本地忽略缓存，不重新发布全文。')
line('\n```sh\npython -m unittest discover -s tests -v\npython evaluate.py --verify-only\npython tests/check_nominal.py --package . --out /tmp/A1_nominal_recheck.json\npython experiments/A1_space/check_spatial_geometry.py --candidate solver.py --out /tmp/A1_geometry_recheck.json\npython evaluate.py --suite full --candidate '+best['snapshot']+' --out results/A1_reproduce_new_directory\n```')
line('\n求解器仅依赖Python标准库；本工作树没有coverage_points.json，因此两题均使用解析点集。若外部提供该文件，原有点集指纹验证仍必须通过；最佳复现应使用记录的无外部点集配置。HTTP客户端和官方通信未改动，Windows官方演练与正式测试仍未执行。代码、结果已在专属分支分轮提交；最终推送状态以主Agent核验为准。')
(HERE/'report.md').write_text('\n'.join(out)+'\n')
# Public aggregate ledger supports root cross-check without re-running candidates.
(HERE/'all_rounds.json').write_text(json.dumps([dict(round=x['n'],q3=x['m'][3],q4=x['m'][4],all_complete=x['summary']['all_complete'],wall_seconds=x['summary']['wall_seconds'],candidate_sha256=x['summary']['candidate_sha256'],path=x['path']) for x in rounds],indent=2))
print('report generated,',len(rounds),'rounds')
