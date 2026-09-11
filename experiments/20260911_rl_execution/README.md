# RL实施与选择评估入口

本目录实现并保存共同控制器、BC、PPO及约束Q的预登记实验。最终结论读[结果报告](REPORT.md)，实现与预算分别读[实现说明](IMPLEMENTATION.md)、[执行协议](EXECUTION_PROTOCOL.md)。此前41篇来源和两轮修订在[统一研究审阅稿](../20260911_rl_research/RESEARCH_PROPOSAL.md)。原主目录求解器、C7与冻结评测保留。

## 阅读与代码入口

|内容|入口|
|---|---|
|共同接口、宏动作候选、费用与独立接管|`core/`、[SCHEMA](core/SCHEMA.md)、[验证报告](core/REPORT.md)|
|共享网络与特征|`shared.py`|
|完整episode BC与masked PPO|`ppo/trainer.py`、[PPO说明](ppo/README.md)|
|支持约束、经验范围、MC及Double-Q TD|`q_learning/`、[Q说明](q_learning/README.md)|
|单次共享示范采集|`runners/collect_demo.py`|
|单初始化BC→PPO/Q训练与恢复|`runners/train_initialization.py`|
|全部检查点冻结与共同选择场景评估|`runners/selection_eval.py`|
|保存行的统计与全部失败项|[统计说明](analysis/README.md)、`analysis/analyze_selection.py`|
|原始数据流、费用、散列及未知成本审计|[审计说明](verification/AUDIT_EVIDENCE.md)、`verification/audit_evidence.py`|
|不运行模型的Q行为诊断|`verification/q_diagnostics.py`|

## 运行环境

实测使用macOS、Python 3.12与PyTorch 2.8.0，CPU、每进程1线程、至多3个并发初始化。安装版本在`requirements-lock-macos.txt`；完整平台与Torch信息在`results/g1_tensor_probe_v2/runtime.json`及`data/selection_freeze.json`。本地已准备的解释器是：

`/Users/t/Documents/Codex/2026-09-10/new-chat/work/rl_execution_runtime/venv/bin/python`

需要保留完整项目，因为共同执行器依赖项目根目录的`local_env.py`及历史C7快照。只复制本目录不构成完整部署包。这里是本地直接函数环境的研究实现，尚未把学习器接入官方Windows HTTP客户端。

## 不新增环境执行的复核

在本目录运行以下命令。`python`应指向以上解释器或版本相符的独立环境。输出目录必须尚不存在，下面的`review_002`仅作新复核目录示例；保留原有结果。

```sh
python analysis/analyze_selection.py --out analysis/review_002
python verification/audit_evidence.py --archives --require-complete --out verification/review_002
python verification/q_diagnostics.py --output-dir verification/q_review_002 --phase both
```

第一条只需要Git中的行账本和计划。后两条的完整模式还需要本地原始gzip轨迹；Git只保存它们的索引和散列，不包含全部原始数据。元数据审计可用`--metadata-only`，但不能据此声称核验了逐动作物理费用或在线特征数据流。

已有合成夹具可以复跑，不新增真实world：

```sh
python -m unittest discover -s tests -v
python -m unittest discover -s analysis -p test_analyze_selection.py -v
```

## 实际实验执行顺序

下面是本轮已执行的入口说明，**不要在现有结果目录重新运行采集或训练来覆盖证据**。runner将检查已完成摘要、原始散列及冻结身份，并拒绝未解决费用的重复执行。

1. `runners/g1_resource.py`完成G1资源诊断；G0与旧v1教师回归入口和证据见`core/`。
2. 固定`data/g2_plan.json`与物理依赖后，`python runners/collect_demo.py`一次性采集512个纯C7示范。
3. 分别执行`python runners/train_initialization.py --seed 81001`、`81002`、`81003`；每个初始化先BC，再分别训练PPO及Q，全部训练完成后才进入下一步。
4. `python runners/selection_eval.py --part freeze`冻结全部模型及192个场景；然后`--part baselines`评估6个对照，`--part initialization --seed <seed>`分别评估各初始化的8个模型。选择与训练的数据和预算分开。
5. 对保存结果进行上述统计与完整审计，再用`python analysis/build_delivery.py`生成主结果报告。

若要做全新重复实验，使用单独完整项目副本和新的实验记录，保持本轮冻结文件与结果原样。这里的runner路径固定在本实验目录，不能把新实验写入已有目录后仍称原始运行复现。重新收集会有新的真实时钟输入、耗时和动作序列，需要另立运行身份；旧训练manifest绑定原共享示范文件，不能混用新采集数据继续旧权重。

## 权重和证据

每个`results/g2/init_<seed>/`保存`bc/final.pt`、`ppo/checkpoints/episode_<position>.pt`及`q/checkpoints/episode_<position>.pt`；位置为128、256、512、1024。`checkpoints.json`给出精确路径和SHA256。Q checkpoint包含online、target、冻结支持网络、经验特征范围及相关状态；选择时关闭探索且不扩展范围。

这些`.pt`由本项目本地训练产生，runner只按保存的索引载入本地权重。权重散列不等于模型内部语义审计。在线策略只能接收公开观测与候选，终局真值仅用于训练标签和评测；接口封装不是抵抗恶意反射的安全沙箱。

`verification/full_audit_v1/local_only_trajectory_manifest.json`列出本地完整原始记录及重新计算的散列。G0历史原始JSON缺少执行时逐文件散列，最终检查补算当前散列，并如实区别记录时点。Git保留检查点、配方、逐局指标、更新账本、审计索引与报告，排除原始大文件和恢复临时状态；这些原文件仍保留在本机。

晋级门槛、统计区间与全部负结果以主报告为准。选择集、旧暴露回归与官方成绩不可互相代替。
