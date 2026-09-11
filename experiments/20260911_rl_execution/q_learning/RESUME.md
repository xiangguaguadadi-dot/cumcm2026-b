# 当前状态：G2 与检查点选择已完成，Q 两题均未晋级

更新于 2026-09-11。不要依据下方历史 G0/G1 待办重复启动采样、训练或测试。root 已实际运行 Q 的 3 个初始化（81001、81002、81003），每个 1024 个新增训练局，共 3072 局；共享 C7 示范为共同的 512 局，每个初始化 Q 另做 4 遍 MC 预拟合。3×4=12 个 Q 部署检查点已全部保存，并完成 12×192=2304 局选择部署。每题仍只有 96 个不同 world。

本轮 Q3 选择后均值 244.157 秒/源，相对 C7 改善 −3.488%、相对对应 BC −0.449%；Q4 468.386 秒/源，相对 C7 −6.478%、相对 BC +0.158%。两题均未达到预登记晋级门槛，保留 C7；没有执行新的最终盲测或官方模拟器评测。选择均值存在检查点选择偏差，不将多个初始化对同一 world 的重复执行当独立样本。

已经完成的审查与诊断：

- [selection_result/REPORT.md](../analysis/selection_result/REPORT.md)：全部检查点、配对统计与晋级门槛；[JSON](../analysis/selection_result/selection_summary.json)保留完整行级配对。
- [checkpoint_review.md](../verification/checkpoint_review.md)及[JSON](../verification/checkpoint_review.json)：27 个部署权重（3BC+12PPO+12Q）内部审查424项、0失败。全部身份/SHA/配置一致；12个Q支持网络对应同init BC，全部范围和history与3584份示范/训练存档独立复算相同。该审查仅加载保存张量，不做forward或恢复训练。
- [Q_DIAGNOSTICS.md](../verification/q_diagnostics_v1/Q_DIAGNOSTICS.md)及[JSON](../verification/q_diagnostics_v1/q_diagnostics.json)：实际运行 `--phase both` 全深读；15账本、5376存档、54组，无输入提示或组内不一致，诊断耗时78.596秒，0world/0模型推理/0训练。部署69512决策中69236为支持Q argmax、276经验范围回退、探索0、整局fallback0；teacher一致48760/69512。训练有8854/80474探索动作、1177/3072局兜底；与冻结部署须分开解释。

[诊断核验与解释](../verification/q_diagnostics_v1/READOUT.md)及[交叉核对JSON](../verification/q_diagnostics_v1/validation_and_readout.json)已完成：对同一5376存档的第二次只读语义复核185项通过，没有新world。部署28632次支持集合仅含teacher；20752次在多个支持候选中选非teacher。训练1177次接管的最后动作全部是显式探索选fallback，这是即时触发记录，不能推断取消探索后训练表现。

模型、共享运行时和范围版本保持冻结。允许的后续工作仅按root新的明确分派执行；本段以下均为历史实现记录，其“0真实训练”指实现作者当时执行范围，不代表本轮没有训练。历史22个独特夹具、累计88次执行和12次合成Adam步骤保留为G0账本，不能替代本轮实际训练预算。

---

# 历史 G0：G2前时钟门控v2已实施并通过原22夹具

root新任务明确修global[6]elapsed_real、[14]remaining_real：保留网络/硬时限，只跳过这两维经验minmax，改为finite+[0,1]固定1e-6物理检查。当前已实现policy.FeatureBounds.violations与metadata；每选择clock_feature_checks含current/finite/physicalvalid/skipreason。其余所有维度经验门控不动。gate contract training_extrema_v2_clocks_physical_only；checkpoint/from_dict明确保存并要求版本，旧v1/无version拒绝，不隐式迁移。Q TD与deployment继续同helper。

原22夹具已扩并通过0.443s（时钟合法偏移/两维端点容差/非法NaNInf/其他14global仍gate/tensor时钟保留/TD相同动作/版本），独特22，累计执行88、合成Adam12，实际world0/primitive0/训练0（本agent）。根已收到完成信息；audit正静态复核，收到后把review记入validation。README/ledger已同步。不要把下文旧0.433s/66/9计数当最新。

# 历史 G0：约束Q实现；部署与TD一致性修订已完成

2026-09-11当前窗口01a0900f-0271-7a53-919a-08f4a9766e2d。下文旧状态保留细节，但其中“待修”均已按本段实现，不要重做。

最新：q_learning/policy.py提取choose_q_action及range_guard；QTrainer._next_values同deployment选择：未fit/越界→teacher或fallback，范围内支持onlineargmax，nonfinite所需online/support→teacher，target只评价其保存位置且nonfinite报错。真实terminal不看next。TrainingExplorer base策略始终enforce_bounds=True，只有epsilon选择其他合法动作。FeatureBounds.extend/violations含schema字段名、当前/训练extrema、count/revision；register_training_snapshots(source shared_c7_demo|q_training)显式合并训练观察并同步trainer已创建selectors。checkpoint保存范围/history/next_action_contract；旧无contract检查点拒绝加载，该历史时点尚无真实训练checkpoint；现已完成12份Q部署checkpoint，见本文顶部。

22个既有合成fixture扩展验证上述规则，全部通过0.433s；独特22、累计执行66、合成Adam9、真实world0/primitive0/tasktrain0。README API现要求示范初始化显式register，每实际Q训练局终止后仅一次register该局snapshots，再TD update。selection绝不注册。当时root正在G1；现已完成G2，勿据此重复启动。

audit只读复核已完成，无阻断：合法有限snapshot且forward返回score时deploy与TD规则一致，terminal/target非finite和existingexplorer同步均正确；实际split来源仍root负责。root已收到完成信息，README/validation/本RESUME全部同步。该历史时点Q G0交付完成，曾等待统一G1/G2 runner；现有3个Q训练初始化均已由root完成。

# 历史 G0：约束Q实现与独立目标/终端审计

2026-09-11，当前窗口01a08fcd-e2df-7162-a56b-6142a1102391。root新任务明确用户已授权3子Agent执行：实现Q路线而非旧C研究；旧E1/E2/E3与RL研究都已结束，不再恢复其resume。本任务只写 q_learning/ 与 tests/test_q*.py。root管shared/runtime/data/runners/budget/Git，geometry管core，audit管ppo/BC；不自行安装或Git。新EXECUTION_PROTOCOL已全文读，AGENTS/README/冻结指标及最终研究方案已读。G0/G1 root放行前不做真实采样/训练。到当前真实world0、primitive0、任务策略训练0。

## 已实现与实测

目录绝对路径 /Users/t/ai project/数学建模2026/代码/experiments/20260911_rl_execution。
共享venv /Users/t/Documents/Codex/2026-09-10/new-chat/work/rl_execution_runtime/venv/bin/python，root已装torch2.8.0/numpy2.2.6。不要另装。

- q_learning/math.py：N(1..16兼容课程)仅标签；T0=1000/gamma1；fail终端一次-100；MC；masksoftmax/behavior_support与DoubleQtarget。真terminal不读next。
- replay.py：FrozenSnapshot JSON深拷贝整payload、候选ID/mask/teacher/散列；ReplayEpisode/Transition。replay_from_episode(raw,N,success=外部validator)严格拒paused/truncated/incomplete，raw总时间=prefix+Σmacro delta+tail；尾折入最后transition d1不bootstrap不双计；prefix不计未来Q；无学习决策不造动作。
- policy.py：FeatureBounds(当前只fit训练范围/contains)、QSelector(sharedmodel+BCsupport)、safe_teacher_choice、TrainingExplorer。早期128局80%teacher/20%合法替代最多8次偏离，之后90%支持Q/10%替代；训练专用，start_episode(i)。**历史待办，已在后续一致性修订中完成；勿重做。**
- trainer.py：QTrainer(shared CandidateNetwork, bc_model,..), fit_mc/fit_td/update/targets，microbatch按episode等权内部残差和；frozen支持与target；fit_mc结束sync_target；checkpoint独立CPU clone+optimizerdeepcopy/单位校验/architecture unused statevaluehead报告。**历史待办：_next_values已完成后续修订；勿重做。**
- __init__.py只导出纯Pythonmath/replay，torch用from q_learning.trainer import QTrainer。
- README.md已给root训练API、预算/区别/未实测限制；validation_g0.json记录sourceSHA及实测。该历史时点README曾写固定512/训练关闭bounds；这些表述已在后续修订中替换，当前采用累计训练范围且基础Q执行门控。

测试 tests/test_q_math.py16 + test_q_torch.py6 =22个独特合成夹具，root已批准22份额。已运行：math16(0.001s)、torch6(0.549s)、严格terminal等修复后22总(0.447s)全部通过。累计44fixture执行、6个合成optimizer step，不是任务训练；0world/primitive。以后复跑同夹具不增加定义数，但记运行次数。
命令：PYTHONDONTWRITEBYTECODE=1 <venv>/bin/python -m unittest discover -s tests -p 'test_q*.py' -v (cwd=execution)。
root调账最终audit16+Q22+shared5+core≤37=≤80；不要加新fixture名字，扩现有测试可。

## 共同API已定

root shared.py：CandidateNetwork(global_dim16,candidate_dim16,channel_dim12,hidden_dim64).forward(global_features,candidate_features,mask,channel_features=None)->(scores[B,K],values[B])；batch_snapshots(snapshots,device)白名单4tensor，model(**batch)。Q不用statevaluehead但architecture_record保留total/path/unusedhead。
core/schema.py已落，G16/C12(20channels)/F16/K≤64，特征名常量可读。snapshot含schema_version,generator_version,decision_id,state_version,global_features,channel_features,candidate_features,valid_mask,candidate_ids,teacher_index,candidates。候选payloadkind/index或channel/target/route_successor/stage/service_state等。teacher仅BC/门控元数据不入feature。selector(snapshot)->int或{index,metadata}。
core raw episode：prefix_time_s+sum(decision.delta_time_s)+tail_time_s=total_time_s；tail只fallback不与macro重合；terminal/success由root终局validator最后给训练器；N不在snapshot，root参数传入。待core/runner正式跑，不能自己采样。

PPO作者给公共BC：BCTrainer(共享网络).update(raw完整C7episodes)，只用完整快照/index，确认teacher；root已固定批8/每批1epoch/512示范8遍历=512Adam/init。建议3独立BC初始对应PPO/Q共同起点；数据不重复采。Q额外MC4遍历初始配置README给出，root最终负责训练预算/epoch。

## root要求修订（本节原计划已完成，见最前最新状态）

root最新核读发现：QSelector部署bounds越界选teacher，而_next_values总argmax支持Q；trainingexplorer创建时enforce_bounds=False，TD bootstrap未对应部署策略。root明确首选修成同一规则target，且仅fit512C7的bounds可能因elapsed_real/计数等让Q几乎总退teacher。必须在看选择集前预定范围更新：每checkpoint范围=共享示范+该路线已实际执行训练snapshots，仍只是经验数值范围，不能选择集扩张。
我已答应root以下方案，下一步直接落实：
1. 提取共同policy选择函数（或复用QSelector规则）让TD next动作和部署一致：bounds未fit/越界→合法teacher或fallback；范围内支持/online非finite→相同teacher保护；其他按κ支持argmax。最后用target网络评价此同一保存候选位置。真terminal仍不读next。target值非finite仍训练失败，不能invent0。
2. TrainingExplorer的90%基础Q也执行bounds合同；仅登记的epsilon分支能采范围外合法动作（offpolicy数据受coreguard）。make_selector(training=True)不再关闭bounds。
3. FeatureBounds增加extend/merge与逐字段explain/violations（用core/schema.py名字或稳定group[index]），metadata统计越界field、观测range、训练range；这是范围原因，非置信度。
4. QTrainer.register_training_snapshots(snapshots)显式合并已发生的训练可观察快照，记录范围revision/样本数，并同步已创建explorer内QSelector范围。root每次加入训练数据/冻结checkpoint前调用，绝不对选择集调用；checkpoint保存范围。可通过维护trainer._selectors列表同步其feature_bounds，勿让旧explorer永远指向旧bounds。
5. 扩现有torch fixture test_torch_double_q...验证next越界时teacher代替argmax；范围内仍onlineargmax/target评值；test_selector...验证逐field原因和rangeextend后匹配；不增夹具定义。测试后更新README/validation/RESUME，报root完成。

我刚给root消息的原意：同意同策略target，TD复用bounds/teacher/fallback/非finite支持规则；训练90%base同规则仅ε合法探索；register_training_snapshots按预定训练数据更新，已有explorer同步；metadata按feature聚合原因。无需再问permission。

## 独立交叉审计与修复

已静态全文读ppo/returns.py及trainer.py，确认MC单位、失败一次、fallbackcost、sampled行过滤、episode actor求和与oldlogprob/version校验。发现PPOcheckpoint state_dict别名live张量，已告audit，audit已修为CPU clone/deepcopy并用已有fixture验证。对照其严格_terminal修了Q对paused等字符串原先误接受问题；N范围/成本bool/label单位也强化。没有额外策略执行。后续可继续审核root数据runner接入，但先完成上节修正。

历史时点root尚在编写registry/通用runner，G0/G1未放行；当时本实现子任务保持零真实采样。当前G2已完成，见顶部。源码修改使用exec_command require_escalated精确写自己目录经正常审核，网络/安装/Git都由root。
