# 方法分类树（A）

截止2026-09-11。29个唯一记录；9个核心关键章节阅读，20个扩展记录。每文只在一个主机制路径出现，跨模块只加标签。这里的核心并不表示全篇证明、全部实验及代码均已核验。

分类轴是决定行动的主机制；同一级不把年份、场景和算法名混为同一分类。IRIS只核元数据，在树上明确标注。

## A 学习动作选择：从已有belief/历史学习调度或轨迹

### A1/候选图注意力

- [CAtNIPP: Context-Aware Attention-based Network for Informative Path Planning](https://proceedings.mlr.press/v205/cao23b.html) — `catnipp-corl2022`，核心关键正文。GP belief-augmented PRM、Transformer attention、LSTM历史与pointer actor/critic，用PPO选择邻接点。
- [Deep Reinforcement Learning with Dynamic Graphs for Adaptive Informative Path Planning](https://arxiv.org/abs/2402.04894) — `2402.04894`，核心关键正文。以局部动态候选位置和yaw构图，继承CAtNIPP注意力actor-critic并用PPO，奖励兼顾探索与目标发现。
- [Attention-based Learning for 3D Informative Path Planning](https://arxiv.org/abs/2506.08434) — `2506.08434`，扩展。3D位置调整sensor footprint/accuracy的attention RL。
- [Scalable Multi-Robot Informative Path Planning for Target Mapping via Deep Reinforcement Learning](https://arxiv.org/abs/2409.16967) — `2409.16967`，扩展。coordination graph加CTDE共享策略的多机器人目标发现。

### A2/统一belief摘要

- [Towards Map-Agnostic Policies for Adaptive Informative Path Planning](https://arxiv.org/abs/2410.17166) — `2410.17166`，核心关键正文。用兴趣概率、地图不确定性、机器人状态与任务超参数统一不同地图；PPO+IMPALA/MLP。

### A3/历史状态聚合

- [Active Sensing with Meta-Reinforcement Learning for Emitter Localization from RF Observations](https://arxiv.org/abs/2605.12569) — `2605.12569`，核心关键正文。单静态RF源的多天线IQ导航；CNN表征与可选LSTM，比较PPO/DQN和meta-adaptation。
- [DyPNIPP: Predicting Environment Dynamics for RL-based Robust Informative Path Planning](https://arxiv.org/abs/2410.17186) — `2410.17186`，核心关键正文。domain randomization加时序动态预测encoder，把16维环境context送入CAtNIPP的LSTM/PPO。
- [LASER: Learning Active Sensing for Continuum Field Reconstruction](https://arxiv.org/abs/2604.19355) — `2604.19355`，扩展。continuum latent worldmodel中想象sensing并输出intrinsic reward。

### A4/离线行为支持约束

- [OffRIPP: Offline RL-based Informative Path Planning](https://arxiv.org/abs/2409.16830) — `2409.16830`，核心关键正文。先行为克隆近似数据行为分布，再用batch-constrained Q选择支持内动作以减轻外推误差。

### A5/扩散轨迹与意图

- [AID: Agent Intent from Diffusion for Multi-Agent Informative Path Planning](https://arxiv.org/abs/2512.02535) — `2512.02535`，核心关键正文。多智能体图attention编码，diffusion一次产生长期意图轨迹，BC后DPPO微调。
- [DIFF-IPPO: Diffusion-Based Informative Path Planning with Open-Vocabulary Belief Maps](https://arxiv.org/abs/2606.16780) — `2606.16780`，扩展。open-vocabulary非高斯belief图条件扩散路径。

### A6/信息导向目标

- [C-IDS: Solving Contextual POMDP via Information-Directed Objective](https://arxiv.org/abs/2602.03939) — `2602.03939`，核心关键正文。contextual POMDP信息目标采用reward+互信息的拉格朗日形式，用variational policy gradient与LSTM实现。
- [Information-Directed Offline-to-Online Reinforcement Learning](https://arxiv.org/abs/2605.29405) — `2605.29405`，扩展。条件于离线数据的剩余信息与IDS regret证书。
- [Information-Guided Safe Reinforcement Learning for Autonomous Gas Source Localization using sUAS](https://arxiv.org/abs/2609.05569) — `2609.05569`，扩展。EMGR estimator+SAC探索与可靠性meta-supervisor混合。
- [CIG-RL: Curiosity-Driven Information-Guided Reinforcement Learning for Source Term Estimation in Uncertain Environments](https://arxiv.org/abs/2608.30673) — `2608.30673`，扩展。belief转移curiosity和uncertainty-adaptive reward指导source-term估计。
- [IRIS: An information path planning method based on reinforcement learning and information-directed sampling](https://doi.org/10.1016/j.patcog.2025.112400) — `iris-patcog112400`，仅元数据。Title identifies reinforcement learning + information-directed sampling for information path planning; DQN,attention,pointer specifics not verified from body.

## B 模型规划：用明确预测/成本模型搜索动作

### B1/增量采样规划

- [IA-TIGRIS: An Incremental and Adaptive Sampling-Based Planner for Online Informative Path Planning](https://arxiv.org/abs/2502.15961) — `2502.15961`，扩展。IA-TIGRIS复用搜索树并随belief变化更新信息路径。

### B2/状态相关代价优化

- [LIPP: Load-Aware Informative Path Planning with Physical Sampling](https://arxiv.org/abs/2603.06924) — `2603.06924`，扩展。将物理采样导致载荷与后续边cost改变纳入MIQP。
- [Hierarchical Informative Path Planning via Graph Guidance and Trajectory Optimization](https://arxiv.org/abs/2601.17227) — `2601.17227`，扩展。图全局引导、分段预算与样条连续优化。
- [Trajectory Optimization for Adaptive Informative Path Planning with Multimodal Sensing](https://arxiv.org/abs/2404.18374) — `2404.18374`，扩展。按不同精度/成本传感器做GP方差轨迹优化。
- [Approximate Sequential Optimization for Informative Path Planning](https://arxiv.org/abs/2402.08841) — `2402.08841`，扩展。convex relaxation给界，dynamic-programming orienteering逐段重算信息路径。

### B3/主动推断目标

- [Expected Free Energy-based Informative Path Planning for Robotic Mars Exploration](https://arxiv.org/abs/2608.14466) — `2608.14466`，扩展。expected free energy统一信息与高价值区域，hard path约束。

## C 表示与约束：估计相关性、约束行为或统一执行接口

### C1/联合状态估计

- [Efficient Localization of Directional Emitters via Joint Beampattern Estimation](https://arxiv.org/abs/2411.04364) — `2411.04364`，扩展。联合估计位置和beampattern以解释directional RSS调制。
- [Multi-robot Learning-based Informative Path Planning Using Spatio-Temporal Gaussian Process Kalman Filter](https://arxiv.org/abs/2609.05515) — `2609.05515`，扩展。spatio-temporal GP-Kalman匿名目标field与covariance intersection融合。

### C2/估计质量保证

- [Informative Path Planning with Guaranteed Estimation Uncertainty](https://arxiv.org/abs/2602.05198) — `2602.05198`，扩展。GP模型转覆盖约束，设计使全域posterior variance低于阈值的路线。

### C2/运行时安全约束

- [Safe Reinforcement Learning via Shielding](https://arxiv.org/abs/1708.08611) — `1708.08611`，扩展。shield约束RL动作满足形式安全规格。
- [A Closer Look at Invalid Action Masking in Policy Gradient Algorithms](https://arxiv.org/abs/2006.14171) — `2006.14171`，扩展。研究policy-gradient invalid action masking。

### C3/统一执行评测接口

- [A Unified Experimental Architecture for Informative Path Planning: from Simulation to Deployment with GuadalPlanner](https://arxiv.org/abs/2602.10702) — `2602.10702`，扩展。GuadalPlanner将高层规划与sensing/执行分离，在sim/SITL/实艇共用接口。

## D 领域综合：定义分类与比较边界

### D/分类与评测综述

- [Learning-based Methods for Adaptive Informative Path Planning](https://arxiv.org/abs/2404.06940) — `2404.06940`，核心关键正文。从学习算法与应用两轴梳理AIPP，统一POMDP、belief、动作和信息目标。

## 同源模块与比较边界

CAtNIPP、Dynamic Graph、DyPNIPP与OffRIPP共享大量图注意力骨架，不能当四个独立“图网络有效”的复制研究；它们分别改变局部动作图、动态context与训练数据约束。AID的主要新增是diffusion意图，不是本题的清除操作。MapAgnostic提供强belief摘要路线，反对把图/循环作为先验必须模块。C-IDS的理论context跨局固定；其policy-gradient机制可反驳“IDS只能DQN”，但不能给本题直接的regret保证。

现实场景相近也不等于协议相同：RF IQ/GNSS、RSS/AOA/TDOA、气体浓度、GP field、果树图像都具有不同信息量和代价。本題只有按频道付费的direction/near/no_signal与clear反馈。29篇不是同benchmark排行榜。

## 未闭合分支

IRIS期刊身份明确，但正文/作者代码仍缺；AID-RL exact名称未核。未做完整IEEE/Scopus/WoS枚举、未复现任一模型、未用这份检索证明组合首创。

R2审阅边界：C-IDS仅支持存在policy-gradient信息目标这一机制归类；其全部证明并未独立核验，B提出的Lemma3.6/Eq19与context条件疑问仍须按原设定确认。IRIS仍只有准确出版身份与元数据，机制归属不作为已核实选型证据。
