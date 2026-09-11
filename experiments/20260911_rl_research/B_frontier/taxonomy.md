# 前沿替代路线分类与阅读导航

截至2026-09-11：21篇去重候选，8篇核心原文选定章节阅读，13篇扩展（其中5篇只下载未深读的相关PDF，8篇只取得元数据/摘要）。下载13份PDF不等于完整阅读13篇；核心也不是全部附录逐式证明核验。主体窗口2024–2026，TD-MPC2与Dreamer以2024更新/发表作为必要祖先。

主分类轴是解决决策瓶颈的机制；每篇只有一条主路径，跨主题属性放入文献JSON。A另行核实用户IRIS/RF/CAtNIPP/Dynamic Graph，本树不把同名IRIS论文冒作用户来源。

```text
面向本题的强化学习与规划替代
├─ 学习长期任务价值
│  ├─ 行为支持约束
│  │  └─ 离线候选Q
│  │     └─ OffRIPP — arxiv:2409.16830
│  ├─ 历史编码稳定性
│  │  └─ 编码器专用学习率
│  │     └─ RESeL — arxiv:2405.15384
│  ├─ 连续多峰动作
│  │  ├─ 流BC蒸馏一步价值策略
│  │  │  └─ FQL — arxiv:2502.02538
│  │  └─ 自举一步流生成
│  │     └─ Bootstrapped Flow Q-Learning — arxiv:2606.10613
│  ├─ 多机器人轨迹策略
│  │  └─ 扩散BC后DPPO
│  │     └─ AID — arxiv:2512.02535
│  ├─ 离线覆盖理论
│  │  └─ belief度量下OPE
│  │     └─ Belief-Metric Offline POMDP — arxiv:2603.03191
│  └─ 混合求解调度
│     └─ RL前缀与扩散补全
│        └─ HyCO — arxiv:2609.07990
├─ 统一任务表示
│  ├─ 概率地图接口
│  │  └─ 兴趣概率与不确定性分离
│  │     └─ Map-Agnostic IPP — arxiv:2410.17166
│  └─ 环境变化适配
│     └─ 动态预测与域随机化
│        └─ DyPNIPP — arxiv:2410.17186
├─ 模型辅助决策
│  ├─ 学习潜在动力学
│  │  ├─ 短视规划与终值
│  │  │  └─ TD-MPC2 — arxiv:2310.16828
│  │  └─ 策略轨迹的梯度MPC
│  │     └─ Dream-MPC — arxiv:2605.04568
│  ├─ 想象轨迹学习
│  │  └─ 循环世界模型训练actor
│  │     └─ DreamerV3 — arxiv:2301.04104
│  ├─ 不确定路线构造
│  │  └─ 机会约束图边启发式
│  │     └─ N(CO)^2 — arxiv:2606.18514
│  ├─ 非Gaussian地图轨迹
│  │  └─ 扩散生成全局路径
│  │     └─ DIFF-IPPO — arxiv:2606.16780
│  └─ 已知观测模型搜索
│     └─ 增量信息树
│        └─ IA-TIGRIS — arxiv:2502.15961
├─ 信息价值与探索
│  ├─ 残余不确定性
│  │  └─ 离线后信息比率
│  │     └─ ROID / Offline-to-Online IDS — arxiv:2605.29405
│  └─ 上下文识别
│     └─ 线性信息比率的策略梯度目标
│        └─ C-IDS — arxiv:2602.03939
├─ 评测与采用边界
│  ├─ 成本摊销
│  │  └─ 质量门槛下部署盈亏平衡
│  │     └─ Amortized Efficiency Threshold — arxiv:2605.14624
│  ├─ 代理风险审计
│  │  └─ 模型不确定性与真实约束分离
│  │     └─ World Feedback Risk Audit — arxiv:2607.16591
│  └─ 分布泛化
│     └─ 经典与神经路线比较
│        └─ Distributional Routing Audit — arxiv:2508.02510
└─ 完成与估计约束
   └─ 模型条件覆盖
      └─ GP方差阈值
         └─ Guaranteed-Uncertainty IPP — arxiv:2602.05198
```

## 分类解释与当前取舍

学习长期任务价值：覆盖离线数据可复用、候选估值、连续多峰动作、序列记忆和混合策略。与本题最近的是OffRIPP，但其专家对照及离线PPO限制要求保留同预算PPO与BC。FQL/后续BFQ侧重连续动作表达，待有限候选本身成为已证瓶颈后再看。

统一任务表示：关注belief表达与学习算法能否拆开。Map-Agnostic IPP直接给出同一表示用于PPO和非学习规划的实验；DyPNIPP的动态场是近邻问题，本题静态源不应跟着改成动态目标。

模型辅助决策：比较已知模型的增量规划、学习潜在动力学、想象训练及不确定路线构造。本题先用已知移动计费+假设透明的观测分支，不必先学习全部物理。TD-MPC2的终值补足短视与Dreamer的想象训练分别启发不同环节，不能混写为同一部署算法。

信息价值与探索：ROID用平方regret比率，C-IDS用reward+MI与线性比率解释。Q差/ensemble方差不天然是Bayesian regret/MI。C-IDS证明中正信息条件尚待确认，因此只保留机制启发。

完成与估计约束：GP模型内后验方差阈值与本题连续集合最坏覆盖保证有不同前提；不得互相替代。

评测与采用边界：分布结构、总成本摊销、风险代理都决定是否值得用学习。最晚2026-09-07的HyCO只是摘要级候选；新不等于本题更优。

## 核心原文阅读结论（顺序与主树一致）

### [C-IDS](https://arxiv.org/abs/2602.03939)

主路径：信息价值与探索 → 上下文识别 → 线性信息比率的策略梯度目标。阅读：PDF p1–8；附录Lemma3.6/Eq19前后；17页全文已取得但非全证明核验。

问题与机制：在未知context的POMDP中同时获取回报和context信息。 reward+τMI的variational policy gradient；LSTM+EKF似然；线性而非平方信息比率。

证据：一维Light–Dark，2 contexts、3 actions、horizon20；10000训练episode；每梯度200轨迹；200测试trajectory；比较POMCP/RDPG-RNN。

本题迁移：说明信息驱动不限DQN；可明确检测可见侧等χ并评估信息作用。

边界：§2.1可变context与§3固定context不同；附录从有限episode断言universal η的正信息界未核通过；实验窄且Gaussian可重复噪声不同；ICML模板不等于录用。

### [ROID / Offline-to-Online IDS](https://arxiv.org/abs/2605.29405)

主路径：信息价值与探索 → 残余不确定性 → 离线后信息比率。阅读：PDF p1–4、§6–7 p7–9、Table1/2；未完整核验附录全部regret证明。

问题与机制：离线warm-start后定向消除剩余不确定性。 Δ²/(g+η)；线性Gaussian精确posterior/MI；deep TD3+BC ensemble仅作posterior/IG代理。

证据：隐藏模式bandit10 seeds、线性context bandit20 seeds；D4RL deep3 seeds；已知动力学线性reward理论与deep实验分开。

本题迁移：IDS若使用要标明学习目标和信息估计；先比较无IDS Q/PPO，后测残余可见侧信息。

边界：预印本；deep保证不随理论自动转移；D4RL优势非本题SOTA；固定误差场、连续joint belief及未知源数均未覆盖。

### [RESeL](https://arxiv.org/abs/2405.15384)

主路径：学习长期任务价值 → 历史编码稳定性 → 编码器专用学习率。阅读：PDF p1–4问题与架构；p6–9实验/限制；附录C.2 p17、表2 p21。

问题与机制：稳定训练部分可观测任务的recurrent off-policy actor-critic。 SAC+8 critic ensemble，context encoder用更小学习率；GRU/Mamba比较；全轨迹重放。

证据：18 POMDP与5 MDP locomotion任务；PyBullet隐藏位置/速度、MuJoCo重力随机化、meta-RL、credit assignment；各任务多百万交互，GRU部分消融0.75M。

本题迁移：部分可观测不排除off-policy；若GRU有增益须调独立编码器学习率并验证训练/部署序列一致。

边界：连续动作SAC不同于本题候选Q；默认Mamba含自定义reset，Apple直接可用未核实；完整序列重放有padding/峰值内存成本；未证明GRU总必要。

### [OffRIPP](https://arxiv.org/abs/2409.16830)

主路径：学习长期任务价值 → 行为支持约束 → 离线候选Q。阅读：PDF p1–6全文；p7参考文献中CAtNIPP、Dynamic Graph、BCQ/CQL链路。

问题与机制：从既有IPP数据学习预算内最大信息量路径。 行为策略拟合+batch-constrained Q；复用GP图注意力/LSTM骨干。

证据：2D光强及3D水果识别；每类数据18500轨迹，预算6/8/10；50环境实例；2D400 PRM节点、20邻居、256步上限；小型机器人投影光场演示。

本题迁移：直接支持先用C7示范、显式约束离线动作支持、对BC独立比较。

边界：表I专家数据下不及数据生成专家；PPO对照直接离线训练，不证明胜正确on-policy PPO；Eq4门槛与端点文字矛盾；数据分布外动作估值问题；无本题方向源/清除完整性。

### [FQL](https://arxiv.org/abs/2502.02538)

主路径：学习长期任务价值 → 连续多峰动作 → 流BC蒸馏一步价值策略。阅读：PDF p1–7，重点§2–3/Algorithm1及§5.1/表2。

问题与机制：用表达力强但高效的策略处理复杂离线动作分布。 flow只做BC；另一个一步策略在蒸馏约束下优化Q，绕开迭代flow的Q反传。

证据：73任务=50 state OGBench+5 visual+6 D4RL antmaze+12 adroit；state8 seeds/pixel4 seeds；固定梯度步评估；部分对照为既有文献数字。

本题迁移：连续多个优良清除/测点落点若为瓶颈，可考虑流策略；当前有限候选先用离散打分。

边界：动作空间R^d；频道/动作类型混合离散需重新设计；不是硬完整性约束；JAX原代码不等于MPS直接部署。

### [TD-MPC2](https://arxiv.org/abs/2310.16828)

主路径：模型辅助决策 → 学习潜在动力学 → 短视规划与终值。阅读：PDF p1–5，§3.1–3.3、Fig1/4和§4开头。

问题与机制：跨连续控制任务训练可扩展、稳健的隐式世界模型并规划。 decoder-free latent dynamics/reward/value联合学习、SimNorm、Q ensemble、MPPI+policy prior+learned terminal value。

证据：104 online control tasks、4 task domains；主要图3 seeds/95%CI；多任务317M模型80任务；连续动作最高39维。

本题迁移：借用短规划+终值分解；本题移动计费已知，优先用解析转移，不直接重学物理。

边界：模型近似误差、规划预算、连续动作；task embedding若含本题不可知任务标签会泄漏；动作维度mask不等于动态候选安全证书。

### [DreamerV3](https://arxiv.org/abs/2301.04104)

主路径：模型辅助决策 → 想象轨迹学习 → 循环世界模型训练actor。阅读：实际取得并阅读arXiv v2（2024-04-17）PDF p1–3、p5–9；未声称读后续期刊终稿。

问题与机制：单配置跨多种控制/游戏任务稳定学习。 RSSM压缩观测，想象轨迹训练actor/critic；symlog、return normalization、KL balance等稳定化。

证据：8 domains、150+任务；任务预算不同；每个agent单A100；环境执行用actor而非每步lookahead；本文版本非本题。

本题迁移：区分训练时想象与部署规划；可借成本尺度稳定化，但不能直接改任务目标。

边界：完整世界模型工程与训练预算大；gamma0.997/T16不可照抄到SMDP时间目标；“跨域通用”不意味源定位保证。

### [Map-Agnostic IPP](https://arxiv.org/abs/2410.17166)

主路径：统一任务表示 → 概率地图接口 → 兴趣概率与不确定性分离。阅读：PDF p1–7，重点§III–IV公式5/8、§V表I–III。

问题与机制：将连续与离散地图上的IPP统一表示，降低任务/地图依赖。 兴趣概率+地图不确定性+机器人/剩余预算/任务参数，PPO或Greedy/MCTS/CMA-ES共享表示。

证据：连续GP与离散occupancy；Static/Varying参数；预算100s；100 missions×3 seeds；Temperature/Potsdam/RIT-18真实地图数据评估。

本题迁移：把belief/动作表示改善与训练算法改善分开消融；不预设图优于小网络。

边界：概率地图成立是其前提；不是有界角度集合定位；实体机器人真实部署与真实地图回放不同；4ms论文耗时不是本机推理证据。

## 扩展发现集

| 论文 | 机制/纳入理由 | 阅读层级与未采用主张 |
|---|---|---|
| [AID](https://arxiv.org/abs/2512.02535) | 扩散生成长期轨迹，既有planner示范BC→DPPO。 BC后RL工作流。 | arXiv摘要与元数据；PDF下载但未读方法全文；单机器狗无队友意图，核心多agent收益不能移植；A负责用户AID-RL身份进一步核实。 |
| [HyCO](https://arxiv.org/abs/2609.07990) | RL prefix后自适应切换conditional diffusion completion；entropy/disagreement trigger。 混合控制器切换是一类方案；启发切换条件应实测且保留固定fallback。 | arXiv摘要与元数据；2026-09-07截止日前；无正文阅读；理论依赖显式error-scaling假设；proxy trigger不等于最优逐局切换；不能直接套清除任务。 |
| [Belief-Metric Offline POMDP](https://arxiv.org/abs/2603.03191) | 价值相关函数belief Lipschitz假设下度量覆盖误差界。 离线覆盖须看belief状态与动作，不只统计出现频道。 | arXiv摘要与元数据；无正文阅读；摘要级；Lipschitz值假设遇硬接收/清除边界未证，不能赋予Q有限数据保证。 |
| [Bootstrapped Flow Q-Learning](https://arxiv.org/abs/2606.10613) | 短位移分解后bootstrapping一步noise-to-action，无额外distillation。 连续落点路线未来比较FQL后续，不以2026更新自动替换主法。 | arXiv摘要/元数据；FQL API前向查询发现；无正文阅读；动作混合离散与本题证书不适配；样本/算力预算未核。 |
| [Guaranteed-Uncertainty IPP](https://arxiv.org/abs/2602.05198) | 把kernel转换coverage map，再选点/路由近似优化。 可靠性条件必须写清模型；覆盖层与效率层可分离。 | arXiv摘要与元数据；无正文阅读；GP模型内方差保证不是有界测向真实位置包络，不能直接认证空频道。 |
| [N(CO)^2](https://arxiv.org/abs/2606.18514) | edge-augmented graph transformer学习边heatmap与构造过程。 路线边特征/学习排序可启发多目标调度。 | PDF p1–2；arXiv元数据；后续方法实验未读；chance constraint允许失败概率，不满足本题全清保证；边成本未知机制不同。 |
| [Dream-MPC](https://arxiv.org/abs/2605.04568) | 少量policy rollout做gradient ascent，uncertainty regularization及跨步复用动作。 策略proposal+有限规划改进可能适用，但先解析转移与离散候选。 | arXiv摘要与元数据；无正文阅读；clear/no_signal不光滑；梯度优化物理接受边界风险，需单独验证。 |
| [IA-TIGRIS](https://arxiv.org/abs/2502.15961) | 增量树 refinement+belief更新适应。 浅belief规划可维护跨步树，避免反复重建。 | arXiv摘要与元数据；无正文阅读；完整动作/观测分支模型不同；摘要最高38%IG不表示本题速度提升。 |
| [DIFF-IPPO](https://arxiv.org/abs/2606.16780) | 开放词汇belief map+diffusion planner。 如果未来概率belief多峰，可考虑多样候选生成。 | arXiv摘要与元数据；无正文阅读；不是已核RL算法；视觉语义与多无人机第一发现，非本题全源清除。 |
| [DyPNIPP](https://arxiv.org/abs/2410.17186) | 域随机化+动态预测模型。 误差场域随机化可借鉴思路。 | arXiv摘要/元数据；PDF下载但未读方法全文；本题源静态；不能因此制造移动源或假装重现wildfire实验。 |
| [World Feedback Risk Audit](https://arxiv.org/abs/2607.16591) | 固定规划器更换世界模型与风险信号，对照真实碰撞/传感器约束。 ensemble方差不能拿作完整性证明。 | PDF p1–2；arXiv摘要/元数据；未独立重跑；论文声称ICML2026 RLxF workshop而非主会，官方workshop名单未核；局部实验不能证明所有uncertainty都无效。 |
| [Distributional Routing Audit](https://arxiv.org/abs/2508.02510) | 在带植入结构base distribution中采样训练/测试routing子问题。 新场景种子不一定代表新分布，需分布迁移压力测试。 | arXiv摘要与元数据；无正文阅读；论文摘要称差距缩小并非普遍超过；只作协议启发。 |
| [Amortized Efficiency Threshold](https://arxiv.org/abs/2605.14624) | 固定训练成本与每次边际成本、质量约束、部署量盈亏平衡。 报告总研发成本、每局推理和部署量，避免只报一次网络快。 | PDF p1–2；arXiv摘要/版本信息；未复算其能源日志；能源数字未独立核，GPU batch吞吐不适合本题在线batch1直接比较；上下文目标虚拟时间不同。 |

## 横向证据与停止边界

这些文献的任务终点分别为GP不确定性、地图准确率、累计回报、orienteering奖励和碰撞率。本题终点为所有源清除，再比较每局T/N与现实完成。它们不构成可按百分比混排的SOTA榜单。

跨论文较稳妥的推断是：任务表示和长程学习目标值得先独立验证；离线数据复用受支持覆盖限制；记忆的必要性与训练稳定性可分别检验；模型不确定性不能代替真实约束。新颖性仍未系统穷尽IEEE/Scopus/Web of Science，不能声称该组合首次。

本轮覆盖主要竞争机制后停止扩展，未下载/未读条目的细节不进入定量选型。8篇核心选定章节阅读、13篇扩展的具体来源与正文定位均在literature.json；初始搜索部分精确查询未保留，search_log如实标注。