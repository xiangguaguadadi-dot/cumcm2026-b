# A6 重现说明

所有命令在本worktree根目录执行。运行Python采用实验使用的解释器：
`/Users/t/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`。
求解器、训练器和评测仅使用标准库；文献文本提取用了现成pypdf，未训练或下载任何神经模型权重。模型是solver中的显式系数，配置与代码散列在best.json。

## 复核最佳

1. 阅读 `best.json` 获取最佳快照路径、SHA256和full结果路径。
2. `python evaluate.py --verify-only` 验证冻结规则/数据/基准。
3. `python -m unittest discover -s tests -v`。
4. `python tests/check_nominal.py --package . --out results/A6_replay_nominal.json`（新路径）。
5. `python experiments/A6_learning/scripts/audit_policy.py BEST_SOLVER_PATH`。
6. `python evaluate.py --suite quick --candidate BEST_SOLVER_PATH --out results/A6_replay_quick`。
7. 快测通过后：`python evaluate.py --suite full --candidate BEST_SOLVER_PATH --out results/A6_replay_full`。

每次输出目录必须不存在。BEST_SOLVER_PATH以best.json为准；不能直接选择较晚但已被拒绝的轮次作为最佳。所有结果是LOCAL-v1，官方Windows演练另行开展。

## 精确重放训练

`python experiments/A6_learning/scripts/replay_training.py --round N --out experiments/A6_learning/reproduced/rN`

`N`对应已经保存的轮次。脚本把冻结local_env、该轮训练架构和对应训练器放到一次性临时目录，按budget.json的预算和种子训练，完成后复制全部结果到指定新目录，比较最终配置是否与原记录一致。不会覆盖原记录或写入冻结评测文件。

历史训练器：R1/R2为`train_policy_r1_r2.py`，R3–R7为`train_policy.py`的对应历史轮次分支；R8起优先使用`snapshots/rN_train_policy.py`冻结训练器。第一轮训练输入是`baseline_solver.py`，其余是`snapshots/rN_training_architecture.py`。R3起只优化Q4，开发改善不足0.5%保留输入策略。不同轮次的数据域相互分开，完整种子可从该轮cases.json重算。开发集参与选择，不能称为盲测。

部署快照全为自包含Python文件。`freeze_candidate.py`用于当时将选中配置写入solver并冻结快照；重现已完成结果优先直接运行已冻结快照，不要覆盖历史文件。

## 文献与额外诊断

`python experiments/A6_learning/scripts/download_literature.py` 从逐篇原文URL重新下载并检查SHA256；下载缓存被Git忽略。若来源更新版本导致散列不同，脚本会报告版本/内容变化，不默默声称相同。`literature.json`的读取范围描述实际阅读，不代表下载后已读全。

`development_ablation`（如已交付）只是在曾用于选择的开发集上，对最终策略逐项移除非零调度特征进行诊断。它不是新留出集，亦未参与候选选择。`ablate_development.py`可在新副本中重现；目录已存在时停止，不覆盖旧结果。
