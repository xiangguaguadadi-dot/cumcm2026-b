# A3独立实验交付

先看[完整结果](REPORT.md)、[逐篇阅读范围](LITERATURE.md)和[候选契约](DELIVERY.json)。最终独立候选为 `snapshots/b4_safe.py`；`r3_guard.py`是另一机制的备选。旧的无保护候选保留用于复核，不作为推荐部署。

在仓库根目录用Python 3.12标准库执行：

```sh
python3.12 -S experiments/parallel_v2_a3/final_audit.py
python3.12 -S experiments/parallel_v2_a3/build_report.py
python3.12 -S evaluate.py --verify-only
python3.12 -S evaluate.py --suite quick --candidate experiments/parallel_v2_a3/snapshots/b4_safe.py --out results/a3_b4_new_run
```

`final_audit.py`只读取原始行，不计作策略新执行。结果目录不可覆盖；重新跑性能时给新的输出目录。现有quick/full及4800案例均已暴露。

`train_gate.py`保存单clear代理标签；`train_rollout.py`保存选定频道局部续跑标签；`train_full_rollout.py`保存整局续跑标签。训练世界配方和fit/calibration分界在各轮registry，全部去重种子在`new_world_seeds.json`。训练脚本默认拒绝覆盖已有轮次目录。R6用于抽取续跑AST的同散列父类源已放入`training_sources`，模型provenance保留实际训练时的原始路径。

网页和已冻结候选的字节原样保存以保留SHA256，包括原站点空白；不为消除格式提示改写这些证据。`comparison_start_rows.json`是本轮开始时已存在父候选的分模式行副本，不是A3新运行。
