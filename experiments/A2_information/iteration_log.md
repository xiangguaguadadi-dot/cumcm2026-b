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

第一轮结论：Q3 改善而 Q4 退步，保留为非支配候选，共同最佳仍为原版。没有以合并指标把取舍说成全面改善。第一轮开发检查 `dev/r1_preliminary.json`：各题24局；Q3 337.1310 vs 341.0363，Q4 766.1990 vs 712.8780。仅试一个规划器，没有隐藏参数扫描。

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

第二轮结论：Q3持平第一轮，Q4由578.9624下降到574.8171，但仍比基准慢0.6891%。第二轮支配第一轮这个取舍候选；共同最佳仍为原版，非支配集为原版和第二轮。quick的Q4虽略胜基准，full未支持该改善，不能用quick替代full。开发集910100–910109每题60局也保留，未做参数扫描。开发数据中boundary/min_radius的第四问可能全定向，属于比题设混合更强的压力场景，不能冒充官方分布。

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

第三轮结论：Q3 299.76540283、Q4 570.73731319，两题均低于基准且均低于第二轮，2400局全清，因此当前共同最佳更新为第三轮。Q4收益仅0.0256%，必须视为很小的本地改进，等待独立新样本检验。第三轮启用Q3主动观测、Q4回退原版测点，两题使用全顶点最近认证清除。几何505项检查通过。

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

第四轮结论：Q3大幅改善，但Q4比第三轮略慢，故为取舍，未刷新严格共同最佳（仍R3）。完整v1的2400局都成功并正常退出。独立压力开发初次运行因过久在nearest_certified_clear内手动中断，未保存完整开发均值；随后用5秒/局的诊断看门狗完整记录120局，部分全定向边界案例顶点数达数千乃至上万，触发诊断限时。这个5秒阈值不是官方1200秒时限，不把它等同于官方超时，但该复杂度风险使R4不可直接部署。详见dev/r4_watchdog.jsonl及development_interrupt.json。下一轮回到可控制复杂度的设计，不进行隐式参数扫描。

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

第五轮结论：Q3 290.85380296、Q4 570.73731319，分别减少5.0430%和0.0256%；2400局全清，刷新严格共同最佳为第五轮（支配R3）。R4的Q3均值仅比R5少0.000024秒/源，而其计算风险明显；保留R4原始数字，不把R5说成在每个小数位都支配R4。计算退化重放120局全部完成，最高49顶点，最长0.0514秒，5秒诊断超时由5个降为0。

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

第六轮结论：Q3 286.01852917、Q4 570.73731319；2400局全清，无异常。Q3进一步改善、Q4与第五轮严格相同，因此当前共同最佳为R6，连续未刷新计数归零。随后按照主Agent调度暂存释放名额，尚未达到两轮未刷新停止条件。无信号排除仅在Q3启用，完整几何证明与独立点验证留存。

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

第七轮结论：Q3 286.01274518、Q4 570.73731319，2400局全清。Q3只比R6快0.00578399秒/源，Q4逐局相同，按预定严格共同最佳口径更新R7并将未刷新计数归零；不把这一极小回归差异描述为显著或稳健改善。新增planning_hypotheses只影响排序；有限提案为空退回原假想点，不改变正确性。

