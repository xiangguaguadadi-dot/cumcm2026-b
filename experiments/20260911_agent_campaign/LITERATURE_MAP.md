# 六路线文献阅读与实现索引

共 58 条按路线记录的阅读条目，按 arXiv 编号或标准化题名去重为 49 个来源。同一论文在不同路线的阅读范围分别保留；这些数字不表示每篇均全文深读，也不表示领域覆盖完整。

以下内容来自各路线的实际阅读清单。主协调审阅了这些清单、完整报告和代码差异，没有把逐篇原文全部重新阅读一遍。本索引用于检索“读了哪里、受到什么启发、进入了哪里”；原论文证据、本题各轮结果、未采用理由与实验支持边界见对应完整报告。

## A1_space

9 个来源，其中 6 个标为关键正文阅读。[该路线完整报告](https://github.com/xiangguaguadadi-dot/cumcm2026-b/blob/3046b9e86fdb7ee2ff9186593c48256cf00940ef/experiments/A1_space/report.md)。

### 1. [Environmental Sampling with the Boustrophedon Decomposition Algorithm](https://arxiv.org/abs/2207.06209)

实际阅读范围（core_sections）：PDF 第 2–5、7–8 页：§II–IV、图6–9及§V结果、§VI开头；摘要。未通读参考文献与全部附图。

启发：应先保证检测覆盖，再优化停点和真实行程；不能只比较扫描节点数量。

实现或未采用记录：R1/R3 certified_points、default_points；采用原则，未实现论文分解算法。

本题实验支持与边界：R1 Q3均值降低4.4355%但边缘和原点簇退步；R3自创观测分支后Q3降低11.1455%。支持本题覆盖/行程分离设计，不检验论文采样插值算法。

未采用或选择理由：本题是无障碍圆域、离散信号探测、有最小接收半径；没有必要栅扫每个小像素。

### 2. [A Closer Cut: Computing Near-Optimal Lawn Mowing Tours](https://arxiv.org/abs/2211.05891)

实际阅读范围（core_sections）：PDF 第 3–5 页（§1.3、§2证明）；第 7 页 §4–4.1、第 8 页 §4.3；第12页图15。未通读所有几何证明和全部实验。

启发：看似覆盖的有限样本不足以保证连续区域覆盖；本题每个新点集需要解析证明。

实现或未采用记录：R1/R3 六环站凸函数端点证明；不是该论文的原始对偶或 SOCP 求解器。

本题实验支持与边界：R1/R3两套环均有连续覆盖证明且full全清；没有路径下界或最优差距，实验不支持近似比声明。

未采用或选择理由：论文移动中持续割草，本题移动中不可检测；见证网格解还需要覆盖认证，且这里圆域对称性允许直接解析设计。

### 3. [Constant-Factor Approximation for TSP with Disks](https://arxiv.org/abs/1506.07903)

实际阅读范围（core_sections）：PDF 第2–4页：相关工作、定理1、§2几何命中集、算法总览和§3预处理开头；摘要。未逐行验证后续近似证明。

启发：访问一个区域与访问其中心不同；必须区分路由的估计中心和真正清除位置。

实现或未采用记录：R2/R3 spatial_next_task 的中心代理；R5 route_clear_point 在20-r的认证可清除圆盘内优化预测的进入+离开距离。未实现原论文几何命中集算法。

本题实验支持与边界：R2 Q4退步0.6574%，暴露中心代理限制；R5比R4两题分别减少0.0711/0.2762秒每源，进入最佳；不归功于未实现的命中集算法。

未采用或选择理由：当前源只由有界误差楔形限制，不是已知圆盘；本文的任意圆盘近似与本题在线未知目标不同。

### 4. [Online Coverage Planning for an Autonomous Weed Mowing Robot with Curvature Constraints](https://arxiv.org/abs/2111.10462)

实际阅读范围（core_sections）：PDF 第2–7页：任务定义、§V界、§VI两算法和伪代码、§VII模拟、§VIII田野实验与§IX。另读摘要。未通读末页参考文献。

启发：同时规划搜索站与已发现目标，避免完成所有搜索后再整圈返回清除；但本题必须保留所有待完成任务。

实现或未采用记录：R2/R3 spatial_next_task 和 run：全局开放路径逐动作重规划，为自创简化，并非复现 JUMP/SNAKE。 R7检验按既定清除段执行、到新扫描站才重规划的稳定性；与论文“执行子路径时不再搜索下一子路径”的描述相关，但为本题自创事件边界。

本题实验支持与边界：R2比R1 Q3变好而Q4变坏；R3回退Q4。R7固定执行段比R6两题均变慢，未采用；只支持本实验中逐动作重规划的相对取舍。

未采用或选择理由：机器狗无 Dubins 转弯半径约束，信号不能边走边测且不直接给准确目标位置；禁止采用 R-SNAKE 的漏清取舍。

### 5. [Informative Path Planning with Guaranteed Estimation Uncertainty](https://arxiv.org/abs/2602.05198)

实际阅读范围（core_sections）：PDF 第3–5页：§III–V、单点方差条件、单调性、二值覆盖矩阵、GreedyCover 和 GCB；第7页 SRTM 实验及ASV段落开头。未读全部附录证明。

启发：点集选择与访问顺序不能割裂；覆盖是硬约束，距离是优化量。

实现或未采用记录：R1 点集与 R2/R3 路由分轮检验；未实现 GP、矩阵覆盖或 GCB 比值规则。

本题实验支持与边界：R1/R2分别测试覆盖点和路径，存在场景取舍；因未实现GP/GCB，无关于原论文算法效果的本题实验证据。

未采用或选择理由：本题只给误差有界且同址固定，不能把未知跨位置误差强行当作可信 GP；先验方差达标也不等于未知源全部检测。

### 6. [Improved Bounds for the Traveling Salesman Problem with Neighborhoods on Uniform Disks](https://arxiv.org/abs/1809.07159)

实际阅读范围（discovery）：arXiv 摘要及作者元数据；下载PDF并核对首页题名作者，未深读正文。

启发：提醒中心近似有额外路程，不能把中心 TSP 看成真实服务路径。

实现或未采用记录：未直接进入代码；对 R2 中心代理风险的背景核对。

本题实验支持与边界：未直接进入实现；没有本题因果/复现实验，只有中心代理风险背景。

未采用或选择理由：不直接解决未知目标、方向丢信号与在线定位，先读更一般的命中集路线。

### 7. [Path Planning for Spot Spraying with UAVs Combining TSP and Area Coverages](https://arxiv.org/abs/2408.08001)

实际阅读范围（core_sections）：追加深读 PDF 第3–5页 §3.1–3.3 开头：成本分解条件、NN/DENN与H1–H4；第6页 §4实验设置和结果讨论。此前仅摘要，扩展授权后补读正文。

启发：改进开放路径时，可以把节点移除-重插与2-opt结合；同时不能把只优化代理路径长度当真实任务耗时最优。

实现或未采用记录：R6：spatial_next_task 内 reinsert 对当前路线穷举单节点重插，再2-opt，并保留原2-opt路线。属于H2思想的确定性改编，非论文10秒随机采样复现。R6 full Q3/Q4均改善；进入当前最佳。

本题实验支持与边界：R6比R5 Q3减少0.4896、Q4减少0.1251秒每源，full全清并进入最佳；开发Q3曾退步，不能据固定状态代理非增推出全过程非增。

未采用或选择理由：本题是点源定位，不是边界已知的喷洒区域；现有无障碍定位器无需其障碍连接算法。

### 8. [Energy-aware Multi-UAV Coverage Mission Planning with Optimal Speed of Flight](https://arxiv.org/abs/2402.10529)

实际阅读范围（discovery）：arXiv 摘要、元数据与PDF首页（RA-L accepted 标注）；未深读正文。

启发：本题目标也应直接使用官方虚拟时间；移动、换频、检测、清除都要计入。

实现或未采用记录：未直接进入代码；保留冻结官方口径统计。

本题实验支持与边界：未实现能耗和速度控制，无算法效果实验；官方计时分项只是评测口径。

未采用或选择理由：机器人速度固定5m/s、只有一只且题面未给电量目标，能量控制不适用。

### 9. [Bounomodes: the grazing ox algorithm for exploration of clustered anomalies](https://arxiv.org/abs/2507.06960)

实际阅读范围（discovery）：arXiv 摘要与元数据、PDF首页；未深读强化学习设置。

启发：观测可以触发不同空间策略，但推断分布不能替代未观测区域的覆盖证书。

实现或未采用记录：R3 仅受原则启发：无信号触发两个已证明覆盖点集的切换；没有强化学习。

本题实验支持与边界：R3保留解析覆盖分支且Q3改善，偏心簇仍退步；未训练RL，不能视为Bounomodes复现。

未采用或选择理由：A1 专注空间几何；在三轮预算下用明确可审计的观测分支更合适，没有训练模型或借用其他 Agent 的学习策略。

## A2_information

9 个来源，其中 4 个标为关键正文阅读。[该路线完整报告](https://github.com/xiangguaguadadi-dot/cumcm2026-b/blob/afec4f08d41198f382408d05aad3c8f95f2d457c/experiments/A2_information/report.md)。

### 1. [Optimization-based Control for Bearing-only Target Search with a Mobile Vehicle](https://arxiv.org/abs/1908.00380)

实际阅读范围（core）：正文 p.1–4 的 I–III；p.5 的 IV-A 估计器；p.7–9 的 VI–VII 仿真与结论。不是全文深读，附录证明未完整阅读。

启发：按任务完成时间评价观测，不把交会角或估计方差当最终目标。

实现或未采用记录：部分原则进入 r1/r2/r3 的 second_point；不是该论文控制器复现。用虚拟秒而不是论文无量纲加权目标。

相关轮次：round: 1；candidate: candidates/r1_solver.py；results: ../../results/A2_information_r1_full；round: 2；candidate: candidates/r2_solver.py；results: ../../results/A2_information_r2_full；round: 3；candidate: candidates/r3_solver.py；results: ../../results/A2_information_r3_full

本题实验支持与边界：R1 Q3改善2.1289%但Q4退步1.4152%；R2缓和Q4退步而未优于基准；R3关闭Q4主动测点。它支持任务模型需要观测失效分支的局部经验，不是原论文算法复现或单篇论文的因果归因。

未采用或选择理由：未用 Dubins 模型、递归最小二乘、CRLB权重或GPS-free控制器；本题动作和可靠性要求不同。

### 2. [Set-Membership Localization via Range Measurements](https://arxiv.org/abs/2603.04867)

实际阅读范围（core）：正文 p.1–4 问题/相关工作；p.7–10 的第3节；p.13–17 的第5节；p.19–20实验设置；p.23–24外点讨论/结论。第4节SDP推导和全部数值表未完整深读。

启发：保留“用于决策的点/分布”和“用于全清证明的外包集合”两层；研究整个可行域允许的最近清除点。

实现或未采用记录：r1–r10保留外包证书；r3全顶点清除动作、r4/r5有效切面、r6全向无信号排除、r7假想点筛选、r8光学失败排除、r9两次约束传播、r10预测后验接收上界，均是本题自创几何或规划步骤，不是论文SOCP复现。R9和R10均未替换最终R8。

相关轮次：round: 1；candidate: candidates/r1_solver.py；results: ../../results/A2_information_r1_full；round: 3；candidate: candidates/r3_solver.py；results: ../../results/A2_information_r3_full；round: 4；candidate: candidates/r4_solver.py；results: ../../results/A2_information_r4_full；round: 5；candidate: candidates/r5_solver.py；results: ../../results/A2_information_r5_full；round: 6；candidate: candidates/r6_solver.py；results: ../../results/A2_information_r6_full；round: 7；candidate: candidates/r7_solver.py；results: ../../results/A2_information_r7_full；round: 8；candidate: candidates/r8_solver.py；results: ../../results/A2_information_r8_full；round: 9；candidate: candidates/r9_solver.py；results: ../../results/A2_information_r9_full；round: 10；candidate: candidates/r10_solver.py；results: ../../results/A2_information_r10_full

本题实验支持与边界：R3首次两题均值优于基准；R4改善Q3但Q4小幅退步，压力开发暴露计算退化；R5控制复杂度；R6与R7继续刷新Q3，R7增益极小；R8两题均值改善到285.86670335/568.44941153。R9为285.95192367/568.40397853，两题取舍，严格最佳仍R8。多步骤相继迭代而非单因素独立消融，不把累计改进归因于论文。 R10的1000个合成几何组合中52个预测被收紧且全部保留合法目标；独立开发120局及full2400局的任务指标均与R8逐局一致。更紧的预测集合没有带来本轮任务收益，因此回退R8；没有用更多参数试跑弥补无收益。

未采用或选择理由：不新增距离传感器，不实现差分距离方程或SOCP/SDP；现有方位半平面交已更直接。

### 3. [MEXGEN: An Effective and Efficient Information Gain Approximation for Information Gathering Path Planning](https://arxiv.org/abs/2405.02605)

实际阅读范围（core）：正文 p.1–5 的 I–III 及 IV 实验设置；p.6–8 的实验结果、运行时间、场地试验与结论。不是完整复现；尾页参考文献只用于定位。

启发：不能把多边形中心当唯一未来真值；有限求积考虑多个假想目标，并逐一推演后验。

实现或未采用记录：r1/r2/r3 的 belief_quadrature 和 predicted_polygon 受该区分启发；采用多假设显式推演，不是MEXGEN平均观测，也未声称继承其理论界或加速比。 R7对规划假想点做观测一致性筛选，R10使预测方向后验纳入接收上界，仍不代表精确后验；R10未进入最终R8。

相关轮次：round: 1；candidate: candidates/r1_solver.py；results: ../../results/A2_information_r1_full；round: 2；candidate: candidates/r2_solver.py；results: ../../results/A2_information_r2_full；round: 3；candidate: candidates/r3_solver.py；results: ../../results/A2_information_r3_full；round: 7；candidate: candidates/r7_solver.py；results: ../../results/A2_information_r7_full；round: 10；candidate: candidates/r10_solver.py；results: ../../results/A2_information_r10_full

本题实验支持与边界：R1 Q3改善2.1289%但Q4退步1.4152%；R2缓和Q4退步而未优于基准；R3关闭Q4主动测点。它支持任务模型需要观测失效分支的局部经验，不是原论文算法复现或单篇论文的因果归因。 R7只比R6快0.0057839893秒/源，Q4相同，这一极小差异不足以称稳健改进。 R10的1000个合成几何组合中52个预测被收紧且全部保留合法目标；独立开发120局及full2400局的任务指标均与R8逐局一致。更紧的预测集合没有带来本轮任务收益，因此回退R8；没有用更多参数试跑弥补无收益。

未采用或选择理由：不直接平均方位、不引入Bernoulli粒子滤波或RSS模型；其观测/动力学与本题不同。

### 4. [Hindsight is Only 50/50: Unsuitability of MDP based Approximate POMDP Solvers for Multi-resolution Information Gathering](https://arxiv.org/abs/1804.02573)

实际阅读范围（core）：正文 p.1–5 的 I–V，尤其p.3–4信息价值定义/定理与tiger反例；最后结论/参考文献未深读。

启发：局部代理必须评估观测后的多边形变化，不能把假想真位置直接当观测后已知状态；也不能只计算几何靠近。

实现或未采用记录：进入r1–r3设计审查与 second_point 的 posterior 分支；未实现作者MDP/POMDP算法。

相关轮次：round: 1；candidate: candidates/r1_solver.py；results: ../../results/A2_information_r1_full；round: 2；candidate: candidates/r2_solver.py；results: ../../results/A2_information_r2_full；round: 3；candidate: candidates/r3_solver.py；results: ../../results/A2_information_r3_full

本题实验支持与边界：R1 Q3改善2.1289%但Q4退步1.4152%；R2缓和Q4退步而未优于基准；R3关闭Q4主动测点。它支持任务模型需要观测失效分支的局部经验，不是原论文算法复现或单篇论文的因果归因。

未采用或选择理由：不构建连续多源全状态POMDP树，计算和建模成本不适合本轮小范围改动。

### 5. [Improving D-Optimal Sensor Placement for Bearing-Only Localization via Maximum-Entropy Reweighting](https://arxiv.org/abs/2605.11116)

实际阅读范围（extended）：正文 p.1–4 摘要、I、II 问题/FIM/Dirac-at-mean重加权推导和求解器；未深读后续实验与全部结论。

启发：FIM依赖选用的分布；“更尖的belief”不是免费新信息。

实现或未采用记录：未进入最终代码，仅作为竞争与不采用证据。

本题实验支持与边界：没有实现或实验，不对本题改进作效果归因；仅承担竞争方案和未采用理由。

未采用或选择理由：不希望在首个方位的长楔形上人为强化中心假设；纯FIM与20m清除任务不直接对齐。

### 6. [Optimal Spatial-Temporal Triangulation for Bearing-Only Cooperative Motion Estimation](https://arxiv.org/abs/2310.15846)

实际阅读范围（extended）：正文 p.1–2 摘要与引言；没有把后续算法或收敛证明当作已深读。

启发：几何约束应显式进入估计，单方位秩缺失不能靠重复同址测量消除。

实现或未采用记录：未新增实现。现有多边形交已经显式保留几何。

本题实验支持与边界：没有实现或实验，不对本题改进作效果归因；仅承担竞争方案和未采用理由。

未采用或选择理由：静态单机器狗不存在多机一致性和动态速度估计需求。

### 7. [Adaptive Information Gathering via Imitation Learning](https://arxiv.org/abs/1705.07834)

实际阅读范围（extended）：正文 p.1 摘要与引言；算法、理论界、实验未深读。

启发：若离线训练应严格分离教师真值和在线可用特征。

实现或未采用记录：没有训练模型，没有进入代码。

本题实验支持与边界：没有实现或实验，不对本题改进作效果归因；仅承担竞争方案和未采用理由。

未采用或选择理由：A2先检验可审查的低维主动观测机制；未训练全知教师或额外策略模型，避免引入本轮未核查的教师信息动作与分布迁移问题。

### 8. [Quantization and Stochastic Control of Trajectories of Underwater Vehicle in Bearings-only Tracking](https://arxiv.org/abs/1703.09924)

实际阅读范围（extended）：正文 p.1 摘要与引言；后续量化算法/实验未深读。

启发：后验与可见性使完整随机规划维度迅速增加，局部短视预测需明确边界。

实现或未采用记录：未进入代码。

本题实验支持与边界：没有实现或实验，不对本题改进作效果归因；仅承担竞争方案和未采用理由。

未采用或选择理由：不为了框架完整性增加高维MDP；本轮需要清楚因果的局部策略比较。

### 9. [Bearing-Only Navigation with Field of View Constraints](https://arxiv.org/abs/2009.07308)

实际阅读范围（extended）：正文 p.1 摘要与引言；稳定性证明/控制器公式未深读。

启发：高信息的测点若观测不可见，预期价值就不存在。

实现或未采用记录：概念提醒进入r2的不可见分支；未实现论文向量场。

相关轮次：round: 2；candidate: candidates/r2_solver.py；results: ../../results/A2_information_r2_full

本题实验支持与边界：仅概念提醒进入R2；Q4从578.96236624降为574.81712193，但仍慢于570.88337144基准，因此R3禁用Q4该规划器。没有复现论文控制器。

未采用或选择理由：不能把相机视场约束公式直接套到发射半平面。

## A3_coordination

10 个来源，其中 5 个标为关键正文阅读。[该路线完整报告](https://github.com/xiangguaguadadi-dot/cumcm2026-b/blob/f8f249a80f64341aceffc4c960376bd7bb08656b/experiments/A3_coordination/report.md)。

### 1. [Adaptive Submodularity: Theory and Applications in Active Learning and Stochastic Optimization](https://arxiv.org/abs/1003.3967v5)

实际阅读范围（core）：4–7、10–11页；§2、§3定义，Algorithm 1/2，Theorem 5；未阅读全部60页附录

启发：每得到一个频道的新方位后，重新判断其他频道是否还值得测，而不预先固定重复次数。

实现或未采用记录：share_observations：预测半径改善筛选，仅借鉴思想，未实现贝叶斯期望或论文算法。

相关轮次：1；2

本题实验支持与边界：正文证明在明确概率与次模假设下的保证；非本题实验。

未采用或选择理由：本题方位观测可能互补，移动成本依赖历史，未证明自适应次模；绝不宣称1−1/e保证。

### 2. [Adaptive Informative Path Planning with Multimodal Sensing](https://arxiv.org/abs/2003.09746v1)

实际阅读范围（core）：1、3–8页；§4.1/4.2，Algorithm 1，§5两实验域与表1/2，§6

启发：本题换频道检测有6秒成本，已付的移动费应被多个频道共同利用；观测并非天然免费。

实现或未采用记录：share_observations：无新增移动的跨频道检测；用半径减少代理信息价值，未实现POMCP。

相关轮次：1；2

本题实验支持与边界：搜索救援与ISRS两模拟域支持联合决策；计算约6秒/步，论文表2与正文试验数描述有30/50差异，不将其数值迁移到本题。

未采用或选择理由：隐藏状态与噪声先验在官方环境未知；完整POMCP开销及模型偏差不合适本轮。

### 3. [GyroCopter: Differential Bearing Measuring Trajectory Planner for Tracking and Localizing Radio Frequency Sources](https://arxiv.org/abs/2410.13081v1)

实际阅读范围（core）：1、3–8页；§III观测/滤波/FIM/路径规划Algorithm 1，§IV模拟与外场，表I/II

启发：即使移动只为一个目标服务，其他源的状态仍可同时更新；但本题单频道需逐个付费。

实现或未采用记录：share_observations与后续每次定位停靠点补测；不改信号模型、无硬件旋转。

相关轮次：1；2

本题实验支持与边界：模拟与外场证据；正文15次飞行拆分11+5，表II为10+5，存在计数不一致，故不使用其试验量作强证据。

未采用或选择理由：本题接口不提供RSSI或天线旋转；源静态且误差有界，因此不复制伪方位/粒子滤波。

### 4. [Approximate Sequential Optimization for Informative Path Planning](https://arxiv.org/abs/2402.08841v2)

实际阅读范围（core）：1、5–8、11–12、16页；顺序重规划说明，§5.1–5.4，§6.1/6.5–6.8，附录B开头

启发：观测改变后续价值；先固定已付移动产生的停靠点，再在这些点分配频道检测预算。

实现或未采用记录：share_observations：每次调用基于当前多边形重估；只是设计启发。

相关轮次：1；2

本题实验支持与边界：网格与GP设置，有120秒算法预算，多种目标分别比较；与本地秒/源不能直接比。

未采用或选择理由：论文核心是线性高斯与图路径，本题为有界方位误差、定向截断；未实现凸松弛或DP。

### 5. [Information-Theoretic Approach to Efficient Adaptive Path Planning for Mobile Robotic Environmental Sensing](https://arxiv.org/abs/1305.6129v1)

实际阅读范围（extended）：arXiv作者摘要与元数据

启发：不要想当然把任意跨目标观测称为有收益。

实现或未采用记录：未实现

本题实验支持与边界：仅摘要发现。

未采用或选择理由：本题源频道独立身份且无已知GP场，不拟合连续环境场。

### 6. [Improved Bounds for the Traveling Salesman Problem with Neighborhoods on Uniform Disks](https://arxiv.org/abs/1809.07159v1)

实际阅读范围（extended）：arXiv作者摘要与元数据

启发：服务区域比服务中心更适合清除半径，但未知源难直接用。

实现或未采用记录：未实现

本题实验支持与边界：仅摘要发现，不将近似界用于本题。

未采用或选择理由：均匀圆假设与真实接收半径未知不同。

### 7. [Beyond Adaptive Submodularity: Approximation Guarantees of Greedy Policy with Adaptive Submodularity Ratio](https://arxiv.org/abs/1904.10748v1)

实际阅读范围（extended）：arXiv作者摘要与元数据

启发：提醒不应仅凭经验效果宣称有次模保证。

实现或未采用记录：未实现

本题实验支持与边界：仅摘要发现，不将作者结果作为深读结论。

未采用或选择理由：尚未推导本题次模比，不据摘要作理论迁移。

### 8. [Robot Path Planning by Traveling Salesman Problem with Circle Neighborhood: modeling, algorithm, and applications](https://arxiv.org/abs/2003.06712v1)

实际阅读范围（core）：1–3、6–8、10–11页；§2.1、两阶段T1/T2、§3、§4

启发：同一坐标可能服务多个目标；要从到源中心转向满足服务条件的区域。

实现或未采用记录：第一轮不引入新路由；现有clear_standoff已覆盖部分思想，保留为竞争路线。

本题实验支持与边界：论文12/20圆实例分别报告500/2400秒，非同平台比较；不能据此宣称算法优劣。

未采用或选择理由：论文已知所有圆的位置且求解器耗时高；本题未知位置、区域逐步变化，直接静态TSP不合适。

### 9. [TIGRIS: An Informed Sampling-based Algorithm for Informative Path Planning](https://arxiv.org/abs/2203.12830v2)

实际阅读范围（extended）：arXiv作者摘要与元数据

启发：信息可能在移动途中产生；本题需要显式停靠检测，不能免费读取整条边。

实现或未采用记录：未实现

本题实验支持与边界：仅摘要发现，不采用摘要中的提升数字。

未采用或选择理由：当前无车辆转弯与障碍约束，不引入高维采样框架。

### 10. [Towards Map-Agnostic Policies for Adaptive Informative Path Planning](https://arxiv.org/abs/2410.17166v2)

实际阅读范围（extended）：arXiv作者摘要与元数据

启发：策略若依赖开发集空间分布，官方转移可能失效。

实现或未采用记录：未实现

本题实验支持与边界：仅摘要发现。

未采用或选择理由：本路线聚焦跨频道协同，学习路线由其他独立Agent负责；未共享策略。

## A4_directional

10 个来源，其中 4 个标为关键正文阅读。[该路线完整报告](https://github.com/xiangguaguadadi-dot/cumcm2026-b/blob/bfe33bca51946380000084b52584fce45eac3ba9/experiments/A4_directional/report.md)。

### 1. [Probabilistic Radio-Visual Active Sensing for Search and Tracking](https://arxiv.org/abs/2011.10474v2)

实际阅读范围（core）：正文PDF第1–3页；第5–6页数值实验、表I与结论；第4页只读部分定理，不声称完整校验全部证明。

启发：有/无信号都更新位置、发射方向、接收半径联合假设；不能把无信号直接改成位置排除。RF与光学各有边界，应成本敏感切换。

实现或未采用记录：round: R1；functions: visibility_hypotheses；predicted_visibility；second_point；rescue_bearing；role: 原创简化迁移：离散位置/方向与解析半径积分，仅排序，不复现论文运动粒子模型；round: R2–R3；functions: rescue_bearing；optical_points；optical_route；role: RF/光学互补启发；R2提前有限光学覆盖，R3由位置假设选择完整路线，均已完成开发与full；round: R4；functions: visibility_hypotheses；clear；role: 失败clear只更新离散位置权重的自拟消融；full退步，最终未采用；round: R6；functions: rescue_bearing；role: 用同一可见性估计门控自拟镜像点；小幅full改善但三个场景退步；round: R7；functions: expected_optical_time；rescue_bearing；role: 近似RF/光学成本切换；full退步，最终未采用

本题实验支持与边界：R1 Q4较原版改善0.32064%，但5/12场景退步；R2、R3改善，R4、R7失败，R6仅小幅均值改善。支持本地排序/模态互补的用途，不证明论文似然在本题校准，也不把逐轮组合差异归因于单一论文。

### 2. [Sequential Bayesian Optimization for Adaptive Informative Path Planning with Multimodal Sensing](https://arxiv.org/abs/2209.07660v1)

实际阅读范围（core）：PDF第1–5页，§III–IV、算法1、ISRS表I与p=1退步说明；第5页Rover设置；未完整阅读第6–8页。

启发：选择一次RF恢复或一段有限光学覆盖，比较真实移动/5+动作耗时；不无限追求定位信息。

实现或未采用记录：round: R1；functions: rescue_bearing；role: 移动/检测成本除以预测可见概率的自拟近似排序；未复现MCTS；round: R2–R3；functions: rescue_bearing；optical_route；role: 以任务成本选择光学搜索及两条完整路线；成本模型为自己的实现；round: R6；functions: rescue_bearing；role: 以预测成本门控镜像一次恢复；自拟有限动作选择；round: R7；functions: expected_optical_time；rescue_bearing；role: 显式RF/光学预计成本比较消融；full退步，不纳入R6；round: R8；functions: rescue_bearing；role: 用移动/检测成本决定是否进入已可见点连线；凸性方案自己的推导，full退步

本题实验支持与边界：成本要与信息共同考虑的原则得到实现，但复杂成本近似R7和保证可见的R8均失败；不能声称更复杂规划必然更快。R2对照含snake端点变化，非单变量因果消融。

### 3. [Set-Membership Localization via Range Measurements](https://arxiv.org/abs/2603.04867v1)

实际阅读范围（core）：PDF第1–3页；§3.1–3.3第7–10页；§5.1及5.1.1第14–15页；§7第19–20页实验设置。抽取含OCR错字，未完整核验SDP公式及全部证明。

启发：保留全部有界测向多边形作为确定性证据；离散可见性模型永不裁掉这个多边形；小多边形可用保守光学格点覆盖。

实现或未采用记录：round: R1–R8；functions: add_bearing；cover_polygon；run；role: 基准已有有界误差外包/覆盖/停止证据，全部保留；未移植论文距离差分或SDP；round: R2–R3；functions: optical_points；optical_route；role: 在小集合内提前覆盖并重排；完整性由本题网格距离证明；round: R5、R8；functions: rescue_bearing；role: 接收圆盘/半圆的凸性是本题直接数学推导；受集合思维启发，不是这篇论文提出的恢复算法

本题实验支持与边界：八轮所有本地回归全清且原几何证书保留；R5改善、R8退步，说明正确几何性质不必然带来效率提升。有限样本不替代可靠性证明。

### 4. [Trajectory Optimization in Single and Dual-UAV Bearing-Only Target Localization](https://arxiv.org/abs/2606.09188v1)

实际阅读范围（core）：PDF第1–5页内导言、§3.1–3.2 FIM/logdet机制段落；§4.1第9–10页与表2；§5第13–15页。未逐页通读整篇，未深读§3.3–3.4优化器细节与双机全部图表。

启发：候选应保持交会几何；只移动到更可见的同侧并不必然缩小范围，因此不取消横向baseline。消融必须分开，不能只报组合最好。

实现或未采用记录：round: R1；functions: second_point；role: 保留原±横向点，只用可见性改变左右选择；未复现FIM/PSO；round: R5–R8；functions: rescue_bearing；role: 交会几何只作设计警示；折返/镜像/凸包点均是自己的启发式，未复现其FIM或PSO

本题实验支持与边界：R1改变第二点左右选择但保留横向基线；R8保证可见而full退步，符合信息几何不能只看可见性的警示。未做本题FIM/PSO对照，不把该现象当作论文机制的因果验证。

### 5. [TIGRIS: An Informed Sampling-based Algorithm for Informative Path Planning](https://arxiv.org/abs/2203.12830v2)

实际阅读范围（extended）：PDF第1–2页导言、贡献和相关工作；未深读算法与实验。

启发：将回程/后续访问成本考虑入动作，但停止检测点才有观测。

实现或未采用记录：round: None；functions: ；role: 未采用全局采样树；本路线可见性问题更直接，且边观测假设不符

本题实验支持与边界：未实现对应论文算法，因此没有本题实验支持；未采用理由见implementation与limitations。

### 6. [Bayesian Optimal Active Search and Surveying](https://arxiv.org/abs/1206.6406v1)

实际阅读范围（extended）：PDF第1–2页任务定义与导言；仅浏览部分后续段落，不标为深读。

启发：优化清除任务耗时而非定位均方误差或模型熵。

实现或未采用记录：round: R1–R3；functions: ；role: 决策/评价原则采用；不复现分类器规划器

本题实验支持与边界：只采用任务目标的概念性区分，没有单独算法消融，不能分配本题提升归因。

### 7. [Discrete Army Ant Search Optimizer-Based Target Coverage Enhancement in Directional Sensor Networks](https://arxiv.org/abs/2307.00696v1)

实际阅读范围（extended）：PDF第1页及第2页开头的系统模型；未深读后半优化器和实验。

启发：扇区几何要显式建模，但不能把本題发射方向当成可调决策变量。

实现或未采用记录：round: None；functions: ；role: 未采用：信息和控制权限不同

本题实验支持与边界：未实现对应论文算法，因此没有本题实验支持；未采用理由见implementation与limitations。

### 8. [Improving D-Optimal Sensor Placement for Bearing-Only Localization via Maximum-Entropy Reweighting](https://arxiv.org/abs/2605.11116v1)

实际阅读范围（extended）：PDF第1页摘要/导言；下载了全文但未读后续方法和实验证明。

启发：概率权重仅作调度参考，和确定性支持集合分离。

实现或未采用记录：round: None；functions: ；role: 未采用该重加权方法：所需准确性约束未建立

本题实验支持与边界：未实现对应论文算法，因此没有本题实验支持；未采用理由见implementation与limitations。

### 9. [Learning Multi-Agent Coordination for Enhancing Target Coverage in Directional Sensor Networks](https://arxiv.org/abs/2010.13110v1)

实际阅读范围（extended）：仅arXiv API元数据及作者摘要；未下载/阅读正文。

启发：学习可作后续竞争路线，但本次以可解释几何模型为主。

实现或未采用记录：round: None；functions: ；role: 未采用：需额外训练分布与保证设计，保留扩展入口

本题实验支持与边界：未实现对应论文算法，因此没有本题实验支持；未采用理由见implementation与limitations。

### 10. [On Balanced k-coverage in Visual Sensor Network](https://arxiv.org/abs/1512.07332v1)

实际阅读范围（extended）：仅arXiv API元数据及作者摘要；未下载/阅读正文。

启发：必须区别有限方向采样的覆盖率与对任意源方向的覆盖保证。

实现或未采用记录：round: None；functions: ；role: 未采用：原覆盖证书已可用，改站点需另证

本题实验支持与边界：未实现对应论文算法，因此没有本题实验支持；未采用理由见implementation与limitations。

## A5_learning

10 个来源，其中 5 个标为关键正文阅读。[该路线完整报告](https://github.com/xiangguaguadadi-dot/cumcm2026-b/blob/dc396791d0f84d4a8083b8a04b2a1768beaa6a69/experiments/A5_learning/report.md)。

### 1. [The Cross-Entropy Method for Optimization](https://people.smp.uq.edu.au/DirkKroese/ps/CEopt.pdf)

实际阅读范围（core）：PDF p.1–8、p.9前半、p.14–19；重点逐式读 §2 的 KL/精英分位数、Algorithm 2.2，以及 §4 Algorithm 4.1 的高斯均值/方差和平滑；其余章节未全文精读

启发：完整任务秒/源作为黑箱反馈；分别优化两题；冻结可靠性逻辑；训练所有尝试完整公开

实现或未采用记录：R1及后续：train_policy.search，平滑0.65、每代12个向量、前三精英、归一化边界、标准差下限0.035

本题实验支持与边界：training/r1及各轮selected.json；full结果由iteration_log.md对应，不能由原文推断

未采用或选择理由：未采用重要性抽样概率估计、网络可靠性任务和其特殊参数；它们不是本题目标

### 2. [Simple random search provides a competitive approach to reinforcement learning](https://arxiv.org/pdf/1803.07055)

实际阅读范围（core）：PDF p.1–9、p.13；逐式读BRS/ARS两份算法、状态归一化、回报标准差归一化、优先方向及多种子失败讨论；未逐页阅读全部22页

启发：简单低维策略也值得实测；优化预算应计入每个完整rollout；保留失败和不同误差场

实现或未采用记录：R1：有界归一化参数；所有轮：训练/开发分离及全轨迹评估；R2：有限观测特征

本题实验支持与边界：所有训练attempts_m*.jsonl记录逐个任务与失败；不声称复现ARS成绩

未采用或选择理由：本题阈值使目标局部不光滑，预算内选择按排名更新的CEM，不使用有限差分梯度或在线状态标准化

### 3. [A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning](https://proceedings.mlr.press/v15/ross11a/ross11a.pdf)

实际阅读范围（core）：PDF p.1–4、p.5前半、p.6实验段、p.8；读Algorithm 3.1、Theorem 2.1/2.2/3.1–3.4和前提，未完整复核有限样本证明，未精读Mario实验p.7

启发：每个候选必须重新运行完整任务以获得它自己诱导的状态；不能只报告基线日志上的离线预测误差

实现或未采用记录：所有轮：train_policy.run_config重新执行候选完整轨迹

本题实验支持与边界：训练/开发逐任务日志与full；没有模仿损失或特权标签

未采用或选择理由：没有优于基线且仅依赖合法观测的可靠专家；使用真值路径专家还会制造部署不可达标签，因此本次选择无专家任务回报搜索

### 4. [Safe Reinforcement Learning via Shielding](https://arxiv.org/pdf/1708.08611)

实际阅读范围（core）：PDF p.1–9、p.11、p.17–19；重点读安全自动机、保守抽象、前置/后置屏蔽、以及网格/驾驶实验；未复核§6全部合成算法和§7证明

启发：将已有几何覆盖、有限光学兜底、退出证书留在部署外壳内；模型只改变效率决策

实现或未采用记录：所有轮：solver.certified_points、cover_polygon、run退出证书原样保留；学习参数有界

本题实验支持与边界：各轮rules/nominal/quick/full与报告可靠性论证

未采用或选择理由：本题已存在解析证明，新增自动机合成成本无必要；全清活性另由有限站点/目标递减及有限兜底论证

### 5. [Attention, Learn to Solve Routing Problems!](https://arxiv.org/pdf/1803.08475)

实际阅读范围（extended）：PDF p.1、p.2部分、p.5–6；重点REINFORCE与greedy rollout baseline及训练预算；未完整精读编码器/解码器附录

启发：训练/开发用同一任务对当前与候选配对；学习须围绕任务级路线成本

实现或未采用记录：train_policy对同组生成案例评价多个候选；并非REINFORCE实现

本题实验支持与边界：训练/开发配对与full；未做注意力网络对照

未采用或选择理由：不能把未知源坐标当输入；小规模已有2-opt及有限参数更适合本次可复查预算

### 6. [The CMA Evolution Strategy: A Tutorial](https://arxiv.org/pdf/1604.00772)

实际阅读范围（extended）：PDF p.1–4部分、p.6末–8；读搜索框架、Hessian/协方差直觉及采样式，未深读完整协方差和步长更新

启发：参数单位需归一；后续若强耦合可考虑更丰富采样分布

实现或未采用记录：无CMA-ES代码

本题实验支持与边界：无直接对照，保留未采用理由

未采用或选择理由：本轮只有少量参数和每代12个样本，先使用易审计对角CEM，不能把它冒称CMA-ES

### 7. [A Tutorial on Bayesian Optimization](https://arxiv.org/pdf/1807.02811)

实际阅读范围（extended）：PDF p.1–3，重点适用前提、Algorithm 1、surrogate/acquisition分工；未精读后续EI/KG推导

启发：预算应针对真实评价开销决定，而非默认最复杂优化器

实现或未采用记录：无GP模型

本题实验支持与边界：pilot_timing记录12局计时；没有BayesOpt性能对照

未采用或选择理由：时间测量显示本地整局评价足够便宜，使用CEM便于公开全部尝试且不需要拟合平滑代理

### 8. [Proximal Policy Optimization Algorithms](https://arxiv.org/pdf/1707.06347)

实际阅读范围（extended）：PDF p.1–4以及p.5开头；逐式读策略梯度、概率比裁剪目标和KL惩罚比较，未深读所有实验

启发：若未来增加高维动作，可把覆盖证书作为外壳；当前没必要引入actor/critic

实现或未采用记录：无PPO训练

本题实验支持与边界：无直接实测，不宣称CEM优于PPO

未采用或选择理由：有限参数CEM能直接利用真实任务成本；本轮资源用于多分布完整验证

### 9. [Reinforcement Learning Trained Observer Control for Bearings-Only Tracking](https://arxiv.org/pdf/2605.02120)

实际阅读范围（core）：PDF p.1–7全部正文、算法式及Table I–III；参考文献仅追踪题名，未全部读取被引原文；图的空间布局未独立复刻

启发：用合法估计几何而非真实坐标产生机动；不要把低均值误差替代可靠清除；可从小型上下文动作开始学习

实现或未采用记录：R3：Solver.second_point 中 length/750-1 的有界特征控制推进/横移比例；训练仍是任务级CEM，约束仍是外包多边形

本题实验支持与边界：R3才新增；不作为R1/R2事后动机。训练/r3与对应quick/full可验证迁移是否奏效

未采用或选择理由：本题静态源、固定误差、计时目标和强制全清与论文不同，照搬高斯CKF会丢失有界保证；不借论文加权误差伪造官方综合分数

### 10. [Cooperative Bearing-Only Target Pursuit via Multiagent Reinforcement Learning: Design and Experiment](https://arxiv.org/pdf/2503.08740)

实际阅读范围（extended）：PDF p.1–4至光谱归一化开头；重点u-PLIF、外层RL/内层PID架构、观测掩码及reward分解；未深入末尾全部实车结果

启发：无信号/不可见必须作为独立观测解释，不能从模型的零掩码推断不存在；分清估计层和执行层

实现或未采用记录：无MARL、信息滤波或光谱归一化代码；仅R3前竞争路线比较

本题实验支持与边界：无本题对照，不声称采用其算法或验证其转移效果

未采用或选择理由：本题一只机器狗且接口串行，已知动作时间明确，不需要实车动力学和同伴通信模型

## A6_learning

10 个来源，其中 4 个标为关键正文阅读。[该路线完整报告](https://github.com/xiangguaguadadi-dot/cumcm2026-b/blob/c833c50831d02691cee6662934d3b9752a581b7d/experiments/A6_learning/report.md)。

### 1. [Simple random search provides a competitive approach to reinforcement learning](https://arxiv.org/pdf/1803.07055)

实际阅读范围（core）：正文1-3；4.1-4.2方法及比较表；未读完附录与其余统计图

启发：任务时间可作为整局反馈，先训练小而可解释的策略，不必先假定深网必要。

实现或未采用记录：进入各轮训练器的参数空间采样及物理特征归一化；本实现采用精英保留搜索，不是ARS梯度更新复刻。

相关轮次：round: 1；training_path: experiments/A6_learning/training/r1；full_path: results/A6_learning_r1_full；decision: not_improved；role: training/search/evaluation principle, not original algorithm replication；round: 2；training_path: experiments/A6_learning/training/r2；full_path: results/A6_learning_r2_full；decision: tradeoff；role: training/search/evaluation principle, not original algorithm replication；round: 3；training_path: experiments/A6_learning/training/r3；full_path: results/A6_learning_r3_full；decision: improved；role: training/search/evaluation principle, not original algorithm replication；round: 4；training_path: experiments/A6_learning/training/r4；full_path: results/A6_learning_r4_full；decision: not_improved；role: training/search/evaluation principle, not original algorithm replication；round: 5；training_path: experiments/A6_learning/training/r5；full_path: results/A6_learning_r5_full；decision: improved；role: training/search/evaluation principle, not original algorithm replication；round: 6；training_path: experiments/A6_learning/training/r6；full_path: results/A6_learning_r6_full；decision: not_improved；role: training/search/evaluation principle, not original algorithm replication；round: 7；training_path: experiments/A6_learning/training/r7；full_path: results/A6_learning_r7_full；decision: improved；role: training/search/evaluation principle, not original algorithm replication；round: 8；training_path: experiments/A6_learning/training/r8；full_path: results/A6_learning_r8_full；decision: not_improved；role: training/search/evaluation principle, not original algorithm replication；round: 9；training_path: experiments/A6_learning/training/r9；full_path: results/A6_learning_r9_full；decision: not_improved；role: training/search/evaluation principle, not original algorithm replication

本题实验支持与边界：参数空间整局搜索实际完成；第1轮静态参数失败，第2轮形成Q3/Q4取舍，第3轮组合成为联合改进。每轮的全部尝试数、开发与full数据可追溯；不把原论文跨任务成绩移植到本题。 全轮full轨迹（秒/源）：R1: Q3=307.779342, Q4=570.883371, not_improved；R2: Q3=306.814064, Q4=552.956004, tradeoff；R3: Q3=306.300434, Q4=552.956004, improved；R4: Q3=306.300434, Q4=552.956004, not_improved；R5: Q3=306.300434, Q4=548.829652, improved；R6: Q3=306.300434, Q4=548.829652, not_improved；R7: Q3=306.300434, Q4=548.515689, improved；R8: Q3=306.300434, Q4=548.515689, not_improved；R9: Q3=306.300434, Q4=548.515689, not_improved。交互特征等后续扩展仍是原创特征搜索，不能归因于论文原算法。 停止后的开发诊断2592/2592全清；移除station_gain、workload、boundary在该已暴露开发集反而更快，不能给每个学得特征都分配正收益；未据此再调参。

### 2. [A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning](https://arxiv.org/pdf/1011.0686)

实际阅读范围（core）：细读1-3、算法3.1、定理条件和第5节两项游戏实验；第4节证明只读部分，不宣称证明全复核

启发：必须在每个候选自己的轨迹上计算整局代价，不能只回归基线动作后便宣称提升。

实现或未采用记录：作为训练协议启发，未实现DAgger：没有可靠优于基线且不泄漏特权信息的教师；整局直接搜索避开专家标签需求。

相关轮次：round: 1；training_path: experiments/A6_learning/training/r1；full_path: results/A6_learning_r1_full；decision: not_improved；role: training/search/evaluation principle, not original algorithm replication；round: 2；training_path: experiments/A6_learning/training/r2；full_path: results/A6_learning_r2_full；decision: tradeoff；role: training/search/evaluation principle, not original algorithm replication；round: 3；training_path: experiments/A6_learning/training/r3；full_path: results/A6_learning_r3_full；decision: improved；role: training/search/evaluation principle, not original algorithm replication；round: 4；training_path: experiments/A6_learning/training/r4；full_path: results/A6_learning_r4_full；decision: not_improved；role: training/search/evaluation principle, not original algorithm replication；round: 5；training_path: experiments/A6_learning/training/r5；full_path: results/A6_learning_r5_full；decision: improved；role: training/search/evaluation principle, not original algorithm replication；round: 6；training_path: experiments/A6_learning/training/r6；full_path: results/A6_learning_r6_full；decision: not_improved；role: training/search/evaluation principle, not original algorithm replication；round: 7；training_path: experiments/A6_learning/training/r7；full_path: results/A6_learning_r7_full；decision: improved；role: training/search/evaluation principle, not original algorithm replication；round: 8；training_path: experiments/A6_learning/training/r8；full_path: results/A6_learning_r8_full；decision: not_improved；role: training/search/evaluation principle, not original algorithm replication；round: 9；training_path: experiments/A6_learning/training/r9；full_path: results/A6_learning_r9_full；decision: not_improved；role: training/search/evaluation principle, not original algorithm replication

本题实验支持与边界：未训练DAgger或行为克隆，无教师对照。实际执行的是每个参数候选自己的整局轨迹，避免只在原专家轨迹评价；这是协议启发，不检验DAgger定理。

### 3. [Attention, Learn to Solve Routing Problems!](https://arxiv.org/pdf/1803.08475)

实际阅读范围（core）：细读模型、掩码和上下文、REINFORCE rollout baseline算法及第5节评测协议/表1；不声称已读25页附录全部

启发：同一候选集合的相对关系比只看最近目标更有价值；和当前最佳在同一自建实例配对比较。

实现或未采用记录：第2轮观测集合的密度与后续站距离特征、每轮配对开发选择；未移植注意力模型，因为本题源位置未知且节点动态出现，预训练TSP坐标输入越界。

相关轮次：round: 2；function: Solver.learned_source_cost；full_path: results/A6_learning_r2_full；decision: tradeoff；role: observation-set context, no attention network；round: 3；function: Solver.learned_source_cost；full_path: results/A6_learning_r3_full；decision: improved；role: observation-set context, no attention network；round: 4；function: Solver.learned_source_cost；full_path: results/A6_learning_r4_full；decision: not_improved；role: observation-set context, no attention network；round: 5；function: Solver.learned_source_cost；full_path: results/A6_learning_r5_full；decision: improved；role: observation-set context, no attention network；round: 6；function: Solver.learned_source_cost；full_path: results/A6_learning_r6_full；decision: not_improved；role: observation-set context, no attention network；round: 7；function: Solver.learned_source_cost；full_path: results/A6_learning_r7_full；decision: improved；role: observation-set context, no attention network；round: 8；function: Solver.learned_source_cost；full_path: results/A6_learning_r8_full；decision: not_improved；role: observation-set context, no attention network；round: 9；function: Solver.learned_source_cost；full_path: results/A6_learning_r9_full；decision: not_improved；role: observation-set context, no attention network

本题实验支持与边界：第2轮上下文调度：Q3 306.814064472退步、Q4 552.956003578改善；第3轮恢复Q3后取得联合改进。整体候选比较支持Q4调度有效，但不等于attention网络复现或单一特征因果证明。 全轮full轨迹（秒/源）：R1: Q3=307.779342, Q4=570.883371, not_improved；R2: Q3=306.814064, Q4=552.956004, tradeoff；R3: Q3=306.300434, Q4=552.956004, improved；R4: Q3=306.300434, Q4=552.956004, not_improved；R5: Q3=306.300434, Q4=548.829652, improved；R6: Q3=306.300434, Q4=548.829652, not_improved；R7: Q3=306.300434, Q4=548.515689, improved；R8: Q3=306.300434, Q4=548.515689, not_improved；R9: Q3=306.300434, Q4=548.515689, not_improved。交互特征等后续扩展仍是原创特征搜索，不能归因于论文原算法。 停止后的开发诊断2592/2592全清；移除station_gain、workload、boundary在该已暴露开发集反而更快，不能给每个学得特征都分配正收益；未据此再调参。

### 4. [Safe Reinforcement Learning via Shielding](https://arxiv.org/pdf/1708.08611)

实际阅读范围（core）：细读问题、抽象与安全规范、前置/后置shield框架、网格实验；未完整重演合成算法证明

启发：学习负责效率，独立解析覆盖负责完整性；不让学得概率提前判定频道不存在。

实现或未采用记录：所有轮保留certified_points、run退出证书、cover_polygon和预算切换。没有实现LTL合成，属于设计原则迁移。

相关轮次：round: 1；function: certified_points / cover_polygon / run exit certificate；full_path: results/A6_learning_r1_full；role: all full runs complete; geometric argument and preserved-code audit, not synthesized LTL shield；round: 2；function: certified_points / cover_polygon / run exit certificate；full_path: results/A6_learning_r2_full；role: all full runs complete; geometric argument and preserved-code audit, not synthesized LTL shield；round: 3；function: certified_points / cover_polygon / run exit certificate；full_path: results/A6_learning_r3_full；role: all full runs complete; geometric argument and preserved-code audit, not synthesized LTL shield；round: 4；function: certified_points / cover_polygon / run exit certificate；full_path: results/A6_learning_r4_full；role: all full runs complete; geometric argument and preserved-code audit, not synthesized LTL shield；round: 5；function: certified_points / cover_polygon / run exit certificate；full_path: results/A6_learning_r5_full；role: all full runs complete; geometric argument and preserved-code audit, not synthesized LTL shield；round: 6；function: certified_points / cover_polygon / run exit certificate；full_path: results/A6_learning_r6_full；role: all full runs complete; geometric argument and preserved-code audit, not synthesized LTL shield；round: 7；function: certified_points / cover_polygon / run exit certificate；full_path: results/A6_learning_r7_full；role: all full runs complete; geometric argument and preserved-code audit, not synthesized LTL shield；round: 8；function: certified_points / cover_polygon / run exit certificate；full_path: results/A6_learning_r8_full；role: all full runs complete; geometric argument and preserved-code audit, not synthesized LTL shield；round: 9；function: certified_points / cover_polygon / run exit certificate；full_path: results/A6_learning_r9_full；role: all full runs complete; geometric argument and preserved-code audit, not synthesized LTL shield

本题实验支持与边界：全部9轮full分别2400/2400完整清除；核心覆盖/清除/终止函数保留并做AST审查。可靠性解析依据写于report第6节；没有LTL自动合成实验。 停止后的开发诊断2592/2592全清；移除station_gain、workload、boundary在该已暴露开发集反而更快，不能给每个学得特征都分配正收益；未据此再调参。

### 5. [Evolution Strategies as a Scalable Alternative to Reinforcement Learning](https://arxiv.org/pdf/1703.03864)

实际阅读范围（extended）：身份、引言、ES算法1/2、镜像扰动/秩变换、策略参数化；未深读全部实验

启发：动作频率和长时延回报不会阻止参数空间学习；适合既有确定求解器。

实现或未采用记录：训练器采用候选参数扰动和整局反馈；未复刻通信噪声表、Adam或大型网络。

相关轮次：round: 1；training_path: experiments/A6_learning/training/r1；full_path: results/A6_learning_r1_full；decision: not_improved；role: training/search/evaluation principle, not original algorithm replication；round: 2；training_path: experiments/A6_learning/training/r2；full_path: results/A6_learning_r2_full；decision: tradeoff；role: training/search/evaluation principle, not original algorithm replication；round: 3；training_path: experiments/A6_learning/training/r3；full_path: results/A6_learning_r3_full；decision: improved；role: training/search/evaluation principle, not original algorithm replication；round: 4；training_path: experiments/A6_learning/training/r4；full_path: results/A6_learning_r4_full；decision: not_improved；role: training/search/evaluation principle, not original algorithm replication；round: 5；training_path: experiments/A6_learning/training/r5；full_path: results/A6_learning_r5_full；decision: improved；role: training/search/evaluation principle, not original algorithm replication；round: 6；training_path: experiments/A6_learning/training/r6；full_path: results/A6_learning_r6_full；decision: not_improved；role: training/search/evaluation principle, not original algorithm replication；round: 7；training_path: experiments/A6_learning/training/r7；full_path: results/A6_learning_r7_full；decision: improved；role: training/search/evaluation principle, not original algorithm replication；round: 8；training_path: experiments/A6_learning/training/r8；full_path: results/A6_learning_r8_full；decision: not_improved；role: training/search/evaluation principle, not original algorithm replication；round: 9；training_path: experiments/A6_learning/training/r9；full_path: results/A6_learning_r9_full；decision: not_improved；role: training/search/evaluation principle, not original algorithm replication

本题实验支持与边界：参数空间整局搜索实际完成；第1轮静态参数失败，第2轮形成Q3/Q4取舍，第3轮组合成为联合改进。每轮的全部尝试数、开发与full数据可追溯；不把原论文跨任务成绩移植到本题。 全轮full轨迹（秒/源）：R1: Q3=307.779342, Q4=570.883371, not_improved；R2: Q3=306.814064, Q4=552.956004, tradeoff；R3: Q3=306.300434, Q4=552.956004, improved；R4: Q3=306.300434, Q4=552.956004, not_improved；R5: Q3=306.300434, Q4=548.829652, improved；R6: Q3=306.300434, Q4=548.829652, not_improved；R7: Q3=306.300434, Q4=548.515689, improved；R8: Q3=306.300434, Q4=548.515689, not_improved；R9: Q3=306.300434, Q4=548.515689, not_improved。交互特征等后续扩展仍是原创特征搜索，不能归因于论文原算法。 停止后的开发诊断2592/2592全清；移除station_gain、workload、boundary在该已暴露开发集反而更快，不能给每个学得特征都分配正收益；未据此再调参。

### 6. [Proximal Policy Optimization Algorithms](https://arxiv.org/pdf/1707.06347)

实际阅读范围（extended）：身份、引言及第3节裁剪目标公式/解释；未完整阅读实验

启发：端到端学习可行但需处理动作混合、信用分配及有效状态表达。

实现或未采用记录：未采用：当前低维参数可直接整局搜索，增加actor-critic和动作分布训练的工程预算未获必要性证据。

本题实验支持与边界：未实现原论文算法，没有同预算本题对照；仅做机制适配分析，不能声称本方案实测优于它。

### 7. [Practical Bayesian Optimization of Machine Learning Algorithms](https://arxiv.org/pdf/1206.2944)

实际阅读范围（extended）：身份、问题及2.1-2.2 GP/PI/EI/UCB机制；不冒充全文深读

启发：搜索本身可自适应集中预算，而非手调看v1结果。

实现或未采用记录：未实现GP BO：单局模拟便宜，额外核拟合/采集优化开销与非平滑目标下的必要性不明确。用更简单精英搜索。

本题实验支持与边界：未实现原论文算法，没有同预算本题对照；仅做机制适配分析，不能声称本方案实测优于它。

### 8. [PILCO: A Model-Based and Data-Efficient Approach to Policy Search](https://mlg.eng.cam.ac.uk/pub/pdf/DeiRas11.pdf)

实际阅读范围（extended）：身份、GP动力学、不确定输入矩匹配和长期策略评价；未读全部实验

启发：本题运动是已知直线和固定速度，未知部分主要是源和固定误差场；不应重复学习已知运动规则。

实现或未采用记录：未采用：动力学模型学习解决的核心困难在本题不突出，定向失信号是非连续观测，模型风险需额外校准。

本题实验支持与边界：未实现原论文算法，没有同预算本题对照；仅做机制适配分析，不能声称本方案实测优于它。

### 9. [Neural Combinatorial Optimization with Reinforcement Learning](https://arxiv.org/pdf/1611.09940)

实际阅读范围（extended）：引言、Pointer Network与REINFORCE目标；未读全部实验与附录

启发：直接用任务代价训练，比模仿一份并非最优的路线标签更贴合目标。

实现或未采用记录：整局直接目标进入训练器；未实现指针网络，亦不在v1上做单实例active search。

相关轮次：round: 1；training_path: experiments/A6_learning/training/r1；full_path: results/A6_learning_r1_full；decision: not_improved；role: training/search/evaluation principle, not original algorithm replication；round: 2；training_path: experiments/A6_learning/training/r2；full_path: results/A6_learning_r2_full；decision: tradeoff；role: training/search/evaluation principle, not original algorithm replication；round: 3；training_path: experiments/A6_learning/training/r3；full_path: results/A6_learning_r3_full；decision: improved；role: training/search/evaluation principle, not original algorithm replication；round: 4；training_path: experiments/A6_learning/training/r4；full_path: results/A6_learning_r4_full；decision: not_improved；role: training/search/evaluation principle, not original algorithm replication；round: 5；training_path: experiments/A6_learning/training/r5；full_path: results/A6_learning_r5_full；decision: improved；role: training/search/evaluation principle, not original algorithm replication；round: 6；training_path: experiments/A6_learning/training/r6；full_path: results/A6_learning_r6_full；decision: not_improved；role: training/search/evaluation principle, not original algorithm replication；round: 7；training_path: experiments/A6_learning/training/r7；full_path: results/A6_learning_r7_full；decision: improved；role: training/search/evaluation principle, not original algorithm replication；round: 8；training_path: experiments/A6_learning/training/r8；full_path: results/A6_learning_r8_full；decision: not_improved；role: training/search/evaluation principle, not original algorithm replication；round: 9；training_path: experiments/A6_learning/training/r9；full_path: results/A6_learning_r9_full；decision: not_improved；role: training/search/evaluation principle, not original algorithm replication

本题实验支持与边界：参数空间整局搜索实际完成；第1轮静态参数失败，第2轮形成Q3/Q4取舍，第3轮组合成为联合改进。每轮的全部尝试数、开发与full数据可追溯；不把原论文跨任务成绩移植到本题。 全轮full轨迹（秒/源）：R1: Q3=307.779342, Q4=570.883371, not_improved；R2: Q3=306.814064, Q4=552.956004, tradeoff；R3: Q3=306.300434, Q4=552.956004, improved；R4: Q3=306.300434, Q4=552.956004, not_improved；R5: Q3=306.300434, Q4=548.829652, improved；R6: Q3=306.300434, Q4=548.829652, not_improved；R7: Q3=306.300434, Q4=548.515689, improved；R8: Q3=306.300434, Q4=548.515689, not_improved；R9: Q3=306.300434, Q4=548.515689, not_improved。交互特征等后续扩展仍是原创特征搜索，不能归因于论文原算法。 停止后的开发诊断2592/2592全清；移除station_gain、workload、boundary在该已暴露开发集反而更快，不能给每个学得特征都分配正收益；未据此再调参。

### 10. [Near-Optimal Sensor Placements in Gaussian Processes: Theory, Efficient Algorithms and Empirical Studies](https://www.jmlr.org/papers/volume9/krause08a/krause08a.pdf)

实际阅读范围（extended）：身份、贡献、GP条件方差、非平稳核与熵准则；未完整阅读50页，未核验全部近似定理

启发：误差相关性和测点几何需纳入开发分布，减少重复同址测量；信息量不是唯一任务目标。

实现或未采用记录：训练生成混合有界误差场并保留固定同址误差；未实现GP地图或互信息优化，避免把协方差假设硬套为覆盖证书。

相关轮次：round: 1；training_path: experiments/A6_learning/training/r1；full_path: results/A6_learning_r1_full；decision: not_improved；role: training/search/evaluation principle, not original algorithm replication；round: 2；training_path: experiments/A6_learning/training/r2；full_path: results/A6_learning_r2_full；decision: tradeoff；role: training/search/evaluation principle, not original algorithm replication；round: 3；training_path: experiments/A6_learning/training/r3；full_path: results/A6_learning_r3_full；decision: improved；role: training/search/evaluation principle, not original algorithm replication；round: 4；training_path: experiments/A6_learning/training/r4；full_path: results/A6_learning_r4_full；decision: not_improved；role: training/search/evaluation principle, not original algorithm replication；round: 5；training_path: experiments/A6_learning/training/r5；full_path: results/A6_learning_r5_full；decision: improved；role: training/search/evaluation principle, not original algorithm replication；round: 6；training_path: experiments/A6_learning/training/r6；full_path: results/A6_learning_r6_full；decision: not_improved；role: training/search/evaluation principle, not original algorithm replication；round: 7；training_path: experiments/A6_learning/training/r7；full_path: results/A6_learning_r7_full；decision: improved；role: training/search/evaluation principle, not original algorithm replication；round: 8；training_path: experiments/A6_learning/training/r8；full_path: results/A6_learning_r8_full；decision: not_improved；role: training/search/evaluation principle, not original algorithm replication；round: 9；training_path: experiments/A6_learning/training/r9；full_path: results/A6_learning_r9_full；decision: not_improved；role: training/search/evaluation principle, not original algorithm replication

本题实验支持与边界：所有训练轮包含自行生成的不同相关误差场；没有训练GP地图、信息增益控制器或验证其子模近似界。源场景退步在report逐项列出。
