# 协调者核读记录

本轮为用户审阅前的方案研究：零算法实现、零训练、零策略环境执行。以下是现有代码/接口和官方工程文档核读，不是学习效果实验。

## 现有实现提供什么

现阶段强对照[C7](../20260911_stage4/combination/geometry_fusions/C7_both.py)已经采用任务排序、站内补测费用门控、持久单轮定位、全顶点清除认证、保守负观测几何和光学兜底。共同4800暴露回归Q3/Q4为235.876945812/456.111820876秒/源，分母与退步见[第四阶段报告](../20260911_stage4/REPORT.md)。新方法不能只打败早期覆盖贪心就称改进现有最佳。

C7第124行localize实际执行一轮服务后还可能补测；一轮内可能有clear、measure、恢复测向、near自动clear等多个付费动作。第132行起的_e2_service_round保留逐频道进度，达到原有限轮数后切入cover_polygon。于是“调度一个频道”和“单次测向”不是同一动作语义；actor所见状态必须含剩余服务预算等影响转移的信息，宏动作耗时应从实际执行差值取得。

其继承run入口见[Q4父组件](../20260911_stage4/baseline/R3_open_R5.py)，会enter并重新设置todo、deadline；新策略不能在中途通过新建Solver后run来假装无损接管。应在同一个控制循环中切换选择器，或预先定义可验证的共享状态与交接协议；这些是待实现设计要求。

## 用户草案需要对齐的接口细节

- [冻结规则](../../docs/评测标准_v1.md)和[环境measure/clear实现](../../local_env.py)：measure成本为移动/5+切频道1+检测5；clear为移动/5+光学3+成功时2。clear不改变测向频道。用独立I_switch/I_detect/I_optical/I_clear描述宏动作容易漏计自动动作或给clear错误加切频，应以接口累计时间差为准。
- 同址误差固定仍不代表近邻误差独立或平滑；这些是训练分布假设。返回示向度保留两位小数，可靠楔形用±1°时还要覆盖舍入误差；现有父组件已用1.005001°。
- 600米方格的方向鲁棒发现论证可作为纸面构造，但项目已有22个站点的三角覆盖结构。不能把更粗的新兜底或既有覆盖思想本身当新增性能/创新证据。
- 仅限制exit不推出有限完成。还需有限动作预算、覆盖/服务进度单调、不重置的兜底队列、当前位置可达的保守回退费用，以及现实推理/通信时间预留。条件性几何证明与真实服务端运行保证分开。

## 目标函数对齐：项目推导，待评议

草案在gamma=1下逐步奖励-DeltaT/T0对应期望总时间E[T]；现有跨局汇总为E[T/N]，N在10–16变化时二者不等价。例如两种策略在N=10/16两类等概率任务分别耗时(100,320)与(180,240)：总时间均值均为210，但每源均值分别为15与16.5。训练必须明确优化哪个目标，不能默认等价。

若拟在离线训练中以真实N做按局权重或奖励归一化，需将其标为训练专用信息，不能放入在线actor、循环记忆输入或观测编码；若actor输入历史reward，也需防止由归一化reward直接泄露N。只有可靠全清时清除数才等于N；失败不能用较小清除数产生有利排名。

固定gamma<1按决策步折扣会因宏动作粒度改变偏好。以负时间为任务目标的有限proper策略可优先论证gamma=1的随机最短路形式，potential在终端置零；若使用gamma^duration的时间折扣，应明确这已采用不同目标，不能仅称实现修正。终止、时限截断与兜底后的成本必须一并进入回报定义。

## 官方软件文档核实（2026-09-11访问）

1. [SB3-Contrib MaskablePPO](https://sb3-contrib.readthedocs.io/en/master/modules/ppo_mask.html)：文档支持表明确不支持recurrent policies；支持Discrete动作与Dict观测，不支持Dict动作。使用专门mask-aware评估方法；子进程环境的action_masks必须在环境内实现。页面标题为2.9.0文档，这不是本机已安装版本或单独核实的正式release日期。
2. [SB3-Contrib RecurrentPPO](https://sb3-contrib.readthedocs.io/en/master/modules/ppo_recurrent.html)：是另一套LSTM策略实现，需正确维护hidden state与episode_start。上述两个公开类并不构成现成的“任意动态图pointer+GRU+mask”组合。
3. [SB3 PPO](https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html)：其工程建议是非CNN时主要使用CPU，并提到frame stacking作为循环策略的简单竞争起点。这不证明本题图网络在CPU一定更快，说明CPU/MPS应实测而不能按显存猜。

原网页与文本仅缓存在workspace的work/rl_research_cache/root/，抓取URL/散列在implementation_sources.json。缓存不是提交材料；本记录只是工程支持约束，不计为三篇研究论文。

## 本机只读检查

当前硬件为arm64、内存25769803776字节（24GiB）。本轮指定Python3.12.14可以找到numpy，但找不到torch、torch_geometric、stable_baselines3、sb3_contrib、torchrl、tensordict或gymnasium；这不代表用户其他虚拟环境没有这些包。本轮未安装依赖或运行神经网络。

“约百万参数”不足以证明可训练、多少小时或何处是瓶颈。后续实施前的预实验应分别测量环境、候选与图构建、推理、更新、进程通信、内存及候选数/序列长度变化；本轮只规定这些将来的决策门槛，不给未测量的吞吐或训练时长。
