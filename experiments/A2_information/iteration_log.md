# A2 实验迭代日志

固定评测：LOCAL-v1；quick 是 full 子集，不是独立留出集。完整成功才比较虚拟时间。原版共同最佳 Q3 306.3004342181635、Q4 570.8833714439976 秒/源。

## 第 1 轮

- 候选：`experiments/A2_information/candidates/r1_solver.py`；SHA256 `98b3ebe2c4ef736a91e1efbc40a917c66f3b413df1787e4dc16544fb8618b1b5`。
- full 结果：`results/A2_information_r1_full`；实际运行 62.941 秒；完整通过：True。
- 规则记录：`results/A2_information_r1_rules/`；quick：`results/A2_information_r1_quick/`。

| 题目 | 全清 | 秒/源 | 对基准减少 |
|---|---:|---:|---:|
| Q3 | 1200/1200 | 299.77975194 | 2.1289% |
| Q4 | 1200/1200 | 578.96236624 | -1.4152% |

逐场景退步（负减少率；不隐藏）：

- Q3 `origin_cluster`：增加 1.4413%。
- Q4 `cell500_shared_field`：增加 2.0852%。
- Q4 `cell50_shared_field`：增加 1.7875%。
- Q4 `edge_mixed_min_radius`：增加 4.0755%。
- Q4 `exactly10_sources`：增加 1.9236%。
- Q4 `exactly16_sources`：增加 3.1254%。
- Q4 `fixed_negative_bias`：增加 3.3933%。
- Q4 `fixed_positive_bias`：增加 2.0575%。
- Q4 `minimum_radius`：增加 4.3272%。
- Q4 `reference_assumed`：增加 2.6624%。
- Q4 `smooth_shared_field`：增加 2.6720%。

相对本轮进入时共同最佳（R0；R0指冻结基准）的场景退步：

- Q3 `origin_cluster`：343.45265759 → 348.40270445 秒/源，增加 4.95004686。
- Q4 `cell500_shared_field`：565.19671769 → 576.98246496 秒/源，增加 11.78574726。
- Q4 `cell50_shared_field`：569.00135758 → 579.17208703 秒/源，增加 10.17072945。
- Q4 `edge_mixed_min_radius`：613.72939159 → 638.74218511 秒/源，增加 25.01279353。
- Q4 `exactly10_sources`：705.16422774 → 718.72871664 秒/源，增加 13.56448890。
- Q4 `exactly16_sources`：442.45192554 → 456.28013187 秒/源，增加 13.82820633。
- Q4 `fixed_negative_bias`：577.73959280 → 597.34394970 秒/源，增加 19.60435690。
- Q4 `fixed_positive_bias`：594.83367733 → 607.07253816 秒/源，增加 12.23886083。
- Q4 `minimum_radius`：583.15604875 → 608.39013626 秒/源，增加 25.23408751。
- Q4 `reference_assumed`：560.02768048 → 574.93796113 秒/源，增加 14.91028064。
- Q4 `smooth_shared_field`：578.30534229 → 593.75737843 秒/源，增加 15.45203614。

第一轮结论：Q3 改善而 Q4 退步，保留为非支配候选，共同最佳仍为原版。没有以合并指标把取舍说成全面改善。第一轮开发检查 `dev/r1_preliminary.json`：各题24局；Q3 337.1310 vs 341.0363，Q4 766.1990 vs 712.8780。仅试一个规划器，没有隐藏参数扫描。

本轮源码提交：`cf24d2a0d8ba0ad37e6fc205466e9cac1d4ca562`。全测异常数：Q3=0，Q4=0。共同最佳更新：False；本轮后为R0，SHA256 `36271e5c84cdcd4468b54484d699dce64194f09d78c0c03f3ec1c38f105f6ca9`；连续未刷新计数1。

## 第 2 轮

- 候选：`experiments/A2_information/candidates/r2_solver.py`；SHA256 `b49e990717ace3c7755931bde58652ec4e76493423f1edd021d2199a687a5c0a`。
- full 结果：`results/A2_information_r2_full`；实际运行 57.606 秒；完整通过：True。
- 规则记录：`results/A2_information_r2_rules/`；quick：`results/A2_information_r2_quick/`。

| 题目 | 全清 | 秒/源 | 对基准减少 |
|---|---:|---:|---:|
| Q3 | 1200/1200 | 299.77975194 | 2.1289% |
| Q4 | 1200/1200 | 574.81712193 | -0.6891% |

逐场景退步（负减少率；不隐藏）：

- Q3 `origin_cluster`：增加 1.4413%。
- Q4 `cell500_shared_field`：增加 1.0591%。
- Q4 `cell50_shared_field`：增加 1.5691%。
- Q4 `edge_mixed_min_radius`：增加 2.2816%。
- Q4 `exactly10_sources`：增加 1.3894%。
- Q4 `exactly16_sources`：增加 2.4227%。
- Q4 `fixed_negative_bias`：增加 2.7973%。
- Q4 `fixed_positive_bias`：增加 1.0475%。
- Q4 `minimum_radius`：增加 3.2862%。
- Q4 `reference_assumed`：增加 2.2238%。
- Q4 `smooth_shared_field`：增加 1.7231%。

相对本轮进入时共同最佳（R0；R0指冻结基准）的场景退步：

- Q3 `origin_cluster`：343.45265759 → 348.40270445 秒/源，增加 4.95004686。
- Q4 `cell500_shared_field`：565.19671769 → 571.18295648 秒/源，增加 5.98623879。
- Q4 `cell50_shared_field`：569.00135758 → 577.92979444 秒/源，增加 8.92843686。
- Q4 `edge_mixed_min_radius`：613.72939159 → 627.73223747 秒/源，增加 14.00284589。
- Q4 `exactly10_sources`：705.16422774 → 714.96183794 秒/源，增加 9.79761020。
- Q4 `exactly16_sources`：442.45192554 → 453.17101197 秒/源，增加 10.71908643。
- Q4 `fixed_negative_bias`：577.73959280 → 593.90055603 秒/源，增加 16.16096324。
- Q4 `fixed_positive_bias`：594.83367733 → 601.06437193 秒/源，增加 6.23069460。
- Q4 `minimum_radius`：583.15604875 → 602.31994672 秒/源，增加 19.16389798。
- Q4 `reference_assumed`：560.02768048 → 572.48164069 秒/源，增加 12.45396021。
- Q4 `smooth_shared_field`：578.30534229 → 588.27035890 秒/源，增加 9.96501661。

第二轮结论：Q3持平第一轮，Q4由578.9624下降到574.8171，但仍比基准慢0.6891%。第二轮支配第一轮这个取舍候选；共同最佳仍为原版，非支配集为原版和第二轮。quick的Q4虽略胜基准，full未支持该改善，不能用quick替代full。开发集910100–910109每题60局也保留，未做参数扫描。开发数据中boundary/min_radius的第四问可能全定向，属于比题设混合更强的压力场景，不能冒充官方分布。

本轮源码提交：`42fd42cd850f6dce6a860caaae6388ad533aa83e`。全测异常数：Q3=0，Q4=0。共同最佳更新：False；本轮后为R0，SHA256 `36271e5c84cdcd4468b54484d699dce64194f09d78c0c03f3ec1c38f105f6ca9`；连续未刷新计数2。

## 第 3 轮

- 候选：`experiments/A2_information/candidates/r3_solver.py`；SHA256 `f9832cb9f401ccdeaa2b37b24ff997f6907d81bd68f4f24d84444e23feb7c757`。
- full 结果：`results/A2_information_r3_full`；实际运行 45.344 秒；完整通过：True。
- 规则记录：`results/A2_information_r3_rules/`；quick：`results/A2_information_r3_quick/`。

| 题目 | 全清 | 秒/源 | 对基准减少 |
|---|---:|---:|---:|
| Q3 | 1200/1200 | 299.76540283 | 2.1335% |
| Q4 | 1200/1200 | 570.73731319 | 0.0256% |

逐场景退步（负减少率；不隐藏）：

- Q3 `origin_cluster`：增加 1.4495%。
- Q4 `cell50_shared_field`：增加 0.2111%。
- Q4 `edge_mixed_min_radius`：增加 0.0912%。
- Q4 `exactly10_sources`：增加 0.0216%。
- Q4 `exactly16_sources`：增加 0.0026%。
- Q4 `reference_assumed`：增加 0.1043%。

相对本轮进入时共同最佳（R0；R0指冻结基准）的场景退步：

- Q3 `origin_cluster`：343.45265759 → 348.43105475 秒/源，增加 4.97839716。
- Q4 `cell50_shared_field`：569.00135758 → 570.20255129 秒/源，增加 1.20119371。
- Q4 `edge_mixed_min_radius`：613.72939159 → 614.28923073 秒/源，增加 0.55983915。
- Q4 `exactly10_sources`：705.16422774 → 705.31683882 秒/源，增加 0.15261108。
- Q4 `exactly16_sources`：442.45192554 → 442.46328327 秒/源，增加 0.01135773。
- Q4 `reference_assumed`：560.02768048 → 560.61173538 秒/源，增加 0.58405489。

第三轮结论：Q3 299.76540283、Q4 570.73731319，两题均低于基准且均低于第二轮，2400局全清，因此当前共同最佳更新为第三轮。Q4收益仅0.0256%，必须视为很小的本地改进，等待独立新样本检验。第三轮启用Q3主动观测、Q4回退原版测点，两题使用全顶点最近认证清除。几何505项检查通过。

本轮源码提交：`f587f7a5ebf988477be9a7ff4a30fabefacae37b`。全测异常数：Q3=0，Q4=0。共同最佳更新：True；本轮后为R3，SHA256 `f9832cb9f401ccdeaa2b37b24ff997f6907d81bd68f4f24d84444e23feb7c757`；连续未刷新计数0。

## 第 4 轮

- 候选：`experiments/A2_information/candidates/r4_solver.py`；SHA256 `e26653b64a69a142b854789d9614d076fdd70c124cc6cf69c0f4ecddf1f5af44`。
- full 结果：`results/A2_information_r4_full`；实际运行 71.085 秒；完整通过：True。
- 规则记录：`results/A2_information_r4_rules/`；quick：`results/A2_information_r4_quick/`。

| 题目 | 全清 | 秒/源 | 对基准减少 |
|---|---:|---:|---:|
| Q3 | 1200/1200 | 290.85377897 | 5.0430% |
| Q4 | 1200/1200 | 570.82995784 | 0.0094% |

逐场景退步（负减少率；不隐藏）：

- Q4 `cell50_shared_field`：增加 0.4931%。
- Q4 `exactly10_sources`：增加 0.0020%。
- Q4 `exactly16_sources`：增加 0.7132%。
- Q4 `fixed_positive_bias`：增加 0.4018%。

相对本轮进入时共同最佳（R3；R0指冻结基准）的场景退步：

- Q3 `cell500_shared_field`：294.90810644 → 295.63657450 秒/源，增加 0.72846806。
- Q3 `cell50_shared_field`：295.54776421 → 296.90917824 秒/源，增加 1.36141403。
- Q3 `exactly16_sources`：250.94383550 → 252.20394315 秒/源，增加 1.26010765。
- Q3 `fixed_negative_bias`：298.43986718 → 300.62729402 秒/源，增加 2.18742685。
- Q3 `reference_assumed`：293.96577383 → 295.06554695 秒/源，增加 1.09977311。
- Q4 `cell50_shared_field`：570.20255129 → 571.80732681 秒/源，增加 1.60477551。
- Q4 `exactly16_sources`：442.46328327 → 445.60748956 秒/源，增加 3.14420629。
- Q4 `fixed_positive_bias`：594.78299229 → 597.22366268 秒/源，增加 2.44067040。
- Q4 `origin_cluster`：537.35371173 → 541.13627191 秒/源，增加 3.78256018。

第四轮结论：Q3大幅改善，但Q4比第三轮略慢，故为取舍，未刷新严格共同最佳（仍R3）。完整v1的2400局都成功并正常退出。独立压力开发初次运行因过久在nearest_certified_clear内手动中断，未保存完整开发均值；随后用5秒/局的诊断看门狗完整记录120局，部分全定向边界案例顶点数达数千乃至上万，触发诊断限时。这个5秒阈值不是官方1200秒时限，不把它等同于官方超时，但该复杂度风险使R4不可直接部署。详见dev/r4_watchdog.jsonl及development_interrupt.json。后续R5修复计算复杂度，没有进行隐式参数扫描。

本轮源码提交：`302a0012452ff75c094455cce861e3721127bc2d`。全测异常数：Q3=0，Q4=0。共同最佳更新：False；本轮后为R3，SHA256 `f9832cb9f401ccdeaa2b37b24ff997f6907d81bd68f4f24d84444e23feb7c757`；连续未刷新计数1。

## 第 5 轮

- 候选：`experiments/A2_information/candidates/r5_solver.py`；SHA256 `e1f545f67406adce022eac57a8be6091bba312631cdd8d260ecce50d7438527d`。
- full 结果：`results/A2_information_r5_full`；实际运行 57.349 秒；完整通过：True。
- 规则记录：`results/A2_information_r5_rules/`；quick：`results/A2_information_r5_quick/`。

| 题目 | 全清 | 秒/源 | 对基准减少 |
|---|---:|---:|---:|
| Q3 | 1200/1200 | 290.85380296 | 5.0430% |
| Q4 | 1200/1200 | 570.73731319 | 0.0256% |

逐场景退步（负减少率；不隐藏）：

- Q4 `cell50_shared_field`：增加 0.2111%。
- Q4 `edge_mixed_min_radius`：增加 0.0912%。
- Q4 `exactly10_sources`：增加 0.0216%。
- Q4 `exactly16_sources`：增加 0.0026%。
- Q4 `reference_assumed`：增加 0.1043%。

相对本轮进入时共同最佳（R3；R0指冻结基准）的场景退步：

- Q3 `cell500_shared_field`：294.90810644 → 295.63657450 秒/源，增加 0.72846806。
- Q3 `cell50_shared_field`：295.54776421 → 296.90917824 秒/源，增加 1.36141403。
- Q3 `exactly16_sources`：250.94383550 → 252.20396977 秒/源，增加 1.26013427。
- Q3 `fixed_negative_bias`：298.43986718 → 300.62729402 秒/源，增加 2.18742685。
- Q3 `reference_assumed`：293.96577383 → 295.06542413 秒/源，增加 1.09965029。

第五轮结论：Q3 290.85380296、Q4 570.73731319，分别减少5.0430%和0.0256%；2400局全清，刷新严格共同最佳为第五轮（支配R3）。R4的Q3均值仅比R5少0.000024秒/源，而其计算风险明显；保留R4原始数字，不把R5说成在每个小数位都支配R4。计算退化重放120局全部完成，最高49顶点，最长0.0514秒，5秒诊断超时由5个降为0。

本轮源码提交：`d22a63e91395860755470124b51361d716aff8f3`。全测异常数：Q3=0，Q4=0。共同最佳更新：True；本轮后为R5，SHA256 `e1f545f67406adce022eac57a8be6091bba312631cdd8d260ecce50d7438527d`；连续未刷新计数0。

## 第 6 轮

- 候选：`experiments/A2_information/candidates/r6_solver.py`；SHA256 `66faeaa85c405b9c582a45132050cc336082ed1e7fc90d7d8aab8cb3ce954db5`。
- full 结果：`results/A2_information_r6_full`；实际运行 52.151 秒；完整通过：True。
- 规则记录：`results/A2_information_r6_rules/`；quick：`results/A2_information_r6_quick/`。

| 题目 | 全清 | 秒/源 | 对基准减少 |
|---|---:|---:|---:|
| Q3 | 1200/1200 | 286.01852917 | 6.6216% |
| Q4 | 1200/1200 | 570.73731319 | 0.0256% |

逐场景退步（负减少率；不隐藏）：

- Q4 `cell50_shared_field`：增加 0.2111%。
- Q4 `edge_mixed_min_radius`：增加 0.0912%。
- Q4 `exactly10_sources`：增加 0.0216%。
- Q4 `exactly16_sources`：增加 0.0026%。
- Q4 `reference_assumed`：增加 0.1043%。

相对本轮进入时共同最佳（R5；R0指冻结基准）的场景退步：

- Q3 `offcenter_cluster`：230.97684274 → 234.85999239 秒/源，增加 3.88314965。

第六轮结论：Q3 286.01852917、Q4 570.73731319；2400局全清，无异常。Q3进一步改善、Q4与第五轮严格相同，因此当前共同最佳为R6，连续未刷新计数归零。无信号排除仅在Q3启用，完整几何证明与独立点验证留存。

本轮源码提交：`e6a187766dff9370a4656434867cdead399842f0`。全测异常数：Q3=0，Q4=0。共同最佳更新：True；本轮后为R6，SHA256 `66faeaa85c405b9c582a45132050cc336082ed1e7fc90d7d8aab8cb3ce954db5`；连续未刷新计数0。

## 第 7 轮

- 候选：`experiments/A2_information/candidates/r7_solver.py`；SHA256 `f963a3fede0c53fab859e8e9e3b339f5afab7da8a3308d426823c796e3f3fb70`。
- full 结果：`results/A2_information_r7_full`；实际运行 49.481 秒；完整通过：True。
- 规则记录：`results/A2_information_r7_rules/`；quick：`results/A2_information_r7_quick/`。

| 题目 | 全清 | 秒/源 | 对基准减少 |
|---|---:|---:|---:|
| Q3 | 1200/1200 | 286.01274518 | 6.6235% |
| Q4 | 1200/1200 | 570.73731319 | 0.0256% |

逐场景退步（负减少率；不隐藏）：

- Q4 `cell50_shared_field`：增加 0.2111%。
- Q4 `edge_mixed_min_radius`：增加 0.0912%。
- Q4 `exactly10_sources`：增加 0.0216%。
- Q4 `exactly16_sources`：增加 0.0026%。
- Q4 `reference_assumed`：增加 0.1043%。

相对本轮进入时共同最佳（R6；R0指冻结基准）的场景退步：

- Q3 `cell500_shared_field`：289.14572792 → 289.15752874 秒/源，增加 0.01180082。
- Q3 `exactly16_sources`：242.96179833 → 243.03457619 秒/源，增加 0.07277786。
- Q3 `fixed_positive_bias`：291.80402996 → 291.90840480 秒/源，增加 0.10437484。

第七轮结论：Q3 286.01274518、Q4 570.73731319，2400局全清。Q3只比R6快0.00578399秒/源，Q4逐局相同，按预定严格共同最佳口径更新R7并将未刷新计数归零；不把这一极小回归差异描述为显著或稳健改善。新增planning_hypotheses只影响排序；有限提案为空退回原假想点，不改变正确性。

本轮源码提交：`a0e9598567b68c5a16165db5e7c40baa1120f8f7`。全测异常数：Q3=0，Q4=0。共同最佳更新：True；本轮后为R7，SHA256 `f963a3fede0c53fab859e8e9e3b339f5afab7da8a3308d426823c796e3f3fb70`；连续未刷新计数0。

## 第 8 轮

- 候选：`experiments/A2_information/candidates/r8_solver.py`；SHA256 `bd0ed7b8d322d6502c04c1bf100857001617cca235038a2d78bcacf4d97b82bc`。
- full 结果：`results/A2_information_r8_full`；实际运行 48.862 秒；完整通过：True。
- 规则记录：`results/A2_information_r8_rules/`；quick：`results/A2_information_r8_quick/`。

| 题目 | 全清 | 秒/源 | 对基准减少 |
|---|---:|---:|---:|
| Q3 | 1200/1200 | 285.86670335 | 6.6711% |
| Q4 | 1200/1200 | 568.44941153 | 0.4263% |

逐场景退步（负减少率；不隐藏）：

- 无；24个题目/场景均值均未比冻结基准退步。

相对本轮进入时共同最佳（R7；R0指冻结基准）的场景退步：

- Q3 `cell500_shared_field`：289.15752874 → 289.31317829 秒/源，增加 0.15564955。
- Q3 `cell50_shared_field`：289.74029762 → 289.78690928 秒/源，增加 0.04661166。
- Q3 `edge_mixed_min_radius`：300.88662708 → 300.93332272 秒/源，增加 0.04669564。
- Q3 `exactly10_sources`：346.07198260 → 346.11056896 秒/源，增加 0.03858636。
- Q3 `exactly16_sources`：243.03457619 → 243.24173285 秒/源，增加 0.20715666。
- Q3 `offcenter_cluster`：234.70528427 → 234.84945912 秒/源，增加 0.14417485。
- Q3 `origin_cluster`：270.58669559 → 270.60294325 秒/源，增加 0.01624766。
- Q3 `reference_assumed`：288.28039774 → 288.30318356 秒/源，增加 0.02278581。

第八轮结论：Q3 285.86670335、Q4 568.44941153；2400局全清。光学失败信息使两题均值均改善，刷新最佳R8，未刷新计数归零；仍需单列场景退步。全局覆盖与格点兜底未修改。

本轮源码提交：`deb4f4b5477fb15d25d1c98bb8d353f6a2c3c400`。全测异常数：Q3=0，Q4=0。共同最佳更新：True；本轮后为R8，SHA256 `bd0ed7b8d322d6502c04c1bf100857001617cca235038a2d78bcacf4d97b82bc`；连续未刷新计数0。

## 第 9 轮

- 候选：`experiments/A2_information/candidates/r9_solver.py`；SHA256 `a759e118611f2443cf66156dc0b3eaf91e49c2a9254eec49a5f42e8050f7a0f2`。
- full 结果：`results/A2_information_r9_full`；实际运行 49.640 秒；完整通过：True。
- 规则记录：`results/A2_information_r9_rules/`；quick：`results/A2_information_r9_quick/`。

| 题目 | 全清 | 秒/源 | 对基准减少 |
|---|---:|---:|---:|
| Q3 | 1200/1200 | 285.95192367 | 6.6433% |
| Q4 | 1200/1200 | 568.40397853 | 0.4343% |

逐场景退步（负减少率；不隐藏）：

- 无；24个题目/场景均值均未比冻结基准退步。

相对本轮进入时共同最佳（R8；R0指冻结基准）的场景退步：

- Q3 `cell500_shared_field`：289.31317829 → 289.52571910 秒/源，增加 0.21254081。
- Q3 `cell50_shared_field`：289.78690928 → 290.18841447 秒/源，增加 0.40150519。
- Q3 `exactly16_sources`：243.24173285 → 243.49816409 秒/源，增加 0.25643124。
- Q3 `fixed_positive_bias`：290.97841251 → 291.07449924 秒/源，增加 0.09608673。
- Q3 `offcenter_cluster`：234.84945912 → 235.22503065 秒/源，增加 0.37557153。
- Q3 `reference_assumed`：288.30318356 → 288.35354953 秒/源，增加 0.05036597。
- Q4 `reference_assumed`：559.43977456 → 559.44262524 秒/源，增加 0.00285068。

第九轮结论：Q3 285.95192367、Q4 568.40397853，2400局全清。相对R8，Q3慢0.08522032秒/源而Q4快0.04543300秒/源，是非支配取舍，严格共同最佳仍为R8；连续未刷新计数1。后续R10由干净上下文仅从本路线自身材料接续设计。

本轮源码提交：`c4511bc1a90a08ee3351b585b534e4cce73317ef`。全测异常数：Q3=0，Q4=0。共同最佳更新：False；本轮后为R8，SHA256 `bd0ed7b8d322d6502c04c1bf100857001617cca235038a2d78bcacf4d97b82bc`；连续未刷新计数1。

## 第 10 轮

- 候选：`experiments/A2_information/candidates/r10_solver.py`；SHA256 `bae43c00cf155f667c01fb3df65545d422cf2fd546c5ea8dd5e624b494f65b60`。
- full 结果：`results/A2_information_r10_full`；实际运行 101.647 秒；完整通过：True。
- 规则记录：`results/A2_information_r10_rules/`；quick：`results/A2_information_r10_quick/`。

| 题目 | 全清 | 秒/源 | 对基准减少 |
|---|---:|---:|---:|
| Q3 | 1200/1200 | 285.86670335 | 6.6711% |
| Q4 | 1200/1200 | 568.44941153 | 0.4263% |

逐场景退步（负减少率；不隐藏）：

- 无；24个题目/场景均值均未比冻结基准退步。

相对本轮进入时共同最佳（R8；R0指冻结基准）的场景退步：

- 无。

第十轮采用接收上界一致的预测后验：predicted_polygon通过已有add_bearing(...,tighten=False)加入24个1500m外切半平面，只影响动作排序。独立开发910900–910909每题60局与R8逐局任务指标一致，1000个合成几何组合全部保持合法目标，52个预测外包发生收紧。full2400局全部清除且与R8逐局秒/源完全一致，未刷新最佳；连续R9/R10未刷新计数2，达到经验停止。没有进一步扫面数或候选参数。编码前解析排除了“中心光学失败后跳过检测”想法，没有把它算作运行候选。

本轮源码提交：`f0af6cd1c6518a84f07b6320df7f7f18900165d3`。全测异常数：Q3=0，Q4=0。共同最佳更新：False；本轮后为R8，SHA256 `bd0ed7b8d322d6502c04c1bf100857001617cca235038a2d78bcacf4d97b82bc`；连续未刷新计数2。

