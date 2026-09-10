# A6 本路线接续记录（2026-09-11 05:45；任务未最终完成）

## 边界与目录

本Agent只使用本路线资料。工作树 `/Users/t/ai project/数学建模2026/agent_experiments/20260911/A6_learning`，分支 `experiments/20260911/a6_learning`。共同学习提示在主repo的 `experiments/20260911_agent_campaign/LEARNING_PROMPT.md` 与 `PROTOCOL.md`；只读这两份共同规则，不读取其他路线目录、报告或共享状态摘要。

第7轮训练、架构与开发选择完成后，整理状态时意外读取共享协调记录中其他路线摘要。此后仅冻结已选择参数并执行规则/quick/full，没有调整参数或设计新动作。文件散列与时间证据见 `r7_provenance.json`；本报告如实记录有限信息暴露。主协调要求后续在只给本文件与本路线记录的干净上下文继续，不把其他路线算法转入后续设计。

## 已完成状态

已完成R1–R7，不重复训练或回归。当前最佳R7：Q3 `306.30043421816345`，Q4 `548.5156891280411` 秒/源；每题1200/1200全清、无异常、正常退出。第三问1200局的时间、距离、动作数等与原基准逐局完全相同；Q3不是学习改进。

R7最佳快照 `experiments/A6_learning/snapshots/r7_solver.py`，SHA256 `7603ac0512b834d85ac499c1c5ce9da454d7f1f64bd8d368c5fe96b30d0b3138`。源码提交在 `best.json.code_commit`（以4698268开头），完整结果 `results/A6_learning_r7_full`。根solver为最佳。R7相对R5 Q4进一步改善约0.0572%，原基准Q4为570.8833714439976。不要用quick代替full：R7 quick Q4 577.277668198，比quick基准更慢，已披露。

当前延长连续未刷新计数=0，下一轮R8。原本前三轮限制已获授权延长：R2→R3两题不差至少一题好且刷新最佳即取得资格；延长后连续两轮未刷新经full验证的当前最佳才经验停止，没有固定7轮上限。本上下文尚未设计R8。暂停用于清洁接续，不是收敛或最终完成。

## 本路线方法与每轮决策

- R1静态参数两阶段精英随机搜索；开发微小改善，full Q3退步，拒绝。
- R2从原版搜索可行圆半径、其他已见待清中心邻近度、相对下一站距离上下文权重与source_priority。full Q3 306.8140644724105 / Q4 552.9560035775925，保存取舍，不作为联合最佳。
- R3固定Q3原版，Q4从R2学习第二测点几何特征。开发收益0.3078%未过预先0.5%门槛，测点权重仍零；组合候选full Q3 306.30043421816345 / Q4 552.9560035775925，刷新联合最佳并取得延长。
- R4新增无信号比例、重复bearing比例、已见待清频道数/16历史特征。开发未过0.5%门槛，权重零，full持平R3。未刷新计数1。
- R5同结构新训练/开发种子再搜索。开发收益1.03%过门槛，历史权重非零，full Q4 548.829651685033刷新，计数0。
- R6新种子域重新训练历史权重与source_priority，开发选回R5输入；候选SHA与R5相同，full持平，计数1。
- R7新增 `boundary=clip((norm(center)-1350)/450,0,1)`，center仅由已公开bearing的可行圆得来。联合搜索boundary、source_priority、station_gain、uncertainty。开发534.7874814166242相对输入539.4368914509976过0.5%；full Q4 548.5156891280411刷新，计数0。这是四权重整体比较，不能归因于boundary单项。

学习仅影响调度成本排序与有限测点启发式。保留认证覆盖、所有未见频道扫描、保守bearing多边形、16成功上界停止、20米清除证书、25米光学格点兜底、预算切换和原定位上限。`audit_policy.py`逐函数AST检查这些保护部分，env属性仅四接口；这不等于安全沙箱证明，最终仍需读实际diff。

## 训练、文件与预算

`scripts/train_policy.py` 是标准库的原创两阶段精英随机搜索，不是ARS完整算法、DAgger或神经网络。R1/R2各48候选×96训练局/题、前5+输入最多6×192开发局；R3只Q4同预算；R4起Q4为32×144、前5+输入最多6×288。从R3起预设开发改善门槛0.005。新轮训练前在日志声明预算、保存training架构，再启动。

各轮新种子域由 `6600000+round*100000+mode*10000+offset+i` 产生，train offset0、dev5000，与v1 5000–5099完全分离。训练模拟器可用真值生成观测和事后时间/全清奖励，但求解器只接入InterfaceOnly，不能读取真值、测试ID、场景名称或缓存。v1是暴露回归集，禁止内层试参；主协调在各路线最终定稿后另生成共同新样本，不能接触它调参。

截至R7实际训练/开发共53376局、参数尝试368组；full16800局、quick840局。另R3训练真实重放5760局，48组参数与逐局虚拟耗时全部复现，这不是新增样本，单列成本。尚未运行最终开发消融：`scripts/ablate_development.py`已起草，等真正停止后可做；它只在选中轮已暴露开发集上单特征移除诊断，不参与候选选择。`scripts/final_audit.py`截至7轮全部通过，`final_audit.json`是阶段审计，后续要重新生成并更新报告。

核心文件：`plan.md`、`iteration_log.md`、`best.json`、`report.md`、`literature.json`、`reproduce.md`，每轮 `training/rN` 全尝试/开发/案例/选中配置、`snapshots/rN_training_architecture.py` 与 `rN_solver.py`、`rN_*aggregate.json`、`results/A6_learning_rN_{quick,full}`。

候选流水：改当前最佳架构并复制训练快照→train_policy产生新training/rN目录→freeze_candidate.py --round N→规则unit/79nominal/verify/边界AST→quick120→record_round --suite quick→full2400→record_round→update_best→若未接受恢复best快照到根solver→报告/日志→提交代码和全结果→将准确源码commit填回best再更新报告提交→push分支。路径不覆盖旧结果。

## 文献与最终交付

实际读取10篇一手来源，4核心正文深读：ARS、DAgger、Attention routing、Shielding；6扩展正文节选：ES、PPO、Bayesian optimization、PILCO、Neural CO、GP sensor placement。逐篇页码/章节/真正范围、URL、版本、哈希与启发/未采用边界在 `literature.json`；不要把下载等同全文深读。`scripts/finalize_literature.py`截至R7已清理empirical_support/round_links待实验占位，最终继续同步所有轮次与实际结果；未实现原论文完整算法均如实标明。

最终需达到停止条件后：完整中文报告（可由render_report.py生成再人工查）、精确best与非支配候选说明、学习预算/重放/可选消融/quick/full分开、场景退步与最差局、来源到轮次函数映射、部署辅助文件散列、最终审计。参数已嵌入solver，无外部权重依赖，仅标准库，coverage_points.json不存在，用原认证覆盖。冻结manifest sha `431210a6d96e721d23c31698aa389702ea87dcffe8fee6250f71ce6e902be140`。

推荐Python `/Users/t/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`；系统Python中文stdin曾编码失败，不用。Git push临时清代理 `git -c http.proxy= -c https.proxy= push origin experiments/20260911/a6_learning`；已授权，无需重复确认，不改全局配置。Windows官方演练尚未做，不启动正式测试。
