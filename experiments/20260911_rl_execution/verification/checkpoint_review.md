# 27 个部署权重内部状态复核

结论：**通过**。共 424 项检查，失败 0 项。

## 直接核验结果

- 3 个 BC、12 个 PPO、12 个 Q 全部可用安全权重模式读取；文件 SHA256 与 BC 摘要或 PPO/Q 索引、选择冻结记录一致。
- 27 份 algorithm/seed 一致；24 份 PPO/Q 内嵌 completed_new_episodes 分别为 128、256、512、1024。BC 未内嵌该字段，其 0 个新增训练局来自已核对摘要。
- 全部网络参数名称、形状、float32 类型及有限值符合冻结网络：16 个张量、31,938 个参数；评分路径 12 个张量、23,617 个参数，未用于 Q 的价值头 8,321 个参数。
- 12 个 Q 的支持评分路径均逐张量精确等于同初始化 BC，且不等于另外两个初始化 BC；完整支持网络也精确相同。Q 自身未使用的价值头保持该 BC 值。
- 已核对 Adam 保存字段、对应参数形状与计步：BC 512；PPO 为训练局数 / 2；Q 为 256 次 MC 初始化更新加新增训练局数。未恢复优化器或执行更新。
- 6 份训练摘要与选择冻结的摘要/行账本散列相符，1024 局完成位置及更新账本相符；6 个 resume.pt 只核验摘要中记录的文件散列，未反序列化。

## Q 累计训练范围

独立读取 512 份共同 C7 示范与 3×1024 份 Q 训练存档，逐份核对压缩 SHA、解压内容 SHA、注册 world/recipe、所属策略和决策数。仅从已保存 snapshot 的三组可观测特征复算 88 个上下界数值，逐 checkpoint 采用精确比较；没有调用运行时的 FeatureBounds 实现。

| 初始化 | 新增训练局 | 共享示范快照 | 自身训练快照 | 累计快照 | revision |
|---|---:|---:|---:|---:|---:|
| 81001 | 128 | 14922 | 2978 | 17900 | 640 |
| 81001 | 256 | 14922 | 6352 | 21274 | 768 |
| 81001 | 512 | 14922 | 13159 | 28081 | 1024 |
| 81001 | 1024 | 14922 | 26891 | 41813 | 1536 |
| 81002 | 128 | 14922 | 3074 | 17996 | 640 |
| 81002 | 256 | 14922 | 6600 | 21522 | 768 |
| 81002 | 512 | 14922 | 13146 | 28068 | 1024 |
| 81002 | 1024 | 14922 | 26729 | 41651 | 1536 |
| 81003 | 128 | 14922 | 3089 | 18011 | 640 |
| 81003 | 256 | 14922 | 6553 | 21475 | 768 |
| 81003 | 512 | 14922 | 13104 | 28026 | 1024 |
| 81003 | 1024 | 14922 | 26854 | 41776 | 1536 |

12 份 checkpoint 的全部 extrema、累计快照数、revision，以及逐次 added_snapshots/source/cumulative_snapshots 历史均与上述原始轨迹复算相同。3 份初始 range_registration 也与共同示范复算相同。保存状态与“仅用共享示范和本初始化已执行训练轨迹”的累计规则完全一致。极值与历史相同本身不能排除未留痕、且未改变这些数值的额外读取；完整访问控制不在本次审查范围。

范围版本为 `training_extrema_v2_clocks_physical_only`；下一动作契约为 `deployment_bounds_teacher_supported_argmax_v2_clock_physical`。时钟字段 global[6]、global[14] 的实测 extrema 仍保存且已复核，但冻结源码对这两项只检查有限值和物理 [0,1]±1e-6，不以训练时钟 extrema 拒绝部署动作。这是源码审查结论，本次没有执行门控。

## 部署字段和单位

| 模型 | 已直接检查的配置 | 字段边界 |
|---|---|---|
| BC | BCTrainer；学习率 0.0003；epochs=1；梯度上限 0.5；forward_batch_size=128；policy_version=512 | 权重无奖励单位、网络配置或 completed_new_episodes 字段；结构按冻结共享网络和部署读取源码核对 |
| PPO | PPOTrainer；学习率 0.0003；clip=0.2；epochs=4；梯度上限 0.5；value coefficient=0.5；forward_batch_size=128；T0=1000；failure penalty=100 | gamma=1 为冻结 returns 源码契约，非 checkpoint 独立字段；policy_version=训练局数/8 |
| Q | network config 16/16/12/64；kappa=0.1；target_tau=0.01；梯度上限0.5；microbatch=128；T0=1000；gamma=1；一次失败惩罚100；true_N_is_deployment_input=false | 已检查 network、target、support、optimizer、range、history、版本契约等读取必需字段；未构造或运行选择器 |

Q 标签单位对应冻结源码中的 `-Δt/(1000·N)`，完整回报采用不折扣累计费用和一次失败惩罚。该句为源码契约审查；本次不从权重证明每条实际训练标签或梯度都正确。BC/PPO 的 sampling_rng 只核对为非空一维 uint8 张量，未调用 set_state。

## 每个部署文件

| 模型 | 字节数 | SHA256 |
|---|---:|---|
| bc_init81001 | 336900 | `8ad9e00ca045a2bd2434a2cd20b60d45d553312423034bae03622733b562f6ad` |
| ppo_init81001_ep0128 | 406752 | `699da9b80a0ed3ce83fa63b31838c82936137cb43a8f7511aafbf236e70142cb` |
| ppo_init81001_ep0256 | 406752 | `dcd3b5da8914163c6faef45a81ba4793d5bd6b39c4e2dd2ed94a3912f779a803` |
| ppo_init81001_ep0512 | 406752 | `1723fc5d854d0b9ceec42bd7c940442e39e17adabfb851a8de3a0d30c4d065fb` |
| ppo_init81001_ep1024 | 406752 | `f2dab241bd10adca9c6328bc1745904e45413400c5556209d4615b61f3ed570c` |
| q_init81001_ep0128 | 630887 | `3c6d0c1e3f73aea23604c4f387067348015ed16f4121a28f2ed7933158136ccb` |
| q_init81001_ep0256 | 637415 | `71e49504c0bd3e2644d320feb6441b4141dbc7d7595d4bcdf6c85fa09fadf8b6` |
| q_init81001_ep0512 | 650471 | `2873a2517099ab88669fd0c3198484f002ac29b2b363b35901b2717841717064` |
| q_init81001_ep1024 | 676583 | `9483208dabe02e0440583ff12b82c98be2df34710f18159f26ed78bdd54f751a` |
| bc_init81002 | 336900 | `2ef3293828bd12952de057dbde6bd612e6f519728df847b2fff84304f5127432` |
| ppo_init81002_ep0128 | 406752 | `39e9522d6fd1330a2d052c8cb1552d4970c6e77b24fef05f80b9c18ede3f530f` |
| ppo_init81002_ep0256 | 406752 | `c0e289d6a1c607eba4816361efa3f351d853808801a436a92b7d7fd0075657d4` |
| ppo_init81002_ep0512 | 406752 | `1f5e86884a827390265c611cb345d43fe4630ddebdb07727af3ceb642491793f` |
| ppo_init81002_ep1024 | 406752 | `10da5d192703cf30f0eb04f7d61cf576c12edee053f7fec8b74fdccbc46627c7` |
| q_init81002_ep0128 | 630887 | `eb07d0145ff830f874f39f086935692de1250cea7a82d3536c8e21ada54a2816` |
| q_init81002_ep0256 | 637415 | `80c0b7f09142f66768f02f7fcf144726546c22fcac696184f0d0ede22e39e408` |
| q_init81002_ep0512 | 650471 | `880cde8a357d841cd9aa8dd361fc35e42b5e961d846b6ad0c7eabb97b3c5d95b` |
| q_init81002_ep1024 | 676583 | `6294fd7cca2469a67b0688c98685561299e9b6b6e1f296d922ada0ed24c0170d` |
| bc_init81003 | 336900 | `00ee637b96c6aa05ef02a8ee4567834a86c7e8de8fa7e655788f8da18206285d` |
| ppo_init81003_ep0128 | 406752 | `e7065172ce712f7d54b9dd22c52cca1bbbfc346c9eaec0f8d482161b02ec7679` |
| ppo_init81003_ep0256 | 406752 | `7b06ea91beafbf7130351cfbff4465f4c536467365bfed44734c7fe79849f4fb` |
| ppo_init81003_ep0512 | 406752 | `35bcbb0a09f1ad6543829115ff407a383529828b1031c53c7d877075b808adcb` |
| ppo_init81003_ep1024 | 406752 | `7444aedcc0fef8fadd1fab5b663a55e8991103e6b843cd6fcaccb18929962db4` |
| q_init81003_ep0128 | 630887 | `efa2d9a46776523501b72a7725f1962eb3412c7a81bd94eb2bc66cb14781e896` |
| q_init81003_ep0256 | 637415 | `dd5cc0551ca9d400a49c6d1fbec703eedfbcadbca236afa749a0d7ac2cc30f15` |
| q_init81003_ep0512 | 650471 | `e73bc4c95ad0d9af141ed1c873956790c32202e1f86de14992d7c4d6d49e6423` |
| q_init81003_ep1024 | 676583 | `b399478c9cc39cc47ae88a28cc4c35639b8c21b13ddb02d89e745973c5997676` |

## 本次执行与证据边界

仅只读审查，耗时 87.737 秒。环境执行、业务调用、模型构造、forward、优化器更新、fixture、Git 操作均为 0；未导入求解器/环境/训练模块，未读选择结果文件。报告所用元数据、27 部署权重、6 个 resume 散列及冻结运行源码在审查结束时再次校验，未发生变化。

通过表示本报告明列的字节身份、张量状态、累计范围和结构条件一致；不代表已运行完整部署恢复、证明每个梯度正确、证实独立随机训练过程或认证策略表现。本次没有进行选择评估、最终测试或官方模拟器验证。完整逐项结果、12 组范围、3,584 个存档散列与输入文件散列见同目录 `checkpoint_review.json`。
