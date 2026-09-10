# A3 多干扰源、多频道协同研究实验报告

研究截止与实验日期：2026-09-11。独立分支：`experiments/20260911/a3_coordination`。研究角度：多个目标怎样共享已经付费的移动与检测机会。文献语料10篇：5篇关键章节深读，5篇仅作者摘要发现；不声称领域完整收录。

## 结论

本路线最佳为**第2轮**，保持2400/2400局全部清除、正常退出且无异常：

- 第三问：**306.300434 → 274.141894 秒/源，降低10.4990%**。
- 第四问：**570.883371 → 556.354234 秒/源，降低2.5450%**。

第三轮没有进一步改善，已恢复第2轮代码。最佳代码提交：`a6702a3a5d2a05cad948a7a9d4121d9f9d921b17`；最佳SHA256：`236958ef338808b621690f72ef7c0d637d13ba6d0716d9722ea892f588f73fa3`。快照为`experiments/A3_coordination/snapshots/r2_solver.py`，当前`solver.py`与其相同。完整结果为`results/A3_coordination_r2_full/`。本报告与`best.json`、`iteration_log.md`及逐局结果相互对应。

这些是**冻结LOCAL-v1自建模拟数据的研发结果，非官方模拟器成绩**。24个分题场景中，Q4的`cell500_shared_field`均值退步0.3032%，本报告保留该退步。没有把两题汇成加权总分，也没有将“每源总耗时”误称为每个目标首次清除时刻的平均。

## 1. 任务分析

官方接口只允许enter、measure、clear、exit。不同频道标识不同源；不能读取真实源个数、位置、方向、半径或案例ID。清除源数/真实源总数由评测层计算，求解器不知道分母。最终目标先确保全部清除，再减少每局总虚拟耗时/清除数。

当前基线已经有多目标与搜索站联合安排，并在认证搜索站对多个已知源补测。遗漏的机会在于：定位源A时走到了一个新坐标，基线通常只测A，尚未让B、C等频道利用这个位置。移动100米花20秒，而同坐标增加一次换频道检测花6秒；如果少量补测减少后续定位绕行，可能净节省时间。反过来，未必有信号或已有信息足够时，补测也可能纯粹增加成本。

因此本路线的研究问题是：**如何把为了某个源支付的移动费用摊到多个源上，并限制额外频道检测成本？** 这是对联合移动/感知和多目标信息更新思想的定制实现，不需要为了形式下载大模型，也不从其他五条路线借用策略。

## 2. 调研范围、来源和方法分类

最初两次web搜索连接失败，随后实际使用arXiv API关键词检索、ID元数据核验和PDF正文读取；Crossref仅用于发现。查询词、失败记录、去重编号、作者、版本、读取页码、PDF散列保存在`literature.json`、`research/discovery.json`和`research/download_manifest.json`。PDF下载全部成功，但“下载完整PDF”不意味着“阅读全文”；实际读取范围如下表。

分类采用“改变哪部分决策”这一主轴：

```text
多源协同
├─ 自适应感知价值
│  ├─ 条件边际收益/自适应贪心 → Golovin & Krause
│  └─ 非次模的近似边界 → Fujii & Sakaue（仅摘要）
├─ 联合移动与检测
│  ├─ POMDP及成本收益rollout → Choudhury et al.
│  ├─ 环境场的自适应熵 → Low et al.（仅摘要）
│  └─ 多源RF状态并行更新 → Chen et al. / GyroCopter
├─ 路径与服务机会
│  ├─ 顺序代理收益及感知资源分配 → Ott et al. / ASPO
│  ├─ 区域服务TSP → Nedjati & Vizvári
│  ├─ 均匀圆邻域近似界 → Bercea（仅摘要）
│  └─ 边上的信息采样 → Moon et al. / TIGRIS（仅摘要）
└─ 学习与表示泛化
   └─ 跨地图策略表示 → Rückin et al.（仅摘要）
```

每篇只列一个主要机制归属。不同任务协议不做数字排行榜；没有声称这里某方法是本题SOTA。

## 3. 到底读了哪些文献、带来什么启发

年份取arXiv首次发布日期；不据预印本页面推断会议录用或奖项。下表全部链接为作者原文。对核心论文的问题、方法、效果条件和边界的逐篇笔记另见`research/reading_notes.md`。

| 文献原文 | 作者与年份 | 实际阅读范围 | 核心机制 | 对本题启发 | 是否进入实现 | 未直接采用完整方法的原因 |
|---|---|---|---|---|---|---|
| [Adaptive Submodularity: Theory and Applications in Active Learning and Stochastic Optimization](https://arxiv.org/abs/1003.3967v5) | Daniel Golovin；Andreas Krause；2010 | 核心章节深读；4–7、10–11页；§2、§3定义，Algorithm 1/2，Theorem 5；未阅读全部60页附录 | 以观测历史为条件重新计算动作边际收益，满足自适应单调和自适应次模时才有贪心近似保证。 | 每得到一个频道的新方位后，重新判断其他频道是否还值得测，而不预先固定重复次数。 | R1/R2；Solver.share_observations, Solver.measure, Solver.localize | 本题方位观测可能互补，移动成本依赖历史，未证明自适应次模；绝不宣称1−1/e保证。 |
| [Robot Path Planning by Traveling Salesman Problem with Circle Neighborhood: modeling, algorithm, and applications](https://arxiv.org/abs/2003.06712v1) | Arman Nedjati；Béla Vizvári；2020 | 核心章节深读；1–3、6–8、10–11页；§2.1、两阶段T1/T2、§3、§4 | 先离散区域访问顺序，再优化区域内部访问点。 | 同一坐标可能服务多个目标；要从到源中心转向满足服务条件的区域。 | 未采用 | 论文已知所有圆的位置且求解器耗时高；本题未知位置、区域逐步变化，直接静态TSP不合适。 |
| [Adaptive Informative Path Planning with Multimodal Sensing](https://arxiv.org/abs/2003.09746v1) | Shushman Choudhury；Nate Gruver；Mykel J. Kochenderfer；2020 | 核心章节深读；1、3–8页；§4.1/4.2，Algorithm 1，§5两实验域与表1/2，§6 | 将移动与选择传感器放入同一动作空间，用可行性剪枝与GCB rollout改进POMCP。 | 本题换频道检测有6秒成本，已付的移动费应被多个频道共同利用；观测并非天然免费。 | R1/R2；Solver.share_observations, Solver.measure, Solver.localize | 隐藏状态与噪声先验在官方环境未知；完整POMCP开销及模型偏差不合适本轮。 |
| [Approximate Sequential Optimization for Informative Path Planning](https://arxiv.org/abs/2402.08841v2) | Joshua Ott；Mykel J. Kochenderfer；Stephen Boyd；2024 | 核心章节深读；1、5–8、11–12、16页；顺序重规划说明，§5.1–5.4，§6.1/6.5–6.8，附录B开头 | 用节点代理收益把信息路径分段解为orienteering；执行首段后更新；扩展包含多传感器分配和多Agent共享测量。 | 观测改变后续价值；先固定已付移动产生的停靠点，再在这些点分配频道检测预算。 | R1/R2；Solver.share_observations；R3仅实验未采用 | 论文核心是线性高斯与图路径，本题为有界方位误差、定向截断；未实现凸松弛或DP。 |
| [GyroCopter: Differential Bearing Measuring Trajectory Planner for Tracking and Localizing Radio Frequency Sources](https://arxiv.org/abs/2410.13081v1) | Fei Chen；S. Hamid Rezatofighi；Damith C. Ranasinghe；2024 | 核心章节深读；1、3–8页；§III观测/滤波/FIM/路径规划Algorithm 1，§IV模拟与外场，表I/II | 差分RSSI获得伪方位，粒子滤波并行跟踪多个源；最近源任务规划配合移动中持续获得信息。 | 即使移动只为一个目标服务，其他源的状态仍可同时更新；但本题单频道需逐个付费。 | R1/R2；Solver.share_observations, Solver.measure, Solver.localize | 本题接口不提供RSSI或天线旋转；源静态且误差有界，因此不复制伪方位/粒子滤波。 |
| [Information-Theoretic Approach to Efficient Adaptive Path Planning for Mobile Robotic Environmental Sensing](https://arxiv.org/abs/1305.6129v1) | Kian Hsiang Low；John M. Dolan；Pradeep Khosla；2013 | 扩展：仅摘要；arXiv作者摘要与元数据 | 以信息论改写多机器人自适应采样，研究适应性何时有益。 | 不要想当然把任意跨目标观测称为有收益。 | 未采用 | 本题源频道独立身份且无已知GP场，不拟合连续环境场。 |
| [Improved Bounds for the Traveling Salesman Problem with Neighborhoods on Uniform Disks](https://arxiv.org/abs/1809.07159v1) | Ioana O. Bercea；2018 | 扩展：仅摘要；arXiv作者摘要与元数据 | 分析访问圆邻域与访问圆心的绕行差别。 | 服务区域比服务中心更适合清除半径，但未知源难直接用。 | 未采用 | 均匀圆假设与真实接收半径未知不同。 |
| [Beyond Adaptive Submodularity: Approximation Guarantees of Greedy Policy with Adaptive Submodularity Ratio](https://arxiv.org/abs/1904.10748v1) | Kaito Fujii；Shinsaku Sakaue；2019 | 扩展：仅摘要；arXiv作者摘要与元数据 | 通过自适应次模比拓展贪心保证范围。 | 提醒不应仅凭经验效果宣称有次模保证。 | 未采用 | 尚未推导本题次模比，不据摘要作理论迁移。 |
| [TIGRIS: An Informed Sampling-based Algorithm for Informative Path Planning](https://arxiv.org/abs/2203.12830v2) | Brady Moon；Satrajit Chatterjee；Sebastian Scherer；2022 | 扩展：仅摘要；arXiv作者摘要与元数据 | 采样规划将边上的信息收益纳入评估。 | 信息可能在移动途中产生；本题需要显式停靠检测，不能免费读取整条边。 | 未采用 | 当前无车辆转弯与障碍约束，不引入高维采样框架。 |
| [Towards Map-Agnostic Policies for Adaptive Informative Path Planning](https://arxiv.org/abs/2410.17166v2) | Julius Rückin；David Morilla-Cabello；Cyrill Stachniss；Eduardo Montijano；Marija Popović；2024 | 扩展：仅摘要；arXiv作者摘要与元数据 | 统一不同地图表示以训练可迁移的信息采集策略。 | 策略若依赖开发集空间分布，官方转移可能失效。 | 未采用 | 本路线聚焦跨频道协同，学习路线由其他独立Agent负责；未共享策略。 |

核心来源之间的取舍如下。自适应次模强调每次按观测重算边际价值，但本题方位互补和路径费用不满足已证明的前提，所以不套近似比。AIPPMS更准确地区分感知与移动的成本，然而完整POMCP需要生成模型，官方先验不可得。ASPO提供了固定访问点后分配观测资源的结构，但其线性高斯/GP假设不适用于有界、同址固定的方位误差。区域TSP说明服务区域可以重合，不过本题源位置未知，基线已有清除裕量优化。GyroCopter实际展示了“当前任务追踪一个源，其他源仍在更新”的系统结构，但其RSSI与连续旋转观测不受本题接口支持。

来源阅读中还发现两处需要保留的不确定性：AIPPMS的ISRS正文与表注对试验数写30/50；GyroCopter外场正文总数与分项11+5不一致，而表II为10+5。本报告不依赖这些数量作强证据，也没有将论文中的时间改善数值当成我们的效果。

## 4. 自创方案与实现

**本题中的新代码均为自创启发式；上述论文提供设计问题与取舍启发，不是已经移植的完整算法。**

R1在清除一个源后，对未清除的已发现频道逐一判断补测价值。已付移动的坐标固定，因此补测本身没有新增移动。若该频道最近已有方位点距离不足60米，或者多边形已经能以20米半径包住，就跳过。对剩余目标，用当前可行域中心生成一个假想方位，计算假想剪裁后的最小包围圆半径；预测半径减少至少30米才调用真实measure。该假想方位从不加入实际观测列表或实际多边形。

R2把此机会扩展到单源定位过程中的检测停靠点。`_active_target`记录正在定位的频道；`measure`读取完主目标后触发其他频道补测；`_sharing`阻止补测递归触发自己；`finally`确保退出定位或异常时清理状态。这样只改变频道与时间安排，所有真实信息仍沿原观测更新路径进入各自多边形。

R3尝试改变第一条方位之后的第二个测点：基线已有左右两个候选点，R3用其他频道的预测半径减少之和偏好更有共享价值的一侧。每频道收益截断200米、系数0.20转换成路线距离的软性代理。这个内部代理不是对外成绩。它没有产生更好的full结果，因此最终代码不包含R3。

### 文献→启发→实现→实测链

| 文献依据 | 本题设计推断 | 实现与轮次 | 实测结论 |
|---|---|---|---|
| AIPPMS：移动和感知各自付成本；GyroCopter：多源状态持续更新 | 在已到达的坐标测别的频道，以检测费换后续移动减少 | R1 `localize`→`share_observations` | 两题分别降8.99%和2.42%，全清；24场景无均值退步 |
| Adaptive Submodularity：新观测后重算边际收益；ASPO：重规划/感知资源分配 | 不固定扫所有频道，用当前多边形重估是否值得补测 | R1/R2 `share_observations` 中预测门槛 | 和位置复用一并实现，未单独消融门槛；不能把总收益单独归因于某篇论文 |
| GyroCopter与AIPPMS的交错感知/移动结构 | 定位中间停靠点也应服务其他频道 | R2 `measure`上下文补测 | 相对R1再降Q3 4.630秒/源、Q4 0.692秒/源；Q4一个场景出现轻微回退 |
| ASPO的未来信息代理；TSPN的区域服务视角 | 两个同等服务主目标的测点，选能帮助其他频道的一侧 | R3 `second_point`与`sharing_gain` | 相对R2两题分别增加0.032/0.016秒/源；未采用，不能宣称方案有效 |

R1→R2只增加中间停靠点补测，可以支持这一增量实现的配对比较；尚未将“门槛值”“测量顺序”“信息中心代理”逐项独立消融。没有把文献未实现的POMCP、粒子滤波、凸优化或学习器写成产生本题收益的原因。

## 5. 全清与终止边界

认证搜索点、扫描遍历、16个已清除源上界停止条件、最小包围圆认证清除以及有限光学格点覆盖均保持原有实现。补测既不会删除任何搜索点，也不会仅根据no_signal宣称未知源不存在。每个真实direction仍按原误差上界剪裁，而near仍触发真实clear。追加别的频道不会混合不同目标的位置约束。

R2仅在当前目标有限的定位/恢复流程内增加一个最多20频道的有限扫描；递归锁使补测不能再次触发补测。每次补测不新增移动，虚拟时间达到安全阈值后不再从measure触发新的补测批次，原安全兜底保留。追加观测可以缩小多边形，不取消覆盖证明；若误差模型被违反，原代码继续显式报错而不是接受虚假认证。规则检查与2400局实测全部通过支持当前实现，但并不等于证明官方二进制、联网时延或未知噪声分布必然一致。

## 6. 实验约定、预算和可复现性

冻结manifest、环境、案例、基准与规则文件没有改动。第一二问未改。基准缓存经散列验证后复用，实际full每轮运行2400次候选；quick每轮120次候选，为full子集。每局指标是虚拟总耗时/清除数，跨局按每题1200局算术平均；12场景每场景100局。清除失败的尝试计入耗时，未选择成功子集排除失败开销。

每轮开发前仅实现一个明确配置：训练种子62000–62004×4场景×2题，共40候选局；开发种子63000–63009×4场景×2题，共80候选局。三轮复用了开发数据，因此开发集虽与训练种子分离，**不是最终新留出集**。开发场景为随机、最小半径、边界、原点聚簇，使用项目已有生成函数；不使用固定v1案例ID决策，没有隐藏的回归试参。没有模型训练、权重、外部推理依赖或特权教师。

三轮合计：内层候选360局、quick候选360局、full候选7200局，共**7920局候选运行**；开发对照另运行360局基准，full/quick基准是冻结缓存。所有结果文件保留，用户后来允许只有第2到第3轮持续改善时才追加第4、5轮。本路线R3未刷新R2，不触发延长，按经验停止规则结束；这不等于证明全局最优。最终新样本统一验证由主Agent随后执行，不把它返给本路线继续调参。

| 轮次 | Q3秒/源 | Q3较基准减少 | Q4秒/源 | Q4较基准减少 | full全清 | full现实秒 | 选择 |
|---|---:|---:|---:|---:|---:|---:|---|
| R1 | 278.772056 | 8.9874% | 557.046187 | 2.4238% | 2400/2400 | 31.432 | 保留记录，未作为最终最佳 |
| R2 | 274.141894 | 10.4990% | 556.354234 | 2.5450% | 2400/2400 | 29.617 | 最终最佳 |
| R3 | 274.173562 | 10.4887% | 556.370057 | 2.5423% | 2400/2400 | 28.936 | 保留记录，未作为最终最佳 |

每轮14/14规则单元测试、79/79独立正常规则核验均通过；每轮quick全清120/120，full全清2400/2400，异常为0。完整日志位于`research/rN_tests.txt`、`research/rN_nominal.json`和`results/A3_coordination_rN_*/`。

R3相对R2的差异很小，不作显著退步的统计断言；选择规则要求证明改善，因此保留R2。

## 7. 最佳R2的24个分题场景

正值表示候选平均时间减少；负值为退步。

| 题目 | 场景 | 基准秒/源 | R2秒/源 | 减少比例 | 全清 |
|---|---|---:|---:|---:|---:|
| Q3 | cell500_shared_field | 301.666 | 285.799 | +5.260% | 100/100 |
| Q3 | cell50_shared_field | 302.681 | 286.460 | +5.359% | 100/100 |
| Q3 | edge_mixed_min_radius | 317.367 | 296.231 | +6.660% | 100/100 |
| Q3 | exactly10_sources | 358.665 | 344.928 | +3.830% | 100/100 |
| Q3 | exactly16_sources | 257.835 | 242.168 | +6.077% | 100/100 |
| Q3 | fixed_negative_bias | 304.293 | 285.049 | +6.324% | 100/100 |
| Q3 | fixed_positive_bias | 304.990 | 287.171 | +5.842% | 100/100 |
| Q3 | minimum_radius | 310.884 | 295.150 | +5.061% | 100/100 |
| Q3 | offcenter_cluster | 269.534 | 202.260 | +24.960% | 100/100 |
| Q3 | origin_cluster | 343.453 | 192.325 | +44.002% | 100/100 |
| Q3 | reference_assumed | 300.793 | 286.444 | +4.771% | 100/100 |
| Q3 | smooth_shared_field | 303.444 | 285.718 | +5.841% | 100/100 |
| Q4 | cell500_shared_field | 565.197 | 566.910 | -0.303% | 100/100 |
| Q4 | cell50_shared_field | 569.001 | 556.347 | +2.224% | 100/100 |
| Q4 | edge_mixed_min_radius | 613.729 | 596.573 | +2.795% | 100/100 |
| Q4 | exactly10_sources | 705.164 | 700.848 | +0.612% | 100/100 |
| Q4 | exactly16_sources | 442.452 | 433.176 | +2.097% | 100/100 |
| Q4 | fixed_negative_bias | 577.740 | 577.012 | +0.126% | 100/100 |
| Q4 | fixed_positive_bias | 594.834 | 591.555 | +0.551% | 100/100 |
| Q4 | minimum_radius | 583.156 | 577.886 | +0.904% | 100/100 |
| Q4 | offcenter_cluster | 519.794 | 468.608 | +9.847% | 100/100 |
| Q4 | origin_cluster | 541.201 | 480.474 | +11.221% | 100/100 |
| Q4 | reference_assumed | 560.028 | 554.154 | +1.049% | 100/100 |
| Q4 | smooth_shared_field | 578.305 | 572.708 | +0.968% | 100/100 |

唯一比基准退步的场景是Q4的500米共享分块误差。R1在所有场景均无基准均值回退，因此如果使用者优先要求每个场景都不退步，可同时复核保留的R1；这与本协议按分题总体均值选择R2并不矛盾。

## 8. 改善来自哪里

根据逐案例记录分解移动时间与非移动动作时间：移动时间=距离/5，非移动部分=总虚拟时间−移动时间；先每局除清除数，再求均值。下表每行给基准→R2。

| 题目 | 移动秒/源 | 非移动秒/源 | 每局检测次数 | 每局移动米数 | 每局失败清除尝试 |
|---|---:|---:|---:|---:|---:|
| Q3 | 247.950 → 213.323 | 58.350 → 60.819 | 110.22 → 116.09 | 15777.7 → 13512.0 | 4.224 → 2.627 |
| Q4 | 428.364 → 409.978 | 142.519 → 146.376 | 284.12 → 292.72 | 27144.6 → 25927.6 | 3.328 → 2.612 |

Q3每源移动减少34.627秒，非移动增加2.469秒，净减少32.159秒；Q4移动减少18.386秒，非移动增加3.857秒，净减少14.529秒。结果与“用少量额外频道测量换取更少定位移动”一致，但仍是这一实现整体的本地证据，不能据此声称所有信息指标或所有论文算法都有这个收益。

现实耗时只报告整批本地full所需秒数。基准缓存的现实耗时是历史值，不能和当前候选直接比较机器计算速度；本地函数调用的毫秒级单局时间不能替代官方联网时延。

## 9. 限制与未做事项

- 固定v1已知回归，开发集重复使用；最终泛化需新样本和官方演练。所有改善依赖本地源分布与误差场假设。
- 预测收益用可行域中心单点代替后验分布，也没有对定向信号可见性建立先验。Q4收益较小且一个误差场回退，说明这一代理仍有边界。
- 30米门槛、60米新视点距离是本轮固定启发参数，没有宣称最优。R3新代理未改善，已完整保留负结果。
- 论文只深读所列章节；另5篇只做摘要发现。没有声称穷尽所有文献、重现原论文或获得SOTA。
- 未更改HTTP、重试、并发和实际官方时限逻辑，未启动官方Windows模拟器，也未伪造官方日志。

## 10. 复现与交付

在本工作树使用Python 3.12.14或兼容的3.10+版本，仅标准库：

```sh
python -m unittest discover -s tests -v
python evaluate.py --verify-only
python tests/check_nominal.py --package . --out results/A3_new_nominal.json
python evaluate.py --suite quick --candidate experiments/A3_coordination/snapshots/r2_solver.py --out results/A3_reproduce_quick
python evaluate.py --suite full --candidate experiments/A3_coordination/snapshots/r2_solver.py --out results/A3_reproduce_full
```

输出目录必须不存在；已交付的原结果不覆盖。辅助开发复现脚本是`experiments/A3_coordination/dev_evaluate.py`，轮次摘要脚本是`summarize_round.py`。最佳求解器无外部模块/权重/配置文件依赖；认证点由`certified_points`在代码中生成，工作树没有`coverage_points.json`。`best.json`记录绝对/相对快照路径、代码SHA256、结果路径、分题成绩、完整清除数、候选轮数、代码提交及依赖清单。

交付包含`report.md`、`literature.json`、`plan.md`、`iteration_log.md`、`best.json`，3份候选快照、3轮全部开发/quick/full结果、阅读笔记和PDF下载散列。最终`solver.py`为R2；所有更新只提交到A3专属分支，主分支与其他Agent代码未改。
