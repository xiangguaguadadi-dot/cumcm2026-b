# A1 阶段实验报告：全局空间搜索与移动成本

研究及实验日期：2026-09-11。路线独立工作树：`/Users/t/ai project/数学建模2026/agent_experiments/20260911/A1_space`。

当前选择 R8：第三问 **270.531505 秒/源**，第四问 **556.703578 秒/源**；相对冻结原版分别降低 **11.6777%** 和 **2.4838%**。每题 1200/1200 局全清、正常退出，无异常。这是本地固定回归结果，不是官方模拟器成绩。

**状态：已完成9轮，当前最佳R8，连续未刷新full最佳计数1。实验继续。**

## 1. 问题与原版分析

目标是总虚拟耗时/清除数，在确保全部清除的前提下尽量小。虚拟耗时包含移动/5、每次检测5秒、切换频道1秒、光学定位3秒、成功清除2秒。算法不能看真实源数、源坐标、案例ID和随机种子；正式环境20分钟现实限制仍适用。

原版已具备：有界误差多边形、最小包围圆、启发式试清、定向丢信号恢复、有限光学格点兜底、Q3七站/Q4二十二站连续覆盖证书、已知最多16源的停止条件，以及三起点2-opt站点路线。A1没有把这些既有模块重新署名成新成果。主要缺口是覆盖点偏外、站点与待清源的全局行程缺少统一安排、区域中心代理与最终服务位置不一致。

- Q3 原版：每源移动时间均值 247.950 秒，占每局秒/源均值的 80.95%；总秒/源 306.300。这是真实本地动作记录分解，不是静态路径推算。

- Q3 最佳：每源移动时间均值 210.684 秒，占每局秒/源均值的 77.88%；总秒/源 270.532。这是真实本地动作记录分解，不是静态路径推算。

- Q4 原版：每源移动时间均值 428.364 秒，占每局秒/源均值的 75.04%；总秒/源 570.883。这是真实本地动作记录分解，不是静态路径推算。

- Q4 最佳：每源移动时间均值 417.386 秒，占每局秒/源均值的 74.97%；总秒/源 556.704。这是真实本地动作记录分解，不是静态路径推算。

## 2. 到底调研了哪些文献

共保留 9 篇一手作者论文；6 篇阅读了下表列明的关键正文/证明/实验章节，3 篇为摘要与身份发现级。**没有把下载等同于通读全文，也没有声称这些文献均已复现。** 逐条结构化记录、原文散列和采用边界见 [literature.json](literature.json)。

检索族包括：离散停点与覆盖采样、连续割草与见证集、旅行商邻域、在线发现/绕行、GP信息路径、跨片区服务成本、多机能耗、学习集中搜索。范围为能帮助本题空间决策的方法谱系，不是整个机器人规划领域的穷尽综述。使用 arXiv 作者页面与正文，沿正文引用扩展竞争路线。常规web搜索两次连接失败，Google直连超时；继承代理下下载SSL失败，随后使用直连成功下载9篇正文。访问失败没有被写成已读。

查询词：`boustrophedon coverage path planning`；`coverage path planning survey autonomous robots`；`traveling salesman neighborhoods disks`；`next best view exploration gain distance`；`coverage planning sweeping sensor discrete stops`。

### 2.1 身份、版本与实际阅读范围

| ID | 题名、作者、初稿年份 | 原文版本 | 实际阅读范围 |
|---|---|---|---|
| 2207.06209 | [Environmental Sampling with the Boustrophedon Decomposition Algorithm](https://arxiv.org/pdf/2207.06209)；He, Hannah; Norby, Joe; Wang, Sean; Sihota, Natasha; Hoelen, Thomas P.; Lowry, Gregory V.; Johnson, Aaron M.；2022 | v1，更新 2022/07/13 | PDF 第 2–5、7–8 页：§II–IV、图6–9及§V结果、§VI开头；摘要。未通读参考文献与全部附图。 |
| 2211.05891 | [A Closer Cut: Computing Near-Optimal Lawn Mowing Tours](https://arxiv.org/pdf/2211.05891)；Fekete, Sándor P.; Krupke, Dominik; Perk, Michael; Rieck, Christian; Scheffer, Christian；2022 | v1，更新 2022/11/10 | PDF 第 3–5 页（§1.3、§2证明）；第 7 页 §4–4.1、第 8 页 §4.3；第12页图15。未通读所有几何证明和全部实验。 |
| 1506.07903 | [Constant-Factor Approximation for TSP with Disks](https://arxiv.org/pdf/1506.07903)；Dumitrescu, Adrian; Tóth, Csaba D.；2015 | v4，更新 2016/08/09 | PDF 第2–4页：相关工作、定理1、§2几何命中集、算法总览和§3预处理开头；摘要。未逐行验证后续近似证明。 |
| 2111.10462 | [Online Coverage Planning for an Autonomous Weed Mowing Robot with Curvature Constraints](https://arxiv.org/pdf/2111.10462)；Maini, Parikshit; Gonultas, Burak M.; Isler, Volkan；2021 | v1，更新 2021/11/19 | PDF 第2–7页：任务定义、§V界、§VI两算法和伪代码、§VII模拟、§VIII田野实验与§IX。另读摘要。未通读末页参考文献。 |
| 2602.05198 | [Informative Path Planning with Guaranteed Estimation Uncertainty](https://arxiv.org/pdf/2602.05198)；Jakkala, Kalvik; Agarwal, Saurav; O'Kane, Jason; Akella, Srinivas；2026 | v3，更新 2026/05/26 | PDF 第3–5页：§III–V、单点方差条件、单调性、二值覆盖矩阵、GreedyCover 和 GCB；第7页 SRTM 实验及ASV段落开头。未读全部附录证明。 |
| 1809.07159 | [Improved Bounds for the Traveling Salesman Problem with Neighborhoods on Uniform Disks](https://arxiv.org/pdf/1809.07159)；Bercea, Ioana O.；2018 | v1，更新 2018/09/19 | arXiv 摘要及作者元数据；下载PDF并核对首页题名作者，未深读正文。 |
| 2408.08001 | [Path Planning for Spot Spraying with UAVs Combining TSP and Area Coverages](https://arxiv.org/pdf/2408.08001)；Plessen, Mogens；2024 | v2，更新 2025/02/19 | 追加深读 PDF 第3–5页 §3.1–3.3 开头：成本分解条件、NN/DENN与H1–H4；第6页 §4实验设置和结果讨论。此前仅摘要，扩展授权后补读正文。 |
| 2402.10529 | [Energy-aware Multi-UAV Coverage Mission Planning with Optimal Speed of Flight](https://arxiv.org/pdf/2402.10529)；Datsko, Denys; Nekovar, Frantisek; Penicka, Robert; Saska, Martin；2024 | v1，更新 2024/02/16 | arXiv 摘要、元数据与PDF首页（RA-L accepted 标注）；未深读正文。 |
| 2507.06960 | [Bounomodes: the grazing ox algorithm for exploration of clustered anomalies](https://arxiv.org/pdf/2507.06960)；Matloob, Samuel; Dutta, Ayan; Kreidl, O. Patrick; Roy, Swapnonel; Bölöni, Ladislau；2025 | v1，更新 2025/07/09 | arXiv 摘要与元数据、PDF首页；未深读强化学习设置。 |

### 2.2 文献 → 启发 → 实现 → 实验的追溯表

| 文献 | 核心机制与本题启发 | 是否进入代码 / 函数 / 轮次 | 未采用部分与理由 |
|---|---|---|---|
| 2207.06209 | 先分解无障碍单元，再按采样间距栅扫，并量化采样精度与路径长度的冲突。 **启发：**应先保证检测覆盖，再优化停点和真实行程；不能只比较扫描节点数量。 | R1/R3 certified_points、default_points；采用原则，未实现论文分解算法。 | 本题是无障碍圆域、离散信号探测、有最小接收半径；没有必要栅扫每个小像素。 |
| 2211.05891 | 以未覆盖区域见证点构造 CETSP 下界，再补齐覆盖形成上界，迭代收紧最优差距。 **启发：**看似覆盖的有限样本不足以保证连续区域覆盖；本题每个新点集需要解析证明。 | R1/R3 六环站凸函数端点证明；不是该论文的原始对偶或 SOCP 求解器。 | 论文移动中持续割草，本题移动中不可检测；见证网格解还需要覆盖认证，且这里圆域对称性允许直接解析设计。 |
| 1506.07903 | 构造穿过全部圆盘的连通几何图，将任意圆盘 TSPN 与最小权命中集连接，再倍边得到游回。 **启发：**访问一个区域与访问其中心不同；必须区分路由的估计中心和真正清除位置。 | R2/R3 spatial_next_task 的中心代理；R5 route_clear_point 在20-r的认证可清除圆盘内优化预测的进入+离开距离。未实现原论文几何命中集算法。 | 当前源只由有界误差楔形限制，不是已知圆盘；本文的任意圆盘近似与本题在线未知目标不同。 |
| 2111.10462 | 在覆盖推进中利用新发现的目标改变局部路径；JUMP 绕行再回主线，SNAKE 绕行后续进，R-SNAKE 允许漏服务换距离。 **启发：**同时规划搜索站与已发现目标，避免完成所有搜索后再整圈返回清除；但本题必须保留所有待完成任务。 | R2/R3 spatial_next_task 和 run：全局开放路径逐动作重规划，为自创简化，并非复现 JUMP/SNAKE。 R7检验按既定清除段执行、到新扫描站才重规划的稳定性；与论文“执行子路径时不再搜索下一子路径”的描述相关，但为本题自创事件边界。 | 机器狗无 Dubins 转弯半径约束，信号不能边走边测且不直接给准确目标位置；禁止采用 R-SNAKE 的漏清取舍。 |
| 2602.05198 | 把 GP 后验方差目标转成保守覆盖矩阵；对比先选点再路由与把覆盖增益/路径增量联合决策。 **启发：**点集选择与访问顺序不能割裂；覆盖是硬约束，距离是优化量。 | R1 点集与 R2/R3 路由分轮检验；未实现 GP、矩阵覆盖或 GCB 比值规则。 | 本题只给误差有界且同址固定，不能把未知跨位置误差强行当作可信 GP；先验方差达标也不等于未知源全部检测。 |
| 1809.07159 | 研究等半径圆盘 TSPN 与访问圆心的附加绕行界。 **启发：**提醒中心近似有额外路程，不能把中心 TSP 看成真实服务路径。 | 未直接进入代码；对 R2 中心代理风险的背景核对。 | 不直接解决未知目标、方向丢信号与在线定位，先读更一般的命中集路线。 |
| 2408.08001 | 固定片区入/出点时分离跨区路由与区内覆盖；TSP比较随机插入与消交叉，并实验组合H2+H4。 **启发：**改进开放路径时，可以把节点移除-重插与2-opt结合；同时不能把只优化代理路径长度当真实任务耗时最优。 | R6：spatial_next_task 内 reinsert 对当前路线穷举单节点重插，再2-opt，并保留原2-opt路线。属于H2思想的确定性改编，非论文10秒随机采样复现。R6 full Q3/Q4均改善；进入当前最佳。 | 本题是点源定位，不是边界已知的喷洒区域；现有无障碍定位器无需其障碍连接算法。 |
| 2402.10529 | 用速度与能耗模型优化多 UAV 覆盖，避免把路径长度等同于能量。 **启发：**本题目标也应直接使用官方虚拟时间；移动、换频、检测、清除都要计入。 | 未直接进入代码；保留冻结官方口径统计。 | 机器人速度固定5m/s、只有一只且题面未给电量目标，能量控制不适用。 |
| 2507.06960 | 交替均匀覆盖和对异常簇的局部集中搜索，以学习策略决定细查。 **启发：**观测可以触发不同空间策略，但推断分布不能替代未观测区域的覆盖证书。 | R3 仅受原则启发：无信号触发两个已证明覆盖点集的切换；没有强化学习。 | A1 专注空间几何；在三轮预算下用明确可审计的观测分支更合适，没有训练模型或借用其他 Agent 的学习策略。 |

### 2.3 核心正文的证据和边界

**[Environmental Sampling with the Boustrophedon Decomposition Algorithm](https://arxiv.org/pdf/2207.06209)**

正文用 Monte Carlo 随机环境比较 RMSE、热点漏检、路径和样本数，增加间距虽然缩短路径但可能漏热点。 本题迁移边界：其连续环境插值和热点分布不等价于本题互异频道点源；论文精度曲线不能当成本题全清证书。

**[A Closer Cut: Computing Near-Optimal Lawn Mowing Tours](https://arxiv.org/pdf/2211.05891)**

§4.1 给见证集扩大时下界单调；§4.3 用分支定界和二阶锥优化，图15展示上下界不同，覆盖率不是最优性证据。 本题迁移边界：本实验没有计算可证明最优的路径下界，不得声称当前路线近似比或全局最优。

**[Constant-Factor Approximation for TSP with Disks](https://arxiv.org/pdf/1506.07903)**

正文把图分为独立圆盘骨架、近处连接和余下命中集连接，说明邻域结构会改变路线代价。 本题迁移边界：中心代理误差可以使重规划变差；R2 Q4 回归就是本实验事实，不能从原论文近似保证推导本题性能。

**[Online Coverage Planning for an Autonomous Weed Mowing Robot with Curvature Constraints](https://arxiv.org/pdf/2111.10462)**

正文分别记录路径和清除比例；JUMP、SNAKE、R-SNAKE 的完整性不一致。田野演示的14个目标位置为预先地理标记并按视野揭示，而非完整视觉检测闭环。 本题迁移边界：论文报告的距离降幅不能迁移成本题成绩；我们的 Q4 负结果保留，实验证明只属于 LOCAL-v1。

**[Informative Path Planning with Guaranteed Estimation Uncertainty](https://arxiv.org/pdf/2602.05198)**

§V-C4 明确两阶段的选点近似不提供联合路径保证；实验把预算受限解与满足方差目标的解分开。 本题迁移边界：其模型内后验不确定性与真实 MSE、以及本题确定性全清，不是同一指标；本报告不照搬近似保证。

**[Path Planning for Spot Spraying with UAVs Combining TSP and Area Coverages](https://arxiv.org/pdf/2408.08001)**

§4比较15/19/197片区，H2+H4在其中两例给更短TSP路线但耗时更大；研究使用真实地理区域实例而非把完整探測任务部署在未知源上。 本题迁移边界：论文闭合路线、片区真值已知、固定入出点假设不同；本题为开放在线路线，提升只能由本题实测决定。

### 2.4 方法分类树

- 覆盖约束 → 离散停点/采样密度 → He等；连续覆盖/见证集 → Fekete等。
- 服务路径 → 邻域访问/几何命中集 → Dumitrescu–Tóth；均匀圆盘中心绕行界 → Bercea；片区入出点与TSP精修 → Plessen。
- 在线决策 → 发现后绕行 → Maini等；局部集中探索/学习 → Matloob等。
- 信息与覆盖 → 显式GP不确定性约束/联合选点路由 → Jakkala等。
- 任务成本 → 能耗与速度/多机分配 → Datsko等。

每篇论文在主树只出现一次；交叉启发在上表说明。

## 3. 方案与实际实现

- R1：自创解析覆盖环。把Q3六个环站由1558.845727米压到1124米，原点保持；原定位器不变。启发来自覆盖约束和采样成本分离，数值与证明由本实验推导，非论文现成结果。
- R2：自创开放空间路线。将未访问认证站和待清源估计中心放入同一开放路线，三起点2-opt，每次执行一个任务后重规划。受在线发现后服务思路启发，未复现JUMP/SNAKE的曲率运动模型。
- R3：原点20频道全无信号时，在任何外站访问前选外环，否则内环；Q4回退原版，公开保留R2的负结果。
- R4：Q4只有在全部待清区域半径不超过原有100米试清尺度时才启用全局路线；加入显式换环索引不变量。
- R5：在半径20−r的认证可清除邻域内近似优化进入+离开距离，使用直线交盘和角度网格/黄金分割，保留旧点候选并复核可行性。
- R6：确定性单节点重插与2-opt组合，保留旧路线；R7：清除段执行既定顺序、扫描站后才重规划，结果退步并回退到R6。所有候选都保存快照，R7未混入当前最佳solver。

“论文启发”不意味着因果归功。真实改变的是上述具体函数；文献中未实现的GP、强化学习、命中集、SOCP、Dubins和能耗模型不承担本题效果解释。R1的覆盖环、R3的无信号分支、R4的就绪条件、R5的认证盘内近似均为本实验设计，原论文只提供相关问题建模视角。

## 4. 完整性与停止证明

Q3：r≤1000的源由原点覆盖。r∈[1000,1800]的源与某一环站极角差≤π/6。站半径为a时，距离平方不超过 f(r)=r²+a²−2ra cos(π/6)。f关于r凸，故只需检查区间端点。a=1124时端点距离562.628556、999.545300米；a=1558.845727时854.400375、900米，均小于1000。两个环都对连续圆域有效；无信号选择哪个环只影响效率。原点无信号只推出源距原点>1000，不能推出全在最边缘；偏心聚簇的退步说明这种信息局限。

换环前现在显式要求所有频道scanned中没有非0站，避免旧索引匹配新坐标。Q4维持原七边形三角剖分覆盖点。每个空间路线包含全部未访问站和已观测未清源；每次外层动作消费一个站，或通过原有限定位/光学兜底清掉一个源，所以外层任务最多22+16=38，不会只重规划而不推进。clear/measure的时间限制守卫和180000秒切换光学覆盖保留。

R5：已知真实源g∈B(c,r)，选点p∈B(c,20−r−10⁻⁶)，则|p−g|≤|p−c|+|c−g|<20。数值优化复核盘内可行性。1000组随机几何检查全部通过只是实现辅助检查，连续可靠性来自三角不等式。有限本地案例全清不替代解析覆盖证明。路径优化没有扩大原定位区域、增加必访站点或改变光学格点覆盖；完整预算边界分析见 [plan.md](plan.md)。

## 5. 实验协议、预算与可复现性

固定评测 LOCAL-v1 的环境、评测脚本、规则、案例和基准保持冻结。每轮先既有单测、冻结散列、79项正常规则，再quick120局，再full2400局；基准取已校验缓存。quick是full的子集；5000–5099固定回归已知，不当作新留出。未按案例ID或测试组在线决策。训练/开发只用重新生成的62000系列，后续验证用63000、64000、65000等明确不同系列，逐个JSON保留。没有下载模型权重，没有训练大模型或用真值教师。

首次开发辅助函数在Q4边缘/原点簇压力场景产生全定向数据，不符合题目混合条件；该批保留为 `r2_development_invalid_mixture.json`，排除出有效证据。修改仅在A1新开发生成脚本中让最后一个源保持全向，所有候选和基准比较均重新运行；冻结生成器和固定案例没有修改。

原用户预算每Agent最多三轮，之后用户因R2→R3持续改善追加授权。停止按主Agent给定的连续两轮full未刷新当前最佳执行；该规则只代表这组有限设计空间的经验停止，不是证明算法或研究方向已经全局收敛。

| 轮次 | Q3秒/源 | 比原版减少 | Q4秒/源 | 比原版减少 | 全清局数 | full现实秒 |
|---|---:|---:|---:|---:|---:|---:|
| 原版 | 306.300434 | — | 570.883371 | — | 2400/2400 | 历史缓存，不比较现实速度 |
| R1 | 292.714541 | 4.4355% | 570.883371 | 0.0000% | 2400/2400 | 26.475 |
| R2 | 276.228217 | 9.8179% | 574.636326 | -0.6574% | 2400/2400 | 18.768 |
| R3 | 272.161671 | 11.1455% | 570.883371 | 0.0000% | 2400/2400 | 29.662 |
| R4 | 272.161671 | 11.1455% | 563.549303 | 1.2847% | 2400/2400 | 26.854 |
| R5 | 272.090541 | 11.1687% | 563.273068 | 1.3331% | 2400/2400 | 36.830 |
| R6 | 271.600919 | 11.3286% | 563.147968 | 1.3550% | 2400/2400 | 27.612 |
| R7 | 273.239020 | 10.7938% | 563.150239 | 1.3546% | 2400/2400 | 25.982 |
| R8 | 270.531505 | 11.6777% | 556.703578 | 2.4838% | 2400/2400 | 25.724 |
| R9 | 271.432619 | 11.3835% | 560.108327 | 1.8874% | 2400/2400 | 26.729 |

所有清除率都保留逐局清除个数/真实源数，真实源数仅在评测层计算。全局均值按每局秒/源再平均，不能把跨局总时间除跨局总源数替代，也不是官方公开的跨案例总分。

### 各轮失败和场景退步

| 轮次 | 问题 | 相比原版退步的场景（负数表示时间降低量为负） |
|---|---|---|
| R1 | Q3 | edge_mixed_min_radius -19.1613%；origin_cluster -6.4854% |
| R1 | Q4 | 无 |
| R2 | Q3 | edge_mixed_min_radius -14.9181% |
| R2 | Q4 | cell500_shared_field -2.3857%；fixed_negative_bias -3.4936%；fixed_positive_bias -1.0622%；origin_cluster -8.0581%；reference_assumed -2.3656%；smooth_shared_field -2.5727% |
| R3 | Q3 | offcenter_cluster -2.4005% |
| R3 | Q4 | 无 |
| R4 | Q3 | offcenter_cluster -2.4005% |
| R4 | Q4 | fixed_positive_bias -0.6551% |
| R5 | Q3 | offcenter_cluster -2.4340% |
| R5 | Q4 | fixed_positive_bias -0.6266% |
| R6 | Q3 | offcenter_cluster -2.4340% |
| R6 | Q4 | fixed_positive_bias -0.8870% |
| R7 | Q3 | offcenter_cluster -5.7397%；origin_cluster -1.2204% |
| R7 | Q4 | fixed_positive_bias -0.8938% |
| R8 | Q3 | offcenter_cluster -2.4669% |
| R8 | Q4 | fixed_positive_bias -0.5798% |
| R9 | Q3 | offcenter_cluster -2.4340% |
| R9 | Q4 | fixed_positive_bias -0.4097% |

所有轮次的异常/不完整行仍在 `case_metrics.json`；若有任何不完整局，不对成功子集做耗时排名。这里列出的全量候选都通过完整性检查；性能退步也完整保留，没有只选表现最好的场景报告。

## 6. 当前最佳版本每场景结果

| 题目 | 场景 | 原版秒/源 | 最佳秒/源 | 时间减少 | 全清 |
|---|---|---:|---:|---:|---:|
| Q3 | cell500_shared_field | 301.665705 | 255.237996 | 15.3904% | 100/100 |
| Q3 | cell50_shared_field | 302.681286 | 255.873313 | 15.4644% | 100/100 |
| Q3 | edge_mixed_min_radius | 317.367453 | 307.565296 | 3.0886% | 100/100 |
| Q3 | exactly10_sources | 358.665224 | 303.872993 | 15.2767% | 100/100 |
| Q3 | exactly16_sources | 257.835329 | 219.210968 | 14.9802% | 100/100 |
| Q3 | fixed_negative_bias | 304.293402 | 257.933154 | 15.2354% | 100/100 |
| Q3 | fixed_positive_bias | 304.989957 | 256.836190 | 15.7886% | 100/100 |
| Q3 | minimum_radius | 310.883745 | 269.697703 | 13.2481% | 100/100 |
| Q3 | offcenter_cluster | 269.533833 | 276.183074 | -2.4669% | 100/100 |
| Q3 | origin_cluster | 343.452658 | 329.443066 | 4.0790% | 100/100 |
| Q3 | reference_assumed | 300.793098 | 256.740757 | 14.6454% | 100/100 |
| Q3 | smooth_shared_field | 303.443521 | 257.783546 | 15.0473% | 100/100 |
| Q4 | cell500_shared_field | 565.196718 | 553.132862 | 2.1345% | 100/100 |
| Q4 | cell50_shared_field | 569.001358 | 554.553563 | 2.5391% | 100/100 |
| Q4 | edge_mixed_min_radius | 613.729392 | 605.922437 | 1.2721% | 100/100 |
| Q4 | exactly10_sources | 705.164228 | 693.391207 | 1.6695% | 100/100 |
| Q4 | exactly16_sources | 442.451926 | 400.716990 | 9.4326% | 100/100 |
| Q4 | fixed_negative_bias | 577.739593 | 569.423794 | 1.4394% | 100/100 |
| Q4 | fixed_positive_bias | 594.833677 | 598.282631 | -0.5798% | 100/100 |
| Q4 | minimum_radius | 583.156049 | 573.463358 | 1.6621% | 100/100 |
| Q4 | offcenter_cluster | 519.793511 | 497.442088 | 4.3001% | 100/100 |
| Q4 | origin_cluster | 541.200985 | 525.488821 | 2.9032% | 100/100 |
| Q4 | reference_assumed | 560.027680 | 545.585233 | 2.5789% | 100/100 |
| Q4 | smooth_shared_field | 578.305342 | 563.039956 | 2.6397% | 100/100 |

开发集表现与固定回归不完全一致，尤其Q4中心代理和Q3偏心聚簇。这不构成官方分布泛化证据。统一新样本验证由主Agent在六路完成后执行，不把其结果返回A1继续调参。

## 7. 证据文件与运行

- 当前最佳：`solver.py`，快照 `experiments/A1_space/snapshots/solver_r8.py`。
- SHA256：`01ef57e64ce910cb50f74eff9fbbd902aefed01c0eb14e7d46b74a03b4e1094e`。
- 实现提交：`51580e981fcde0b40fd6abd2300dff2ab83df475`。
- 全量结果：[results/A1_space_r8_full/summary.json](../../results/A1_space_r8_full/summary.json)，逐局原始结果同目录。
- 版本与依赖：[best.json](best.json)；逐轮判断：[iteration_log.md](iteration_log.md)；方案和证明：[plan.md](plan.md)。
- 逐篇文献：[literature.json](literature.json)；身份元数据与正文散列：`research/source_metadata.json`。原论文PDF、HTML和提取文本仅保留本地忽略缓存，不重新发布全文。

```sh
python -m unittest discover -s tests -v
python evaluate.py --verify-only
python tests/check_nominal.py --package . --out /tmp/A1_nominal_recheck.json
python experiments/A1_space/check_spatial_geometry.py --candidate solver.py --out /tmp/A1_geometry_recheck.json
python evaluate.py --suite full --candidate experiments/A1_space/snapshots/solver_r8.py --out results/A1_reproduce_new_directory
```

求解器仅依赖Python标准库；本工作树没有coverage_points.json，因此两题均使用解析点集。若外部提供该文件，原有点集指纹验证仍必须通过；最佳复现应使用记录的无外部点集配置。HTTP客户端和官方通信未改动，Windows官方演练与正式测试仍未执行。代码、结果已在专属分支分轮提交；最终推送状态以主Agent核验为准。
