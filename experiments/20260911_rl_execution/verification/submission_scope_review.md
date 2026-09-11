# 提交范围只读审查

文件系统扫描时间（UTC）：2026-09-11T11:48:19.774776+00:00。训练仍可继续写入，本表不是最终提交清单。

本次未运行 Git、世界、模型、训练或夹具，未修改 runtime。只写本审查文件；疑似凭据值和文件内容均不写入报告。

当前根 `.gitignore` 的这些规则按路径语义覆盖原始 episode 目录、G0 逐局 JSON/gzip、运行中 resume、pending_update 和临时文件；未发现另一个嵌套 `.gitignore`。本审查没有查询 Git 索引，因此不能证明曾经已跟踪或已暂存的原始轨迹已被排除；忽略规则本身不移除已跟踪文件。

| 路径 | 类型 | 字节 |
|---|---|---:|
| `experiments/20260911_rl_execution/` | 全部当前文件 | 1,601,207,912 |
| `experiments/20260911_rl_execution/` | 按当前根忽略规则覆盖的文件 | 1,574,182,395 |
| `experiments/20260911_rl_execution/` | 未被当前根规则覆盖的文件 | 27,025,517 |
| `experiments/20260911_rl_research/` | 全部当前文件 | 529,776 |
| `experiments/20260911_rl_research/` | 按当前根忽略规则覆盖的文件 | 0 |
| `experiments/20260911_rl_research/` | 未被当前根规则覆盖的文件 | 529,776 |
| `.gitignore` | 根忽略规则 | 635 |

未忽略文件最大为 2,828,393 字节；未发现意外巨型未忽略文件。未忽略 JSON/JSONL 的有界结构扫描未发现完整 events/trace/decision 轨迹对象；论文 PDF/全文网页/文档媒体候选为 0；明确凭据格式或凭据文件名候选为 0。二进制模型未反序列化，已忽略的大型原始轨迹未作凭据全文扫描。

下表列出较大的未忽略文件，仅包含路径、类型、大小。

| 路径 | 类型 | 字节 |
|---|---|---:|
| `experiments/20260911_rl_execution/core/regression_v1/full/case_metrics.json` | .json，未忽略 | 2,828,393 |
| `experiments/20260911_rl_execution/data/g2_plan.json` | .json，未忽略 | 1,123,642 |
| `experiments/20260911_rl_execution/results/g2/init_81002/ppo/rows.jsonl` | .jsonl，未忽略 | 1,035,890 |
| `experiments/20260911_rl_execution/results/g2/init_81001/ppo/rows.jsonl` | .jsonl，未忽略 | 1,035,765 |
| `experiments/20260911_rl_execution/results/g2/init_81003/ppo/rows.jsonl` | .jsonl，未忽略 | 1,031,583 |
| `experiments/20260911_rl_execution/results/g2/init_81001/q/rows.jsonl` | .jsonl，未忽略 | 1,017,067 |
| `experiments/20260911_rl_execution/results/g2/init_81003/q/rows.jsonl` | .jsonl，未忽略 | 1,014,808 |
| `experiments/20260911_rl_execution/results/g2/init_81002/q/rows.jsonl` | .jsonl，未忽略 | 992,962 |
| `experiments/20260911_rl_execution/results/g2/init_81001/q/updates.jsonl` | .jsonl，未忽略 | 812,717 |
| `experiments/20260911_rl_execution/results/g2/init_81003/q/updates.jsonl` | .jsonl，未忽略 | 811,031 |
| `experiments/20260911_rl_execution/results/g2/init_81002/q/updates.jsonl` | .jsonl，未忽略 | 793,663 |
| `experiments/20260911_rl_execution/results/g2/init_81001/q/checkpoints/episode_0512.pt` | .pt，未忽略 | 650,471 |

以下较大的原始轨迹已被当前路径规则覆盖；保留本地文件，不执行清理。

| 路径 | 类型 | 字节 |
|---|---|---:|
| `experiments/20260911_rl_execution/core/g0_results_v1/11_teacher_wrapper.json` | 原始轨迹，规则覆盖 | 14,388,621 |
| `experiments/20260911_rl_execution/core/g0_results_v1/17_teacher_wrapper.json` | 原始轨迹，规则覆盖 | 8,658,740 |
| `experiments/20260911_rl_execution/core/g0_results_v1/09_teacher_wrapper.json` | 原始轨迹，规则覆盖 | 8,482,386 |
| `experiments/20260911_rl_execution/core/g0_results_v1/07_teacher_wrapper.json` | 原始轨迹，规则覆盖 | 8,367,570 |
| `experiments/20260911_rl_execution/core/g0_results_v1/01_teacher_wrapper.json` | 原始轨迹，规则覆盖 | 7,919,680 |
| `experiments/20260911_rl_execution/core/g0_results_v1/03_teacher_wrapper.json` | 原始轨迹，规则覆盖 | 6,506,962 |

预定部署文件为每初始化 1 份 BC，加 PPO/Q 各 4 个检查点，共 27 个路径；这些路径均不匹配当前忽略规则。扫描时已有 24 份：BC 3、PPO 12、Q 9；Q 的 3 份 episode_1024.pt 尚未出现，属于仍在执行的训练阶段，不据此断言运行失败。保存的 Q 检查点包含 network/support/bounds/config，BC/PPO 检查点包含模型与所需 trainer 状态，无需将 resume.pt 作为部署依赖提交。

| 路径 | 类型 | 字节 |
|---|---|---:|
| `experiments/20260911_rl_execution/results/g2/init_81001/bc/final.pt` | BC deployment checkpoint；未忽略 | 336,900 |
| `experiments/20260911_rl_execution/results/g2/init_81001/ppo/checkpoints/episode_0128.pt` | PPO registered deployment checkpoint；未忽略 | 406,752 |
| `experiments/20260911_rl_execution/results/g2/init_81001/ppo/checkpoints/episode_0256.pt` | PPO registered deployment checkpoint；未忽略 | 406,752 |
| `experiments/20260911_rl_execution/results/g2/init_81001/ppo/checkpoints/episode_0512.pt` | PPO registered deployment checkpoint；未忽略 | 406,752 |
| `experiments/20260911_rl_execution/results/g2/init_81001/ppo/checkpoints/episode_1024.pt` | PPO registered deployment checkpoint；未忽略 | 406,752 |
| `experiments/20260911_rl_execution/results/g2/init_81001/q/checkpoints/episode_0128.pt` | Q registered deployment checkpoint；未忽略 | 630,887 |
| `experiments/20260911_rl_execution/results/g2/init_81001/q/checkpoints/episode_0256.pt` | Q registered deployment checkpoint；未忽略 | 637,415 |
| `experiments/20260911_rl_execution/results/g2/init_81001/q/checkpoints/episode_0512.pt` | Q registered deployment checkpoint；未忽略 | 650,471 |
| `experiments/20260911_rl_execution/results/g2/init_81001/q/checkpoints/episode_1024.pt` | Q registered deployment checkpoint；未忽略；待训练生成 | 尚无文件 |
| `experiments/20260911_rl_execution/results/g2/init_81002/bc/final.pt` | BC deployment checkpoint；未忽略 | 336,900 |
| `experiments/20260911_rl_execution/results/g2/init_81002/ppo/checkpoints/episode_0128.pt` | PPO registered deployment checkpoint；未忽略 | 406,752 |
| `experiments/20260911_rl_execution/results/g2/init_81002/ppo/checkpoints/episode_0256.pt` | PPO registered deployment checkpoint；未忽略 | 406,752 |
| `experiments/20260911_rl_execution/results/g2/init_81002/ppo/checkpoints/episode_0512.pt` | PPO registered deployment checkpoint；未忽略 | 406,752 |
| `experiments/20260911_rl_execution/results/g2/init_81002/ppo/checkpoints/episode_1024.pt` | PPO registered deployment checkpoint；未忽略 | 406,752 |
| `experiments/20260911_rl_execution/results/g2/init_81002/q/checkpoints/episode_0128.pt` | Q registered deployment checkpoint；未忽略 | 630,887 |
| `experiments/20260911_rl_execution/results/g2/init_81002/q/checkpoints/episode_0256.pt` | Q registered deployment checkpoint；未忽略 | 637,415 |
| `experiments/20260911_rl_execution/results/g2/init_81002/q/checkpoints/episode_0512.pt` | Q registered deployment checkpoint；未忽略 | 650,471 |
| `experiments/20260911_rl_execution/results/g2/init_81002/q/checkpoints/episode_1024.pt` | Q registered deployment checkpoint；未忽略；待训练生成 | 尚无文件 |
| `experiments/20260911_rl_execution/results/g2/init_81003/bc/final.pt` | BC deployment checkpoint；未忽略 | 336,900 |
| `experiments/20260911_rl_execution/results/g2/init_81003/ppo/checkpoints/episode_0128.pt` | PPO registered deployment checkpoint；未忽略 | 406,752 |
| `experiments/20260911_rl_execution/results/g2/init_81003/ppo/checkpoints/episode_0256.pt` | PPO registered deployment checkpoint；未忽略 | 406,752 |
| `experiments/20260911_rl_execution/results/g2/init_81003/ppo/checkpoints/episode_0512.pt` | PPO registered deployment checkpoint；未忽略 | 406,752 |
| `experiments/20260911_rl_execution/results/g2/init_81003/ppo/checkpoints/episode_1024.pt` | PPO registered deployment checkpoint；未忽略 | 406,752 |
| `experiments/20260911_rl_execution/results/g2/init_81003/q/checkpoints/episode_0128.pt` | Q registered deployment checkpoint；未忽略 | 630,887 |
| `experiments/20260911_rl_execution/results/g2/init_81003/q/checkpoints/episode_0256.pt` | Q registered deployment checkpoint；未忽略 | 637,415 |
| `experiments/20260911_rl_execution/results/g2/init_81003/q/checkpoints/episode_0512.pt` | Q registered deployment checkpoint；未忽略 | 650,471 |
| `experiments/20260911_rl_execution/results/g2/init_81003/q/checkpoints/episode_1024.pt` | Q registered deployment checkpoint；未忽略；待训练生成 | 尚无文件 |

以下静态部署/本地复评依赖均在工作区存在。两个目录以外的 local_env.py 与已固定 C7_both.py 也必须随完整仓库保留；只复制 rl_execution/ 不能独立运行共同控制器。Python/PyTorch 等包由 requirements-lock-macos.txt 描述，虚拟环境本身不应放入 Git。本次仅核对文件存在及当前根忽略规则，不检查远端仓库或安装环境。

| 路径 | 类型 | 字节 |
|---|---|---:|
| `local_env.py` | 模型/控制器代码 | 8891 |
| `experiments/20260911_stage4/combination/geometry_fusions/C7_both.py` | 模型/控制器代码 | 200259 |
| `experiments/20260911_rl_execution/shared.py` | 模型/控制器代码 | 4958 |
| `experiments/20260911_rl_execution/requirements-lock-macos.txt` | 锁定依赖清单 | 181 |
| `experiments/20260911_rl_execution/data/worlds.py` | 模型/控制器代码 | 5107 |
| `experiments/20260911_rl_execution/data/g2_plan.json` | 运行与场景记录 | 1123642 |
| `experiments/20260911_rl_execution/data/runtime_dependency_freeze.json` | 运行与场景记录 | 1120 |
| `experiments/20260911_rl_execution/runners/common.py` | 模型/控制器代码 | 8933 |
| `experiments/20260911_rl_execution/runners/selection_eval.py` | 模型/控制器代码 | 13577 |
| `experiments/20260911_rl_execution/core/__init__.py` | 模型/控制器代码 | 390 |
| `experiments/20260911_rl_execution/core/engine.py` | 模型/控制器代码 | 18872 |
| `experiments/20260911_rl_execution/core/fallback.py` | 模型/控制器代码 | 2542 |
| `experiments/20260911_rl_execution/core/geometry.py` | 模型/控制器代码 | 1544 |
| `experiments/20260911_rl_execution/core/interface.py` | 模型/控制器代码 | 9831 |
| `experiments/20260911_rl_execution/core/schema.py` | 模型/控制器代码 | 2407 |
| `experiments/20260911_rl_execution/core/teacher_adapter.py` | 模型/控制器代码 | 1341 |
| `experiments/20260911_rl_execution/ppo/__init__.py` | 模型/控制器代码 | 215 |
| `experiments/20260911_rl_execution/ppo/returns.py` | 模型/控制器代码 | 3367 |
| `experiments/20260911_rl_execution/ppo/trainer.py` | 模型/控制器代码 | 19049 |
| `experiments/20260911_rl_execution/q_learning/__init__.py` | 模型/控制器代码 | 760 |
| `experiments/20260911_rl_execution/q_learning/math.py` | 模型/控制器代码 | 5074 |
| `experiments/20260911_rl_execution/q_learning/policy.py` | 模型/控制器代码 | 16269 |
| `experiments/20260911_rl_execution/q_learning/replay.py` | 模型/控制器代码 | 7542 |
| `experiments/20260911_rl_execution/q_learning/trainer.py` | 模型/控制器代码 | 12323 |

后续新增的 selection 原始 episode 目录同样匹配既有忽略规则；选择摘要、rows.jsonl、检查点索引及 verification 文档不在这些忽略模式内。提交前应由负责 Git 的协调者复核实际索引与最终生成的检查点清单。本报告没有读取或输出任何疑似凭据值。
