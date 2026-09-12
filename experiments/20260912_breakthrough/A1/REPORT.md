# A1 最终结果：R11 保留

最终自包含候选 [BEST.py](BEST.py) 与 `snapshots/r11.py` 字节完全相同，SHA256 `6c73bf90ac76b6e6e3d34b90883bf9acbf5e6a1443640633d29b3eb653a55cd7`。它不替换主目录 solver.py。

4800 个已暴露本地案例全部正常退出全清，其中 Q3 2400 局、30970 个源，平均 **229.870324746073 秒/源**；相对 C7 235.876945811892 改善 2.546506%。Q4 2400 局仍为 456.111820875735，任务指标逐行不变。

这是固定模拟规则下的实际策略执行/虚拟任务费用，不是官方成绩、生产实测、RL训练结果或新的盲测。指标先逐局 T/真实清除数，再算术平均；不等于所有时间求和除以所有源数。

## 1. 逐轮选择与停止

| 运行版本 | 结论 | Q3 quick（60局） | Q3 两批合并（2400局） | 对当时保留法 Δ秒/源 | 实际策略运行 |
|---|---|---:|---:|---:|---:|
| [r1](snapshots/r1.py) | retained | 235.674186132 | 233.167600766 | — | 4920 |
| [r2](snapshots/r2.py) | retained | 233.245748511 | 230.821418099 | -2.346182668 | 4920 |
| [r3](snapshots/r3.py) | rejected_quick | 237.053895849 | — | 3.808147338 | 120 |
| [r4](snapshots/r4.py) | rejected_quick | 235.490563581 | — | 2.244815069 | 120 |
| [r5](snapshots/r5.py) | rejected_quick_stop_D2 | 235.811803800 | — | 2.566055289 | 120 |
| [r6](snapshots/r6.py) | draft_not_executed | — | — | — | 0 |
| [r6a](snapshots/r6a.py) | execution_failure_not_efficiency_ranked | — | — | — | 120 |
| [r6b](snapshots/r6b.py) | retained | 233.189956355 | 230.475642950 | -0.345775149 | 4920 |
| [r7](snapshots/r7.py) | retained_marginal | 233.189956355 | 230.444716605 | -0.030926345 | 4920 |
| [r8](snapshots/r8.py) | not_promoted_opposite_batch_signs | 233.086542807 | 230.437994713 | -0.006721891 | 4920 |
| [r9](snapshots/r9.py) | retained_marginal | 233.086542807 | 230.406547879 | -0.038168726 | 4920 |
| [r10](snapshots/r10.py) | retained_marginal | 233.086542807 | 230.401345901 | -0.005201977 | 4920 |
| [r11](snapshots/r11.py) | retained | 232.909581829 | 229.870324746 | -0.531021155 | 4920 |
| [r12](snapshots/r12.py) | rejected_quick | 233.006667478 | — | 0.097085649 | 120 |
| [r13](snapshots/r13.py) | rejected_quick | 232.935575101 | — | 0.025993272 | 120 |
| [r14](snapshots/r14.py) | rejected_both_batches_stop_D3 | 232.602383352 | 229.952165279 | 0.081840533 | 4920 |

表中只有 quick 的 Δ 也仅指 quick，不能冒充4800回归。R6是未执行稿；R6a有59次Q3 NameError，其均值不排名；R6b仅修复缺失导入后重跑，不算三个独立算法轮。

`retained_marginal` 明确标出两批同向但很小的已接受增量（R7/R9/R10）；其他 `retained` 的实际幅度直接见数值，不另造综合得分或显著性结论。R8设计父是R6b，晋级对照已更新为R7；两批异号，所以即使合计略低也没有晋级。

* D1：把已知频道站内补测接入已有任务费用门控，保留R1。
* D2：每个定位轮次后全局重规划，保留R2；R3–R5的服务位置/信息价格变体连续三轮不晋级后停止。
* D3：认证 paid-stop 替站、未来站旋转、有限 minimax 更新，再到只裁短已选扫描站进入段；真实扫描与退出证据都保留。

最终方向状态：

- D1：R1 retained; moved to a genuinely different scheduling mechanism, not an abandoned failure streak
- D2：R2 retained, R3/R4/R5 three consecutive quick nonpromotions; direction stopped
- D3：STOPPED after R12/R13 quick nonpromotions and R14 both-batch full regression (three consecutive). Retain R11. Earlier R7/R9/R10 were explicitly retained_marginal; no new direction renamed to reset this streak.

## 2. 退步与尾部风险

最终候选相对 r10：599 快 / 1584 同 / 217 慢；最大单局退步 72.219256500 秒/源；最终最差 Q3 局 400.969544000 秒/源。平均改善并不意味逐局或最差局改善。

| Q3 场景（每组200局） | 相对当时保留法 Δ秒/源 | 快 / 同 / 慢 |
|---|---:|---:|
| cell500_shared_field | -0.032340835 | 49 / 135 / 16 |
| cell50_shared_field | -0.139740552 | 56 / 127 / 17 |
| edge_mixed_min_radius | 0.214470296 | 109 / 0 / 91 |
| exactly10_sources | -0.097495094 | 42 / 141 / 17 |
| exactly16_sources | -0.122439277 | 48 / 130 / 22 |
| fixed_negative_bias | -0.163760676 | 58 / 127 / 15 |
| fixed_positive_bias | -0.197690926 | 70 / 125 / 5 |
| minimum_radius | -0.236346560 | 2 / 198 / 0 |
| offcenter_cluster | -5.349601625 | 60 / 140 / 0 |
| origin_cluster | 0.000000000 | 0 / 200 / 0 |
| reference_assumed | -0.045408418 | 49 / 127 / 24 |
| smooth_shared_field | -0.201900195 | 56 / 134 / 10 |

所有前轮、每批、每组和C7对照都保存在 [iteration_ledger.json](iteration_ledger.json)，没有省略负结果。上述场景是已暴露研发分组；任何读后修正仍属于开发，不可称未见验证。

## 3. 正确性与在线权限

只通过 enter/measure/clear/exit。源真值、案例ID与源总数只在评测脚本计分，不传给策略。站点只在未扫描状态改变，仍在最终坐标真实扫描未知频道。退出时，除16个真实clear成功达到公开上界外，每个未清频道必须没有正观测，并用自己的真实no_signal位置通过连续覆盖充分条件。Q4不使用该全向无信号证明。

证书采用外包目标圆的256边多边形、向外放宽的Voronoi半平面、所有顶点至所属站≤999.999米和范数凸性。离散点只做拒绝；浮点实现带0.001米余量，不伪称区间算术证明。详见 [RESEARCH.md](RESEARCH.md) 和 [R6_RESULT.md](R6_RESULT.md)。

进入段裁短只保证给定下一点时两条欧氏边的路长不增；新观测可能改变整个闭环，因此完整运行才决定效率晋级。规则14/14、nominal79/79和冻结manifest检查的原始输出按轮留存，这些规则检查不是14或79次候选游戏。

## 4. 成本与样本账本

- 候选评测实际执行 45000 次，v1记录的请求数 8786052；含59次运行错误，未丢弃。评测墙钟合计 1224.780293 秒。
- 另计诊断重放 2580 次、同口径记录请求 330896 次；总策略执行 47580 次、v1口径记录请求 9116948 次。
- 首次R6b诊断的读日志错误发生在第60局；其请求数按同一冻结候选/世界的确定性重放恢复，不冒充第一次完整保留下来的动作账。
- 仍只有 4800 个独立案例ID；quick是full子集，exposed复用full再追加另一批。新增最终盲测0，官方执行0，RL训练0。
- 请求计数严格沿用v1：measures + clear_attempts + int(started) + int(user_exit)。参数或状态预校验拒绝的尝试未完整计入，因未安装独立attempted/accepted计数包装，不能声称这是全部接口调用尝试账。诊断的完整成功局以measure/clear计数加2复现同一口径；规则和纯合成几何另列。
- 墙钟没有包含全部研究阅读、下载、代码编辑、合成几何、汇总与协调审计开销；各轮有并行负载，不用这些时长宣称受控CPU加速。

诊断账：

- C7 quick action-cost trace：60 次、8235 条v1口径记录请求；saved counters and actions。
- R6b first diagnostic reader failure：60 次、7885 条v1口径记录请求；count reconstructed by deterministic replay of the same immutable candidate and worlds, not an independently saved first-attempt action ledger。
- R6b repaired diagnostic replay：60 次、7885 条v1口径记录请求；saved counters。
- Final R11 real measurement and exit-negative evidence replay on all 2400 exposed Q3 worlds：2400 次、306891 条v1口径记录请求；results/r11_all_q3_cover_diagnostic.json。

## 5. 研究与复核入口

[RESEARCH.md](RESEARCH.md) 按付费信息、服务调度、发现几何三层机制组织3篇核心定向阅读与1篇引用发现；[literature.json](literature.json) 保存一手来源、版本、实际阅读页节、未读范围、SHA和本题迁移边界。未把文献定理直接套到本题，也未把后读论文追溯为先实现机制的原因。

重新核账与封装（不重跑策略）：

```bash
python3.12 -S -B experiments/20260912_breakthrough/A1/summarize.py
python3.12 -S -B experiments/20260912_breakthrough/A1/package_final.py
```

最终包见 [BEST_manifest.json](BEST_manifest.json)。BEST_Q3_COMPONENT.py只供协调者在固定C7命名空间内融合；主候选BEST.py本身不依赖外部文件。最终Q3/Q4融合、逐请求等价验证与Git提交由协调者独立负责，本子分支没有提交或推送。
