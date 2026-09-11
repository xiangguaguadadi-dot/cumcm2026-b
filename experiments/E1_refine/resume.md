# E1第四阶段已完成当前结构探索

最新状态：五轮三种结构假设已经完成；所有本地运行已结束，没有等待中的终端任务，不重跑已保存结果。完整报告report.md、路径optimization_path.md/json、full_results_summary.json、best.json。R1 full+旧final4800清，Q4=471.470944912203；R5同样4800清，Q3=235.80780532211148（仅0.0293%均值收益且旧final反向），Q4=472.05832359165936（不如R1）。R5 SHA f8413f0017d5699e6d1e06b2f8c85d2e86c0f6b69afc32a29377dbda8907d604。

R3固定联合落点开发仅Q3/Q4快0.0406/0.1628，择序版退步；24诊断重放每次路由平均认证区0.79/0.29个。R4完整有向服务块两题开发慢1.186/5.180；R5针对性只给当前首任务入口计费。未继续扫先验、格点、扫数与费用权重，因为证据指向未来信息流程错配和很小的联合空间。root已允许在当前结构假设实证饱和后收束。

预算15096实际策略任务，1488新独特开发案例：开发4752、quick720、完整回归9600、诊断重放24。冻结环境、第一二问、根solver未改，无新holdout或官方Windows运行。规则12通过。

外部协调参照C1 Q4=464.925920209869，随后E2 one_round=457.721499866更好。root正在研究C1+one_round；R5入口→center在one_round于测点返调度时不再对应真实控制，不能机械叠加。上述数值由root实际4800评测提供，最终共同best由root维护。

首次进展commit4cbca446a6363f3b1488101d383087e655b33f93已由root在补齐原用户授权、private+ADMIN仓库身份、文件范围证据后正常推送。当前Agent默认网络DNS失败；后续新提交需确认真实push状态，不能把本地提交当已上传。原审核拒绝已被新增证明处理，不得换渠道规避。

--- 以下为历史过程，已完成，不再执行 ---

# E1 第四阶段工作恢复点

工作区仅写 experiments/E1_refine；分支 experiments/20260911-stage4/e1_refine。固定 S1 为 Q3 R2R4 / Q4 R3R5，235.876945812 / 473.897493 秒/源。已读 AGENTS、协议、v1评测口径、第三阶段报告、70节点紧凑入口及相关未实施节点。

当前主线：条件发现路线评分；随后联合多个认证清除区域的连续路线。E2负责Q4机会补测成本/可见性与单步服务；E3负责新文献及多步定位。只通过四接口决策；概率代理不能删除覆盖站或提前发退出证书。50h保护与原安全fallback保持。

开发种子独占 [44000000,45000000)，逐轮登记于 used_seeds.json。禁止读取场景、种子、真值或成绩进入策略。没有新最终留出。

待做：实现R1条件发现代理，对S1做新合法开发对照，规则+quick，有价值候选full+4800，保存负结果；好结果立即commit/push。

## 当前执行状态（阶段4开放研究）

R1已做144个新Q4开发，种子44000000..44000011：S1=490.711017、后验=492.606767、乐观=493.578000，全清；后验请求少3.02但移动多189m。R1后验quick120全清，1.895s。

R2缩到已发现15频道的收尾代理。新288个Q4开发，种子44000012..44000035：S1=465.691593、原后验=464.592032、lastsource=465.538740、lastsource_optimistic=466.172848。全清，但原后验两批排序反转，不能宣称稳定收益。

正在执行：r1_posterior full2400 -> results/r1_full；r2_lastsource quick120 -> results/r2_quick。完成后用实际S1缓存比对应题（不要拿evaluate默认原v1baseline当本阶段S1）。有价值候选用stage4 evaluate_exposed.py + --v1-results（单文件可复用）补2400旧final得到4800，之后立即commit/push。

单文件构建：research/build_candidate.py，把两个parents原字节嵌入独立ModuleType命名空间；snapshots每个文件自包含，不依赖外部父代码。父源码仍在parents/S1_Q3.py和S1_Q4.py便于审阅；部署完整性由单文件SHA涵盖。研究组件research/conditional_route_component.py。

下一主线预案：JOINT_CLEAR_ROUTE_PROPOSED。基于父spatial_next_task的完整固定任务序，记录任务/点位。对每个MEC<=20的已认证源，使用现有_lens_route_point(poly,prev,next,fallback)沿凸可清交集逐点坐标下降2-3扫，其他未知中心/站点固定；只执行首个任务，下次重新规划。保存第一任务的认证clear点，route_clear_point时重新检验全部顶点<=20，不改变覆盖/退出。可先Q4，随后Q3共同探测。尚未实施。

R1 exposed已经完成（勿重跑），全4800清；Q3原样，Q4=471.470944912203；结果results/r1_exposed，best已更新。当前开始R3联合认证区域落点。
