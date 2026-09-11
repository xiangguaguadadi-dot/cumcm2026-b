# 第四阶段：两位深化当前最佳，一位扩展新方法

用户2026-09-11重新授权：前两个子Agent观察当前数据和迭代路径，挖掘当前最佳方法的上限与突破点，允许结构调整、组件替换、融合此前有潜力未采纳的方向，优化到当前探索范围收敛。有好效果就提交代码。第三个子Agent扩大既有方法起点之外的研究范围，参考指定论文并读更多文章，对判断有潜力且可实现的方向进行实验。

同时沿用用户刚才明确偏好：不要把时间耗在冗长、重复的校验上，要及时形成方法与结果。研究停止由实际假设饱和、收益/失败与用户后续指令决定，没有固定轮数、固定两次失败规则，也不声称全局最优。

## 工作区与基线

原项目 /Users/t/ai project/数学建模2026/代码；本阶段基点52fbf08。协调树 /Users/t/Documents/Codex/2026-09-10/new-chat/work/stage4/coordinator；同级E1_refine、E2_refine、E3_expand各自只写experiments/<ID>/。分支experiments/20260911-stage4/<lowercase ID>。不要修改原solver、第一二问、冻结评测/数据/测试，或别人的实验文件。

先读AGENTS.md、README.md、docs/评测标准_v1.md和上一阶段experiments/20260911_stage3/REPORT.md；图先读experiments/R1_atlas/exploration_index.json、DIRECTION_MAP.md、STAGE3_PROGRESS.md，再按需读取nodes/<id>.json与其原始结果/源码。已有检索与论文账本也先复用。只对真正相关的失败案例、未采纳方向做深入诊断；不重新批量审计全部历史文件，也不把逐文件解析当逐轨迹深读。

本阶段固定基线S1是当前已实际部署运行过的最佳统一入口：Q3 R2_open R4，Q4 R3_open R5。默认源码及依赖在本阶段baseline/S1.py、R2_open_R4.py、R3_open_R5.py；复用已执行4800局的任务记录baseline/expected_rows.json，不再次花时间跑相同基线。每题2400例、30970源，Q3 235.87694581189243、Q4 473.8974929996439秒/源。基线原始现实耗时为历史值，不用它做本机速度排名。

区分固定S1、自身上一最佳、共同当前最佳。共同CURRENT_BEST.json由root更新；互发成熟成果。若研究者各改善一题，不因另一题的新进步否认独立组件效益；相同题目的新候选要明确相对最新已知最佳是否仍有增益。

## 三位职责

E1_refine与E2_refine的授权相同：不限题号、不限定小修，不只是扫参数。各自从当前最强方法的任务轨迹、时间/距离/动作构成、退步分布和历史有潜力未采纳节点，提出结构性假设；可以重排搜索/定位/清除流程、改变规划对象、替换组件，也可以读新论文。两人先自主给出短候选清单，再交流避免完全重复；不强制一人只Q3另一人只Q4。每次说明潜在节时来自什么动作变化及其真实可执行性。

E3_expand是研究加实现角色，不能只列论文。使用automated-research-report技能，优先核实用户所列论文的规范题名、版本、年份、作者、正文与适用条件；再追引用、后续工作及竞争机制，拓宽此前方法谱系。不要把不同论文换名但相同机制当新方向。对每个判定有潜力且可实现的方向，完成最小有意义的实现和开发对照，优胜候选再完整回归；明显不适用者注明理由及未实施状态。及时将可行动材料和实测结果发给两位深化者。

用户给定线索（题名/年份尚需一手来源核实）：
- IROS 2011：Active Target Localization for Bearing Based Robotic Telemetry；状态空间搜索主动定位，β-cautious前身。
- ICRA 2012：Cautious Greedy Strategy for Bearing-based Active Localization: Experiments and Theoretical Analysis（用户原文CRA2012，需核实）。
- ICRA 2013：Sensor Placement and Selection for Bearing Sensors with Bounded Uncertainty（用户原文CRA2013，需核实）。
- ISER 2013线索：Local-Search Strategy for Active Localization of Multiple Invasive Fish；单目标到多目标初始化与邻近目标分摊搜索代价。
- JFR 2014：Cautious Greedy Strategy for Bearing-only Active Localization: Analysis and Field Experiments；J. Vander Hook、P. Tokekar、V. Isler。
- T-RO 2015：Cooperative Active Localization under Communication Constraints，可能完整题名含Target。
- ISRR 2015线索：Detecting, Localizing, and Tracking an Unknown Number of Moving Targets；未知数量、假设增删。
- arXiv 2020：Active Localization of Multiple Targets using Noisy Relative Measurements；Engin & Isler；非贪心多目标路径/贝叶斯直方图。

优先研究真实来源，不照抄用户所列年份和标题。双机/运动目标/高斯噪声保证不能直接移植到本题单机、静态、频道已知、±1度有界测向与20米clear。可以改造成规划代理，但可靠集合与完整退出条件仍要成立。

## 每轮高效实验

1. 写一个简短的实验前条目：观察、来源/父节点、方案、预计改变的动作、关键对照、开发种子和选择规则。无需冗长的独立批准材料。
2. 用本阶段分配的互不重叠种子做适量合法开发，保存具体案例及全部尝试、失败。development_seed_allocation.json已核对旧具体种子无冲突：E1 [44000000,45000000)、E2 [45000000,46000000)、E3 [46000000,47000000)。每位维护本地递增登记即可，不反复全局扫描。10–16源、频道互异；Q4必须混有全向与定向。单向压力案例单列诊断。
3. 算法修改的规则检查与quick120保留；有价值候选再full2400。单文件候选完整v1结果可复用，只补跑2400旧final，得到4800统一对比。部署有多文件依赖则明确记录，无法证明同一部署时实际跑4800，不造缓存证据。
4. 使用本阶段evaluate_exposed.py，与固定S1比较（字段comparisons_to_S1）；可用--previous-rows比较上一个4800最佳。报告完整性/失败、两题均值、分批/场景、快同慢、主要退步，必要动作统计。不能只选成功局排名，也不能用跨题加权数掩盖退步。给清除/覆盖关键改动简短数学依据或针对性检查；不做重复全历史审计、额外最终留出或为汇报而持续追加校验。
5. 结果好就提交候选/原始结果/简短说明并推送既有私有仓库。失败和未采纳结果也保存，阶段收尾一并提交。不等全部研究结束才推送有效进展。不要上传凭据、官方身份日志、模拟器二进制、论文PDF/全文缓存。

运行时：/Users/t/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3（3.12）。系统python3为3.9，不改冻结环境适配旧版本。

例：
```
PYTHON=/Users/t/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
$PYTHON -m unittest discover -s tests -p test_rules.py
$PYTHON evaluate.py --candidate experiments/ID/snapshots/r1.py --suite quick --out experiments/ID/results/r1_quick
$PYTHON evaluate.py --candidate experiments/ID/snapshots/r1.py --suite full --out experiments/ID/results/r1_full
$PYTHON experiments/20260911_stage4/evaluate_exposed.py --candidate experiments/ID/snapshots/r1.py --v1-results experiments/ID/results/r1_full --out experiments/ID/results/r1_exposed
```

只通过enter/measure/clear/exit读环境。禁止推理读取源真值、测试ID、场景标签、随机种子或成绩缓存。真值可以在离线诊断/评测层分析，不能把该信息直接交给求解器。任何全知下界/Oracle诊断只写潜力分析，不冒充可部署策略。保留完整覆盖/安全兜底和100小时约束；HTTP或并发改动另需必要通信检查，不启动官方Windows。

每位至少保存plan.md、optimization_path.md/json、report.md、best.json、execution_budget.json、used_seeds.json、snapshots/、results/；文献角色另有literature.json、RESEARCH_BRIEF.md和新方向树。精确记录真实执行、独立案例、复用案例及阅读深度。root负责简洁协调、整合有效结果和最后更新总方向图/报告，不因文档或无关审计拖延方法研究。
