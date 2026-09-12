# A2并行第二轮实验报告

保留候选：`snapshots/finite_r7.py`；SHA256 `6891cc27d3cd23f9c4c91e0b7ab2bb2fe0104b4768d8f68ab44e01b36f254671`。

4800个已暴露本地案例全部清除且正常退出；Q4为2400局、30970/30970个源，Q3为2400局、30970/30970个源。Q3动作统计与本分支基线相同。Q4每局秒/源再取算术均值由455.434476124降至453.727487920，差-1.706988204秒/源。该合并均值仅用于已登记研发选择，不是官方总分；逐场景结果在下表。

相对本分支起点BEST_R2，Q4逐局更快/相等/更慢为1673/11/716。最差退步案例`LOCAL-v1-q4-reference_assumed-5062`增加62.630959秒/源；所有退步行均保留。

## 证据层级与计算

这是接口动作真实执行的本地模拟评测。v1为2400个案例，旧previous_final为另2400个案例；二者均已在此前暴露。quick 120局是v1子集，不作独立重复证据；exposed复用候选散列严格相同的v1结果，只新跑旧previous_final部分。未增加盲测案例，未接触官方服务，不宣称官方成绩。

官方逐局字段平均定位清除时间=本局总虚拟耗时/本局清除数；跨局使用算术均值。没有把源总数聚合后的总时间/总源数混称为该均值，也没有加入自造加权评分。原始行检查同时核对ID集合、完整清除、正常退出、异常字段和每局分母。

## 分组结果

|集|Q4局数|基线秒/源|候选秒/源|差值|
|---|---:|---:|---:|---:|
|combined|2400|455.434476|453.727488|-1.706988|
|v1|1200|451.900782|450.382326|-1.518456|
|previous_final|1200|458.968171|457.072650|-1.895521|

|已暴露合并场景|局数|基线秒/源|候选秒/源|差值|
|---|---:|---:|---:|---:|
|cell500_shared_field|200|457.143453|455.529867|-1.613586|
|cell50_shared_field|200|458.388124|455.539895|-2.848228|
|edge_mixed_min_radius|200|502.907455|501.796173|-1.111282|
|exactly10_sources|200|586.989218|585.565996|-1.423221|
|exactly16_sources|200|309.587250|306.195810|-3.391440|
|fixed_negative_bias|200|459.693859|458.960303|-0.733556|
|fixed_positive_bias|200|461.144706|459.886524|-1.258182|
|minimum_radius|200|473.710548|472.552064|-1.158485|
|offcenter_cluster|200|404.654026|404.033319|-0.620708|
|origin_cluster|200|433.235436|431.191544|-2.043891|
|reference_assumed|200|458.893878|456.534394|-2.359484|
|smooth_shared_field|200|458.865761|456.943966|-1.921795|

## 算法与迁移边界

1. 保留A2原始认证发现路线与一次统一旋转。新增六边Voronoi光学cover，与原square及两种相位、四种角度之间选整份完整cover；失败clear只能通过凸片全部顶点认证排除格。
2. 从同批A1迁移完整2/3/多盘服务操作符，再适配Q4。将保守凸定位域分成闭凸条，每条认证能在20米内清除；固定点集的首次命中期望费用由子集DP计算。保留者还扩大可用盘数；数量与门槛见快照。
3. 规划分布、可见概率和standoff只做动作选择，不当成官方真分布，也不代替连续覆盖证明。没有迁移Q3专属的no_signal排除1000米整圆假设。
4. `_protected_clear_plan`包围完整clear列表，防止融合学习组件改写未certified的中间点。守卫异常路径恢复与2400局逐字段一致检查均通过。父协调者负责融合后的独立评测。

完整证明和数值余量见`PROOF.md`。本文没有声称路线全局最优或论文近似界适用于本题。

## 研究来源与实际阅读

实际获取与阅读范围见`literature/READING.md`，涵盖guaranteed IPP、lawn mowing、bearing-only MaxEnt与circle-neighborhood TSP的方法段落。全文保存不等于全文通读；前两项曾在旧工作出现，本次是继续深读而非首次发现。三份A1组件的原路径与散列见`finite_provenance.json`。本分支六边格与连续朝向积分是本题的独立实现，有限光学几何/DP明确归属于A1迁移来源。

## 每轮执行记录

以下都是事后执行审计，不把事后ledger称为预注册。基准列对应实现父候选；是否晋级另按当时最新保留者判断，特别是r8虽然胜过其构造父r6，却未胜过当时保留者r7。

|候选|阶段|Q4局数|秒/源|与实现父差|全清|
|---|---|---:|---:|---:|---|
|route_r1|quick|60|468.063271|+4.169978|True|
|route_r2|quick|60|464.068786|+0.175493|True|
|route_r3|quick|60|461.178429|-2.714864|True|
|route_r3|full|1200|452.099639|+0.198857|True|
|visibility_r1|quick|60|464.032926|+0.139633|True|
|visibility_r2|quick|60|464.032926|+0.139633|True|
|visibility_r3|quick|60|464.281886|+0.388593|True|
|hex_r1|quick|60|463.760353|-0.132940|True|
|hex_r2|quick|60|463.501109|-0.392183|True|
|hex_r2|full|1200|451.830225|-0.070556|True|
|hex_r2|exposed|2400|455.372283|-0.062193|True|
|hex_r3|quick|60|463.599084|+0.097975|True|
|hex_r3|full|1200|451.640781|-0.189444|True|
|hex_r3|exposed|2400|455.166459|-0.205824|True|
|hex_r4|quick|60|463.902104|+0.303020|True|
|hex_r4|full|1200|452.029483|+0.388701|True|
|hex_r5|quick|60|463.806510|+0.207426|True|
|hex_r5|full|1200|451.890742|+0.249960|True|
|hex_r6|quick|60|463.643308|+0.044223|True|
|hex_r6|full|1200|451.627486|-0.013295|True|
|hex_r6|exposed|2400|455.094042|-0.072417|True|
|hex_r7|quick|60|463.728023|+0.084715|True|
|hex_r8|quick|60|463.638671|-0.004636|True|
|hex_r9|quick|60|463.640507|-0.002801|True|
|minradius_r1|quick|60|463.599084|+0.000000|True|
|minradius_r2|quick|60|463.599084|+0.000000|True|
|minradius_r3|quick|60|463.599084|+0.000000|True|
|minradius_r3|full|1200|451.644772|+0.003990|True|
|finite_r1|quick|60|462.322601|-1.320707|True|
|finite_r1|full|1200|451.482324|-0.145162|True|
|finite_r2|quick|60|463.791466|+0.148158|True|
|finite_r3|quick|60|462.688337|-0.954971|True|
|finite_r3|full|1200|450.814512|-0.812974|True|
|finite_r3|exposed|2400|454.297152|-0.796890|True|
|finite_r3_guarded|quick|60|462.688337|+0.000000|True|
|finite_r3_guarded|full|1200|450.814512|+0.000000|True|
|finite_r4|quick|60|462.688337|+0.000000|True|
|finite_r5|quick|60|462.688337|+0.000000|True|
|finite_r6|quick|60|461.645674|-1.042663|True|
|finite_r6|full|1200|450.431483|-0.383028|True|
|finite_r6|exposed|2400|453.890076|-0.407076|True|
|finite_r7|quick|60|463.232289|+1.586615|True|
|finite_r7|full|1200|450.382326|-0.049158|True|
|finite_r7|exposed|2400|453.727488|-0.162588|True|
|finite_r8|quick|60|461.119511|-0.526163|True|
|finite_r8|full|1200|450.329771|-0.101713|True|
|finite_r8|exposed|2400|453.752968|-0.137107|True|
|finite_r9|quick|60|461.971659|+0.325985|True|
|finite_r9|full|1200|450.474475|+0.042992|True|
|finite_r10|quick|60|461.717463|-1.514827|True|
|finite_r10|full|1200|450.432226|+0.049900|True|
|finite_r11|quick|60|462.965161|-0.267128|True|
|finite_r12|quick|60|461.695149|-1.537140|True|

归档31份候选快照（含一次守卫等价修复）；ledger记载Python3.12有效候选执行总计56520局次。这是包含quick/full重复运行的工作量，不是独立案例数；冻结基准缓存不计作本轮推理。最初Python3.9还发生120次worker_crash（0/120完成），原因是冻结环境需要Python3.10+的类型语法；这些全部失败行另记environment_failure_ledger.json并保留，不作性能比较。规则导入失败和未经-S的site启动告警日志也保留，但不纳入成功验证；最终使用Python3.12 -S -B清洁启动。

## 停止与验证

- 执行位置一致路线：最新保留base；连续未晋级route_r1, route_r2, route_r3；停止=True。
- 连续朝向积分：最新保留base；连续未晋级visibility_r1, visibility_r2, visibility_r3；停止=True。
- 六边覆盖portfolio：最新保留hex_r6；连续未晋级hex_r7, hex_r8, hex_r9；停止=True。
- 最小接收半径负信息：最新保留hex_r3；连续未晋级minradius_r1, minradius_r2, minradius_r3；停止=True。
- 完整有限光学计划：最新保留finite_r7；连续未晋级finite_r8, finite_r9, finite_r10；停止=True。

r11/r12只保留澄清停止口径前已经启动的quick结果，没有追加full，不把这些未完成确认的探索候选作为正式保留者。

冻结manifest SHA256：`431210a6d96e721d23c31698aa389702ea87dcffe8fee6250f71ce6e902be140`。最终14项规则/指标单元检查、名义物理校验与manifest校验通过；有限盘DP与3–6点全排列最优代理相符，缺失规划假说守卫通过，连续格/条的实现随机诊断通过。这些采样检查不替代PROOF中的连续推导。

保留者已暴露Q4的本次程序现实时间中位数/P95/最大值为0.105037/0.172711/0.369724秒。现实时间受同时运行任务影响，基准时间为旧缓存，不能据两者声称运行速度加速。没有改通信层，Windows官方通信与正式测试仍未在本分支执行。

所有31份快照都以相同归档BEST_R2为精确前缀；新增后缀AST没有文件/动态执行调用或直接env属性读取。该检查只说明新增代码的静态边界，不宣称Python封装是安全沙箱。完整输出见`results/source_interface_inspection.json`。

## 重现

在隔离仓库根目录执行；所有输出路径应换为新目录。

```sh
python3.12 -S -B evaluate.py --verify-only
python3.12 -S -B evaluate.py --candidate experiments/parallel_v2_a2/snapshots/finite_r7.py --suite full --out /tmp/a2_fresh_full
python3.12 -S -B experiments/20260911_stage4/evaluate_exposed.py --candidate experiments/parallel_v2_a2/snapshots/finite_r7.py --v1-results /tmp/a2_fresh_full --out /tmp/a2_fresh_exposed
python3.12 -S -B experiments/parallel_v2_a2/audit.py
python3.12 -S -B experiments/parallel_v2_a2/build_report.py --winner finite_r7 --stopped
```
