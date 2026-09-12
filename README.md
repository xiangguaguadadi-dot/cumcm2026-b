# 数学建模2026 B题代码

2026-09-12 第六阶段非RL研究已收束：[本轮完整报告](experiments/20260912_breakthrough/REPORT.md)、[冻结推荐与证据](experiments/20260912_breakthrough/CURRENT_BEST.json)、[研究路径增量](experiments/R1_atlas/breakthrough_increment/README.md)。推荐本轮[Q3 R11 + Q4 R2 单文件候选](experiments/20260912_breakthrough/final_candidates/combined.py)：4800已暴露本地案例全部正常全清，Q3为229.870325秒/源、相对C7改善2.5465%；Q4为455.434476秒/源、改善0.1485%（边际增量）。组合与父法4800行任务指标全等，另24例请求轨迹全等。所有负结果、59次已修复运行错误与成本口径保留；主solver、Q1/Q2和冻结v1未改，无新盲测或官方执行。另已完成[新RL方案与审查](experiments/20260912_breakthrough/RL/PROPOSAL.md)，用户批准原Agent执行G0/G1零训练诊断，后续进度单独记录，不将计划或诊断误称已训练改进。

2026-09-11 第五阶段已完成BC、PPO和约束Q的实施及预算内训练：[本轮结果报告](experiments/20260911_rl_execution/REPORT.md)、[代码与复核入口](experiments/20260911_rl_execution/README.md)、[RL方向图增量](experiments/R1_atlas/rl_increment/README.md)。PPO/Q各3次初始化、每次1,024个新训练局；24个检查点和6个对照共5,760次选择评估全部正常全清，但PPO在Q3/Q4比C7慢3.836%/5.569%，Q慢3.488%/6.478%，两路线均未达到预登记晋级门槛，继续保留C7。结果属于本地检查点选择证据，未新增最终密封测试或官方执行；此前[41篇来源的研究审阅稿](experiments/20260911_rl_research/RESEARCH_PROPOSAL.md)与全部负结果一并保留。

2026-09-11 第四阶段已完成13轮方法研究和3批融合筛选：[本轮报告](experiments/20260911_stage4/REPORT.md)、[第四阶段方向图](experiments/R1_atlas/STAGE4_PROGRESS.md)、[AI增量索引](experiments/R1_atlas/stage4_increment/index.json)。推荐[C7单文件候选](experiments/20260911_stage4/combination/geometry_fusions/C7_both.py)：Q3保持235.876946秒/源，Q4为456.111821秒/源，比本轮起点降低3.7531%；4800已暴露本地案例全部正常全清。三位的负结果、实际阅读范围和来源版本均保留，无新增最终留出或官方测试。

2026-09-11 第三阶段已收束：[研究汇总与最终效果](experiments/20260911_stage3/REPORT.md)、[全历程方向图](experiments/R1_atlas/DIRECTION_MAP.md)、[AI读取入口](experiments/R1_atlas/AI_README.md)。第三问与第四问相对本阶段起点分别改善1.0693%和9.7041%，4800已暴露案例全部清除。按用户最新要求直接交付，不再执行额外新留出；Windows官方测试尚未运行。

2026-09-11 第二阶段按用户要求暂停。B4已取消，B1/B2/B3完成5轮候选并生成[前三位成果报告](experiments/20260911_breakthrough/STAGE_REPORT.md)与[优化路径总图](experiments/20260911_breakthrough/OPTIMIZATION_JOURNEYS.md)。本轮所有4800局结果均为已暴露研发回归，未生成新的最终验证样本。

2026-09-11 六路线研究已完成43轮迭代，并对原基准及10个冻结候选统一复核2400个新案例。入口为[完整研究与新样本报告](experiments/20260911_agent_campaign/REPORT.md)、[逐篇文献阅读与实现索引](experiments/20260911_agent_campaign/LITERATURE_MAP.md)及[可独立运行的候选快照](experiments/20260911_agent_campaign/final_candidates)。主目录solver.py仍为原冻结基准；候选分别保存在快照和各自实验分支。全部结果是本地模型验证，官方Windows测试尚未执行。

主要迭代第三、四问；第一问固定，第二问已保存为文档与候选点函数。Python 3.10及以上，仅需标准库。官方Windows模拟器不放入此代码目录。

- `docs/评测标准_v1.md`：与题目/公开协议对齐的指标、计时、分布假设和冻结约定。
- `local_env.py`、`evaluation/`、`evaluate.py`、`tests/`：固定v1环境、2400个具体案例、冻结基准与回归检查。
- `solver.py`：后续修改此求解器；只通过enter、measure、clear、exit读取观测。
- `http_client.py`：Windows官方环境的实际接入入口。
- `docs/第一问_定稿.md`、`docs/第二问_结果与候选区域.md`：前两问的固定结果。

在此目录运行（Windows可能使用`py -3`，Mac可能使用`python3`替代`python`）：

```bash
python -m unittest discover -s tests -v
python evaluate.py --verify-only
python evaluate.py --suite quick --out results/iteration_001_quick
python evaluate.py --suite full --out results/iteration_001_full
```

输出目录必须尚不存在，防止覆盖旧迭代。每次保存逐案例JSON、官方指标同列的本地CSV和分场景汇总。默认复用已验证的基准缓存，快测实际跑120次候选，全测2400次；添加`--rerun-baseline`会分别跑240次或4800次。候选与冻结基准使用相同具体案例和相同误差场。初始两者代码相同，虚拟指标应完全相等。

正常规则79项复核：

```bash
python tests/check_nominal.py --package . --out results/nominal_rerun.json
```

Windows官方模拟器启动并显示接口就绪后：

```bash
python http_client.py --robot-id YOUR_TEAM_ID --mode 3 --log private_logs/q3_client.jsonl
python http_client.py --robot-id YOUR_TEAM_ID --mode 4 --log private_logs/q4_client.jsonl
```

团队身份填写当前登录的真实队号。程序日志只是客户端记录，不能替代官方加密日志。正式测试须按题目要求各做3次，不从本地CSV伪造官方成绩。

每次迭代先检查完整性和失败行，再看虚拟耗时。涉及HTTP、超时或重试的改动须另做通信验证；本地函数模拟器无法验收真实服务端通信。详见评测标准。

GitHub工作流：每次有明确的算法变更并完成快测/全测后，提交候选与对应结果，推送到已确认的项目仓库。不能把未跑过的策略标记为验证通过；不得随策略变更修改冻结评测以改善分数。专用私有仓库：https://github.com/xiangguaguadadi-dot/cumcm2026-b 。首次冻结验证与实测耗时见docs/冻结交付与耗时.md。
