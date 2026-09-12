# 文献机制图谱与实际阅读账本

检索截至2026-09-12。本目录收录15篇有一手页面或原文依据的机制候选：7篇定向阅读方法/实验或边界章节，8篇扩展阅读。没有声称穷尽领域、15篇全部全文精读或逐条复现。源码侧继承的文献缓存与本轮新获取页面分别标注；最新页面身份不意味着审稿接收状态。

分类采用“更新对象或决策结构→机制→论文”：belief/model adaptation、controller structure、policy learning signal、planning and representation四条主线。只把有实际实现的R1-R6/B1-B7称为本轮成果。

## maxent · Improving D-Optimal Sensor Placement for Bearing-Only Localization via Maximum-Entropy Reweighting

来源：[一手页面](https://arxiv.org/html/2605.11116v1)；获取记录：primary page retrieved this run。

实际阅读：II bearing FIM and two layers; IV setup; V limitations; no full proof audit。层级：core。

分类：belief/model adaptation → planning-only posterior reweighting → maxent。

原文方法：Particle reweighting changes placement objective while the Bayesian observation update retains the original prior.

原文实验范围：Multi-source 2D synthetic bearing localization; Gaussian noise 8 or 15 degrees, D-optimal comparison.

迁移边界：No guarantee on complete-task time; Gaussian independence and particle approximation differ from bounded fixed error.

本地对应：Separate planning estimates from reliable polygons; no direct MaxEnt reproduction.

本地身份页面：`experiments/parallel_v2_a3/research/bearing_maxent_current.html`；SHA256 `ba8075cc22b4b72206a0a40ab0e0e86dfbd5124580aad2226cbc9a1bbb3c2ee0`。

实际方法阅读原文存档：`research/bearing_maxent_current.html`（actual primary body used for targeted reading，SHA256 `ba8075cc22b4b72206a0a40ab0e0e86dfbd5124580aad2226cbc9a1bbb3c2ee0`）。

## bias_registration · Multisensor--Multitarget Bearing--Only Sensor Registration

来源：[一手页面](https://arxiv.org/abs/1603.03450)；获取记录：primary page retrieved this run。

实际阅读：PDF pages 1-6 including measurement model and likelihood; simulation setup excerpt。层级：core。

分类：belief/model adaptation → shared sensor-bias estimation → bias_registration。

原文方法：Triangulated pseudo-measurement differences identify sensor bias, fitted with batch maximum likelihood.

原文实验范围：Distributed multisensor multitarget bearing tracking; simulations also consider missed detections and false alarms.

迁移边界：Requires identifiable sensor geometry; independent Gaussian assumptions and moving targets differ from this problem.

本地对应：B1-B4 shared-angle planning hypotheses inferred from successful-clear regions; not the original estimator.

本地身份页面：`experiments/parallel_v2_a3/research/bias_registration_current.html`；SHA256 `cc782bce8b3fa9f4045792ba7708435e7a383a0f3f99f17da471168522e6be6e`。

实际方法阅读原文存档：`research/bias_registration.pdf`（actual primary body used for targeted reading，SHA256 `4ac02d6b7958f9d290f83b61394d93c582538ebbbd819344da447ea636a4a6ae`）。

## vb_noise · Tracking an Underwater Target with Unknown Measurement Noise Statistics Using Variational Bayesian Filters

来源：[一手页面](https://arxiv.org/abs/2305.08390)；获取记录：primary page retrieved this run。

实际阅读：PDF pages 1-4; VII setup and VIII discussion excerpts; no full VB derivation audit。层级：core。

分类：belief/model adaptation → joint noise mean and covariance inference → vb_noise。

原文方法：Normal-inverse-Wishart model jointly adapts unknown noise mean and covariance through variational filtering.

原文实验范围：Moderate/high nonlinear underwater bearing tracking, static/varying covariance, RMSE and track-loss comparisons.

迁移边界：Gaussian noise, process model and 30-minute sensing differ; some reported metrics exclude divergent tracks.

本地对应：Motivates learning a noise bias instead of assuming zero mean; our grid profile likelihood is not VB.

本地身份页面：`experiments/parallel_v2_a3/research/vb_noise_current.html`；SHA256 `4396d307bbbf740bbf54e4970c855745e1300aca23b118302c19f7a0d3498411`。

实际方法阅读原文存档：`research/vb_noise.pdf`（actual primary body used for targeted reading，SHA256 `f4a5883771cc65f6d948be948650347d82687052922d94c00e8fccfc18359e9f`）。

## residual · Residual Reinforcement Learning for Robot Control

来源：[一手页面](https://arxiv.org/abs/1812.03201v2)；获取记录：primary page retrieved this run。

实际阅读：Cached PDF pages 1-5 method, setup, real block-assembly result。层级：core。

分类：controller structure → retain controller and learn residual → residual。

原文方法：An additive learned control policy complements a hand-engineered controller, trained using a TD3 variant.

原文实验范围：MuJoCo and physical block assembly, including misalignment and control-noise experiments.

迁移边界：Continuous torque/position control differs from discrete service replacement; reported sample efficiency does not transfer.

本地对应：R1-R6 alter narrowly defined trial/service decisions while keeping coverage and fallback.

本地身份页面：`experiments/parallel_v2_a3/research/residual_current.html`；SHA256 `d1cc7f376bc8dd5ba67210870de3e191fc28ea574fc6ad02a56d9d7e140460c3`。

实际方法阅读原文存档：`research/residual_method_cached.txt`（cached primary PDF text; only reading_scope sections were read，SHA256 `4610d4d7b860308b20986a38d2d59a0829d30a6df100e88cb2be361b31c9f06c`）。

## spibb · Safe Policy Improvement with Baseline Bootstrapping

来源：[一手页面](https://proceedings.mlr.press/v97/laroche19a.html)；获取记录：primary page retrieved this run。

实际阅读：Cached PDF page 3 method/theorems, page 5 experimental protocol。层级：core。

分类：controller structure → conservative policy improvement → spibb。

原文方法：On insufficiently supported state-action pairs, retain the baseline action probabilities.

原文实验范围：Finite MDP/gridworld mean and CVaR comparisons; approximate deep variants are separate.

迁移边界：Our empirical gates have no finite-MDP SPIBB bound or state-action count guarantee.

本地对应：Use fixed validation gates and keep a baseline action; do not infer mathematical safety from a model score.

本地身份页面：`experiments/parallel_v2_a3/research/spibb_current.html`；SHA256 `41e35c89b28052a05ec0015c877ba40abef3df69bb28d19273bf9e7bfc0ed498`。

实际方法阅读原文存档：`research/spibb_method_cached.txt`（cached primary PDF text; only reading_scope sections were read，SHA256 `993a66a1e505a285970e89470c1ab2099f98080c15b8069070ddc67d14083c9a`）。

## aggrevate · Reinforcement and Imitation Learning via Interactive No-Regret Learning

来源：[一手页面](https://arxiv.org/abs/1406.5979)；获取记录：primary page retrieved this run。

实际阅读：Cached PDF pages 1-3, algorithm and regression reduction; theoretical work。层级：core。

分类：policy learning signal → cost-sensitive rollout labels → aggrevate。

原文方法：Explore an action at a visited state, complete a reference-policy rollout, and learn from its cost-to-go.

原文实验范围：Theoretical no-regret framework; no benchmark score imported into our report.

迁移边界：Finite feature approximation and imperfect reference do not ensure monotone real-task improvement.

本地对应：R2 explicitly one-action surrogate; R3-R5 actual local tails; R6 exact whole-task paired tails.

本地身份页面：`experiments/parallel_v2_a3/research/aggrevate_current.html`；SHA256 `67205b031de046da3a1932991cf7f8baf61a905b4fd5554a5885ddd7552fecf5`。

实际方法阅读原文存档：`research/aggrevate_method_cached.txt`（cached primary PDF text; only reading_scope sections were read，SHA256 `28ce3211325cb9ce3cc238a0835488327bad4487e9d370fcf3ef114f962372e4`）。

## catnipp · CAtNIPP: Context-Aware Attention-based Network for Informative Path Planning

来源：[一手页面](https://proceedings.mlr.press/v205/cao23b.html)；获取记录：primary page retrieved this run。

实际阅读：Cached PDF pages 4-6 architecture/training/planning, page 8 limitations。层级：core。

分类：planning and representation → attention and receding-horizon IPP → catnipp。

原文方法：GP belief graph, attention/LSTM policy, budget mask, optional sampled receding-horizon trajectories.

原文实验范围：Information mapping and light-intensity experiment; comparison objective is covariance reduction, not full clearance time.

迁移边界：GP-kernel sensitivity, graph discretization and substantial training budget; sensing reward mismatch matters.

本地对应：Supports history and macro planning alternatives; full graph PPO not repeated after repository negative result.

本地身份页面：`experiments/parallel_v2_a3/research/catnipp_current.html`；SHA256 `9bbc379898e3df78f891655e916aa17b95caeb6350144cf261ada657865e20ea`。

实际方法阅读原文存档：`research/catnipp_method_cached.txt`（cached primary PDF text; only reading_scope sections were read，SHA256 `f2eca034eeb3d6542fca773c08bcd7463b0fcbe3357080661b9f364c1cd87cfe`）。

## lols · Learning to Search Better than Your Teacher

来源：[一手页面](https://proceedings.mlr.press/v37/changb15.html)；获取记录：primary page retrieved this run。

实际阅读：Cached PDF page 3 algorithm; other results not deeply read。层级：extended。

分类：policy learning signal → mixed-reference local rollout search → lols。

原文方法：One-step deviations evaluated by mixed reference/current-policy tails generate cost-sensitive examples.

原文实验范围：Structured prediction search; no numeric transfer claim.

迁移边界：Teacher mismatch and downstream distribution shift remain.

本地对应：R5 changes visited-state distribution; R6 evaluates reference and two deviations.

本地身份页面：`experiments/parallel_v2_a3/research/lols_current.html`；SHA256 `a43dcfa8b31087a3a1707db62bb2c5e120155dc23016b7b96b8ec86f49780c18`。

实际方法阅读原文存档：`research/lols_method_cached.txt`（cached primary PDF text; only reading_scope sections were read，SHA256 `60d3210effd4f1c18bae3b6034bf8c0e7083c40ffbde90e6e9168daf9305794a`）。

## aggrevated · Deeply AggreVaTeD: Differentiable Imitation Learning for Sequential Prediction

来源：[一手页面](https://proceedings.mlr.press/v70/sun17d.html)；获取记录：primary page retrieved this run。

实际阅读：Current primary metadata and abstract; cached repository proposal context only。层级：extended。

分类：policy learning signal → differentiable cost-to-go imitation → aggrevated。

原文方法：Differentiable policy improvement with reference cost-to-go information.

原文实验范围：Primary abstract only in this pass; no reproduced experiment or numerical claim.

迁移边界：Neural optimization alone cannot enlarge useful actions or correct a poor target.

本地对应：Considered neural alternative; chose auditable ridge before a larger model.

本地身份页面：`experiments/parallel_v2_a3/research/aggrevated_current.html`；SHA256 `ae0e8b1506e933c9eb0cd49bfe542afa242d833f624853b3dfc09b049bd7af9c`。

## dagger · A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning

来源：[一手页面](https://proceedings.mlr.press/v15/ross11a.html)；获取记录：frozen cached primary page, not freshly retrieved。

实际阅读：Cached PDF pages 1-2 introduction; current live page not re-fetched。层级：extended。

分类：policy learning signal → on-policy data aggregation → dagger。

原文方法：Collect reference supervision on learner-visited states to address compounding imitation error.

原文实验范围：Imitation and sequence labeling; no exact benchmark number used.

迁移边界：Imitating actions cannot by itself outperform a strong teacher.

本地对应：R5 learner-state recollection inspired by distribution correction, with cost labels instead of action agreement.

本地身份页面：`experiments/parallel_v2_a3/research/dagger_cached.html`；SHA256 `e515cc08883fb65a967c7cc1cd4905107d7dc31aeed4a71c254ea250a670ad75`。

实际方法阅读原文存档：`research/dagger_method_cached.txt`（cached primary PDF text; only reading_scope sections were read，SHA256 `0f4b7f008756e82061002860254405d8942b84dc90f09f05bc6d50dca9470971`）。

## offripp · OffRIPP: Offline RL-based Informative Path Planning

来源：[一手页面](https://arxiv.org/abs/2409.16830)；获取记录：primary page retrieved this run。

实际阅读：Cached PDF first page and current metadata。层级：extended。

分类：planning and representation → offline support-constrained IPP → offripp。

原文方法：Batch-constrained offline RL limits extrapolation from pre-collected informative path data.

原文实验范围：2D light intensity and 3D fruit identification tasks stated in introduction.

迁移边界：Dataset support and information-gain objective differ from legal clear-completion time.

本地对应：Did not rerun old constrained-Q route that already failed in the repository.

本地身份页面：`experiments/parallel_v2_a3/research/offripp_current.html`；SHA256 `d9fb9f05426f5e620c4a8083843c7ec3ee7663a6f67bc9a385295f706392ebf2`。

实际方法阅读原文存档：`research/offripp_method_cached.txt`（cached primary PDF text; only reading_scope sections were read，SHA256 `9b3382b3084cbc22fa40d079b6d844cf4ea2dada4e270765834857d4e3e6a985`）。

## meta_rf · Active Sensing with Meta-Reinforcement Learning for Emitter Localization from RF Observations

来源：[一手页面](https://arxiv.org/html/2605.12569v1)；获取记录：primary page retrieved this run。

实际阅读：Current full body IV-V methods/data sections; VI results not fully audited。层级：extended。

分类：planning and representation → recurrent RF adaptation → meta_rf。

原文方法：CNN/LSTM observation encoders and meta adaptation for source-seeking from RF observations.

原文实验范围：Synthetic Sionna indoor RF environment with current and goal feature tensors.

迁移边界：Raw multi-antenna IQ and goal observations are absent from the four contest interfaces; distance shaping differs.

本地对应：Rejected direct transfer of architecture/reward, retained idea of online latent-context adaptation.

本地身份页面：`experiments/parallel_v2_a3/research/meta_rf_current.html`；SHA256 `99b9d6eec4c073baaa725608d1d0db9b6027c76b0ea8fbc109ad422afbb8b46d`。

实际方法阅读原文存档：`research/meta_rf_current.html`（actual primary body used for targeted reading，SHA256 `99b9d6eec4c073baaa725608d1d0db9b6027c76b0ea8fbc109ad422afbb8b46d`）。

## tdmpc2 · TD-MPC2: Scalable, Robust World Models for Continuous Control

来源：[一手页面](https://arxiv.org/abs/2310.16828)；获取记录：primary page retrieved this run。

实际阅读：Current primary metadata and abstract only。层级：extended。

分类：planning and representation → latent world-model planning → tdmpc2。

原文方法：Local trajectory optimization in a learned latent world model.

原文实验范围：Broad continuous-control benchmark in abstract; no reproduced score.

迁移边界：Would add model error for deterministic geometry that is already available analytically.

本地对应：Not implemented; exact simulator tails are cheaper for this bounded experiment.

本地身份页面：`experiments/parallel_v2_a3/research/tdmpc2_current.html`；SHA256 `2902676cfa8cf64a5daff5d9775fa34de28e6ba2a2cf475fa7e1a7f7adf1ecf1`。

## fql · Flow Q-Learning

来源：[一手页面](https://arxiv.org/abs/2502.02538)；获取记录：primary page retrieved this run。

实际阅读：Current primary metadata and abstract only。层级：extended。

分类：planning and representation → expressive offline action distribution → fql。

原文方法：Flow-matching behavior policy guides an expressive one-step RL actor.

原文实验范围：D4RL/OGBench according to primary abstract; not compared numerically here.

迁移边界：Useful for broad continuous action spaces; our small legal residual set does not need a generative actor.

本地对应：Deferred until finite alternatives show substantial verified action-space headroom.

本地身份页面：`experiments/parallel_v2_a3/research/fql_current.html`；SHA256 `c5949bfffa38d89ab056b429109099b452687b07aa3b2e6ebf65450f068b86a8`。

## cids · C-IDS: Solving Contextual POMDP via Information-Directed Objective

来源：[一手页面](https://arxiv.org/abs/2602.03939)；获取记录：primary page retrieved this run。

实际阅读：Current primary metadata and abstract only。层级：extended。

分类：planning and representation → latent-context information objective → cids。

原文方法：Reward augmented with information about latent context in contextual POMDPs.

原文实验范围：Light-Dark experiment described in primary abstract.

迁移边界：Mutual-information bonus is not the contest time metric; Bayesian regret assumptions need a correct context model.

本地对应：Shared-bias hypothesis is a context candidate; no IDS bound or bonus is claimed.

本地身份页面：`experiments/parallel_v2_a3/research/cids_current.html`；SHA256 `8fef086f136b08010170c35ea1c2aaf623d8508a3d073c255674e89f0ddf08a3`。

共享偏差方法中的后验、模型证据和污染混合是本地profile规划构造，没有重现原论文的动态模型、Gaussian假设或理论保证。B3/B4/B5/B6/B7分别是点估计、后验盘规划、跨频道稳定性、污染混合及模型平均的机制后继，而非把同一阈值扫描重命名成新方向。
