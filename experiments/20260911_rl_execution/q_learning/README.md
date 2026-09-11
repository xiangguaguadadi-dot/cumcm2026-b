# 约束 Q：实现与本轮 G2 结果

本轮 G2 训练与检查点选择已完成（2026-09-11）。root 已实际运行 3 个 Q 初始化（81001、81002、81003），各 1024 个新增训练局，共 3072 局；共同 512 局 C7 示范只采集一次，每个初始化完成 4 遍 MC 预拟合。已保存 12 个 Q 部署检查点（各初始化的 128/256/512/1024 局位置），并完成 12×192=2304 局 Q 检查点部署评估。每题只有 96 个不同选择 world，同一批 world 被不同初始化/检查点重复使用。

**Q 两题均未达到预登记晋级门槛，保留 C7。** 选择后按同一 world 先平均三个初始化，Q3 为 244.157 秒/源，相对 C7 改善 −3.488%；Q4 为 468.386 秒/源，改善 −6.478%。相对对应 BC 的改善分别为 −0.449% 与 +0.158%。这些是本地、已暴露的检查点选择结果，不能称盲测或官方验证。

结果和核验入口：

- [选择结果与全部预登记检查点](../analysis/selection_result/REPORT.md)及[完整统计](../analysis/selection_result/selection_summary.json)。
- [27 个部署权重内部状态审查](../verification/checkpoint_review.md)：424 项检查、0 失败；12 个 Q 支持网络精确对应本初始化 BC，累计范围从共同示范与本初始化训练存档独立复算一致。
- [训练与部署完整 Q 诊断](../verification/q_diagnostics_v1/Q_DIAGNOSTICS.md)及[诊断数据](../verification/q_diagnostics_v1/q_diagnostics.json)：15 份账本、5376 份已有 Q 训练/部署存档全深读，54 组，输入提示和组内不一致均为 0。

[诊断核验与解释](../verification/q_diagnostics_v1/READOUT.md)补充支持单候选、实际探索和备用触发的交叉表；185项独立复核通过。

当前部署的 69512 次决策中，69236 次为支持集合内 Q argmax，276 次为经验范围回退，探索动作和整局兜底均为 0。teacher 候选一致 48760/69512；这不表示与 BC 在同一快照上的选择一致。本轮模型、运行时代码和数据范围保持冻结；以下 API 为实现说明，文末 G0 合成夹具记录属于训练前历史。

## 已使用的训练接口（示意）

以 `experiments/20260911_rl_execution` 为 `PYTHONPATH`，使用root准备的共享venv。原始轨迹必须来自共同core，经过root外部真值validator结束标签。不得把N放进snapshot。

```python
from shared import CandidateNetwork
from q_learning.replay import replay_from_episode
from q_learning.trainer import QTrainer

# bc.model来自ppo.trainer.BCTrainer；三种模型使用同一共享网络结构。
# 每个训练初始化可用对应BC权重作为PPO/Q共同起点，BC数据只采集一次。
q_network = CandidateNetwork(**bc.model.config)
q_network.load_state_dict(bc.model.state_dict())
q = QTrainer(q_network, bc.model, device='cpu')
q.register_training_snapshots(
    (d['snapshot'] for raw in shared_c7_demonstrations for d in raw['decisions']),
    source='shared_c7_demo'
)

# true_n只由root在该完整episode结束后取得；success由root validator判定。
replay = [replay_from_episode(raw, true_n, success=validated_success,
                             episode_id=run_id)
          for raw, true_n, validated_success, run_id in labeled_demonstrations]
mc_log = q.fit_mc(replay, epochs=4, batch_episodes=8, seed=training_shuffle_seed)
# fit_mc结束后同步target到MC初始化末状态；本轮已实际完成4遍共同示范MC预拟合。

explorer = q.make_selector(training=True, seed=exploration_rng_seed)
for training_episode_index in registered_training_indices:
    explorer.start_episode(training_episode_index)  # 0-based训练计数，不是环境seed
    raw = run_authorized_registered_episode(selector=explorer)  # root拥有采集与预算
    item = replay_from_episode(raw, root_true_n, success=root_success,
                               episode_id=root_run_id)
    replay_buffer.append(item)
    q.register_training_snapshots(
        (d['snapshot'] for d in raw['decisions']), source='q_training'
    )  # only this run's newly executed training observations; each episode once
    # root从buffer按完整episode均匀抽样，批大小8；不是按transition长短重采样。
    td_log = q.update(root_uniform_episode_batch, kind='td')

# 固定权重、行为门控和训练数据范围；绝不把TrainingExplorer用于部署。
deploy_selector = q.make_selector(training=False)
frozen_checkpoint = q.checkpoint()  # CPU独立副本，继续训练不会改写此对象。
restored = QTrainer.from_checkpoint(frozen_checkpoint, device='cpu')
```

`fit_td(episodes, epochs=1, batch_episodes=8, seed=...)`是离线批处理便利入口；在线runner可直接调用`update(episode_batch, kind='td')`。返回loss、episode/transition数量、optimizer step、梯度范数和累计更新数，root逐批保存。根级runner负责实际训练轮数、checkpoint节点、预算、真实评测和模型选择，不由本模块隐式采样。

本轮共享BC按root已固定的批8/每次update一轮/512示范8遍历执行；Q的MC额外预拟合成本单列，不能称共同BC免费工作。MC标签评价采集行为的后续成本，不等于最优Q或新部署策略价值。

## 轨迹与费用合同

`replay_from_episode(raw, true_source_count, success=...)`接收root协议：

- `decisions`: 每项含原始不可变`snapshot`、`index`、`delta_time_s`，可带`candidate_id`；快照完整保存candidate IDs/payload、route_successor、生成/状态版本、有效mask及teacher_index。
- `prefix_time_s`：第一次选择前的成本，保留在完整账本，不计为未来Q回报。
- `tail_time_s`：最后学习宏动作之后、与decision成本不重叠的完整备用尾段。
- `total_time_s`或`virtual_time_s`：必须等于prefix+Σdecision delta+tail，容差1e−5秒；不一致即拒绝，防双计/漏计。
- `terminal`只允许真实完整终端编码；`paused/truncated/incomplete`必须恢复后再入库。`success`是真值validator的终局布尔值。

最后transition将尾段成本折入一次，d=1、next_snapshot=None，不bootstrap。其余transition使用记录中的下一个完整snapshot，不重新生成候选。没有学习决策的纯备用局不造人工动作、logprob或Q样本；仍保存完整费用和失败记录。

T0=1000、γ=1，r=−真实宏动作费用/(1000N)；实际失败仅终端一次额外−100。MC及TD同单位，N不再进入其他权重。真实N接受1–16以容纳预登记课程，正式采集分布仍由root严格保持10–16及Q4混合类型。有限失败罚分不是词典序零失败保证。

## 网络、支持与探索

`CandidateNetwork`和`batch_snapshots`直接使用root的shared.py。所有网络调用只白名单取global/channel/candidate特征和valid_mask；teacher_index是BC标签/支持锚点，未进入网络；真N和归一reward从不传网络。Q使用score head，state-value head未参与损失；checkpoint保留共享`architecture_record()`的总参数、候选路径和额外未用head参数。target和冻结BC支持模型是额外训练/部署内存，不能从容量报告省掉。

行为门控κ=.1：合法候选中保留qβ≥κ·max qβ，并强保留当前合法teacher。它是经验支持代理，不是置信集/MI/安全证书。部署遇到训练特征范围之外、非有限Q/行为分数或无有效支持时选teacher；teacher不合法时选共同fallback候选。范围按看选择集前预定的累计规则更新：每个checkpoint只使用共享C7示范及该Q初始化已经实际执行的训练快照。`register_training_snapshots`显式登记新增快照，保存来源、数量和范围版本，并同步已创建的部署selector和训练explorer；传`source=selection`等其他值即拒绝。调用者仍须保证所传数据确属该split，字符串标签不证明数据来源。推理过程中不自动扩范围，选择/回归/最终评测永不登记。范围只是逐字段经验检查，不是联合支持、置信度或几何支持保证。G2开始前固定版本`training_extrema_v2_clocks_physical_only`：仅`global_features[6]=elapsed_real_1200`和`[14]=remaining_real_1200`跳过经验min/max，因为策略推理开销和机器负载本身会改变这两个时钟，旧1e−6范围容差仅约1.2毫秒，不能把这种差异解释为几何OOD。两项仍保留在共同网络输入与独立硬期限守卫；门控只要求有限且在[0,1]内，固定允许1e−6数值量。训练时仍记录其经验极值供审计，永不据此拒绝。其余14个global维度以及channel/candidate所有维度保持原经验规则，未经选择集扩界。每次选择的`clock_feature_checks`单独保存字段名、当前值、物理合法性、记录用训练极值、skip原因；无效时钟以`invalid_physical_clock_range`单列，不能当几何OOD。模型可能仍因其他经验范围触发teacher，需要在真实评估报告接管率与分字段原因。越界metadata记录字段名、训练最小/最大值、当前最小/最大值、越界行数和范围版本。

`TrainingExplorer.start_episode(i)`明确开始训练局。前128局80% teacher、20%其余合法候选均匀，每局最多8次偏离；之后90%使用与部署完全相同的范围/teacher/支持Q规则，10%其余合法候选。只有显式ε分支能越过经验范围去探索，所有动作仍受共同core守卫约束。全部耗费来自本算法/初始化的新增额度，模型、随机流不会在selector内产生新world。metadata保存实际混合概率、探索标记和偏离数。它不是PPO on-policy样本来源，也不能用于正式部署。

TD与部署复用`choose_q_action`：next快照未拟合范围或越界时选合法teacher/备用；范围内按冻结BC支持集合做在线Q argmax，非有限支持/所需Q值同样退teacher/备用。target网络只评价这个已保存的候选位置，选中target值非有限则报训练错误，不伪造零值。真终端完全不读取next或网络。因经验范围随已执行训练数据扩展，TD目标策略也跟随该训练时范围版本；冻结checkpoint同时冻结对应范围，保存并检查gate v2与next-action v2；旧无版本或v1检查点拒绝加载，不隐式迁移。 两处动作一致性的合同限于合法有限快照及网络forward能返回分数；部署可在范围检查后跳过网络，而TD还需要target估值。若快照畸形或模型forward直接抛错，训练明确中止，不能据部署teacher回退伪造target值。独立作者已只读核验这些分支，未额外执行world或训练。episode均匀、episode内残差求和，microbatch梯度累积不改变权重。Adam3e−4、target τ=.01、梯度上限.5、microbatch128为明示初始配置；无GRU、IDS、世界模型、优先重放或隐藏参数搜索。

## 历史 G0 合成检查与实现边界（训练前）

共享venv命令：

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/t/Documents/Codex/2026-09-10/new-chat/work/rl_execution_runtime/venv/bin/python -m unittest discover -s tests -p 'test_q*.py' -v
```

最后一次：22/22通过，unittest报告0.443秒；这是合成检查时间，不是策略推理或训练吞吐。先前分别运行16数学和6张量、严格终端解析后复跑22项，部署/TD一致性修复后复跑22项，本次预G2时钟门控v2再复跑同22项，累计88个fixture执行；独特夹具22、任务world0、primitive0。张量夹具累计12次合成optimizer step，不是实际任务策略训练。详见validation_g0.json。

时钟v2继续扩展原有夹具，覆盖合法时钟偏移不触发经验回退、两维[0,1]端点与固定1e−6容差、非法/NaN/Inf时钟拒绝、其他14个global维度仍保留min/max、网络张量仍含原时钟值、TD与部署动作一致、旧gate版本拒绝。独特夹具数未增加。

扩展既有夹具确认范围外next选teacher、范围扩展后online选/target评同一候选、非有限online退teacher但非有限target拒绝、已有explorer同步、逐字段原因与checkpoint范围往返。

覆盖：N10/16符号回报、失败一次、真终端不读next、next顺序/在线选择target评价、空mask报错、支持端点、完整payload深拷贝、尾账本/前缀、人工暂停拒绝、共同网络白名单、冻结支持/target、microbatch等权、checkpoint快照和训练探索上限。

独立核读PPO returns/trainer已确认共同目标、sampled决策过滤与episode actor权重；发现并由PPO作者修复了checkpoint live-tensor别名。Q也据对照强化了人工暂停字符串、N范围和输入类型检查。以上 G0 实现子任务当时未执行实际采集、旧回归quick/full或新选择评估。后续本轮真实训练与选择已由root统一运行并登记，当前结果见本文顶部；此处的world0仅指该历史合成检查范围。接口包装/候选正确性属于core的G0责任，本模块不把22合成通过称全系统通过。历史固定集仍仅暴露回归，正式Windows网络未验。
