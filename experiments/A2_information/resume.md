# A2 调度暂存与恢复点

**状态：主Agent要求暂存以释放并发名额；不是经验收敛，不是最终停止。**

## 可以直接恢复的事实

- 工作树：`/Users/t/ai project/数学建模2026/agent_experiments/20260911/A2_information`。
- 分支：`experiments/20260911/a2_information`；只推该分支，不碰main或其他Agent。
- 六轮均已完成规则、quick 120局、full 2400局；无正在运行的求解或评估进程。
- 当前源码 `solver.py` 与最佳快照 `experiments/A2_information/candidates/r6_solver.py` 完全相同。
- 当前最佳 **R6**：Q3 **286.01852916752495秒/源**（基准306.3004342181635，减少6.6216%）；Q4 **570.7373131854504秒/源**（基准570.8833714439976，减少0.0256%）；各1200/1200全清、0异常。
- 最佳代码提交：`e6a187766dff9370a4656434867cdead399842f0`。
- 最佳SHA256：`66faeaa85c405b9c582a45132050cc336082ed1e7fc90d7d8aab8cb3ce954db5`。
- 完整结果：`results/A2_information_r6_full`；完整依赖/结果散列见 `best.json`。
- **下一轮是R7，连续未刷新严格共同最佳的计数是0。** R6比R5的Q3更快、Q4严格不变，所以计数已归零。

用户已授权超过最初3轮，“第四、第五轮”不是新上限。主Agent明确统一规则：有持续full验证提升时继续R6/R7等，直到连续两轮未刷新当前最佳才经验停止。严格共同最佳要求full全部清除、两题均不差且至少一题更快；不同取舍单列，不能自造加权总分。之后仍须主Agent统一新样本检验和官方演练，不声称全局最优。

## 方法现状

- Q3：多假想目标的主动第二测点；有预算的1500m接收界/1800m目标域有效切面细化；利用已有no_signal记录的1000m圆外凸包排除；20m全顶点最近可靠清除点。
- Q4：原版第二测点；不使用no_signal距离排除，也不启用范围切面细化；只用20m全顶点清除动作优化。Q4收益很小，配对描述性区间包含0，不能称显著改进。
- 所有全局覆盖、跨频道调度、源数上界、有限格点兜底和时间保留逻辑仍来自原版。只通过enter/measure/clear/exit决策。
- 冻结评测和基准未修改。无额外推理模块、权重或第三方依赖；coverage_points.json不存在，使用解析覆盖点。

## 6轮摘要与关键失败

1. R1任务代价主动测点：Q3 299.77975194，Q4 578.96236624；取舍，未刷新共同最佳。
2. R2补不可见观测分支：Q3相同，Q4 574.81712193；缓和退步但仍取舍。quick曾略胜Q4基准而full没有支持，必须保留此证据。
3. R3 Q4回退，加入最近可靠清除点：Q3 299.76540283，Q4 570.73731319；首次刷新共同最佳。
4. R4自适应圆边界细化：Q3 290.85377897，Q4 570.82995784；取舍且开发计算退化。v1 full全通过，但额外全定向边界压力案例有数千至11787个顶点，使O(n³)清除枚举很慢。原始开发手动中断记录和120局5秒诊断（5个超时）完整保存。
5. R5限顶点预算、Q3启用细化/Q4回退、复杂时用安全退让：Q3 290.85380296，Q4与R3相同；共同最佳刷新。原120局退化重放0超时、最高49顶点。R4的Q3仅快0.000024秒/源，不能隐藏，但不值得带入复杂度风险。
6. R6 Q3无信号圆外凸包排除：Q3 286.01852917，Q4与R3严格相同；共同最佳刷新。

每轮快照在candidates，每轮rules/quick/full在results，不覆盖。开发种子使用910000、910100、910200、910300、910400、910500批次，均与冻结5000–5099分离。r4_watchdog是额外的5秒诊断，不是官方1200秒超时。开发boundary/min_radius在Q4可能全定向，是压力测试，不能当官方混合分布。

## 文献与报告入口

- `report.md`：自包含阶段报告，9篇文献逐篇“读到哪里、什么机制、带来什么启发、采纳函数/轮次、为何不采用”。
- `literature.json`：4核心+5扩展，9份PDF来源、SHA、日期、查询、访问失败、作者/版本、证据边界。
- `research/reading_evidence.md`：核心正文推导与批判性阅读。
- `research/optical_projection_proof.md`、`exclusion_proof.md`：A2自行推导的本题几何证明，不能归功给未实现论文。
- 原PDF/抽取文本/检索HTML保留本地且由research/.gitignore排除。`research/fetch.py`可以重下；curl --noproxy '*'可访问arXiv；web搜索连接失败。

已实际深读核心：Li等2019的任务/信息双目标控制，Calafiore2026集合定位，MEXGEN2024预测测量偏差，Arora等2018信息动作近似失效。其他5篇阅读范围明确较浅，不能说成9篇全文深读。

## 恢复后的工作建议（尚未执行，不是承诺某个方法）

先验证源码、快照和best散列一致，再提出单个R7机制，不要在固定回归集扫参数。可研究：当前9个假想目标仍从凸外包采样，而凸外包可能把已被无信号排除的孔重新填回；假想目标可以根据所有既有观测筛除不一致点（只影响排序、不作为证明），或研究光学失败这个独立于天线的负观测。若使用这些方向，需明确新规则、实际可观察字段、数值/终止边界，补独立开发验证后再冻结一个候选。没有开始R7，没有消耗R7预算。

所有外部模型/下载允许，但本题低维几何不需要为了形式下载大模型。保持本路线独立，不获取其他Agent策略。

运行Python：`/Users/t/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`。

```sh
python -m unittest discover -s tests -v
python evaluate.py --verify-only
python tests/check_nominal.py --package . --out results/A2_information_r7_rules/nominal.json
python evaluate.py --suite quick --candidate solver.py --out results/A2_information_r7_quick
python evaluate.py --suite full --candidate solver.py --out results/A2_information_r7_full
```

`dev_eval.py`生成独立开发数据，`update_log.py`从已有full读取并更新数值；新增轮次的解释需显式补进脚本。`build_report.py`目前是调度暂存版本，恢复/最终停止时要更新报告状态与停止原因，不能让旧暂存声明残留。它通过当前提交的候选快照定位代码提交，因此先提交新候选/结果，再生成best与报告。推送可用 `git -c http.proxy= -c https.proxy= push origin experiments/20260911/a2_information`，无需改全局配置。

## 恢复后的实时进度

R7 已完成开发(910600–910609)、规则、quick120全清，候选 f963a3fede0c53fab859e8e9e3b339f5afab7da8a3308d426823c796e3f3fb70；full 已启动，输出 results/A2_information_r7_full。本段优先于上文暂存状态；不要重跑已完成步骤。

R7 full完成：2400全清、Q3=286.01274517821093、Q4=570.7373131854504；Q3比R6仅改善0.0057839893秒/源，Q4相同。最佳R7、未刷新0，下一轮R8。
