# BC-RPI 第一轮真实训练与开发验证报告

生成时间：2026-09-12T10:13:52.883823+00:00。

本次授权的一轮训练与完整开发验证已完成；实际效果见下表。当前仍保留 Q3 R11 + Q4 R2，不自动晋级、不启动第二轮。

## 方法与证据边界

这是从冻结 π0=C7 出发的一次完整反事实监督拟合：同一公开状态下，每个保留动作执行完整“动作+C7续局”，以终局费用差监督网络；不是已经完成多轮策略更新的迭代 RL。三个初始化分别训练、分别校准、分别评估，不是集成模型。

旧 G1 的不足 2% 诊断没有改写。本次用户明确要求真实训练，覆盖的是“不足门槛就不训练”的停止条件，授权仅限这一轮。所有结果属于本地开发证据；没有密封最终集、4800 例追加全回归或官方 Windows 执行。

## 数据、模型与校准

共 180 个独特新 Q4 world，四种角色互不混用。600 是开发执行次数，不是 600 个新 world；另有 12 个旧兼容 probe，不进入新训练/校准/开发角色。

|角色|独特 world|公开入口状态|标签/执行|
|---|---|---|---|
|fit|24|96|702 个非 reference 标签；唯一梯度来源|
|fit_val|12|48|358 个非 reference 标签；仅选 epoch|
|calibration|24|48|24 共有 roll-in + 87 个唯一完整续局|
|development|120|闭环实际决策|五臂全配对，共 600 次 full|
|旧兼容 probe|12|真实前向、强制教师动作|两臂 24 次 full，请求/观测/费用完全一致|

训练为 3 seed × 20 epochs × 每 epoch 3 个完整 world minibatch，共 180 次实际优化更新；每模型 61,121 个参数。三个初始化共用同一份 36-world 完整标签，不重复计交互。每 seed 仅在 epoch 5/10/20 中由永久 fit_val 的 world→state→非 reference 动作等权 Huber 损失选择，平手取较早 epoch；开发结果不反馈调参。

标签尺度为 (T_ref−T_action)/(1000N)，N 仅供终局监督，不进入模型输入。q 取自 24 个 C7 roll-in world 抽样入口：每 world 最大乐观残差的第 22 小值与 0 取 max；这是经验校准，不是完整 πθ 闭环或 OOD 安全概率保证。线上严格 predicted_gain > q+0.0005，每局最多两次干预，其他情况保留教师。

|seed|选中 epoch|独立复算 Val loss|q|严格阈值 q+0.0005|拟合 wall 秒|
|---|---|---|---|---|---|
|912101|20|1.426984|0.000641742803|0.001141742803|0.961126|
|912102|20|1.422318|0.004569529185|0.005069529185|0.935136|
|912103|20|1.425281|0.001815307536|0.002315307536|0.921317|

- [912101 权重](<RL/training_round1_20260912/results/fit_v1/seed_912101_epoch_20.pt>)；SHA256 `fde843fcd26fbdc381406fa35602cc424217e0abc7751c0e906f18866e3f9ac3`；policy SHA256 `f32b23657a49bcf0ac479c2ce63fa30dea55ff93e9f3422d1a8f88562634de0b`。
- [912102 权重](<RL/training_round1_20260912/results/fit_v1/seed_912102_epoch_20.pt>)；SHA256 `a4a18c71212bc11d4ac17edf4ed3314ef1a8249ddc579bfa89beb3dbd9b64076`；policy SHA256 `e329e966654f2b826c0f1dbace6a2c2fc5dfee05fcee7fc02af1e4d002020ab1`。
- [912103 权重](<RL/training_round1_20260912/results/fit_v1/seed_912103_epoch_20.pt>)；SHA256 `bc8e4a36c5c363862c3c7ba7d5aa73ca081be95f75af7daa0253e55e72aed8cb`；policy SHA256 `e20153b05d6f49c776318998e18b19ebf11f7e7e8faa71aa4093711005a41665`。

## 完整开发结果

每臂 120 world。统计量为每局 T/N 的算术平均，不是总 T/总 N；只有相应完整配对全部正常全清，才比较速度。失败保留，未按成功子集重算。

|策略|正常全清|失败|mean(T/N)，秒/源|可比较速度|
|---|---|---|---|---|
|c7|120/120|0|466.939890|是|
|q4_r2|120/120|0|468.370778|是|
|neural_912101|120/120|0|467.004208|是|
|neural_912102|120/120|0|466.939890|是|
|neural_912103|120/120|0|466.954066|是|

Δ=模型−对照，负值更快；改善率=100×(1−模型均值/对照均值)，正值更快。12 组内各重抽 10 个配对 world，10,000 次、seed=912199；六比较共享抽样。95% 区间为线性插值的 percentile 描述性区间，没有最终测试或多重比较校正保证。

|模型|对照|Δ 秒/源|Δ 95% 区间|改善率 %|改善率 95% 区间|快/同/慢|
|---|---|---|---|---|---|---|
|neural_912101|c7|0.064318|[0.000000, 0.192955]|-0.013774|[-0.041809, 0.000000]|0/119/1|
|neural_912101|q4_r2|-1.366569|[-5.057206, 2.450568]|0.291771|[-0.524955, 1.081219]|45/20/55|
|neural_912102|c7|0.000000|[0.000000, 0.000000]|0.000000|[0.000000, 0.000000]|0/120/0|
|neural_912102|q4_r2|-1.430887|[-5.114269, 2.363478]|0.305503|[-0.509027, 1.088732]|45/20/55|
|neural_912103|c7|0.014176|[0.000000, 0.028407]|-0.003036|[-0.006139, 0.000000]|0/117/3|
|neural_912103|q4_r2|-1.416712|[-5.100069, 2.375107]|0.302477|[-0.511741, 1.084672]|44/20/56|

## 实际推理与计时范围

下表只汇总实际 model-scored、batch=1 决策的延迟；没有用大量教师直通分支稀释模型延迟，也没有平均每局 P95。全部决策、wrapper 与 enter-to-finish 统计另见 JSON。独立前向审计使用真实公开输入复算保存网络，不把复算次数计为开发执行。

|模型|实际 scored/干预|端到端 P95/P99 毫秒|模型 forward P95/P99 毫秒|冷启动秒|
|---|---|---|---|---|
|neural_912101|2235/1|90.214/104.561|0.332/0.405|0.597989|
|neural_912102|2236/0|91.846/115.664|0.331/0.395|0.400710|
|neural_912103|2234/4|97.784/118.288|0.330/0.400|0.451461|

端到端 selector 包含初始 prepare、候选/特征、IPC、forward、选择和输入 capture；prepared-state capture 在 selector 外、wrapper episode 内。模型冷启动另记；candidate 只有进程 launch 时间，ready 时间未知，不能把 launch 当 ready。主审/纯测试与开发存在并行计算，现实 wall 有机器争用，因此这些是本次仪器化运行观测，不是独占硬件延迟 benchmark，更不是因果优化收益。

各模型所有拒绝原因、实际 fallback 及不可获得的直接基线 fallback 字段在 JSON 中保留；捕获开销原值见绑定 SHA 的逐局源记录。不可获得不等于零。

## 费用与墙钟

|阶段|本次业务调用|实际执行|full/suffix|执行 wall 合计秒|
|---|---|---|---|---|
|labels|155180|1240|36/1204|1844.636502|
|calibration|15451|111|24/87|184.309604|
|compatibility|6274|24|24/0|35.836219|
|development|160858|600|600/0|1039.312328|

本轮新增 **337763 次业务调用、1975 次环境执行**。旧 G0/G1 carry-in 为 197456 次调用、1696 次执行，未重跑；仅 G0/G1 加本轮合计 535219 次调用、3671 次执行，不含更早 PPO/Q 或仓库其他实验。拟合、独立前向审计和纯张量测试不虚增环境执行计数。

三个拟合计时合计 2.817579 wall 秒、2.806154 CPU 秒，包含各自训练循环、Val 与检查点保存。整轮从预算登记到最后账本更新为 4178.920 秒，到报告生成时为 4368.575 秒；包含采集、拟合、审核与等待，不是纯训练耗时。审核独占时间未单独计量，不用总墙钟减拟合秒冒充审核时间。

## 逐组完整结果

每组固定 10 world；所有 12 组及六比较保留。局部组差异仅作开发描述，不据此挑选模型或修改参数。

|组|模型|对照|Δ 秒/源|改善率 %|快/同/慢|
|---|---|---|---|---|---|
|cell500_shared_field|neural_912101|c7|0.771819|-0.169863|0/9/1|
|cell500_shared_field|neural_912101|q4_r2|-14.047659|2.993974|6/0/4|
|cell500_shared_field|neural_912102|c7|0.000000|0.000000|0/10/0|
|cell500_shared_field|neural_912102|q4_r2|-14.819478|3.158472|6/0/4|
|cell500_shared_field|neural_912103|c7|0.000000|0.000000|0/10/0|
|cell500_shared_field|neural_912103|q4_r2|-14.819478|3.158472|6/0/4|
|cell50_shared_field|neural_912101|c7|0.000000|0.000000|0/10/0|
|cell50_shared_field|neural_912101|q4_r2|3.299852|-0.825587|3/1/6|
|cell50_shared_field|neural_912102|c7|0.000000|0.000000|0/10/0|
|cell50_shared_field|neural_912102|q4_r2|3.299852|-0.825587|3/1/6|
|cell50_shared_field|neural_912103|c7|0.000000|0.000000|0/10/0|
|cell50_shared_field|neural_912103|q4_r2|3.299852|-0.825587|3/1/6|
|edge_mixed_min_radius|neural_912101|c7|0.000000|0.000000|0/10/0|
|edge_mixed_min_radius|neural_912101|q4_r2|0.000000|0.000000|0/10/0|
|edge_mixed_min_radius|neural_912102|c7|0.000000|0.000000|0/10/0|
|edge_mixed_min_radius|neural_912102|q4_r2|0.000000|0.000000|0/10/0|
|edge_mixed_min_radius|neural_912103|c7|0.000000|0.000000|0/10/0|
|edge_mixed_min_radius|neural_912103|q4_r2|0.000000|0.000000|0/10/0|
|exactly10_sources|neural_912101|c7|0.000000|0.000000|0/10/0|
|exactly10_sources|neural_912101|q4_r2|7.480982|-1.280377|3/2/5|
|exactly10_sources|neural_912102|c7|0.000000|0.000000|0/10/0|
|exactly10_sources|neural_912102|q4_r2|7.480982|-1.280377|3/2/5|
|exactly10_sources|neural_912103|c7|0.000000|0.000000|0/10/0|
|exactly10_sources|neural_912103|q4_r2|7.480982|-1.280377|3/2/5|
|exactly16_sources|neural_912101|c7|0.000000|0.000000|0/10/0|
|exactly16_sources|neural_912101|q4_r2|-37.519848|10.744717|7/0/3|
|exactly16_sources|neural_912102|c7|0.000000|0.000000|0/10/0|
|exactly16_sources|neural_912102|q4_r2|-37.519848|10.744717|7/0/3|
|exactly16_sources|neural_912103|c7|0.000000|0.000000|0/10/0|
|exactly16_sources|neural_912103|q4_r2|-37.519848|10.744717|7/0/3|
|fixed_negative_bias|neural_912101|c7|0.000000|0.000000|0/10/0|
|fixed_negative_bias|neural_912101|q4_r2|15.677212|-2.987526|2/0/8|
|fixed_negative_bias|neural_912102|c7|0.000000|0.000000|0/10/0|
|fixed_negative_bias|neural_912102|q4_r2|15.677212|-2.987526|2/0/8|
|fixed_negative_bias|neural_912103|c7|0.000000|0.000000|0/10/0|
|fixed_negative_bias|neural_912103|q4_r2|15.677212|-2.987526|2/0/8|
|fixed_positive_bias|neural_912101|c7|0.000000|0.000000|0/10/0|
|fixed_positive_bias|neural_912101|q4_r2|6.340852|-1.286675|3/1/6|
|fixed_positive_bias|neural_912102|c7|0.000000|0.000000|0/10/0|
|fixed_positive_bias|neural_912102|q4_r2|6.340852|-1.286675|3/1/6|
|fixed_positive_bias|neural_912103|c7|0.000000|0.000000|0/10/0|
|fixed_positive_bias|neural_912103|q4_r2|6.340852|-1.286675|3/1/6|
|minimum_radius|neural_912101|c7|0.000000|0.000000|0/10/0|
|minimum_radius|neural_912101|q4_r2|-1.595742|0.309909|6/1/3|
|minimum_radius|neural_912102|c7|0.000000|0.000000|0/10/0|
|minimum_radius|neural_912102|q4_r2|-1.595742|0.309909|6/1/3|
|minimum_radius|neural_912103|c7|0.000000|0.000000|0/10/0|
|minimum_radius|neural_912103|q4_r2|-1.595742|0.309909|6/1/3|
|offcenter_cluster|neural_912101|c7|0.000000|0.000000|0/10/0|
|offcenter_cluster|neural_912101|q4_r2|2.206823|-0.578395|1/4/5|
|offcenter_cluster|neural_912102|c7|0.000000|0.000000|0/10/0|
|offcenter_cluster|neural_912102|q4_r2|2.206823|-0.578395|1/4/5|
|offcenter_cluster|neural_912103|c7|0.000000|0.000000|0/10/0|
|offcenter_cluster|neural_912103|q4_r2|2.206823|-0.578395|1/4/5|
|origin_cluster|neural_912101|c7|0.000000|0.000000|0/10/0|
|origin_cluster|neural_912101|q4_r2|-1.867083|0.449273|6/0/4|
|origin_cluster|neural_912102|c7|0.000000|0.000000|0/10/0|
|origin_cluster|neural_912102|q4_r2|-1.867083|0.449273|6/0/4|
|origin_cluster|neural_912103|c7|0.170108|-0.041117|0/7/3|
|origin_cluster|neural_912103|q4_r2|-1.696975|0.408341|5/0/5|
|reference_assumed|neural_912101|c7|0.000000|0.000000|0/10/0|
|reference_assumed|neural_912101|q4_r2|3.437447|-0.689713|4/0/6|
|reference_assumed|neural_912102|c7|0.000000|0.000000|0/10/0|
|reference_assumed|neural_912102|q4_r2|3.437447|-0.689713|4/0/6|
|reference_assumed|neural_912103|c7|0.000000|0.000000|0/10/0|
|reference_assumed|neural_912103|q4_r2|3.437447|-0.689713|4/0/6|
|smooth_shared_field|neural_912101|c7|0.000000|0.000000|0/10/0|
|smooth_shared_field|neural_912101|q4_r2|0.188334|-0.038870|4/1/5|
|smooth_shared_field|neural_912102|c7|0.000000|0.000000|0/10/0|
|smooth_shared_field|neural_912102|q4_r2|0.188334|-0.038870|4/1/5|
|smooth_shared_field|neural_912103|c7|0.000000|0.000000|0/10/0|
|smooth_shared_field|neural_912103|q4_r2|0.188334|-0.038870|4/1/5|

## 完整性与交付边界

纯测试 284 项全部通过，另有分层统计合成测试及原始冻结 v1 文件校验。纯张量梯度测试不是本轮真实拟合；真实 3 次拟合、180 次更新、9 个检查点由独立记录与参数审计确认。

失败结果行数：0，完整失败行保存在本报告配套 JSON；出现失败的对应完整臂不产加速排名。

本汇总只读取已完成的审计及 JSON/gzip 证据：新增环境调用 0、神经前向 0、优化更新 0。所有依赖逐一复核 SHA256 后才生成；不执行 Git、不修改主求解器、Q1/Q2 或当前推荐组合。下一轮或部署需要新的明确授权。

证据入口：

- [development](<verification/rl_round1_development_v1.json>)
- [forwards](<verification/rl_round1_development_forwards_v1.json>)
- [records](<verification/rl_round1_final_records_v1.json>)
- [fit](<verification/rl_round1_fitted_models_v1.json>)
- [calibration](<verification/rl_round1_calibration_v1.json>)
- [labels](<verification/rl_round1_labels_v1.json>)
- [public](<verification/rl_round1_public_export_v3.json>)
- [pure_tests](<verification/rl_round1_final_pure_tests_v1.json>)
