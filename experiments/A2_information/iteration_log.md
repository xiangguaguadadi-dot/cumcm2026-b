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

