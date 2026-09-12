# G0/G1实现进度交接

## 最终：G0/G1 已完成，按不足 2% 门槛停止，无训练

2026-09-12 最后真实请求于 07:51:06 UTC 结算。G1 `results/g1_v1/` 的 24/24 world 完整结束，1554 执行=72 full+1482 suffix，160384 次接受调用，全部完整全清。C7/O1/O2 world 等权均值为 430.3747917042208 / 423.6641387881062 / 422.9931024287261 秒/源；有限特权改善为 1.559257894622823% / 1.7151769615186496%，均低于预登记 2%，所以不进入 G2 或网络训练。

累计 G0/G1 197456 attempts=197454accepted+2known rejected+0unknown，1696started=completed，current_run=null；无未决调用或仍在运行的 G1/worker。原始 journal 保留，完整快照在 `../../verification/rl_g0g1_final_ledger_v1/`（相对 implementation），未压缩重复文件不上传，压缩字节与原文 SHA 可复核。

主协调者已完成所有 1554 个 G1 outcome 的逐请求物理费用、全 24 world 身份、公开 uniform 抽样、全部 retained bundle、O2 真正改变的前缀/槽位、有限整数最小值与48次整局 replay独立审计：`../../verification/rl_g1_headroom_v1.json`、`../../verification/rl_g1_records_v1.json`。140 项独立审计合成测试通过；G1执行前28项实现纯测试通过。G1启动前另一子Agent只读复核通过；其最终人工全量复核因额度耗尽未完成，不冒称多方全套最终复核。

最终对外入口 `../../RL_EXECUTION_REPORT.md`、`../../RL_EXECUTION_RESULT.json`。无需重复运行或延续 G1；剩余预算不自动授权其他动作空间/训练。O1/O2不是观察可得策略，不证明所有双干预或RL均无效；Q4最新R2未同批重跑，未声称超越它。worker CPU未知为null，clone_cpu_wall_s为墙钟，不能算0。原部署/运行代码及G1 source/input档案未改。

## 最新：G0 正式接受，G1 v1 已冻结启动（2026-09-12 07:18 UTC）

协调者正式接受：`../verification/rl_g0_acceptance_v1.json`（相对RL目录），绑定independent_v2 SHA `26b1bf6f79cb60e22c0ee8af74b651a10a406e4337a8eaa7980cc6d5a65d01d6`。不可改此接受文件。G1新增`evaluator/g1.py`、`tests/test_g1.py`，共28个纯测试通过；search只读复核确认O1/O2核心语义无阻断，24唯一Q4/index0..23/12组各2、runtime/budget/g0_fixtures匹配G0 freeze。复核g1.py SHA `9806adb68dd17616b5bffd25bf29071f5b57cb3edea2a76f8b0bbe7271d4726b`。

已执行唯一启动命令：`/opt/homebrew/bin/python3.12 -S -B -m implementation.evaluator.g1 --out implementation/results/g1_v1 --g0-acceptance ../verification/rl_g0_acceptance_v1.json`，cwd=RL目录，exec session 24399。runner在第一环境调用前保存完整source/input zip与hash和纯测试结果。运行中禁止改任何implementation Python源或冻结依赖，不重跑已有ID；350000实际累计调用/2000执行/6h/零网络训练与官方限制不变。等待runner结束，再由主独立审计。成本报告必须披露worker_cpu_s为null、clone_cpu_wall_s实际是墙钟，不能声称所有CPU分项齐全。

## G0 已完成的历史状态（G1启动前）

2026-09-12 当前 G0 聚合：`results/g0_final/`，index 141 个唯一验收运行，48 C7配对、12最新Q3直通配对、21/24额外真实夹具、117检查全部通过。统一 `execution_status.json`：37072 attempted = 37070 accepted + 2 known_rejected + 0 unknown，142 started =142 completed（122full/14suffix/6fixture），current_run=null，无进程；零网络训练、零G1世界、零官方接口。

历史不删：g0_v1 在第1个originalC7完成142调用后因相对输出目录错误停；v2修out.resolve重冻，48C7配对全通过，首最新Q3对只有机器诊断counters.a1_cover_cpu_s不等而停；主独立验证后批准仅对latestQ3白名单这个perf_counter值，g0_v2_resume1复用98个已完成局（新增调用0），补11Q3对+20真实夹具。g0_partial_override_v1再补1次A6接受后接管仍b2→1且不返还。所有源字节已存各阶段sources.zip并逐项匹配freeze；v1唯一g0.py旧字节由反向单一路径修正重构，原SHA验证通过，来源明确。不得覆盖旧失败/轨迹。

冻结deploy综合SHA `342fa54ce8d9d9b27d5c715bf398302a44af376e06bc331c96aee15ed9f1b11b`，engine SHA `aa93af9926963acda3e6d9e01ec5544649316dc001773e92b8c7e1e21241babb`。当前源码不可随意改，否则已保存token失效并须重新G0。新G1代码只能新增evaluator/tests；主正在独立审计并将提供g0_accepted=true的接受JSON及被冻结journal/status快照，收到前不调用G1环境。

新增实现已真实验证：完整公开typed JSON/递归白名单、token全payload校验及clock/前缀分母断言、整体deploy+旧core依赖hash、prepared事务commit一次、worker独立进程/request_id/超时禁用、后端未知接受禁止二次调用或盲fallback、Budget互斥accepted/rejected/unknown计数与未知后阻止新run。evaluator/runtime.py私有ForkHandle整组world/token/prepared绑定、BranchClock队列不消耗前缀预算、真实clone/suffix/重放支持；prepared首步不二次prepare。21纯测试与真实G0均通过。所有命令用 `/opt/homebrew/bin/python3.12 -S -B`（系统python3是3.9缺bit_count；3.12有旧hostile.pth，-S规避，不改系统文件）。

下一步G1实现计划：新g1.py（尚未创建）。24登记Q4 probe，逐world C7 roll-in完整捕获source READY；纯索引uniform选4个（floor(k*(n-1)/(m-1))），每个retained action完整a+C7 tail含A0，按真实整局微秒选O1（包括零干预），完整重放验证请求序列/成本；O1重放capture after_intervention，真实新轨迹均匀选后续4入口，逐动作完整续局选贪心O2，再完整重放。若O1选零干预则O2零干预，不搜索协同双步，明确有限贪心类。失败分支保留+100标签惩罚；部分bundle或少于24world只报未决。所有branch start预留15846实际call，累计350k/2000/6h硬界，不进入G2。baseline与各state A0尾局应完整一致；b各分支独立扣，O2来源绝不能用原C7第二个入口。逐world保存所有结果、候选/handle、公有入口抽样列表、完整replay plan，完整集合再算world等权mean(T/N)和相对改善。G1结束不论正/负/预算未决均停。

主最新非RL冻结combined SHA08dbe1dc5018b98c3b4ac0b128953174e4067be96b22683e61b030f10087ef01；Q3父r11 SHA6c73bf90...。Q3 passthrough新模块直接返回该Solver，绝不经过C7 Engine。只写本implementation，不碰agent_experiments/parallel_v2，不自行Git。主已推送非RL d160008；breakthrough_search只读复核G0，当前所有已指出实质问题闭合。

## 以下是开始实施时的历史笔记，数字已由上节替代

授权：用户要求原方案Agent继续执行；协调者限定G0/G1，零网络训练，350000实际业务调用（含测试/失败/重复）、2000 full/suffix/真实接口夹具、6小时从2026-09-12 06:07:41 UTC起、8GiB、16GiB RSS。G0必须先过，G1完成/负结果/预算未决即停，不进入G2/final/官方/Git。只写implementation/；冻结PROPOSAL/spec/test不改。

当前：**尚未执行任何环境任务**。只运行register.py生成72个probe（G0 Q3/Q4各24，G1 Q4 24），没有实例化LocalEnv。status=implementing_g0，各计数确实0。固定证据：execution_registration.json、execution_status.json、未来execution_calls.jsonl。注册namespace bc_rpi_g0_20260912_v1/bc_rpi_g1_20260912_v1，index0..23，group_index=index%12；旧worlds.py只读加载，禁止import有写数据副作用的evaluation/generate_cases.py。

已写但未语法/单测/实际验证：deploy/vendor.py,state.py,interface.py,operations.py,worker.py,engine.py；evaluator/budget.py,register.py。evaluator/fork runner、真实G0测试/runner、G1尚未写。

实现要点：vendor以私有package加载SHA固定旧core（不改源码），controller只注入原_time_guard的clock读取；NoCalls禁止detached准备触发接口。state用带类型JSON保留dictkey/tuple/set/float.hex，全控制器与完整接口状态/clock offsets，semantic hash仅剔机器时钟。interface记录inflight和timing已结算，旧_pending_timing允许保留上一已结算dict。operations实现9规范动作和20/20x12/Lx14/32x2/Kx14公开特征，独立Python worker只收controller/engine/meta JSON，禁止truth依赖。engine显式READY_PREPARE→prepare→select→compare/commit一次→execute→finalize；partial station不移todo、失败A0不清forced，按分支独立扣槽。默认π0tail只构造A0不调用候选worker；expand才生成9动作。

待重点修/核：engine.expand生成器异常目前向外抛，合同要求记录拒绝并teacher；assert_ready未知slot目前抛，需明确teacher处理而不隐藏原值。Engine.run把RuntimeError/TimeoutError视controller recovery走fallback，所以G0必须要求零非预期recoveries而不以fallback成功掩盖bug。所有源码刚写未运行，不能称实现通过。

下一步fork：evaluator私有复制LocalEnv（所有mutableSource.cleared/seed/errorfield/账本），仅public ResumeToken给deploy。Engine.run回调先token、on_pre_ready、再prepare/on_choice；应在token时点捕获private时钟，token时点可由api.started_at+token.clock_offsets.task_elapsed_real_s重建。branch以BranchClock重建private _t0/_ready_at/_deadline与public elapsed/deadlines；restore不enter。同一PreparedChoice首动作各分支commit一次后冻结π0完整tail。可考虑将token后共同prepare墙钟以BranchClock.advance计入各branch，必须明示并由审计认可；尚未实现该细节。

Budget持久append调用start/response/exception，start每run预留15846、finish结算，所有实际env调用必须走CountedBackend。单活动run，未结算旧run拒绝重启。status每25调用及run/phase刷新；journal是逐调用依据。原始C7对照直接CountedBackend，不用新controller。真实G0=48world×2=96，额外<=48检查；每次都start/finish记费用。G1 only after G0 pass/audit；O1最多4个公开均匀source边界，完整a+C7 tail并重放；O2沿第一次干预后的真实trajectory选后续4边界，不拼原轨迹、不相加局部优势。24world或bundle不完整则未决。

协调：root负责独立审查与最终非RL封装；breakthrough_search正在只读审查已写deploy和budget/register，会直接发风险；不要再派Agent。breakthrough_geometry做图谱，已通知状态固定路径。最新Q3 A1 r11 SHA6c73bf90ac76b6e6e3d34b90883bf9acbf5e6a1443640633d29b3eb653a55cd7，组合08dbe1dc...仍在主验证中；Q3 G0暂仅C7 wrapper等价，等待主冻结最新入口。教师C7 cf378...与Q4 BEST_R2 789096...详registration，不能换锚。

已读本轮AGENTS/README/评测v1及旧engine全部328行/interface192/fallback49/worlds105/geometry/teacher_adapter。先前RL文稿与25合成测试已完整验收，不重做纸面研究或更改冻结文档。已有git脏改动是协调者/其他Agent的，不碰。
