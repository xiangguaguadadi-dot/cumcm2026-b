# A2最终交付：十轮完成，经验停止

状态：**completed_empirical_stop**。R9是题间取舍、R10与R8逐局任务指标相同，连续两轮未刷新经full验证的严格共同最佳，计数2。实验已经结束，不再设计新候选；这不表示数学收敛或全局最优。

- 工作树：`/Users/t/ai project/数学建模2026/agent_experiments/20260911/A2_information`。
- 分支：`experiments/20260911/a2_information`。
- 最终共同最佳：R8；workspace solver.py逐字等于R8快照。
- 最佳快照：`experiments/A2_information/candidates/r8_solver.py`。
- 最佳SHA256：`bd0ed7b8d322d6502c04c1bf100857001617cca235038a2d78bcacf4d97b82bc`。
- 最佳代码提交：`deb4f4b5477fb15d25d1c98bb8d353f6a2c3c400`。
- 最佳full目录：`results/A2_information_r8_full`。
- Q3：285.8667033463909 秒/源，1200/1200全清。
- Q4：568.449411526069 秒/源，1200/1200全清。
- 题间取舍R9：Q3 285.9519236676399、Q4 568.4039785307609；SHA256 `a759e118611f2443cf66156dc0b3eaf91e49c2a9254eec49a5f42e8050f7a0f2`；代码提交`c4511bc1a90a08ee3351b585b534e4cce73317ef`。
- R10：预测后验加入接收上界，full2400局和R8逐局秒/源相同；SHA256 `bae43c00cf155f667c01fb3df65545d422cf2fd546c5ea8dd5e624b494f65b60`；代码提交`f0af6cd1c6518a84f07b6320df7f7f18900165d3`；目录`results/A2_information_r10_full`。保留更简R8作为同指标代表，不把R10称新增取舍。

R1–R10每轮14个单测、79个正常规则核验、quick120与full2400均完整保存，全测共24000局候选、快测1200局候选；开发2016次参考/候选运行和240次诊断尝试。明确记录27456次运行/尝试；规则/几何另计，R4中断开发未知额外调用未虚构计数。细目为execution_budget.json。

final_audit.json只读核对全部20个suite的快照SHA、唯一ID配对、全清、无异常、正常user_exit、覆盖证书，未重跑R1–R9。冻结manifest SHA256 `431210a6d96e721d23c31698aa389702ea87dcffe8fee6250f71ce6e902be140`。策略只通过enter/measure/clear/exit决策；无相邻coverage_points.json、无模型/权重/外部推理依赖。覆盖/停止证明见最终report第9节。

文献为A2累计9篇：4核心正文部分阅读、5扩展有限阅读；逐篇实际范围、启发、函数和轮次、实验支持与未采用原因均在report.md和literature.json。R10没有新增论文阅读声明，依自身研究材料设计。光学失败后跳过测量的想法在编码前被解析排除，不计运行候选。

独立性边界保留既有一次共享状态暴露记录，不宣称全程绝对隔离。R10是干净上下文仅阅读A2自身树和协议后的独立设计；未读任何其他路线或协调摘要。

这是LOCAL-v1已知固定回归集上的研发结果；主协调的共同新样本检验不能回馈调参，Windows官方模拟器未启动。全部运行参数在候选快照，最佳精确元数据以best.json为准。
