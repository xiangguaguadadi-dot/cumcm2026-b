# G0/G1执行预登记

登记：2026-09-12 06:07 UTC（14:07 Asia/Shanghai），在任何本轮环境调用前。

用户最新要求：接着用原方案子Agent执行。协调者限定本轮只实施并运行已验收方案的G0/G1：真实正确性和有限操作余量检查；**零网络训练**。旧PROPOSAL.md、implementation_spec.md、test_contracts.py及原C7/旧RL core/v1环境和数据不改。

## 冻结输入

- 教师锚：C7_both.py，`cf37866829b9c6f376895075e819a732939e6fa8ad6d8d6297a151d7a213dcb3`。
- Q4最新稳定对照：A2/BEST_R2.py，`789096af68fcf470e3973fd93757c556d81d60f3fe3910c5991c537def3f91cc`。G1 headroom针对C7；若采集该对照，单独记实际费用，不能换掉机制锚。
- 已验收PROPOSAL：`000281b9a17183763957bd4318b6a00173193ad53254d1e94147d6f810efa736`。
- 已验收spec：`deb0ac21bcbe326bdb32023ea3ba23cb858645dc410875249d6a5d4fbebcc2b8`。
- 旧core engine：`dd143ba911a7e6bd46a79fe7ae5d98bd98681e7d20764b57436c321e1af0894c`；interface：`ed5d3e98ab846dc546f9e5d5adcbc8e8c63e936e99e1f5f2cdf1096dd77042f3`；fallback：`fcc07db4e62341cbdc8d20335096d3541bacfbbdbd1614bf3c1a5936525f00c3`；geometry：`a7a5a98efe5be405e45f796421b35eb1ecdad07bcb3977774d45a3bcedd764a3`。
- 只读world配方：旧data/worlds.py，`f595623edd01fbcaeefd64a05bf3905f13deb25f9508d2f813e94715a5509f80`；禁止导入有写数据副作用的evaluation/generate_cases.py。
- v1 manifest：`431210a6d96e721d23c31698aa389702ea87dcffe8fee6250f71ce6e902be140`；local_env：`99587518fa378e1bef2fbbaa9425ee907bea80885a69666b3765311cbcf4f42a`。

## Probe world配方

使用冻结worlds.py的12场景及sources分布，但使用新namespace：`bc_rpi_g0_20260912_v1`与`bc_rpi_g1_20260912_v1`；seed按该模块seed_for(namespace,mode,index)生成。G0每mode 24world，index=0..23、group_index=index%12；G1仅Q4 24world，index=0..23。全部是probe/exposed诊断，不进入未来最终密封测试。

运行前生成完整源配置/误差场recipe的world hash和登记文件；核对v1/旧4800/旧RL已用registry及此次A1/A2已登记world的seed和内容hash。相同world所有分支属于同一probe集合，绝不按snapshot切分。哈希碰撞/重复发现时先停止和更正登记，不看表现另选seed。

## 成本和停止

- 业务调用硬上限350,000，包括enter/measure/clear/exit、测试、重复、失败、对照、prefix重放、fallback；另外区分attempted与accepted，未决费用不按0。
- full/suffix及真实接口夹具启动数总上限2,000；研发墙钟上限6小时（以本登记时间起计）、数据8GiB、RSS16GiB。
- 每个真实full/suffix启动前预留15,846业务调用，结算实际尝试调用后释放剩余预留；余额不足不启动下一项。对未启动的登记ID保留not_started_budget，对未完整bundle保留incomplete_budget。
- G0：48world×original C7/teacher0=96全局；另最多48个force-operation/恢复/时钟/guard检查执行。所有实际调用均入统一账本。任何正确性未通过不进入G1。
- G1：24个Q4 C7 roll-in，均匀公开规则选至多4个服务入口、每入口至多9动作。O1完整a+C7 tail，取有限单干预最优并完整重放；O2沿第一次干预后真实轨迹至多4个后续入口，再评估/重放第二次干预，不能拼接原C7路径或累加独立优势。
- O1/O2包含零干预；均值改善都不足2%则停止当前动作空间。24world/完整bundle未完成则结论未决，不把部分有利结果当完整均值。
- G0/G1完成、否定或预算未决即交付。G2训练、发布验证、新sealed集、官方接口和Git提交均未授权。

## 实现与验证次序

1. 独立implementation/deploy与implementation/evaluator；truth/fork只在evaluator，候选生成只看公开状态，部署导入图不含local_env/世界生成器。
2. 实现完整ResumeToken/interface/clock offsets；只保存READY_PREPARE，prepared choice产生一次，各fork提交相同patch一次；原分支、反事实各按自己动作扣槽。
3. 运行标准库纯合同单测、冻结规则与G0真实接口/等价检查。真实clock-bound控制器只把原_time_guard中的monotonic读取换成注入clock，保留其严格大于deadline的判定及错误语义，原C7源码不变。
4. 保存每阶段代码hash、全部运行/失败及逐请求成本，再由协调者独立审计后进入G1。

Q3仅用C7做wrapper一致性；本轮最新Q3仍在迭代，其接口兼容待协调者冻结后另查，不悄悄换用旧C7作为部署Q3。
