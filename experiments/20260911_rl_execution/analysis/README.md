# G2选择结果统计

`analyze_selection.py`只读取已保存的选择评估账本，不导入环境、生成器、策略或训练器，不执行world。输入是`data/g2_plan.json`，以及`results/g2_selection/baselines/`的6个对照和`models/`的24个预登记检查点目录内的`rows.jsonl`。

与`runners/selection_eval.py`的输出目录和模型编号已静态核对：

| 相对`results/g2_selection/`的目录 | 位置数 | 用途 |
|---|---:|---|
| `baselines/original_c7` | 1 | 原始C7对照 |
| `baselines/teacher_wrapper` | 1 | 共同控制器的teacher对照 |
| `baselines/same_candidates_greedy` | 1 | 同候选即时成本贪心对照 |
| `baselines/bc_init{81001,81002,81003}` | 3 | 每个初始化对应的BC对照 |
| `models/{ppo,q}_init{81001,81002,81003}_ep{0128,0256,0512,1024}` | 24 | 两算法各三个初始化、各四个预登记检查点 |

花括号表示路径模式，不是一个实际目录。评估器只执行训练确实保留的检查点；分析仍逐项报告全部24个预登记位置。每个已执行位置包含同一批192个注册world，Q3/Q4各96个；统计按world ID配对，不依赖文件行顺序。

先由协调运行器完成选择评估，再做正式统计。已配置实验运行时后，在本实验目录执行：

```sh
python analysis/analyze_selection.py --out analysis/selection_result
```

当前macOS环境可从任意目录直接运行下面的完整命令，不依赖系统默认Python版本：

```sh
'/Users/t/Documents/Codex/2026-09-10/new-chat/work/rl_execution_runtime/venv/bin/python' '/Users/t/ai project/数学建模2026/代码/experiments/20260911_rl_execution/analysis/analyze_selection.py' --out '/Users/t/ai project/数学建模2026/代码/experiments/20260911_rl_execution/analysis/selection_result'
```

生成`selection_summary.json`与中文`REPORT.md`；已有交付文件不会被覆盖。可用`--execution-root`、`--results`、`--plan`指定路径。输出目录应在每次正式重算时换新。程序不会因数据缺失就省略计划位置；输入在分析过程中改变会拒绝封存。缺失位置会读取对应最终训练摘要，区分未提供检查点与已有检查点但没有选择结果。

每题按注册的96个world核验ID、mode/group、源数、全清、异常、秒/源分母和费用字段。任何缺失、重复、身份错误、失败或费用矛盾都使该检查点不能参加该题选择；不对成功子集做耗时排名。失败、缺失、异常原因与已记录费用均保留。

每个初始化在该题完整检查点中取平均秒/源最小者，精确并列取较早预登记位置。三个初始化均有完整选择且C7和各自BC对照完整后，先按同一world平均三个初始化，再对C7和对应BC做12场景分层配对bootstrap：10000次，种子84771，NumPy默认PCG64，双侧百分位95%区间。该题独立单位为96个world；不把288次执行当作288个独立world。

算法级选择门槛同时要求：相对两对照均至少改善2%；候选减对照的均值差95%区间上界均严格小于0；至少两个相同初始化同时优于C7与自己的BC。这是已确认的保守“同向”口径。程序报告每个初始化、合并结果、全部场景及单world退步数量。

这些都是检查点选择后的本地证据，有选择偏差，区间未校正选择或多重比较。旧暴露回归、额外盲测与官方Windows验证不能由本分析替代；分析不授权默认替换C7，未过题保留C7。

费用是所有已记录评估行的业务调用与逐局现实执行耗时之和，包括失败和被拒绝的检查点。缺失或无法解析记录的成本未知，不能记作零；此统计不包含训练或文件I/O，不能据此进行受控机器速度排名。完整原始轨迹、模型checkpoint与冻结身份由`selection_eval.py`核验和保存；本分析校验行级字段与输入账本散列，不代替一次独立的原始gzip/模型文件审计。

新增验证严格限于`test_analyze_selection.py`的3个合成统计夹具，0实际world、0训练。运行：

```sh
python -m unittest discover -s analysis -p test_analyze_selection.py -v
```

夹具分别检查配对分层区间与先合并初始化、完整性和费用拒绝边界、选择门槛及文件到中文报告全链路。内部数据全为人为固定统计行，不含环境源坐标或可执行world recipe。运行次数与结果写入`validation.json`。

后续与`selection_eval.py`的对接复核仅做静态阅读和此说明更新，没有新增或重跑夹具、没有读取选择成绩、没有运行world；G0独特夹具仍为79/80。
