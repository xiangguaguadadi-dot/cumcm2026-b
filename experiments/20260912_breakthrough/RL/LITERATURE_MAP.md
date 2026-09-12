# 本轮16篇来源：分类与逐篇阅读边界

从 [literature.json](literature.json) 生成；只生成索引，不替代原文核验。9篇核心指定章节阅读，7篇扩展；本轮与旧41篇重叠9篇，新增身份7篇，并集48篇。

## 控制对象的分解

### S05_residual · [Residual Reinforcement Learning for Robot Control](https://arxiv.org/abs/1812.03201v2)

主路径：控制对象的分解 → 保留解析控制 → 学习连续动作残差。

身份：2018-12-07；arXiv preprint; formal venue not independently verified this round。层级：core。

实际阅读：正文方法与simulation/real robot实验，Fig.3及实体块装配结果。

问题：已知反馈控制可处理大部分物理，但接触摩擦残差难建模且手调脆弱。

机制：将传统控制器信号与学得连续残差信号叠加，使用off-policy RL训练残差。

实验/效果：手工控制、纯学习/残差在特定控制和错位块装配条件比较。 Fig.3错位实体块实验为残差15/20、手工控制2/20成功；小样本任务限定。

边界：本题不是连续扭矩叠加；不能迁移机器人训练时间、稳定性或样本效率。

本题取舍：采用保留强控制器、限制改变范围的原则；动作改为离散整段服务替换。

### S14_tdmpc2 · [TD-MPC2: Scalable, Robust World Models for Continuous Control](https://arxiv.org/abs/2310.16828)

主路径：控制对象的分解 → 学习预测模型 → 隐式世界模型局部规划。

身份：2023-10-25；arXiv preprint; formal venue not independently verified this round。层级：extended。

实际阅读：本轮arXiv摘要/元数据；未重新下载正文。

问题：连续控制世界模型和规划的鲁棒性/跨任务可扩展性。

机制：隐式latent world model中作局部轨迹优化并预测价值。

实验/效果：摘要说明统一超参及规模实验；本轮未核正文可比性。 摘要报告104任务和317M参数80任务模型；只是来源背景，不是本题算力要求。

边界：重学已知移动物理可能浪费；离散可见性边界难以无误差学习。

本题取舍：暂不采用完整世界模型；先用真实模拟器生成成本标签。

## 真实任务损失驱动的策略改进

### S01_dagger · [A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning](https://proceedings.mlr.press/v15/ross11a.html)

主路径：真实任务损失驱动的策略改进 → 诱导状态分布 → 数据聚合动作示范。

身份：2011-06-14；Proceedings of the Fourteenth International Conference on Artificial Intelligence and Statistics。层级：core。

实际阅读：正文§1–4的方法和实验；未逐项复核附录定理。

问题：行为克隆部署时遇到自身错误诱导的输入分布，固定专家数据存在分布偏移。

机制：迭代以当前/混合策略roll-in，查询专家动作并聚合数据，以no-regret学习器更新策略。

实验/效果：比较监督学习及迭代模仿基线；任务与评价不同，不构成本题秒/源对照。 正文展示聚合数据改善顺序预测；本报告不跨图读取单一综合改善百分比。

边界：不能仅靠动作模仿保证超过教师；理论依赖no-regret等条件，本提案小网络不自动满足。

本题取舍：仅借诱导状态采样；本题主标签改为真实完整配对剩余费用。

### S02_lols · [Learning to Search Better than Your Teacher](https://proceedings.mlr.press/v37/changb15.html)

主路径：真实任务损失驱动的策略改进 → roll-in与roll-out解耦 → 参考及学得策略续局混合。

身份：2015-06-01；International Conference on Machine Learning。层级：core。

实际阅读：正文§2–5，算法1、roll-in/roll-out比较与实验表；非附录逐行证明审计。

问题：次优reference及不匹配roll-in/roll-out使训练忽略学得策略真实访问或复合错误。

机制：在学得策略产生的状态评估不同动作，以reference/learned混合续局得到结构化预测损失。

实验/效果：改变reference质量及roll-in/roll-out组合；局部结果依任务而异。 次优reference依存分析条件learned/mixture为90.2 UAS，learned/reference为87.1；POS条件reference续局有优势。

边界：非处处优于reference；结构化损失与有限宏操作部分观测控制不同，不迁移定理。

本题取舍：明确当前π_j roll-in/tail；首版不用混合tail，避免标签语义多版本。

### S03_aggrevated · [Deeply AggreVaTeD: Differentiable Imitation Learning for Sequential Prediction](https://proceedings.mlr.press/v70/sun17d.html)

主路径：真实任务损失驱动的策略改进 → cost-to-go策略优化 → 可微策略更新。

身份：2017-07-17；International Conference on Machine Learning。层级：core。

实际阅读：正文引言、算法/梯度推导与实验章节；未独立核所有理论证明。

问题：仅模仿专家动作忽略动作损失差，难利用可查询cost-to-go的训练信号。

机制：将cost-to-go oracle用于可微模仿学习，提出相应随机梯度及自然梯度更新。

实验/效果：比较行为克隆、模仿/强化学习方法；有可供查询的oracle条件。 报告多任务性能和样本效率改善；本报告未将曲线视觉读数转作本题预期提升。

边界：训练oracle可得性和质量是关键；C7续局不等于论文近最优oracle。

本题取舍：借完整未来损失查询，不照搬natural gradient；本题先配对回报回归。

### S06_aggrevate · [Reinforcement and Imitation Learning via Interactive No-Regret Learning](https://arxiv.org/abs/1406.5979)

主路径：真实任务损失驱动的策略改进 → cost-to-go策略优化 → 当前策略完整续局标签。

身份：2014-06-23；arXiv preprint; formal venue not independently verified this round。层级：core。

实际阅读：§2 AggreVaTe，§2.5专家续局反例，§3 NRPI算法及理论条件；非全文证明复核。

问题：动作模仿不利用任务成本；以不适合的专家tail估计动作价值会过于乐观。

机制：AggreVaTe查询专家cost-to-go；NRPI查询当前策略cost-to-go，将策略改进规约为交互no-regret学习。

实验/效果：以理论框架、算法和窄路反例为主；不当作本题或现代神经网络基准成绩。 提供近似策略迭代/no-regret分析；§2.5说明专家tail不能无条件代表学习策略未来。

边界：分布覆盖、损失/学习器等假设不可自动由有限样本非凸回归满足。

本题取舍：本提案最近机制祖先；γ=1变长operation、预算b及部分观測均是本题另立合同。

### S10_multistep · [Multi-step Proximal Policy Improvement in Offline Reinforcement Learning](https://arxiv.org/abs/2609.03842)

主路径：真实任务损失驱动的策略改进 → 离线actor优化 → 重定中心近端多步改进。

身份：2026-09-03；arXiv v1; manuscript explicitly states not peer-reviewed。层级：extended。

实际阅读：2026-09-03 v1摘要、引言、目录；未深读实验和证明。

问题：离线actor需保留数据支持，又希望获得超过单步近端更新的改进。

机制：顺序重定中心的proximal policy improvement，可用于确定性或高斯策略。

实验/效果：摘要提及TD3+BC/ReBRAC/IQL；本轮未核完整配置/分母。 仅记录摘要主张若干任务改善；不引用其数字或普遍效力。

边界：v1明确未经同行评审；仍依赖critic误差，未解决本题缺完整反事实标签。

本题取舍：作为近期竞争优化机制扩展，暂不采用。

## 主动信息决策的表示与动作约束

### S07_catnipp · [CAtNIPP: Context-Aware Attention-based Network for Informative Path Planning](https://proceedings.mlr.press/v205/cao23b.html)

主路径：主动信息决策的表示与动作约束 → 显式空间候选表示 → GP图与预算mask。

身份：2023-03-06；CoRL 2022; PMLR volume 205 published 2023-03-06。层级：core。

实际阅读：正文§3–5：GP图、注意力/LSTM/Pointer/PPO、奖励与仿真/机器人实验。

问题：连续信息路径规划需同时考虑预测不确定性、空间结构及剩余预算。

机制：GP增强图输入注意力网络、LSTM与Pointer；PPO选择图中下一点，mask保留返程可行性。

实验/效果：每预算30个实例×10次试验；机器人灰度图实验另列。 展示信息收集与路径规划性能；动态归一化信息奖励和原目标仍有偏差。

边界：到终点及信息质量不等于未知多频道全部清除；GP也不描述本题固定测角/可见性。

本题取舍：借显式候选及预算mask，拒绝把熵/面积下降直接代替秒/源。

### S08_offripp · [OffRIPP: Offline RL-based Informative Path Planning](https://arxiv.org/abs/2409.16830)

主路径：主动信息决策的表示与动作约束 → 离线数据支持 → 行为约束候选Q。

身份：2024-09-25；arXiv preprint; formal venue not independently verified this round。层级：core。

实际阅读：正文方法Eq.4与实验Table I；2D/3D设置及数据/成本范围。

问题：IPP在线收集训练数据昂贵，离线Q又会外推到缺乏行为支持的候选。

机制：拟合行为分布，在行为支持内使用batch-constrained Q选择信息路径候选。

实验/效果：各50测试实例，expert/greedy/random数据条件；CAtNIPP对照是naive offline PPO。 Table I expert数据预算10：covariance trace行为3.73、OffRIPP3.96、BC7.02（低好）；未超过行为专家。

边界：Eq.4不等号与τ端点文字冲突；不能推出Q普遍优于正确on-policy PPO；论文算力不移植。

本题取舍：作为旧约束Q近祖和负面边界，首版不继续将支持内宏排序Q当主突破口。

### S09_rf · [Active Sensing with Meta-Reinforcement Learning for Emitter Localization from RF Observations](https://arxiv.org/abs/2605.12569v1)

主路径：主动信息决策的表示与动作约束 → RF部分观测表示 → 高维IQ与循环策略。

身份：2026-05-12；arXiv preprint; formal venue not independently verified this round。层级：extended。

实际阅读：v1正文输入/网络/实验指定章节；只作扩展邻近任务，不新增核心结论。

问题：多径环境中单RF观测难确定发射源位置，需要主动移动和历史信息。

机制：2×2天线IQ、深度特征和可选循环模块，比较DQN/PPO及环境迁移。

实验/效果：单静态源、多天线IQ；PPO/DQN折扣和环境并行不同，测试N未在本轮落实。 论文报告80.1%定位成功；不同信息/配置，不作本题RL选型因果依据。

边界：current/goal输入的部署可得性和对比配置不一致；本题多源离散接口不匹配。

本题取舍：提醒部分观测表示问题；不因此认定必须PPO/LSTM。

### S12_robust_ipp · [DyPNIPP: Predicting Environment Dynamics for RL-based Robust Informative Path Planning](https://arxiv.org/abs/2410.17186)

主路径：主动信息决策的表示与动作约束 → 环境变化适应 → 动态预测context与域随机化。

身份：2024-10-22；arXiv preprint; formal venue not independently verified this round。层级：extended。

实际阅读：本轮只读arXiv元数据/摘要；尝试HTML v2返回404，未取得所请求正文。

问题：IPP在时空动态不同的环境间缺乏鲁棒性。

机制：摘要描述domain randomization与dynamics prediction model辅助策略。

实验/效果：本轮未核正文设置/数据规模，不复用旧轮深读标签。 仅摘要声称鲁棒性提高；本轮不报告数值。

边界：本题源静态；HTML获取失败不等于全文不存在，当前机制证据深度有限。

本题取舍：作为将来域变化路线，不引入本题没有的移动源。

### S13_recurrent · [Efficient Recurrent Off-Policy RL Requires a Context-Encoder-Specific Learning Rate](https://arxiv.org/abs/2405.15384)

主路径：主动信息决策的表示与动作约束 → 历史记忆训练 → context编码器独立学习率。

身份：2024-05-24；arXiv preprint; formal venue not independently verified this round。层级：extended。

实际阅读：本轮只读元数据/摘要；尝试HTML v3返回404，未复读旧轮正文。

问题：recurrent off-policy RL的context编码器与MLP共同学习率可能不稳定。

机制：对context encoder采用更低学习率，集成现有off-policy方法。

实验/效果：本轮没有核正文表格和实验超参。 摘要报告稳定性/性能改善；本轮不作精确效果比较。

边界：循环结构不保证本题收益，获取的摘要不能替代复现或证明。

本题取舍：提醒GRU不能当无代价修补；首版先简单集合编码。

### S15_fql · [Flow Q-Learning](https://arxiv.org/abs/2502.02538)

主路径：主动信息决策的表示与动作约束 → 连续动作分布 → flow行为模型与一步Q策略。

身份：2025-02-04；arXiv preprint; formal venue not independently verified this round。层级：extended。

实际阅读：本轮arXiv元数据/摘要；未重新深读方法正文。

问题：复杂离线动作分布难用简单策略表示，迭代flow的RL优化昂贵。

机制：flow-matching行为表示配合一步策略接受Q学习，避免反复反传迭代flow。

实验/效果：state/pixel、offline/offline-to-online多设置；本轮无公平数值比较。 仅保留摘要跨任务主张，不预测本题增益。

边界：本题有限离散候选未证明需连续多峰生成器；不核代码即不声称可运行。

本题取舍：连续落点若后续确为瓶颈再比较；首版不使用flow。

### S16_cids · [C-IDS: Solving Contextual POMDP via Information-Directed Objective](https://arxiv.org/abs/2602.03939)

主路径：主动信息决策的表示与动作约束 → 信息与任务回报联合 → context互信息目标。

身份：2026-02-03；arXiv preprint; formal venue not independently verified this round。层级：extended。

实际阅读：本轮arXiv元数据/摘要；不重述旧轮未独立核通过的证明为已验证。

问题：未知latent context的POMDP中同时优化奖励和context识别。

机制：加入context与观测的互信息，构造information-directed目标。

实验/效果：上下文假设及Bayesian regret证明本轮未独立核验。 仅保留摘要方法与实验主张，不采用理论保证。

边界：ensemble分歧不等于互信息；本题需另行定义context与观测模型。

本题取舍：不把本题Q差和预测残差命名为真实information ratio。

## 限制统计/执行风险

### S04_spibb · [Safe Policy Improvement with Baseline Bootstrapping](https://proceedings.mlr.press/v97/laroche19a.html)

主路径：限制统计/执行风险 → 低数据支持约束 → 复制基线概率质量。

身份：2019-05-24；International Conference on Machine Learning。层级：core。

实际阅读：正文§2–4：Π_b-SPIBB定义、保证条件与实验；区分理论版和放松版。

问题：固定数据离线策略改进可能在低支持状态动作上发生外推并劣于基线。

机制：对不够支持的state-action复制基线策略概率，在有支持区域进行改进。

实验/效果：有限折扣MDP理论与连续深度实验不是同一保证；比较数据规模/风险表现。 支持基线约束有助降低不安全改进风险；不引用为本题经验分位数的保证。

边界：有限MDP、覆盖/误差条件不能直接用于本题压缩历史和分布改变后的门控。

本题取舍：仅借不足支持回基线原则；本题用经验裕量，明示不是SPIBB实现。

### S11_shield · [Safe Reinforcement Learning via Shielding](https://arxiv.org/abs/1708.08611)

主路径：限制统计/执行风险 → 执行约束 → 形式规格前置与后置屏障。

身份：2017-08-29；arXiv preprint; formal venue not independently verified this round。层级：core。

实际阅读：正文安全规格、shield构造、前置/后置方案与实验边界；不复核全部证明。

问题：只最大化奖励的RL可能在训练或执行期违背安全规格。

机制：依据环境抽象及temporal-logic规格合成shield，预先给安全动作或事后修正违规动作。

实验/效果：具有给定抽象/规格条件的shield实验；本轮不建立统一数值榜。 展示不同RL场景下屏障作用；本题无直接部署试验。

边界：safety fragment不自动证明最终全部清除的liveness；可靠抽象是前提。

本题取舍：保留四接口、几何证书、有限进展及独立fallback，不以统计阈值代替。
