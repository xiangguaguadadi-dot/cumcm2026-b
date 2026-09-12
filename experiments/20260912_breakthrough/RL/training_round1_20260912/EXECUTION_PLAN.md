# BC-RPI 第一轮训练执行计划（待协调者审核采集配置）

2026-09-12。用户已明确授权第一轮真实网络训练、三个初始化、独立校准和同批整局评估，并覆盖旧 G1 改善不足 2% 时不训练的停止门槛。旧 G0/G1 结论和全部代码、结果、账本只读保留；本轮不改动作空间或把旧诊断变成训练/测试集。此文件写入时新增业务调用、网络训练均为 0。

## 范围与当前事实

- 旧 G1 已完成 24/24，O1/O2 特权改善为 1.559258%/1.715177%，不是可部署学习收益。旧累计 197456 次尝试调用、1696 次执行全部结算，unknown=0、current_run=null；不恢复旧进程。
- 新代码、模型、数据、注册和账本仅放本目录；复用已验收 `../implementation/deploy/` 和 `../implementation/evaluator/runtime.py` 等只读底座，不改旧 Budget 的全局时间/计数。
- 本轮只有 π0=C7 的一次完整反事实监督训练，不宣称已证明迭代 RL 增量；3 初始化不是 ensemble。不会自动运行第二轮、额外策略臂、4800 暴露全回归、sealed final、官方接口或发布部署。
- 同批机制锚 C7 SHA `cf37866829b9c6f376895075e819a732939e6fa8ad6d8d6297a151d7a213dcb3`；最新 Q4 R2 SHA `789096af68fcf470e3973fd93757c556d81d60f3fe3910c5991c537def3f91cc`。Q3 最新 R11/Q4 R2 现有组合不变。

## 数据与真实标签

新 namespace 固定为 `bc_rpi_r1_20260912_v1_{fit,fit_val,calibration,development}`，每角色 index 从 0 起，group_index=index%12；使用原冻结 worlds.py 配方。完整 source+noise+seed+mode 内容 hash、模式无关源配置/误差 family hash、seed 唯一性均检查；不构造旋转增强。登记时检查旧 v1/4800/旧 RL/A1/A2 和 G0/G1 registry，碰撞先停，不读取效果后换种子。

|角色|独特 Q4 world|每组|用途|
|---|---:|---:|---|
|fit|24|2|唯一梯度来源|
|fit_val|12|1|仅选择 epoch 5/10/20；永不转入 fit|
|calibration|24|2|网络冻结后，仅确定每初始化的经验裕量|
|development|120|10|全部 3 个模型+C7+R2 的同批完整闭环；不是密封最终|

合计 180 个独特新 world；同一 world 的所有状态/分支/初始化不跨角色。actor 只收到公开 feature JSON，trainer 只读取 fit/fit_val 的公开特征和终局标签，不读取 calibration/development 源配置。

π0 对三个初始化相同，因此只采集一份共有的 36 world 标签，显式记录共享 origin run ID；不把标签读取三次算成三份交互。每 world C7 完整 roll-in 后，按旧固定公开均匀入口索引规则抽至多 4 状态，每状态所有 retained 动作（含 A0，最多9）都执行完整 `a+C7 tail`。状态相同、动作相同的精确缓存必须绑定 world/handle/动作/continuation/环境/计费/source SHA，复用调用记0。失败完整保留 +100 标签惩罚；未完整 bundle 不进入拟合。

任务目标是 episode 等权平均 T/N。标签 `y=(T_ref-T_a)/(1000*N)`（T为真实完整尾段秒，公共前缀差抵消），失败分支 cost 额外 +100；γ=1。不用局部熵、面积或操作数代替任务损失。N仅在终局标签侧，绝不进入模型输入。

## 网络、拟合、校准、闭环

- 完整沿用 spec D2 的 `20,20×12,L≤128×14,32×2,K≤9×14` 输入和掩码；五路编码网络实际 trainable tensors 必须恰 61121 参数。公开输入不得含 N、真值、seed、world/group ID、真实墙钟或未来奖励。
- 初始化 seed 固定 `[912101,912102,912103]`，CPU 单线程、独立模型和优化器。Adam lr=3e-4、weight_decay=1e-5；完整 world batch=8，20 epochs；仅保存 epoch 5/10/20，用12永久 fit_val world 的同一损失挑选，平手取较早 epoch。
- loss为 world→已抽状态→非reference合法动作三级等权 Huber((d-y)/0.002)，gradient clip=1，排序权重0。只有 A0 的状态 loss=0但仍占原 world 的抽中状态分母；无状态 world loss=0并仍占 world 分母，异常/缺失字段不是空状态且必须失败停机。所有空状态计数明示，不能悄悄删 world。
- 每初始化选定网络并冻结后，在同24 calibration world 的 C7 roll-in上公开均匀抽至多2入口；先固定每状态 argmax 动作（规范hash平手），再真实评估该动作与A0的完整C7续局。3初始化可共享完整C7 roll-in与确实相同的分支，必须保留逐初始化选择映射和缓存资格，不能复用不同动作成本。
- 每world最大乐观残差，24 world 的第22小值并与0取max得到q；部署严格 `predicted_gain > q+0.0005`，b最多2，forced teacher/guard不变。校准不足24 world则该初始化未决，不调小q。
- 固定 q/weights 后，120 development world按index顺序，全部3模型+C7+R2同批完整运行（最多600 full）。报告全清/失败后再比较 world等权 mean(T/N)、配对差、分场景、快同慢、P95/P99/fallback及所有失败。采用12组分层world bootstrap，10000次、seed=912199；三初始化各自与两个对照的区间为开发描述性证据，不是最终多重比较发布验证。
- 开发均值无收益、阈值导致全teacher或初始化不一致均原样交付；不据开发结果回调checkpoint、阈值或网络。当前部署保持不变。

## 拟议新增硬预算（本轮独立账本，阶段不自动挪用）

|阶段|新增尝试调用上限|计划最大执行|
|---|---:|---:|
|采集 fit/fit_val 完整标签|500000|36 full+1296 suffix=1332|
|独立 calibration|150000|24共有full+最多288 suffix=312|
|development 三模型+双对照|300000|600 full|
|必要真实接口/新selector直通检查|50000|最多24 full/fixture，固定旧probe，不训练|
|本轮合计|1000000|硬界3000，计划最多2268|

本轮另设采样/拟合6小时准入停止时限、原始新数据8GiB、单进程及所管理worker合计RSS16GiB。新预算时钟在协调者通过采集配置后、第一实际调用前独立登记；此前准备墙钟另记，旧注册时钟不改。协调者明确：6小时后不启动新full/suffix或fit初始化，已启动完整任务在原剩余现实窗口内结算，不研究性截尾造标签；串行采样的总研究墙钟可能超出6小时至多一个在途任务，已启动的20epoch小拟合亦可结算并单记实际时间。每次启动均检查RSS/raw；若真实资源中止导致未完整，标为incomplete_resource，不混入+100真实环境失败训练标签。每次full/suffix/真实fixture都预留15846调用，阶段或总余额不足不启动；调用接受未知即停并保留，不能盲重试。最新旧账本作为carry-in展示，总历史边界为1197456调用/4696执行，但旧额度不转入本轮。

G1本次真实O1/O2共1482 suffix耗费160384调用（另含72 full），只作运行量级参考；不是本轮成本保证。拟议上限有余量但不改变固定世界集合，不为填满额度增加训练。

## 分阶段冻结与执行顺序

1. 采集器、独立预算、完整 world manifest、只读底座及全部实际采集依赖先冻结、存精确字节zip；协调者审核后才采集。本阶段网络模块未执行，可以在本目录单独实现，不纳入该采集依赖freeze，禁止借此改实际采集依赖。
2. 全部36world完整标签收齐并审计后，冻结模型/拟合代码、张量与纯测试，再进行3次真实拟合。每个checkpoint保存初始化/optimizer/RNG与loss曲线，供独立复算，不把梯度纯测试计作本轮训练完成。
3. 仅fit_val选择后冻结3权重和argmax规则；再采集24完整校准world并冻结q。
4. 冻结新selector、3完整policy身份和双对照后再完整development；本轮结束即停，不自动发布。所有阶段输出新目录、全部成本归独立统一账本；旧证据不覆写。

目前只做只读恢复、库可用性/纯张量检查和实现准备；尚未开始上述任何新真实world或fit。
