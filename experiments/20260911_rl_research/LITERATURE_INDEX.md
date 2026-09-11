# 去重文献与实际阅读范围索引

截止2026-09-11。A纳入29篇、B纳入21篇；合并9项交集后共**41篇**，其中**14篇至少一位研究者阅读了明确记录的关键正文，27篇为扩展记录**。核心不等于逐页全文精读，扩展不等于排除，也不等于已确认适用。

按arXiv去版本号、DOI或规范题名合并。保留两位分别记录的读取范围与发表状态；官方接受、作者自报、预印本与尚未核定状态不混用。代码链接只代表可定位来源，本轮没有安装、运行或复现实验。IRIS目前是元数据可核、正文机制不可核；相似简称不代替来源。

机器可读的全部字段、作者、协议、预算、来源定位与局限见[literature_merged.json](literature_merged.json)。真实查询和访问失败见[A检索日志](A_user_method/search_log.json)、[B检索日志](B_frontier/search_log.json)。

## 核心：阅读了指定关键正文

### L01 · [Active Sensing with Meta-Reinforcement Learning for Emitter Localization from RF Observations](https://arxiv.org/abs/2605.12569)

唯一标识：`arxiv:2605.12569`。

- **A读取范围**：IV-A–D, V, VI(a–c); figures 2–9 and hyperparameter footnote
- **A发表状态**：arXiv v1 2026-05-12; paper header ©2025 IEEE alone does not establish a venue or acceptance date；首次公开日期记录：2026/05/12。
- **A机制**：A3/历史状态聚合。
- **A迁移边界**：未找到实际evaluation N/CI；gamma、并行度等不同；goal-state输入的部署可得性未澄清；不支持多源全清或PPO普遍优于DQN。

### L02 · [AID: Agent Intent from Diffusion for Multi-Agent Informative Path Planning](https://arxiv.org/abs/2512.02535)

唯一标识：`arxiv:2512.02535`。

- **A读取范围**：§3.2, §4.1–4.6, §5; Table1
- **A发表状态**：arXiv v1 2025-12-02/v2 2026-04-30; formal venue not verified；首次公开日期记录：2025/12/02。
- **A机制**：A5/扩散轨迹与意图。
- **A代码入口**：[官方/作者来源所指仓库](https://github.com/marmotlab/AID)；public repository API verified; not installed/run。
- **A迁移边界**：AID不是已确认AID-RL全称；多智能体意图非本题需求；BC alone较专家差，FT收益依专家。15–30h来自RTX4080SUPER不可外推Mac。
- **B读取范围**：arXiv摘要与元数据；PDF下载但未读方法全文
- **B发表状态**：arXiv preprint；首次公开日期记录：2025-12-02。
- **B机制**：学习长期任务价值；多机器人轨迹策略；扩散BC后DPPO。
- **B代码入口**：[官方/作者来源所指仓库](https://github.com/marmotlab/AID)；Official repository page fetched and title/identity checked 2026-09-11; implementation not read or executed。
- **B迁移边界**：单机器狗无队友意图，核心多agent收益不能移植；A负责用户AID-RL身份进一步核实。

### L03 · [C-IDS: Solving Contextual POMDP via Information-Directed Objective](https://arxiv.org/abs/2602.03939)

唯一标识：`arxiv:2602.03939`。

- **A读取范围**：§2.1–2.2, §3 statement/assumptions, §4 experiment; proofs not line-by-line verified
- **A发表状态**：arXiv preprint/version verified; separate venue not independently checked；首次公开日期记录：2026/02/03。
- **A机制**：A6/信息导向目标。
- **A迁移边界**：本题新局重新源配置，与固定context跨局设定不同；不能把actor分数或log-area称真实regret/MI。 B对Lemma3.6/Eq19及跨episode context语义提出尚待核实疑问；A未完成全证明复核，不将regret保证迁移本题，也不声称已证伪整篇。
- **B读取范围**：PDF p1–8；附录Lemma3.6/Eq19前后；17页全文已取得但非全证明核验
- **B发表状态**：arXiv preprint；首次公开日期记录：2026-02-03。
- **B机制**：信息价值与探索；上下文识别；线性信息比率的策略梯度目标。
- **B迁移边界**：§2.1可变context与§3固定context不同；附录从有限episode断言universal η的正信息界未核通过；实验窄且Gaussian可重复噪声不同；ICML模板不等于录用。

### L04 · [CAtNIPP: Context-Aware Attention-based Network for Informative Path Planning](https://proceedings.mlr.press/v205/cao23b.html)

唯一标识：`title:catnippcontextawareattentionbasednetworkforinformativepathplanning`。

- **A读取范围**：PDF pp3–7: §3,§4.1–4.4,§5.1; Fig2,Table1; p1 venue and p6 hardware footnotes
- **A发表状态**：CoRL2022 (paper page1); PMLR205:1928–1937,2023 (official proceedings)；首次公开日期记录：未记录。
- **A机制**：A1/候选图注意力。
- **A代码入口**：[官方/作者来源所指仓库](https://github.com/marmotlab/CAtNIPP)；public repository API/README verified; original code and pretrained model link, not run。
- **A迁移边界**：到destination的预算mask不提供多源全清；原文自己指出动态reward归一化与目标有偏差；图/LSTM/PPO/pointer组合已有先例。

### L05 · [Deep Reinforcement Learning with Dynamic Graphs for Adaptive Informative Path Planning](https://arxiv.org/abs/2402.04894)

唯一标识：`arxiv:2402.04894`。

- **A读取范围**：III-A–D, IV-A–D; Tables I–III
- **A发表状态**：arXiv v1 2024-02-07/v2 2024-07-05; official author repo identifies RA-L 2024 and links IEEE10578000; no award claim；首次公开日期记录：2024/02/07。
- **A机制**：A1/候选图注意力。
- **A代码入口**：[官方/作者来源所指仓库](https://github.com/dmar-bonn/ipp-rl-3d)；public repository API and README verified; not installed/run。
- **A迁移边界**：按移动固定间隔免费获图像，指标是预算内发现率，未全清；局部图可能遗漏全局任务。作者代码README列Python3.7/PyTorch1.13/Ray2.7，非本机就绪。

### L06 · [DyPNIPP: Predicting Environment Dynamics for RL-based Robust Informative Path Planning](https://arxiv.org/abs/2410.17186)

唯一标识：`arxiv:2410.17186`。

- **A读取范围**：III-B1–3, IV-A–D; TablesI–IV
- **A发表状态**：arXiv preprint/version verified; separate venue not independently checked；首次公开日期记录：2024/10/22。
- **A机制**：A3/历史状态聚合。
- **A迁移边界**：研究真实动态场，和本题静态源+同址固定误差不同；单纯有历史不证明GRU在本题有收益。
- **B读取范围**：arXiv摘要/元数据；PDF下载但未读方法全文
- **B发表状态**：arXiv preprint；首次公开日期记录：2024-10-22。
- **B机制**：统一任务表示；环境变化适配；动态预测与域随机化。
- **B迁移边界**：本题源静态；不能因此制造移动源或假装重现wildfire实验。

### L07 · [Efficient Recurrent Off-Policy RL Requires a Context-Encoder-Specific Learning Rate](https://arxiv.org/abs/2405.15384)

唯一标识：`arxiv:2405.15384`。

- **B读取范围**：PDF p1–4问题与架构；p6–9实验/限制；附录C.2 p17、表2 p21
- **B发表状态**：arXiv preprint；首次公开日期记录：2024-05-24。
- **B机制**：学习长期任务价值；历史编码稳定性；编码器专用学习率。
- **B迁移边界**：连续动作SAC不同于本题候选Q；默认Mamba含自定义reset，Apple直接可用未核实；完整序列重放有padding/峰值内存成本；未证明GRU总必要。

### L08 · [Flow Q-Learning](https://arxiv.org/abs/2502.02538)

唯一标识：`arxiv:2502.02538`。

- **B读取范围**：PDF p1–7，重点§2–3/Algorithm1及§5.1/表2
- **B发表状态**：ICML 2025 / PMLR267；首次公开日期记录：2025-02-04。
- **B机制**：学习长期任务价值；连续多峰动作；流BC蒸馏一步价值策略。
- **B代码入口**：[官方/作者来源所指仓库](https://github.com/seohongpark/fql)；Official repository page fetched and title/identity checked 2026-09-11; implementation not read or executed。
- **B迁移边界**：动作空间R^d；频道/动作类型混合离散需重新设计；不是硬完整性约束；JAX原代码不等于MPS直接部署。

### L09 · [Information-Directed Offline-to-Online Reinforcement Learning](https://arxiv.org/abs/2605.29405)

唯一标识：`arxiv:2605.29405`。

- **A读取范围**：arXiv metadata and abstract only; B supplied discovery identity
- **A发表状态**：arXiv preprint/version verified; separate venue not independently checked；首次公开日期记录：2026/05/28。
- **A机制**：A6/信息导向目标。
- **A迁移边界**：不是IRIS；理论posterior和参考策略条件不可直接用于Q+IG代理。
- **B读取范围**：PDF p1–4、§6–7 p7–9、Table1/2；未完整核验附录全部regret证明
- **B发表状态**：arXiv preprint；首次公开日期记录：2026-05-28。
- **B机制**：信息价值与探索；残余不确定性；离线后信息比率。
- **B迁移边界**：预印本；deep保证不随理论自动转移；D4RL优势非本题SOTA；固定误差场、连续joint belief及未知源数均未覆盖。

### L10 · [Learning-based Methods for Adaptive Informative Path Planning](https://arxiv.org/abs/2404.06940)

唯一标识：`arxiv:2404.06940`。

- **A读取范围**：§2, §3.2–3.3, §4.2 and CAtNIPP/graph references; not all cited papers
- **A发表状态**：arXiv preprint/version verified; separate venue not independently checked；首次公开日期记录：2024/04/10。
- **A机制**：D/分类与评测综述。
- **A迁移边界**：2024综述不能代表2026已穷尽；其引用条目不计作本轮已读正文。

### L11 · [Mastering Diverse Domains through World Models](https://arxiv.org/abs/2301.04104)

唯一标识：`arxiv:2301.04104`。

- **B读取范围**：实际取得并阅读arXiv v2（2024-04-17）PDF p1–3、p5–9；未声称读后续期刊终稿
- **B发表状态**：arXiv v2, 2024-04-17 read；首次公开日期记录：2023-01-10。
- **B机制**：模型辅助决策；想象轨迹学习；循环世界模型训练actor。
- **B迁移边界**：完整世界模型工程与训练预算大；gamma0.997/T16不可照抄到SMDP时间目标；“跨域通用”不意味源定位保证。

### L12 · [OffRIPP: Offline RL-based Informative Path Planning](https://arxiv.org/abs/2409.16830)

唯一标识：`arxiv:2409.16830`。

- **A读取范围**：III-A–B, IV-A–E; Eq3–5 and TablesI–II
- **A发表状态**：arXiv preprint/version verified; separate venue not independently checked；首次公开日期记录：2024/09/25。
- **A机制**：A4/离线行为支持约束。
- **A迁移边界**：PPO对照是直接用固定离线集训练，非公平在线PPO算法排序。Eq4阈值条件与tau=0/1解释文字表面相反，未核官方代码，不能直接照抄实现。
- **B读取范围**：PDF p1–6全文；p7参考文献中CAtNIPP、Dynamic Graph、BCQ/CQL链路
- **B发表状态**：arXiv preprint；首次公开日期记录：2024-09-25。
- **B机制**：学习长期任务价值；行为支持约束；离线候选Q。
- **B迁移边界**：表I专家数据下不及数据生成专家；PPO对照直接离线训练，不证明胜正确on-policy PPO；Eq4门槛与端点文字矛盾；数据分布外动作估值问题；无本题方向源/清除完整性。

### L13 · [TD-MPC2: Scalable, Robust World Models for Continuous Control](https://arxiv.org/abs/2310.16828)

唯一标识：`arxiv:2310.16828`。

- **B读取范围**：PDF p1–5，§3.1–3.3、Fig1/4和§4开头
- **B发表状态**：ICLR 2024；首次公开日期记录：2023-10-25。
- **B机制**：模型辅助决策；学习潜在动力学；短视规划与终值。
- **B代码入口**：[官方/作者来源所指仓库](https://github.com/nicklashansen/tdmpc2)；Code link read from official project page; repository implementation not independently audited。
- **B迁移边界**：模型近似误差、规划预算、连续动作；task embedding若含本题不可知任务标签会泄漏；动作维度mask不等于动态候选安全证书。

### L14 · [Towards Map-Agnostic Policies for Adaptive Informative Path Planning](https://arxiv.org/abs/2410.17166)

唯一标识：`arxiv:2410.17166`。

- **A读取范围**：IV-A–C, V-A–D; Eq5 and TableI
- **A发表状态**：arXiv v1 2024-10-22/v2 2025-04-07; manuscript says accepted2025-03-18; final publisher record not checked；首次公开日期记录：2024/10/22。
- **A机制**：A2/统一belief摘要。
- **A代码入口**：[官方/作者来源所指仓库](https://github.com/dmar-bonn/ipp-rl-gen)；public repository API verified; not installed/run。
- **A迁移边界**：依赖指定概率地图模型；兴趣概率/熵摘要不因此成为任何任务的充分Markov状态。
- **B读取范围**：PDF p1–7，重点§III–IV公式5/8、§V表I–III
- **B发表状态**：IEEE RA-L accepted 2025-03-18；首次公开日期记录：2024-10-22。
- **B机制**：统一任务表示；概率地图接口；兴趣概率与不确定性分离。
- **B代码入口**：[官方/作者来源所指仓库](https://github.com/dmar-bonn/ipp-rl-gen)；Official repository page fetched and title/identity checked 2026-09-11; implementation not read or executed。
- **B迁移边界**：概率地图成立是其前提；不是有界角度集合定位；实体机器人真实部署与真实地图回放不同；4ms论文耗时不是本机推理证据。

## 扩展：以记录的实际访问深度为准

### L15 · [A Closer Look at Invalid Action Masking in Policy Gradient Algorithms](https://arxiv.org/abs/2006.14171)

唯一标识：`arxiv:2006.14171`。

- **A读取范围**：arXiv metadata and abstract only
- **A发表状态**：arXiv preprint/version verified; separate venue not independently checked；首次公开日期记录：2020/06/25。
- **A机制**：C2/运行时安全约束。
- **A迁移边界**：mask合法性不等于任务完整性。

### L16 · [A Covering Framework for Offline POMDPs Learning using Belief Space Metric](https://arxiv.org/abs/2603.03191)

唯一标识：`arxiv:2603.03191`。

- **B读取范围**：arXiv摘要与元数据；无正文阅读
- **B发表状态**：arXiv preprint；首次公开日期记录：2026-03-03。
- **B机制**：学习长期任务价值；离线覆盖理论；belief度量下OPE。
- **B迁移边界**：摘要级；Lipschitz值假设遇硬接收/清除边界未证，不能赋予Q有限数据保证。

### L17 · [A Unified Experimental Architecture for Informative Path Planning: from Simulation to Deployment with GuadalPlanner](https://arxiv.org/abs/2602.10702)

唯一标识：`arxiv:2602.10702`。

- **A读取范围**：arXiv metadata and abstract only
- **A发表状态**：arXiv preprint/version verified; separate venue not independently checked；首次公开日期记录：2026/02/11。
- **A机制**：C3/统一执行评测接口。
- **A迁移边界**：本题固定HTTP/JSON协议且只单狗，无需引入整个机器人栈。

### L18 · [An Amortized Efficiency Threshold for Comparing Neural and Heuristic Solvers in Combinatorial Optimization](https://arxiv.org/abs/2605.14624)

唯一标识：`arxiv:2605.14624`。

- **B读取范围**：PDF p1–2；arXiv摘要/版本信息；未复算其能源日志
- **B发表状态**：arXiv preprint；首次公开日期记录：2026-05-14。
- **B机制**：评测与采用边界；成本摊销；质量门槛下部署盈亏平衡。
- **B代码入口**：[官方/作者来源所指仓库](https://github.com/sohaibafifi/aet)；Official repository page fetched and title/identity checked 2026-09-11; implementation not read or executed。
- **B迁移边界**：能源数字未独立核，GPU batch吞吐不适合本题在线batch1直接比较；上下文目标虚拟时间不同。

### L19 · [Approximate Sequential Optimization for Informative Path Planning](https://arxiv.org/abs/2402.08841)

唯一标识：`arxiv:2402.08841`。

- **A读取范围**：arXiv metadata and abstract only
- **A发表状态**：arXiv preprint/version verified; separate venue not independently checked；首次公开日期记录：2024/02/13。
- **A机制**：B2/状态相关代价优化。
- **A迁移边界**：不存在对本题联合belief的直接近似界。

### L20 · [Attention-based Learning for 3D Informative Path Planning](https://arxiv.org/abs/2506.08434)

唯一标识：`arxiv:2506.08434`。

- **A读取范围**：arXiv metadata and abstract only
- **A发表状态**：arXiv preprint/version verified; separate venue not independently checked；首次公开日期记录：2025/06/10。
- **A机制**：A1/候选图注意力。
- **A迁移边界**：高度/footprint权衡不存在于本题。

### L21 · [CIG-RL: Curiosity-Driven Information-Guided Reinforcement Learning for Source Term Estimation in Uncertain Environments](https://arxiv.org/abs/2608.30673)

唯一标识：`arxiv:2608.30673`。

- **A读取范围**：arXiv metadata and abstract only
- **A发表状态**：arXiv preprint/version verified; separate venue not independently checked；首次公开日期记录：2026/08/31。
- **A机制**：A6/信息导向目标。
- **A迁移边界**：不能把curiosity直接当信息theorem。

### L22 · [DIFF-IPPO: Diffusion-Based Informative Path Planning with Open-Vocabulary Belief Maps](https://arxiv.org/abs/2606.16780)

唯一标识：`arxiv:2606.16780`。

- **A读取范围**：arXiv metadata and abstract only
- **A发表状态**：arXiv preprint/version verified; separate venue not independently checked；首次公开日期记录：2026/06/15。
- **A机制**：A5/扩散轨迹与意图。
- **A迁移边界**：语义感知/图像target并非本题。
- **B读取范围**：arXiv摘要与元数据；无正文阅读
- **B发表状态**：arXiv preprint；首次公开日期记录：2026-06-15。
- **B机制**：模型辅助决策；非Gaussian地图轨迹；扩散生成全局路径。
- **B迁移边界**：不是已核RL算法；视觉语义与多无人机第一发现，非本题全源清除。

### L23 · [Dream-MPC: Gradient-Based Model Predictive Control with Latent Imagination](https://arxiv.org/abs/2605.04568)

唯一标识：`arxiv:2605.04568`。

- **B读取范围**：arXiv摘要与元数据；无正文阅读
- **B发表状态**：arXiv preprint；首次公开日期记录：2026-05-06。
- **B机制**：模型辅助决策；学习潜在动力学；策略轨迹的梯度MPC。
- **B迁移边界**：clear/no_signal不光滑；梯度优化物理接受边界风险，需单独验证。

### L24 · [Efficient Localization of Directional Emitters via Joint Beampattern Estimation](https://arxiv.org/abs/2411.04364)

唯一标识：`arxiv:2411.04364`。

- **A读取范围**：arXiv metadata and abstract only
- **A发表状态**：arXiv preprint/version verified; separate venue not independently checked；首次公开日期记录：2024/11/07。
- **A机制**：C1/联合状态估计。
- **A迁移边界**：本题只有方向/near/no_signal，无RSS/TDOA可读；半平面模型也不同。

### L25 · [Expected Free Energy-based Informative Path Planning for Robotic Mars Exploration](https://arxiv.org/abs/2608.14466)

唯一标识：`arxiv:2608.14466`。

- **A读取范围**：arXiv metadata and abstract only
- **A发表状态**：arXiv preprint/version verified; separate venue not independently checked；首次公开日期记录：2026/08/14。
- **A机制**：B3/主动推断目标。
- **A迁移边界**：目标是地图+价值非allclear time。

### L26 · [Fast and Highly Expressive Policy Learning for Offline Reinforcement Learning via Bootstrapped Flow Q-Learning](https://arxiv.org/abs/2606.10613)

唯一标识：`arxiv:2606.10613`。

- **B读取范围**：arXiv摘要/元数据；FQL API前向查询发现；无正文阅读
- **B发表状态**：arXiv preprint；首次公开日期记录：2026-06-09。
- **B机制**：学习长期任务价值；连续多峰动作；自举一步流生成。
- **B迁移边界**：动作混合离散与本题证书不适配；样本/算力预算未核。

### L27 · [Hierarchical Informative Path Planning via Graph Guidance and Trajectory Optimization](https://arxiv.org/abs/2601.17227)

唯一标识：`arxiv:2601.17227`。

- **A读取范围**：arXiv metadata and abstract only
- **A发表状态**：arXiv preprint/version verified; separate venue not independently checked；首次公开日期记录：2026/01/23。
- **A机制**：B2/状态相关代价优化。
- **A迁移边界**：本题无障碍、观测要停车且按频道付费。

### L28 · [HyCO: A Hybrid Neural Solver for Combinatorial Optimization](https://arxiv.org/abs/2609.07990)

唯一标识：`arxiv:2609.07990`。

- **B读取范围**：arXiv摘要与元数据；2026-09-07截止日前；无正文阅读
- **B发表状态**：arXiv preprint；首次公开日期记录：2026-09-07。
- **B机制**：学习长期任务价值；混合求解调度；RL前缀与扩散补全。
- **B迁移边界**：理论依赖显式error-scaling假设；proxy trigger不等于最优逐局切换；不能直接套清除任务。

### L29 · [IA-TIGRIS: An Incremental and Adaptive Sampling-Based Planner for Online Informative Path Planning](https://arxiv.org/abs/2502.15961)

唯一标识：`arxiv:2502.15961`。

- **A读取范围**：arXiv metadata and abstract only
- **A发表状态**：arXiv preprint/version verified; separate venue not independently checked；首次公开日期记录：2025/02/21。
- **A机制**：B1/增量采样规划。
- **A迁移边界**：控制模型与预算任务不同。
- **B读取范围**：arXiv摘要与元数据；无正文阅读
- **B发表状态**：arXiv preprint；首次公开日期记录：2025-02-21。
- **B机制**：模型辅助决策；已知观测模型搜索；增量信息树。
- **B迁移边界**：完整动作/观测分支模型不同；摘要最高38%IG不表示本题速度提升。

### L30 · [Information-Guided Safe Reinforcement Learning for Autonomous Gas Source Localization using sUAS](https://arxiv.org/abs/2609.05569)

唯一标识：`arxiv:2609.05569`。

- **A读取范围**：arXiv metadata and abstract only
- **A发表状态**：arXiv preprint/version verified; separate venue not independently checked；首次公开日期记录：2026/09/04。
- **A机制**：A6/信息导向目标。
- **A迁移边界**：气体扩散/噪声和安全supervisor不等于本题硬全清证书。

### L31 · [Informative Path Planning with Guaranteed Estimation Uncertainty](https://arxiv.org/abs/2602.05198)

唯一标识：`arxiv:2602.05198`。

- **A读取范围**：arXiv metadata and abstract only
- **A发表状态**：arXiv preprint/version verified; separate venue not independently checked；首次公开日期记录：2026/02/05。
- **A机制**：C2/估计质量保证。
- **A迁移边界**：依赖GP模型的uncertainty guarantee不是确定性有界误差的全源清除。
- **B读取范围**：arXiv摘要与元数据；无正文阅读
- **B发表状态**：arXiv preprint；首次公开日期记录：2026-02-05。
- **B机制**：完成与估计约束；模型条件覆盖；GP方差阈值。
- **B迁移边界**：GP模型内方差保证不是有界测向真实位置包络，不能直接认证空频道。

### L32 · [IRIS: An information path planning method based on reinforcement learning and information-directed sampling](https://doi.org/10.1016/j.patcog.2025.112400)

唯一标识：`doi:10.1016/j.patcog.2025.112400`。

- **A读取范围**：Crossref registered metadata; Elsevier article API coredata; no accessible abstract/body
- **A发表状态**：Pattern Recognition172,112400; print date2026-04 verified by publisher/Crossref; DOI registered2025-09-04 is not proven online-publication date；首次公开日期记录：未记录。
- **A机制**：A6/信息导向目标。
- **A迁移边界**：ScienceDirect content error,SSRN and UCL challenge pages; indexOA search no accessible manuscript; exact mechanisms remain open

### L33 · [LASER: Learning Active Sensing for Continuum Field Reconstruction](https://arxiv.org/abs/2604.19355)

唯一标识：`arxiv:2604.19355`。

- **A读取范围**：arXiv metadata and abstract only
- **A发表状态**：arXiv preprint/version verified; separate venue not independently checked；首次公开日期记录：2026/04/21。
- **A机制**：A3/历史状态聚合。
- **A迁移边界**：重建动态worldmodel成本高，本题几何已强。

### L34 · [Learning from World Feedback: Why Model Uncertainty Fails as a Risk Signal in Model-Based RL](https://arxiv.org/abs/2607.16591)

唯一标识：`arxiv:2607.16591`。

- **B读取范围**：PDF p1–2；arXiv摘要/元数据；未独立重跑
- **B发表状态**：arXiv preprint；首次公开日期记录：2026-07-18。
- **B机制**：评测与采用边界；代理风险审计；模型不确定性与真实约束分离。
- **B迁移边界**：论文声称ICML2026 RLxF workshop而非主会，官方workshop名单未核；局部实验不能证明所有uncertainty都无效。

### L35 · [LIPP: Load-Aware Informative Path Planning with Physical Sampling](https://arxiv.org/abs/2603.06924)

唯一标识：`arxiv:2603.06924`。

- **A读取范围**：Abstract; III-A–C, IV overview, VI setup selectively
- **A发表状态**：arXiv preprint/version verified; separate venue not independently checked；首次公开日期记录：2026/03/06。
- **A机制**：B2/状态相关代价优化。
- **A迁移边界**：未知场景与MIQP开销；改变代价模型与本题clear频道状态不同。

### L36 · [Multi-robot Learning-based Informative Path Planning Using Spatio-Temporal Gaussian Process Kalman Filter](https://arxiv.org/abs/2609.05515)

唯一标识：`arxiv:2609.05515`。

- **A读取范围**：arXiv metadata and abstract only
- **A发表状态**：arXiv preprint/version verified; separate venue not independently checked；首次公开日期记录：2026/08/31。
- **A机制**：C1/联合状态估计。
- **A迁移边界**：本题频道已区分目标，静态源不需动态GP预测。

### L37 · [N(CO)$^2$: Neural Combinatorial Optimization with Chance Constraints to Solve Stochastic Orienteering](https://arxiv.org/abs/2606.18514)

唯一标识：`arxiv:2606.18514`。

- **B读取范围**：PDF p1–2；arXiv元数据；后续方法实验未读
- **B发表状态**：arXiv preprint；首次公开日期记录：2026-06-16。
- **B机制**：模型辅助决策；不确定路线构造；机会约束图边启发式。
- **B迁移边界**：chance constraint允许失败概率，不满足本题全清保证；边成本未知机制不同。

### L38 · [On Distributional Dependent Performance of Classical and Neural Routing Solvers](https://arxiv.org/abs/2508.02510)

唯一标识：`arxiv:2508.02510`。

- **B读取范围**：arXiv摘要与元数据；无正文阅读
- **B发表状态**：arXiv preprint；首次公开日期记录：2025-08-04。
- **B机制**：评测与采用边界；分布泛化；经典与神经路线比较。
- **B迁移边界**：论文摘要称差距缩小并非普遍超过；只作协议启发。

### L39 · [Safe Reinforcement Learning via Shielding](https://arxiv.org/abs/1708.08611)

唯一标识：`arxiv:1708.08611`。

- **A读取范围**：arXiv metadata and abstract only
- **A发表状态**：arXiv preprint/version verified; separate venue not independently checked；首次公开日期记录：2017/08/29。
- **A机制**：C2/运行时安全约束。
- **A迁移边界**：安全不自动包含liveness或现实deadline完成。

### L40 · [Scalable Multi-Robot Informative Path Planning for Target Mapping via Deep Reinforcement Learning](https://arxiv.org/abs/2409.16967)

唯一标识：`arxiv:2409.16967`。

- **A读取范围**：arXiv metadata and abstract only
- **A发表状态**：arXiv preprint/version verified; separate venue not independently checked；首次公开日期记录：2024/09/25。
- **A机制**：A1/候选图注意力。
- **A迁移边界**：多机器人通信/碰撞组件不需要用于本题。

### L41 · [Trajectory Optimization for Adaptive Informative Path Planning with Multimodal Sensing](https://arxiv.org/abs/2404.18374)

唯一标识：`arxiv:2404.18374`。

- **A读取范围**：arXiv metadata and abstract only
- **A发表状态**：arXiv preprint/version verified; separate venue not independently checked；首次公开日期记录：2024/04/29。
- **A机制**：B2/状态相关代价优化。
- **A迁移边界**：传感器概率模型/连续轨迹与本题不同。

