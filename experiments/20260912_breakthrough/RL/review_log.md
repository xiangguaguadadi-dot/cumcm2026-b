# RL方案质疑、回应与修订记录

日期：2026-09-12。范围：研究计划。用户未授权本轮训练；最终接纳也只能是“值得依门槛实施”，不能记为方法有效性认可。

前两轮按当前文稿与协作记录整理为**概述**，不是逐字会议记录。第三轮问题与修订有明确逐项对应。所有内容只改RL目录，原C7、v1环境/数据、主solver、第一/二问均不改。

## R1：旧学习对象与新动作语义

|质疑概述|回应和修订|仍未证明|
|---|---|---|
|旧PPO/Q负结果不能通过“训练不够”直接解释；要先证明操作余量|不把探索/fallback占比说成因果证明；改到Q4源服务入口，先G0/G1无训练余量检查|哪个因素导致旧退步、新动作是否有2%余量|
|只按候选中心挑宏任务，可能遗漏localize内部全部费用与信息|新有限动作定义为真实controller operation；A0仍完整localize，干预后重规划|新候选实时触发率及局内收益|
|恢复嵌套Python调用栈不可靠|只在READY自然边界保存完整控制器/公开历史；禁止在near/clear/localize内部挂起后run重入|真实恢复接口可用性|
|一步收益可能只是把成本推给tail|所有标签真实运行完整终局，明确γ=1、T/(1000N)、失败罚和整局对照|完整标签是否可由公开特征预测|
|真值/世界ID与泄漏风险|fork仅在隔离evaluator；候选/actor只接白名单JSON；N仅终端标签使用|真实导入图与序列化白名单需G0验收|

## R2：同状态反事实、预算与RL归因

|质疑概述|回应和修订|仍未证明|
|---|---|---|
|替代分支缺教师controller_patch/route_successor会改变基准|在detached公开副本prepare一次，同一prepared_state和common patch给所有分支；teacher0逐请求等价|实际patch完整且恰一次提交|
|一次操作不等于一次业务请求，Q4 near会自动clear|将`event_range`真实计费作为唯一依据；READY要求_active_target=None、_sharing=False；冻结配置e2_same_here=False，不靠改教师配置取得等价|真实继承链附加请求检查|
|两分支强行都扣一个槽会错误比较|同一(h,b)起点；a_ref亦可能干预，各自按动作扣b，禁止补槽/省略干预机会代价|真实state-machine预算实现|
|标签跟不上策略版本导致伪策略迭代|每轮冻结π_j、真实重跑旧历史的π_j完整tail；不重评分冒充重标注|PI比固定监督续局是否有增量|
|第一轮是监督，不能把额外数据收益全归RL|单独设同实际调用/标签预算固定C7 roll-in/tail基线；PI无增量则保留监督方案|匹配预算后的归因|
|oracle单步收益累加不成立，二次干预有状态变化|O1仅有限类单干预事后最优；O2沿第一次干预后真实trajectory贪心再选并完整重放，不称全局上界|真实headroom|
|现实排队/恢复不能重置任务期限|BranchClock保留已用前缀，仅隔离本地分支排队；真实研究时间/序列化另记，官方无fork|时钟/guard真实接口测试|

## R3：六项必须修订

1. **损失尺度。** 原未归一Huber误差0.001只有5×10^-7，而0.1×softplus约0.069，混加会压倒回归并破坏价值标尺。改为`Huber_1((d-y)/0.002)`，首版排序权重0，排序只作独立消融。合成测试核误差0.001时损失0.125、梯度250及旧比例问题。
2. **fit_val预算和永久角色。** 每轮36明确为24fit+12fit_val；第2/3轮12旧fit+12新fit+12新fit_val。fit_val永不进梯度、不改fit；三个初始化共享world配方但独立roll-in/训练，三轮最多84独特world配方，不冒称324。
3. **部署不能递归旧模型。** 在线仅当前冻结θ、A0和门槛；π_j仅训练参考/隔离tail，历史模型链不进入部署。
4. **预算不兼容。** 原研发500万中的110万“验证”不足以同时承诺开发、4800暴露回归与1200×3 final。现研发500万只含开发及有限消融，发布验证另申请300万；列完整算术、精确缓存资格、先后顺序及预算不足逐ID未决。任何额度都未执行或默认获批。
5. **措辞。** 将“固定全局任务次序”改“保留任务选择规则”，承认真实观测变化使序列改变。Markdown说明改为仓库追溯选择，不再误称用户指定。
6. **异常和公共结算。** 未知slot/特征/候选→teacher；API接受状态未知不能重复teacher，保留unknown_cost并guard。station/source/teacher/部分异常均走同一finalizer，不在station路径continue漏账。

协调者完整重读v2后确认：上述六项已实质修正，未提出新的机制级阻挡；要求继续完成来源/测试并保留“方案而非有效性”边界。

## R3补充：校准预算与三个确定性定义

- 校准先冻结θ及每状态选择的a*，只采a*与A0同π_j完整tail；每world最多2状态×2分支。最大24×2×2×3初始化×3轮×2臂=1,728个suffix，纳入3,000校准/消融排程；若对全部K=9会有7,776分支，与原排程不兼容，因此不宣称校准所有K动作。
- `event_age`明确为当前虚拟微秒减事件结束微秒，再换成秒；不是事件数。
- 替代候选坐标用1e-7米Decimal ROUND_HALF_EVEN，负零归一，执行规范化后的点并重验合法性/覆盖证书；A0内部请求不舍入。
- 经验90%分位数固定nearest-rank `ceil(.9*n)`；24world取第22个，不插值、不做conformal宣称；非有限/不足24拒绝启用。

## R4：独立第二视角的状态机审查

第二位算法Agent只读审查后提出、协调者确认的两项实质缺口及一个finalizer责任已修：

1. **ResumeToken不完整。** 增加完整`interface_public_state`（guard/cap/phase/请求数/观测/证书/费用和已结算timing）及明确`clock_offsets`。保留前缀已用时间、接口及solver各自剩余deadline、最后响应年龄；不把learning_requests清零，不重置期限。旧`_pending_timing`可以是已落账的上一请求信息，要求已结算而非误要求dict为空。
2. **prepare/commit顺序冲突。** B1/B3/E1及两段伪代码统一为detached prepare→选择retained→校验pre-hash→commit恰一次→execute。ResumeToken只允许READY_PREPARE；各branch恢复pre状态并共用已算PreparedChoice，首步不得再prepare。choice_id/counter即使空patch也防止重复提交。
3. **partial不是complete。** 公共finalizer总记已接受费用，但partial station不能从todo移除/加入visited，失败A0不能清forced标志；partial/unknown/接管不得回READY，进入现有fallback/失败处理。新增4项合成夹具检验指定语义，仍不是实际solver运行。

## 合成验收与剩余授权

[25项合成检查](contract_check_results.json)已通过，检查范围见 [SOURCE_AUDIT.md](SOURCE_AUDIT.md)。它们不导入真实模拟器/solver/训练框架，仅验证构造夹具和元数据一致性。

下一步最小请求是用户验收本方案，随后可另批准G0/G1。真实teacher0等价、恢复/时钟、候选余量必须先通过；之后训练包及最终发布验证仍分阶段授权。当前环境执行0、反事实训练分支0、模型更新0；不交“有效RL权重”，不声称突破C7或本轮新最佳。
