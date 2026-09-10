# A2 干净上下文接续点：九轮完成，尚未经验停止

**状态：按主协调要求，R9完成后调度暂停，等待干净上下文接续同一A2路线。不是最终停止。**

仅阅读本A2工作树中的resume、best、report、iteration_log、plan、literature及本路线代码/结果。不要读取共享协调摘要或其他路线工作树/输出。本文件没有下一轮设计建议。

## 接续所需的精确事实

- 工作树：`/Users/t/ai project/数学建模2026/agent_experiments/20260911/A2_information`。
- 分支：`experiments/20260911/a2_information`；只提交推送该分支，不改main。
- R1–R9均已完成规则、quick120局、full2400局；全清2400，无正在运行的评估。**不要重跑这些轮次。**
- 当前严格共同最佳为 **R8**，源码solver.py已与R8快照逐字一致。
- R8：Q3 **285.8667033463909**；Q4 **568.449411526069** 秒/源；每题1200/1200局全清。
- R8代码提交：`deb4f4b5477fb15d25d1c98bb8d353f6a2c3c400`。
- R8快照：`experiments/A2_information/candidates/r8_solver.py`。
- R8 SHA256：`bd0ed7b8d322d6502c04c1bf100857001617cca235038a2d78bcacf4d97b82bc`。
- R9是非支配取舍：Q3 **285.9519236676399**（较R8慢0.08522032），Q4 **568.4039785307609**（较R8快0.04543300），2400全清。
- R9快照：`experiments/A2_information/candidates/r9_solver.py`；代码提交`c4511bc1a90a08ee3351b585b534e4cce73317ef`；SHA256 `a759e118611f2443cf66156dc0b3eaf91e49c2a9254eec49a5f42e8050f7a0f2`。
- 当前非支配集为R8、R9；完整记录在best.json。不合并为一个加权分数，不按案例选择版本。
- **下一轮R10，连续未刷新严格共同最佳计数为1。** R9未刷新；R8刷新后计数曾归零。当前上下文未设计/未运行R10。

用户授权持续改进时超过初始3轮；主协调统一为连续两轮未刷新经full验证的当前严格共同最佳则经验停止，不称数学收敛。全清且两题均不差、至少一题更快才刷新共同最佳；取舍保留但不清零。若R10不刷新即达到停止，若刷新则归零继续。最终仍须主协调共同新样本复核，不能用其结果回馈调参。

## R7–R9发生了什么

- R7：规划假想点筛选，排除违反圆域/正观测接收上界/Q3无信号约束的假想点。只改变排序，9点一致则不改；否则81点提案过滤选至多9点，空则回原点。Q3=286.01274517821093，比R6只快0.00578399秒/源，Q4不变；微小刷新不能称稳健改进。
- R8：记录光学失败位置。20m内光学必成功，所以失败点20−1e−6m圆盘对两题都是有效排除；用outside_disk_hull保守凸包，后续方向更新后重施。两题一起刷新。
- R9：在方向、无信号或光学失败后固定最多两次负约束传播，原理是后施约束可能暴露前次凸包中的信息。只保守收缩，固定两次预算不称固定点收敛。结果是小取舍，未替换R8。

R1–R6历史和失败都在report/iteration_log，不再复制长旧恢复状态。特别R4开发压力例曾生成11787顶点并触发5秒诊断超时；R5有预算修复的120例重放0超时、最高49顶点。5秒诊断不是官方1200秒失败。

## 当前方法与安全边界

- Q3：多假想目标主动第二测点、预算化1500/1800m有效切面、已有无信号1000m圆外凸包、20m最近全顶点可靠清除、已有光学失败排除。
- Q4：原版第二测点、不作无信号距离排除、不作范围切面细化；保留20m全顶点清除和光学失败排除。
- 全局覆盖、跨频道调度、16源上界、180000秒保留阈值、局部迭代上限和格点兜底沿用原版。后验收缩不修改已生成格点列表，保留原有限覆盖。
- 只调用enter/measure/clear/exit；不读源真值、案例、场景、种子或缓存。参数均在快照，无模型、权重或外部推理模块；相邻coverage_points.json不存在。
- 冻结manifest SHA256 `431210a6d96e721d23c31698aa389702ea87dcffe8fee6250f71ce6e902be140`。原基准sha `36271e5c84cdcd4468b54484d699dce64194f09d78c0c03f3ec1c38f105f6ca9`，Q3=306.3004342181635，Q4=570.8833714439976。
- 固定回归种子5000–5099不能称新留出，也不能内层扫参。quick是full子集。

## 文献、预算、验证和独立性记录

9篇文献4核心+5扩展的真实阅读范围、启发、代码映射、实验支持和不采用原因均在literature.json与report.md。没有把全部9篇称全文深读，也没声称复现论文原算法。research/reading_evidence.md保存核心推导；两个exclusion/optical_projection证明是A2题面自推。

execution_budget.json列九轮已记录21600次full候选、1080次quick候选、1776次开发运行及240次诊断尝试，共24696；R4中断前未知额外运行未虚构计数，规则/几何检查另计。开发种子批次为910000、910100、910200、910300（中断/诊断）、910400、910500、910600、910700、910800，最新完成910800–910809。

checkpoint_audit.json已核验九轮全部quick/full的快照sha、唯一ID配对、全清/异常、当前源码=R8、冻结manifest、无附加coverage JSON；这是只读原始结果审核，没有重跑。官方Windows尚未演练。

恢复过程中曾有一次共享协调状态暴露，故不声称全程绝对隔离。仅以research/independence_boundary.md和checkpoint_reason.json记录范围，其他路线具体信息不应传给接续上下文。R7已冻结和原resume中R8方向建议的前置证据，在f3ab3d5提交与research/pre_exposure_resume.md。主协调因此要求当前上下文完成已冻结R9后释放，后续干净接续；这不是经验停止。

## 执行与报告工具

先读AGENTS.md、README.md、docs/评测标准_v1.md、自己的report/best。推荐Python：`/Users/t/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`。系统python3的中文heredoc曾有编码问题。

每次候选先独立开发、规则，再quick/full；使用新的输出目录，保留失败快照。dev_eval.py生成开发分布；其中Q4 boundary/min_radius可能全定向，是压力分布而非题设混合分布。update_log.py需新增轮次解释；build_report.py当前是九轮调度暂存版本，其状态、预算数和章节8有九轮硬编码，接续/最终停止必须更新，不让旧暂停声明残留。write_literature.py已补到R9的映射，也需随真实后续改动更新。

每轮完整代码与结果提交后再生成best/report以取得精确快照提交。推送可用`git -c http.proxy= -c https.proxy= push origin experiments/20260911/a2_information`，不要改全局代理。用户已授权提交推送，不需重问。原文PDF和抽取缓存由research/.gitignore排除。
