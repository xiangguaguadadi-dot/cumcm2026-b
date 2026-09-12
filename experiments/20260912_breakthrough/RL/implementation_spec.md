# BC-RPI 实现合同 v2

日期：2026-09-12。**待验收实施规范；下列模块和训练命令尚未实现/运行。** 实际已存在的文件仅为研究文档、来源获取/源码阅读辅助脚本与合成合同检查。本文优先级：用户范围与 [本轮协议](../PROTOCOL.md) > 本文 > 旧 RL 实现惯例。

## A. 设计冻结与只读依赖

1. 机制锚固定 `experiments/20260911_stage4/combination/geometry_fusions/C7_both.py`，SHA256 `cf37866829b9c6f376895075e819a732939e6fa8ad6d8d6297a151d7a213dcb3`。
2. `local_env.py`、v1 manifest/数据/规则、主目录 `solver.py` 和原 C7 不改。新工程未来放入独立 `RL/implementation/`；不直接覆写 `20260911_rl_execution/core/`。
3. 复用已有 `MeteredInterface`、`GuardConfig`、独立 fallback、几何工具时记录文件内容 hash。复制/拆分 engine 的外层循环以暴露可恢复边界，须写明来源与差异。
4. `teacher_anchor` 与 `best_at_execution` 分开冻结。后者来自协调者本轮最终登记，并须实际重跑同批对照。换 anchor 不是改一个路径：重新检查继承链、配置、状态结构、控制器 patch 和 G0 全等价。
5. Q3 部署直接加载执行时最新非 RL 最佳 Q3 入口；BC-RPI 禁止改变其请求序列。教师包装的 Q3 检查只用于共同接口兼容，不代表使用旧 Q3 替换新最佳。

## B. 精确决策时钟和状态机

### B1. 唯一允许决策的位置

现有 engine 在每次 source/localize 或 station/scan 完整返回后，维护 `todo`、进展和宏账本，然后再执行 `_teacher_task`。新入口保留这个边界：

```text
READY
  -> CHECK_GUARD
  -> PREPARE_TEACHER_ON_COPY
  -> SELECT_RETAINED_OPERATION_ON_PREPARED_SNAPSHOT
  -> COMPARE_AND_COMMIT_COMMON_PATCH_EXACTLY_ONCE
  -> EXECUTE_OPERATION_TO_RETURN_OR_TAKEOVER
  -> FINALIZE_COST_AND_PROGRESS
  -> READY / FALLBACK / EXIT
```

禁止：在 `localize` 嵌套循环、`rescue_bearing`、`cover_polygon`、near 自动 clear、`share_observations` 内暂停后恢复 Python 栈。整个教师服务仍是不可学习拆分的一个宏操作，内部 guard 可以因预算接管，这与原实现一致。

宏时刻 n 是 READY 的次数，不是付费请求数，也不是物理秒。宏成本为实际接受的 `measure/clear` 事件之和；宏内多请求的持续时间不等长。训练不按 n 折扣（γ=1）。新 operation 返回后重新运行全局 C7 调度，其未来选择取决于新真实观测，因此它不是原任务排序器的另一组权重。

### B2. ResumeToken 与恢复合同

在 READY 且无活动调用栈时才允许创建：

```python
@dataclass(frozen=True)
class ResumeToken:
    schema: Literal['bc-rpi-engine-state-v1']
    boundary_phase: Literal['READY_PREPARE']
    teacher_sha256: str
    engine_sha256: str
    generator_sha256: str
    controller_public_state: dict
    interface_public_state: dict
    clock_offsets: dict
    todo: tuple[int, ...]
    visited: tuple[int, ...]
    no_progress: int
    previous_macro_seconds: float
    decision_counter: int
    last_committed_choice_id: str | None
    interventions_remaining: int
    forced_teacher_channels: tuple[int, ...]
    used_operation_ids: tuple[str, ...]
    accepted_event_count: int
    prefix_virtual_us: int
    public_ledger_digest: str
    # evaluator stores private backend handle in a separate object, never here
```

`controller_public_state` 包括 C7 全部非 env/时钟 callable 状态：位置、当前测量频道、observations、no_signal_points、polygons、scanned、cleared、counters、points、config、`_e2_progress`、`_e2_failed_clear`、visibility cache、route successor、sharing spent、递归锁等。原始 trace 可改为内容寻址前缀引用，但回放语义必须一致。禁止仅保存几个特征再凭猜测重建控制器。

`interface_public_state` 按冻结MeteredInterface完整白名单保存：guard配置和hash、position、channel、virtual_time及整数微秒对账值、events或不可变前缀引用、cleared、positive_observations、started、exited、phase、takeover_reason、learning_requests、exit_certificate、accounting_max_error_s、`_pending_timing`的已结算值，以及新增instrumentation的`timing_settled_through_event_count`和`inflight_request`。不保存`_enter/_measure/_clear/_exit`绑定方法、backend引用或clock callable；这些由可信执行器重绑。不能只恢复accepted_event_count后把learning_requests、phase或takeover_reason初始化回0/learning/None。

`clock_offsets` 明确包含 `task_elapsed_real_s`（至fork前缀已用）、`interface_deadline_remaining_s`、`controller_deadline_remaining_s`（可能比接口早5秒）、`last_response_age_real_s`。用分支起始单调时间now重建 `started_at=now-task_elapsed_real_s`、接口/solver `deadline=now+对应remaining`、`_last_response_at=now-last_response_age_real_s`；不能重置为1200秒。backend私有`_t0/_ready_at/_deadline`由evaluator在同一坐标系重建，不进入actor。控制器原绝对deadline字段序列化时转成上述offset，不与过期绝对数值混用。

READY前置断言：`boundary_phase=READY_PREPARE`、尚未本轮prepare/commit，`_active_target is None`、`_sharing is False`，接口已started未exited、phase=learning且无takeover_reason，`inflight_request is None`，timing已结算到accepted_event_count，API与solver位置/频道/微秒账本/cleared一致。`_pending_timing`在旧wrapper中可能仍保留上一已结算请求的时长dict，不要求它为空；要求该值已对应记入最后事件，不能有尚未落账的调用。否则不创建token、不介入，按异常/guard处理。

恢复时从相同 frozen class 构造不发接口请求的控制器容器，填入完整公开状态；backend 的恢复只在 evaluator 处理。不能再次 `enter`，不能重置位置/清除/虚拟时间/任务截止时间。新的 `resume_loop(token, api)` 只继续 engine 外循环，不是调用原 `Solver.run()`。未知字段、hash 不匹配、未结算事件均拒绝恢复。

### B3. controller_patch 的统一承接

`_teacher_task` 会改变 route successor 和派生计数/缓存，因此：

1. 在深拷贝公开控制器 `s_copy` 上计算一次 teacher task、后继和 patch；生成过程不调用任何接口。
2. 将 patch 应用于另一个临时公开状态，形成 `prepared_state_hash`；候选全部基于这个相同状态生成。
3. 选择器只看 detached snapshot。执行前校验 live state 的 pre-prepare hash，再提交同一 common patch。
4. 所有 a 分支与 reference 分支从相同 prepared state 起步。不能只给 teacher 原始优化 successor，而替代操作接另一个任意后继。
5. 完成 operation 后，自然进入下一 READY；下一次 teacher routing 会重新计算 route successor。新动作不能提前把虚构 source/point 标作已服务。

唯一顺序是 **prepare detached→选择retained→校验live pre-hash→commit恰一次→execute**，station也走同样顺序。`PreparedChoice`保存 `choice_id, pre_state_hash, prepared_state_hash, teacher_task, common_patch, retained_payloads, public_snapshot`；choice_id绑定本轮decision_counter及pre_state_hash。commit事务校验pre-hash和`last_committed_choice_id`，应用patch、记录choice_id并推进decision_counter；不执行网络或请求。即使patch为空，第二次commit也必须拒绝。

fork只保存/恢复**prepare前**的ResumeToken。每个branch拿同一个已计算PreparedChoice，在自己的pre状态验证并提交一次，然后执行各自保留的首动作；不能在branch内部再次调用`_teacher_task`为首动作重新prepare。首operation完整finalize后才允许进入下一READY并由冻结π_j正常prepare。禁止把prepared控制器当pre-token恢复后二次patch；`boundary_phase`或hash不合即拒绝分支。

未介入 `teacher0` 必须等价原 C7：请求坐标/频道/动作、公开响应语义、源清除、scanned、所有费用逐项相同；只排除真实时间戳与现实剩余时间这两类机器时钟字段。计数差异若仅来自 instrumentation 要白名单化，不能掩盖控制器状态差异。

## C. 动作定义：只在 Q4 source-service 入口

### C1. Eligibility

以下全部成立才给网络非 teacher 选项：

- mode=4；本轮 teacher task 是 source ch；ch 已有正 bearing 且未清除。
- 冻结配置和依赖 hash 正确，原配置 `e2_same_here=False`；不能为兼容另一版教师而偷偷改配置。
- READY 不在嵌套服务；b>0；该频道不在强制 teacher 集。
- 可靠 polygon 非空、有限；原 C7/guard 未进入 fallback；操作端点满足 [-4000,4000]²。
- 全部必需公开字段可编码；不存在未完成业务请求；候选构建没有异常。

否则直接 teacher，不调用网络。未知 slot/schema、必需字段缺失、非有限输入、候选生成异常或模型输出不属于 retained 集时，记录拒绝原因并执行 teacher；如果 API 是否已接受请求不确定或 solver/API 状态不一致，则不能盲目重复 teacher，保留 unknown_cost 并交给独立 guard/现有接管。候选不提供 `exit` 或 `fallback` 给学习器探索，后者完全由独立 guard 决定，避免旧 Q 训练中随机选择高费用 fallback 的机制。

### C2. 九个有限选项

令 c,r 为原保守 polygon 的 enclosing circle；p 为当前狗位置；(p_l,θ_l) 是主动频道最近正 bearing；u=(cosθ_l,sinθ_l)，v=(-sinθ_l,cosθ_l)。令 `ell=min(120,max(25,0.15*r))`。

|ID|操作|目标与构造|特别规则|
|---|---|---|---|
|A0|teacher_service|执行原 `s.localize(ch)`|不消耗槽位；总成本未知，不能用中心距离当真实宏成本|
|A1|clear_center|c|只在 r≤300m 开放；若全 polygon 已被20m覆盖才 certified=True，否则合法试清|
|A2|clear_nearest_cover_cell|原 `s.optical_points(ch)` 中离 p 最近的点|只在 r≤300m；几何构造保留所有可靠覆盖点，不借 true source 挑点；certified 标志单独检查|
|A3|measure_center|c|若等于该频道既往确定测量位置则不提供此额外候选；teacher 不受此去重约束|
|A4|measure_second|在 detached controller 调用原 `second_point(ch)`|计算缓存/副作用不提交到 live；若候选本身不合法则删此项|
|A5|measure_mirror|将 A4 点沿通过 p_l、方向 u 的直线作镜像|q'=p_l+dot(q-p_l,u)u-dot(q-p_l,v)v|
|A6|measure_midpoint|0.5(p+p_l)|不是“保证可见”的点：p 可能不可见；只作为有代价候选|
|A7|measure_left|c+ell*v|保留±落点；不能先用 hidden visibility 挑一侧|
|A8|measure_right|c-ell*v|同上|

所有候选按完整 payload 的规范 JSON SHA256 排序；教师 ID 另存，不能把 teacher 固定放 index=0 当隐式标签。清除与测量即便坐标相同也不是同一动作。替代操作坐标规范化为 `Decimal(str(float(q))).quantize(Decimal('0.0000001'), rounding=ROUND_HALF_EVEN)`（米），负零统一为正零；执行器使用这个规范坐标，随后重新检查合法性和certified覆盖，不能沿用舍入前的证书。去重key为 `(kind, channel, canonical_x, canonical_y)`，合并生成来源标签并按标签排序，物理字段不得冲突。payload以UTF-8、sort_keys=True、separators=(',',':')、allow_nan=False序列化后hash；十进制坐标为固定7位字符串。A0不按此规则舍入或去重，原localize内部坐标/请求不变。其他几何容差与C7一致，world ID不参与去重。

候选 payload：`kind, channel, target, certified_before_action, prepared_state_hash, controller_patch_hash, route_successor, operation_implementation_sha256, next_boundary='READY', budget_cost_slots, generator_version`。teacher payload 含完整 `service_state` 与原 localize hash。任何选择只引用 retained payload，不能接受 actor 回传的新坐标。

### C3. Operation 执行与附加动作

`teacher_service` 直接 `s.localize(ch)`，不插入任何网络 hook。

替代操作调用正常 `s.measure(q,ch)` 或 `s.clear(q,ch,certified=...)`，保持 C7 的真实观测更新路径；不绕开它直接操作 api 后漏更几何。执行时 `_active_target=None`，所以新的外部 measure 不触发 `_OpportunitySensing` 的服务内共享。当前 Q4 的正常 measure 是 1 条请求；near 额外触发 1 条 clear；e2_same_here=False 时 clear 本身不连清。**这是待 G0 用真实事件验证的源码合同，不是所有 solver 的一般性质。** 实际 `event_range` 才是费用依据；若实测附加请求超合同，登记失败并停止升级，不假装它们免费。

不递增 `_e2_progress`：它代表原 C7 已做的服务轮次，不是任意测量次数。不手工写入 cleared；只承认实际 clear success。不把原始 no_signal 当无源，不删未经证明的站点。

每个替代操作先将 b 减 1，再执行。若异常发生在已接受请求后，槽位不返还；保留最后事件并走已有接管，不能回滚物理副作用。若 operation 没有新正观测、清除或 polygon 收紧，则把 ch 加入 `forced_teacher_channels`；下次该频道 source-service 必须执行 A0，成功返回后移除该 forced 标志。即便 no_signal 是新的观察，也不因此无限重试：b 不可增加，最多 2 次替换。

## D. 在线输入 schema 与网络

### D1. 坐标和历史

坐标变换：x'=R(-θ_first)(x-p)/1800。θ_first 为主动频道首个已接受正 bearing；角度输入为相对 θ_first 的 sin/cos。目标圆中心、计划后继、其他频道区域中心同样变换。单位比例固定，不从测试极值拟合；不将未知 true emitter orientation 代入。

频道置换只保留“当前测量频道/主动频道/各频道账本”的对应关系；绝对频道数字、world ID、场景标签都不进网络。bearing 保留实际报告值，可靠几何角容差仍为 1.005001°；同址固定误差不按独立噪声平均。

actor 不输入真实墙钟，避免机器负载直接改变策略评分；real remaining 只由 guard 使用。虚拟已用时间是合法输入。数据视图采用字段白名单，独立进程接收 JSON，不传 env/controller 对象、callable、文件路径或 pickle。

### D2. 精确张量

1. `global[20]`，顺序：已用虚拟时间/360000、前宏时间/10000、已清数/20、已发现数/20、未知频道数/20、剩余站数/49、b/2、主动频道是否当前测频、e2_progress/9、主动频道强制teacher标志、目标圆心相对xy、计划后继相对xy、has_successor、主动poly半径/1800、面积/(π1800²)、主动poly中心相对xy、候选数/9。
2. `channels[20,12]`：cleared、has_positive、positive_count/64、no_signal_count/64、failed_clear_count/64、scanned_fraction、中心相对xy、半径/1800、面积/(π1800²)、is_active、is_current_frequency。共享编码后做集合池化。
3. `active_events[L≤128,14]`：事件类型one-hot5（direction/near/no_signal/clear_fail/clear_success），位置xy，bearing sin/cos，has_bearing，event_age/10000，same_location_as_previous，真实本事件虚拟增量/2300，is_first_positive。`event_age=(snapshot_virtual_us-event_end_virtual_us)/1_000_000`，单位为虚拟秒，不是事件索引差；负值/缺失拒绝介入。保留第一个正 bearing 加最近127个不同记录索引，按事件序；不足处mask，不能把padding当no_signal。所有原始历史在可靠层/记录层继续保留。
4. `polygon[V=32,2]`：完整保守polygon周界等弧长采样编码点，仅给网络；原完整顶点不被替换。少于3顶点或数值异常禁止介入。可靠面积/半径来自完整polygon，不由32点重算。
5. `actions[K≤9,14]`：kind one-hot3（teacher/measure/clear），target相对xy、移动距离/8000、是否换测頻、直接操作最小费用/10000、直接操作最大费用/10000、target到c距离/1800、certified_before、重复已测位置、C7 predicted_visibility代理、cost_proxy_only。teacher 费用位置为已有中心代理，最后一位为1；不得声称这是其真实成本。measure最大直接费用含near自动clear；clear成功与失败差2秒。

缺失 bearing 的 sin/cos 置0且 has_bearing=0；polygon存在但空是异常，不生成“无源”样本。超过128事件是明确的压缩损失，可记 `events_dropped` 到诊断但不伪造完整Markov状态。传入数值非有限即teacher。

### D3. 首版网络与拟合

每条编码 MLP 均 ReLU，包含 bias：

- active_events：14→32→32，masked mean/max 拼为64，再64→64。
- polygon：2→32→32，mean/max→64→64。
- channels：12→32→32，mean/max→64→64。
- global：20→32→32。
- 每 action：14→32→32。
- 拼接三个64维摘要、global32、action32，共256维；256→128→64→1，得到 fθ(h,a)。

参数数为 61,121（合成算术已核；实际实施必须从 trainable tensors 重新数并断言）。预测配对收益 `dθ(h,a,ref)=fθ(h,a)-fθ(h,ref)`，reference 与自身差严格为0。f不是可靠几何/源位置预测。模型为单个固定网络，三个训练初始化用于稳健性复核，不自动作为 ensemble 或置信区间。

损失以一世界权重1归一；该world抽中状态等权，每状态合法非reference动作等权。全部成本先除1000N且只除一次，令 s=0.002，首版只用无量纲回归：

\[
L_{reg}=\frac1M\sum_w\frac1{|S_w|}\sum_h\frac1{|A_h\setminus ref|}\sum_a
\operatorname{Huber}_{1}\!\left(\frac{d_\theta(h,a,ref)-y_j(w,h,a)}s\right).
\]

`Huber_1(z)=0.5z²`（|z|≤1），否则 `|z|-0.5`。误差0.001时回归损失为0.125，而不是旧未归一式的5×10^-7；对d的梯度为250，而不是0.001/旧式量级。首版排序权重为0，只在独立消融中试0.1：对 `|y_a-y_b|≥0.001` 的有效动作对，用 `softplus(-sign(y_a-y_b)*(f(a)-f(b))/s)`，最多全部36对，平均后与无量纲回归相加。不能把未归一Huber与此排序直接相加；两者梯度/量级必须记入测试和拟合诊断。0.001单位是1秒/源，而非1秒/局。常数是设计选择，不冒充理论最优。失败分支仍保留 `+100`惩罚的标签；不把失败行从统计/账本删除。

Adam lr=3e-4、weight_decay=1e-5、batch=8个完整fit world的状态包，最多20个epoch，每轮只在预登记epoch5/10/20保存；checkpoint只用12个永久fit_val world的world等权误差选，不接触calibration/development。24 fit 与12 fit_val包含在每轮36world内；fit_val无梯度、无表示归一化拟合，且不能下一轮改为fit。梯度范数上限1；三个初始化固定、各自训练状态独立；CPU单线程先实测。不能把模型训练步数当环境交互预算。

### D4. 部署门控

在线部署**不计算历史 `π_j(h,b)`，也不加载或递归调用旧模型链**。只加载本次冻结θ、固定阈值、当前公开状态及保留的A0，部署候选为 `a*=argmax_a [fθ(h,a)-fθ(h,A0)]`；最终是否取非teacher由经验门槛和 b/forced/guard 决定。`ref=π_j(h,b)` 仅存在于本轮训练标签/离线改进诊断中，反事实tail的旧π_j只由隔离evaluator持有。

为消除 reference 改变导致的分数基准混淆，**必须在每个样本同时保存 A0 的 cost-to-go，模型可学习任意动作差；门控校准始终针对“new predicted action 相对 A0 + π_j tail”实际成本差**。主要策略改进诊断另比较 `a_ref=π_j(h,b)`，二者不能混称。执行候选的完整闭环包含其自身以后的所有门控，需开发整局验收，不能从teacher基准门控推导单调改善。

calibration：先固定网络、候选生成器和每状态按预测值选出的 `a*(h)`，用独立calibration world在冻结π_j访问的预登记状态上仅收集 `a*(h)+π_j tail` 与 `A0+π_j tail` 两条分支。令 `e_w=max_h(predicted_gain_to_A0(h,a*) - realized_gain_to_A0(h,a*))`，取 `q=max(0, empirical_quantile_0.9(e_w))`。若a*=A0只跑一次并将残差记0；每world最多2状态×2分支。只校准已冻结选择器将选的动作，不声称覆盖全部K动作。每个world整体进入一个校准样本，不把动作/状态当独立样本。规则 `predicted_gain_to_A0 > q + 0.0005` 才准入，即额外要求0.5秒/源预测余量。少于24个完整calibration world/初始化则不启用新候选（或登记不足），不靠删坏状态补齐。

分位数采用nearest-rank：将n个完整world残差升序排列，取1起始秩 `ceil(0.9*n)`（n=24时第22个），再与0取max；不做插值，不用n+1修正，不称conformal。所有值必须有限且n≥24，否则该初始化校准未决/不启用，不删除异常world重算。相等收益按canonical payload hash稳定打破平局。

这是固定采样方案下的经验保守阈值，不声称conformal全轨迹保证或外分布概率。π_{j+1}诱导的新状态不服从原校准分布；门槛主要用于减少错误介入，最终由完整闭环测试判断。余量过大导致全teacher也是实际失败结果，不能事后降低阈值直到有效。

## E. 训练反事实 API、续局与时钟

### E1. 分层 API

```python
# deploy-facing; imports no local_env/evaluation/torch trainer
def prepare_source_choice(public_state: PublicState) -> ChoiceSnapshot: ...
def select(snapshot: ChoiceSnapshot, weights: FrozenWeights) -> ActionId: ...
def execute_operation(engine: ObservableEngine, retained: Operation) -> MacroRecord: ...
def resume_loop(token: ResumeToken, api: FourCallInterface, policy: FrozenPolicy) -> Episode: ...

# training-only evaluator; never reachable from actor's import graph
def fork_world(private_handle: EvaluatorHandle, token: ResumeToken) -> BranchHandle: ...
def run_branch(handle: BranchHandle, action: Operation,
               continuation: FrozenPolicy, budget: RunBudget) -> BranchOutcome: ...
def paired_labels(outcomes: list[BranchOutcome], terminal_n: int) -> LabelBundle: ...
```

`EvaluatorHandle` 持有 LocalEnv 的源配置、固定误差场与完整物理状态；`ResumeToken` 没有它。fork 后复制 mutable source.cleared、位置/频率、`_virtual_us`、接受请求计数、日志前缀索引等。必须保证不同分支不会共享可变 source 对象而串扰。readonly源参数可共享但只在 evaluator。

所有分支从**同一个prepare前ResumeToken中的h,b**出发，首步共用同一PreparedChoice并各自commit一次。reference执行 `π_j(prepared_snapshot,b)`，其他分支执行a；各自独立计算 `b'=b-1[a≠A0]`。然后**只按同一个冻结 π_j hash**续局到底。A0也可能与a_ref不同，A0的完整成本必须收集以便校准/对照。旧续局标签如果hash变了，必须真实重跑当前π_j tail，不能用新模型重评分冒充新标签。

### E2. 真实时钟不是免费可重置状态

训练分支仍须受现实期限约束，但不能让“排队轮到后面的分支”凭空少掉预算。给每个独立模拟分支使用 `BranchClock`：fork起点公开已用现实时间相同，实际开始后按该分支自身单调运行时间递增；排队/另一分支的运行不消耗此分支模拟任务时间。它只适用于本地反事实研究，属于明示的本地执行条件，不是官方窗口重置。

`BranchClock` 注入已有 LocalEnv 构造/状态恢复接口；不修改冻结物理计费或观测规则。token保存“fork时已用/剩余时长”，恢复后不能补回已经耗掉的前缀时间；模拟 `_ready_at/_t0/_deadline` 与 wrapper保持同一坐标系。前缀/clone/序列化的实际研究墙钟另计，因此该分支时钟不把计算成本宣称为零。

G0 必须用控制时钟构造期限前/后、排队两分支、在near自动clear前触发接管等测试。官方部署从不启用 BranchClock/fork，使用真实四接口和绝对截止时间。若无法可靠实现以上时钟语义，退回“每个分支从enter完整重放前缀再续局”，并按真实费用/时间重新预算，不能忽略差异。

### E3. 成本账本

每项分别记录，不能合并后失去分母：

- `unique_world_count`：所有分支/初始化共享同world只计1。
- `entered_episode_count`：真实调用enter的完整运行数。
- `suffix_rollout_count`：从fork状态运行到terminal的次数，不能叫新world或完整重新入场局。
- `accepted_business_calls`：实际执行enter/measure/clear/exit次数，包括prefix重放、对照、失败、fallback、校准、消融。
- `modeled_full_virtual_time=prefix_virtual+suffix_virtual`：每条候选完整任务结果；可复用的prefix在统计成绩中加回，但研究实际调用账本不重复虚增未执行的请求。
- `clone_cpu_s/prefix_replay_s/suffix_execution_s/feature_build_s/model_forward_s/serialization_s/fit_s`、wall start/end和峰值RSS。
- started预留、完成、失败、未知中断分别状态；未知费用不按0，也不自动重试。

对每完整分支验证 `prefix + Σ completed_macro_delta + partial_last_macro_delta + tail = total`，同一事件恰属于一个macro/tail。reference与alternative仅前缀可抵消；tail绝不能被截掉。清除数真实N只在终端标签区出现。

单分支启动前按旧合同预留剩余至多15,846个业务调用的保守额度，结束后按实际使用释放预留。总stage剩余不足则不启动下一分支；已开始的分支必须完成/保留真实失败。若一个world动作bundle未完成，标为预算未决；不把该world纳入完整headroom均值，也不把部分有利动作当完整候选集。

## F. 无训练余量检查

### F1. G0：先证明新 wrapper 没破坏 C7

48个新诊断world（每题24，12场景各2）上：originalC7与teacher0共96次完整运行；每对请求坐标/频道/顺序/返回观测和微秒账本完全相等。Q3最新非RL部署入口另外验证未被包装改变。第三组最多48次用于预登记force-operation smoke/接管检查，不计训练。

核心合成/接口检查至少覆盖：

- 冻结hash、candidate生成无请求/无副作用、patch提交恰一次。
- clone分支顺序不改变结果；相同history生成完全相同候选，与private source字段变化无关。
- no_signal不能删除未知频道；clear失败写入原失败账本；near自动clear全费用。
- source微秒账本、slot变化、forcedteacher、route_successor、_e2_progress、重复坐标语义。
- actor输入递归字段白名单；导入图中无local_env/evaluation；训练奖励和N不能经过previous_reward漏入。
- teacher0日志不含额外measure；fork恢复不enter；不同分支cleared对象不串扰。
- deadline/请求拒绝/超时/未知费用真实失败；fallback接管一次且尾费完整。

任一正确性失败先修底座，不进行网络拟合，不用“通过大部分夹具”替代接口验收。

### F2. H1：有限事后oracle的准确含义

24个Q4训练诊断world，12场景各2；world配方在读取结果前冻结。每world先运行C7，按纯公开规则抽至多4个源服务入口（从完整C7入口索引均匀确定，不按真实未来耗时挑最差源），每状态≤9动作。

**O1：有限单干预最优。** 每个(h,a)都从相同C7历史真实运行 `a + C7 tail` 到终端。将每条分支加回自己的真实前缀；在“从这4个C7边界选至多1个干预”这一个有限类中取整局成本最小，包含零干预C7。再完整重放选中计划以确认费用一致。它可作该明确有限类的事后最优基准，不是可观察策略。

**O2：两次贪心闭环诊断。** 从O1选择的第一次干预后真实出现的trajectory中，按同样公开抽样规则选至多4个后续入口，逐个评估第二次干预+C7 tail；包含不使用第二槽。重新执行整个最多2次干预计划。不能沿原C7 trajectory拼第二次干预，不对独立局部收益求和。O2是贪心搜索到的特权策略，不是所有双干预计划的最优上界。

报告全部24个world的C7/O1/O2秒/源、清除/异常、所选干预、slot次数、分支调用与完整成本。若可完整评估的24world不足，H1结论为“预算/工程不足，未决”，不是“无提升”。若两类均不足2%改善则不训练当前动作空间；如果达到，仍只能说明有探索动机，下一步必须证明公开历史可预测。

## G. 训练/选择/最终验证隔离

### G1. 分区与泄漏防线

所有数据先冻结`world_manifest.json`，world由完整源配置与误差场配方hash识别，seed只是生成手段。同一world的模式变体/旋转派生/所有分支/所有初始化必须同一分区，不能训练一个旋转、测试另一个旋转。旧5000–5099、旧campaign、旧RL选择、此次A1/A2开发等所有已读world进入exposed registry；若无法证明新world未重复则不叫sealed。

预登记角色：`probe`、`train`、`fit_val`、`calibration`、`development`、`sealed_final`；按角色设文件读取白名单。actor、trainer进程看不到development/final的源配置。calibration只能定固定分位数裕量，不反向调候选或网络。development可以选版本，但所有结果保留并明确选择偏差。最终world生成或解封发生在完整冻结之后，角色一旦被读取用于调整不可降回blind。

### G2. 三轮计划

每个方法臂3个初始化，每初始化每轮36world、每world≤4入口、K≤9。第1轮为24个新fit（每场景2）+12个新fit_val（每场景1）；第2/3轮为12个旧fit重访+12个新fit+12个新fit_val（每类每场景1）。旧fit_val保留原角色，不转fit、不混入梯度；12个fit重访的ID/抽样规则在看结果前固定。旧历史当前标签必须重跑π_j。不同初始化使用相同注册world配方以配对，但分别按自己的π_j访问状态；重复运行不是独特world增加。三轮最多108个world名额，其中24次旧fit重访，故主训练/fit_val合计至多84个独特world/共同配方，而非324个独特world。

每轮开始冻结：π_j权重/阈值、候选generator、所有库hash、world和状态采样规则。所有分支采集完再拟合，不在分支中更新π。fit完成后calibration24独立Q4world/初始化、每局≤2边界；再development120个Q4world（每场景10）完整闭环。校准和开发之间不回流数据。

参考标签不同版本不直接混合：旧数据用于保留负结果或选择需重新评估的公开历史；当前epoch训练集合只接受 `continuation_policy_sha == frozen_pi_j_sha`。用fit_val选择5/10/20epoch后固定calibration；不能先看development再选checkpoint。

每轮保留要求：完整开发全清且均值优于当前已保留候选、配对差区间支持改善、至少2/3初始化方向一致，无场景>2%明显退步。小于最终2%总门槛的进步可记中间有效轮，但不能直接晋级。连续3轮没有有效提升停止；保存checkpoint数不算轮数。

### G3. 非迭代基线与消融

必须先有 `teacher0`、相同操作集即时代价贪心、第一轮反事实监督门控。若BC-RPI有潜力，再完成一个预算匹配的固定教师续局基线：始终C7 roll-in/tail，逐轮取得相同数量新world/标签、同候选网络与训练更新数、同calibration/development预算。实际业务调用可能因策略长度不同而不同，报告并在较低共同完整bundle预算处做主比较；不能用等epoch冒称等交互。

必要消融按优先顺序：

1. **对象**：旧宏调度 vs 新源服务操作（旧已冻结权重可重测，但不能把旧不同world分数直接减新值）。
2. **标签**：局部费用/半径代理 vs 完整π_j续局回报；一个变更，不同时改网络。
3. **迭代**：固定C7 roll-in/tail同预算监督 vs 当前π_j roll-in/tail。
4. **表示**：去掉真实事件历史token，仅全局/频道/多边形摘要；候选不变。
5. **风险**：b=1 vs b=2；无经验门槛 vs冻结门槛；仅在训练/开发测试，保留失败。

若某消融因预算不足没完成，其对应因果解释标为未证明。若固定监督基线已经优于C7而PI无增量，保留监督方案，不伪称RL成功。

### G4. 最终统计与官方边界

最终另行申请发布验证授权，不能从研发预算中默认挤出：只冻结一个候选（初始化挑选也是选择的一部分）、C7和本轮最终best_at_execution。Q4预登记1200个新world（12场景×100）；Q3新非RL入口另做等价检查，不把保持Q3当RL泛化成绩。计算指标严格沿冻结v1：先全部清除/正常退出/时限，再逐world T/N 算术均值；任何未全清场景不作成功子集加速排名。

主要统计：候选减对照的配对均值，12场景分层world bootstrap 10000次，预登记seed；两对照的单侧Bonferroni 97.5%上界均<0，Q4相对两个对照均≥2%才晋级。附每场景均值、最差局、快/同/慢、P95/P99真实运行与虚拟耗时、总源分母、fallback率。该有限本地world置信结论不证明官方分布；正式Windows通信/重试/窗口仍单独验证。

### G5. 预算算术、缓存与未决

研发阶段总业务调用硬上限5,000,000：G0/G1 350,000；G2-P 1,500,000；G2-S 1,500,000；校准及必要分支消融550,000；development闭环/有限消融1,100,000。前一阶段未用完不自动授权后一阶段；任一容量不够先登记未决，不能改变抽样以换更有利的world。

以下263调用/完整局只是旧C7历史量级的**规划假设**，不是本轮实测或上界；suffix分支不得直接按完整局均值定价。

|用途|最大完整运行算术|按263/局的计划调用|缓存/授权|
|---|---:|---:|---|
|三轮两方法臂候选development|3×3初始化×120world×2=2,160|568,080|各候选独立跑；旧候选对同world可按完整hash缓存|
|development C7与best_at_execution|120×2=240|63,120|冻结后各跑一次；同world虚拟结果可复用，不复用现实耗时作速度对照|
|development有限非分支消融|最多240|63,120|先登记具体臂/固定全120world，最多2臂；额外消融需额外额度|
|development计划合计|2,640|694,320|在1,100,000调用阶段上限内留异常/成本漂移余地，不保证可完成|
|发布前4800暴露兼容回归|4,800×1冠军组合入口|1,262,400|原C7/最新best的精确匹配历史行可复用；这是暴露回归|
|最终Q4三个冻结策略|1,200×3=3,600|946,800|全新world，无历史缓存；冻结后单独授权|
|Q3入口等价|48world×2=96|25,248|独立接口检查，不是RL性能成绩|
|独立发布验证合计|8,496|2,234,448|另申请3,000,000调用、3小时、4GiB数据、16GiB RSS|

研发另受40,000个full/suffix执行、6小时、8GiB数据、16GiB RSS上限。24/36/120/1200都是预登记完整集合，不保证在调用预算内完成。G2的36×4×9×3×3=11,664个分支/方法臂包括fit_val标签；最多3轮还另有每臂324次roll-in、校准分支及development完整局，全部纳入40,000计数。校准仅冻结a*与A0（D4），最大24world×2状态×2分支×3初始化×3轮×2臂=1,728个suffix，校准/必要消融合计不超过3,000个suffix分支；G0/G1至多2,000个full/suffix；研发两臂分支23,328+roll-in648+校准roll-in432+校准/消融分支3,000+G0/G1 2,000+开发2,640=32,048个执行的排程上限，剩余不是自动新增实验许可。每次必须先预留至多15,846调用，因而低于实用预算亦可能提前停止。

缓存只可用于world内容hash、策略权重/阈值/入口hash、候选生成器、环境/接口hash、计费版本均相同且终局正常/费用完整的已有行；实际未重执行的调用记0，复用行有origin run ID，不计新独特world。已有前轮π结果可以作为当前development的配对对照，不等于重测实时速度。发生依赖变更则缓存失效，额外费用必须有余额，不能静默复用。

固定运行次序：G0→G1→各轮fit/fit_val→calibration→完整development候选块→（如有保留）同预算监督基线/已登记消融→冻结冠军→另授权发布兼容回归→再冻结→sealed final。已使用的development不升格密封。每个120/1200world集合采用预登记分场景交错顺序，不能按已知快慢或前半结果挑选。预算不足时已启动完整分支结算，其余逐ID记`not_started_budget`；部分bundle记`incomplete_budget`，所有已花费用保留。未完成完整登记集合不作晋级/无余量结论；最终若中断，仅可保持同一冻结协议续跑（另获额度），或公开终止，不能看部分结果改策略后继续称同一sealed test。

## H. 文件清单、接口与伪代码

未来实现文件（目前未创建）：

|文件|职责|必须禁止的依赖|
|---|---|---|
|implementation/deploy/state.py|公开ResumeToken、完整状态hash、序列化|local_env、源truth、trainer|
|implementation/deploy/engine.py|显式READY状态机、common patch、execute/resume|测试数据读取|
|implementation/deploy/operations.py|纯历史九选项生成/合法性|fork、error()、true source|
|implementation/deploy/features.py|精确白名单张量、相对坐标、mask|奖励/N/seed/scenario|
|implementation/deploy/model.py|61121参数网络与冻结forward|训练数据路径|
|implementation/deploy/policy.py|固定阈值、b/forcedteacher、teacher回退|在线更新、采样探索|
|implementation/train/fork_runner.py|evaluator私有fork、BranchClock、分支续局|把handle传给actor|
|implementation/train/labels.py|真实终端N、配对成本标签与版本验证|写入deploy snapshot|
|implementation/train/fit.py|world等权拟合、3初始化、恢复|读取calibration/dev/final用于拟合|
|implementation/train/calibrate.py|独立world经验残差裕量|更改模型/候选架构|
|implementation/evaluate.py|同world闭环、逐行metrics、失败和CI|更改冻结环境与规则|
|implementation/audit.py|成本hash、输入边界、candidate与branch复核|把hash当真实性或训练正确性证明|
|implementation/tests/|状态恢复、预算、公式、泄漏、等价夹具|把合成通过当任务收益|

训练伪代码：

```python
pi = immutable_teacher_anchor()
for round_id in preregistered_rounds:
    freeze(pi, generator, data_manifest, compute_budget)
    bundles = []
    for w in registered_train_worlds(round_id):
        # private w exists only in evaluator, not in public policy process
        rollin = evaluator.run_to_terminal_and_save_ready_states(w, pi)
        states = sample_by_public_rule(rollin.ready_states, max_states=4)
        for h_b in states:
            prepared = prepare_once_on_detached_public_copy(h_b.public_only)
            snap = prepared.public_snapshot
            ref = pi(snap)
            outcomes = []
            for a in snap.retained_operations:
                reserve_full_continuation_or_stop()
                handle = evaluator.fork_at_same_world_history(h_b)
                compare_and_commit_once(handle, prepared)  # no second prepare here
                # each branch starts at the SAME b; then its action consumes own slot
                outcome = execute(a, handle)
                outcome += resume_to_true_terminal(handle, frozen_policy=pi)
                settle_real_costs(outcome)
                outcomes.append(outcome)
            verify_complete_bundle_or_mark_pending(outcomes)
            bundles.append(label_with_terminal_N_only(outcomes, ref, A0))
    theta = fit_current_policy_version_labels(bundles, world_equal=True)
    margin = calibrate_on_disjoint_worlds(theta, frozen_continuation=pi)
    proposed = FrozenPolicy(theta, margin, max_interventions=2)
    # Actual full rollout, not sum of predicted one-step advantages
    result = paired_closed_loop_development(proposed, pi, C7, best_at_execution)
    archive_every_result()
    if result.passes_intermediate_keep_gate:
        pi = proposed
        consecutive_no_gain = 0
    else:
        consecutive_no_gain += 1
    if consecutive_no_gain == 3 or budget_exhausted():
        break
```

部署伪代码：

```python
while engine.has_unresolved_obligations():
    api.check_learning()
    prepared = prepare_teacher_on_detached_copy(engine)
    teacher_task = prepared.teacher_task
    if teacher_task.kind != 'source' or mode != 4:
        operation = exact_teacher_operation(teacher_task)  # station OR source
    elif not eligible(prepared.public_snapshot):
        operation = teacher_service(teacher_task)
    else:
        operation = choose_retained_operation_or_teacher(
            prepared.public_snapshot, frozen_model, margin)
    engine.compare_and_commit_once(prepared)  # validates pre-hash, then exactly once
    start_event, start_virtual = api.event_count, api.virtual_time
    if operation.kind in ('measure_override', 'clear_override'):
        engine.interventions_remaining -= 1  # before any accepted physical effects
    outcome = 'partial_or_unknown'
    try:
        execute_controller_operation(operation)
        outcome = 'complete_return'
    finally:
        # ALL paths, including station, teacher, partial operation and takeover
        record_actual_event_range_and_delta(start_event, start_virtual)
        finalize_macro_or_partial_failure(operation, outcome)
        update_progress_todo_visited_and_forced_teacher(operation, outcome)
    # No network hook inside the controller operation
certificate_or_independent_fallback_then_exit()
```

共同finalizer总是记下真实已接受事件/部分成本，但**控制流完成不由finally推断**。仅`complete_return`的station才可remove todo/append visited；partial station保留原todo/visited义务。强制teacher频道只有对应A0完整返回才清标志，失败/中断A0保留。request拒绝/未知接受/guard接管的partial路径不得回READY或继续学习，而是保留未决义务进入现有独立fallback/失败处理；不把部分scan误当完整覆盖。新替代操作无论结果如何都不返还已消耗槽位。

恢复与出错：分支 started/weights pending 使用原子文件；已保存完整轨迹但索引缺失时从轨迹补索引，不重跑；请求接受但轨迹未知时保留unknown_cost并停止，而非自动重复。所有输出使用新目录，不覆盖上一轮候选。

## I. 验收交付与未证实部分

正式实施后应交：manifest、全代码hash、每轮冻结权重、样本分区、world/分支/调用分母、全部行和失败、O1/O2训练诊断、所有闭环比较、成本及读取审计、部署导入图、未干预等价轨迹、最终与官方边界。

当前未证实：新动作余量、监督可学习性、PI增量、calibration有用性、候选生成完整耗时、真实恢复接口可用性、官方执行。61,121参数/三轮/九动作/2%与资源上限都是明确可修改的设计选择；任何修改须在使用对应开发/最终数据前重新登记，不能事后选有利口径。
