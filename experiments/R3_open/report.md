# R3_open 开放研究报告

2026-09-11。R1已通过4800局完整暴露回归并刷新本路线最佳：Q3与S0逐局相同，Q4由524.827143981降至514.876836277秒/源，改善1.89592%。所有4800局全部清除、正常退出、零异常；每题清除30970/30970个源。不是新留出或官方成绩。

## R1做了什么

S0按题选B1 Q3与B3 Q4，是已知对照。R1在Q4把B1沿途补测与B3原样21个连续认证站合在同一轨迹中；训练/开发进一步比较朴素、可见性与三假说门控。最终Q4单中心预测半径减少乘可见概率达到30米才真实measure；Q3保持B1的60米单中心门控。假想观测只排序，不写入真实多边形。没有把两个父算法历史降幅相加。

原始历史940份文件全字节读取、JSON递归聚合与源码AST检查零错误，304958指标行包含重复和缓存，不能当新增运行或逐轨迹人工复演。报告叙述、文献账本和关键函数单独审阅；旧论文PDF未全部重读。阅读身份见reading_coverage.json。新方向的依据来自历史原始实验和源码结构，未声称复现论文系统。

## 独立训练/开发与组件对照

训练43000000–43000011、开发43001000–43001011；每分割288个完整案例，12场景×12种子×2题。历史结构化记录与源码中的候选种子均无冲突；Q4逐例校验同时有全向、定向。六种配置每分割全部288/288全清，合计3456次执行；训练是方案校准，无学习权重，开发参与选择，均不是留出。

|配置|训练Q3|训练Q4|开发Q3|开发Q4|
|---|---:|---:|---:|---:|
|S0|245.630141449|537.224678519|248.755394147|553.100319846|
|B1|245.630141449|542.080888579|248.755394147|554.837283556|
|naive60|245.630141449|530.852805656|248.755394147|547.451396891|
|visibility60|245.630141449|529.190674882|248.755394147|546.067379603|
|quadrature60|245.630141449|529.219363529|248.755394147|545.871310520|
|visibility30|245.630141449|529.695484648|248.755394147|545.632186079|


可见性门控在这两个新分割均优于朴素融合，支持条件性贡献。三假说、30/60米阈值的排名跨分割变化；训练visibility60最优，开发visibility30最优。按开发最低均值冻结visibility30，完整保存这项选择不稳定性，不能把细小参数差声称稳健理论收益。

## 完整暴露比较

|批次|题|S0秒/源|R1秒/源|降幅|快/同/慢|清除源数|
|---|---|---:|---:|---:|---|---|
|combined|Q3|238.426470616|238.426470616|0.00000%|0/2400/0|30970/30970|
|combined|Q4|524.827143981|514.876836277|1.89592%|1399/115/886|30970/30970|
|v1|Q3|237.932052825|237.932052825|0.00000%|0/1200/0|15550/15550|
|v1|Q4|521.471318659|511.818732674|1.85103%|704/62/434|15550/15550|
|previous_final|Q3|238.920888407|238.920888407|0.00000%|0/1200/0|15420/15420|
|previous_final|Q4|528.182969304|517.934939880|1.94024%|695/53/452|15420/15420|


Q4 886个单局变慢，最大退步162.668230秒/源，案例LOCAL-v1-q4-origin_cluster-5062。分批场景均值退步0个，完整行见下表与results/r1_case_regressions.json。均值改善不表示逐局更快。

|批次|题|场景|S0|R1|差值秒/源|快/同/慢|
|---|---|---|---:|---:|---:|---|
|v1|Q3|cell500_shared_field|245.224248|245.224248|+0.000000|0/100/0|
|v1|Q3|cell50_shared_field|246.391342|246.391342|+0.000000|0/100/0|
|v1|Q3|edge_mixed_min_radius|283.168681|283.168681|+0.000000|0/100/0|
|v1|Q3|exactly10_sources|293.271770|293.271770|+0.000000|0/100/0|
|v1|Q3|exactly16_sources|204.918361|204.918361|+0.000000|0/100/0|
|v1|Q3|fixed_negative_bias|246.899431|246.899431|+0.000000|0/100/0|
|v1|Q3|fixed_positive_bias|246.948263|246.948263|+0.000000|0/100/0|
|v1|Q3|minimum_radius|255.627721|255.627721|+0.000000|0/100/0|
|v1|Q3|offcenter_cluster|183.474890|183.474890|+0.000000|0/100/0|
|v1|Q3|origin_cluster|156.863638|156.863638|+0.000000|0/100/0|
|v1|Q3|reference_assumed|246.356771|246.356771|+0.000000|0/100/0|
|v1|Q3|smooth_shared_field|246.039518|246.039518|+0.000000|0/100/0|
|v1|Q4|cell500_shared_field|520.017162|515.696418|-4.320744|53/2/45|
|v1|Q4|cell50_shared_field|521.059523|515.556738|-5.502785|57/2/41|
|v1|Q4|edge_mixed_min_radius|589.122103|576.534356|-12.587747|68/0/32|
|v1|Q4|exactly10_sources|655.179972|649.618377|-5.561595|51/3/46|
|v1|Q4|exactly16_sources|407.528879|402.156992|-5.371887|54/0/46|
|v1|Q4|fixed_negative_bias|522.635700|516.113992|-6.521708|57/2/41|
|v1|Q4|fixed_positive_bias|518.493981|513.610070|-4.883911|50/2/48|
|v1|Q4|minimum_radius|541.318575|534.712959|-6.605616|60/1/39|
|v1|Q4|offcenter_cluster|464.404548|441.535797|-22.868751|76/18/6|
|v1|Q4|origin_cluster|478.048346|447.160318|-30.888027|66/28/6|
|v1|Q4|reference_assumed|518.918843|514.619778|-4.299065|55/2/43|
|v1|Q4|smooth_shared_field|520.928192|514.508997|-6.419196|57/2/41|
|previous_final|Q3|cell500_shared_field|245.721656|245.721656|+0.000000|0/100/0|
|previous_final|Q3|cell50_shared_field|246.535552|246.535552|+0.000000|0/100/0|
|previous_final|Q3|edge_mixed_min_radius|288.727453|288.727453|+0.000000|0/100/0|
|previous_final|Q3|exactly10_sources|296.139951|296.139951|+0.000000|0/100/0|
|previous_final|Q3|exactly16_sources|203.106336|203.106336|+0.000000|0/100/0|
|previous_final|Q3|fixed_negative_bias|245.378209|245.378209|+0.000000|0/100/0|
|previous_final|Q3|fixed_positive_bias|248.032999|248.032999|+0.000000|0/100/0|
|previous_final|Q3|minimum_radius|255.659553|255.659553|+0.000000|0/100/0|
|previous_final|Q3|offcenter_cluster|185.719646|185.719646|+0.000000|0/100/0|
|previous_final|Q3|origin_cluster|158.768168|158.768168|+0.000000|0/100/0|
|previous_final|Q3|reference_assumed|246.202675|246.202675|+0.000000|0/100/0|
|previous_final|Q3|smooth_shared_field|247.058463|247.058463|+0.000000|0/100/0|
|previous_final|Q4|cell500_shared_field|528.430085|522.946794|-5.483291|55/1/44|
|previous_final|Q4|cell50_shared_field|528.003168|525.954653|-2.048516|51/1/48|
|previous_final|Q4|edge_mixed_min_radius|597.420321|586.403154|-11.017167|68/0/32|
|previous_final|Q4|exactly10_sources|647.444478|643.784053|-3.660424|41/3/56|
|previous_final|Q4|exactly16_sources|410.860333|403.060124|-7.800209|54/0/46|
|previous_final|Q4|fixed_negative_bias|530.014919|523.638247|-6.376672|57/2/41|
|previous_final|Q4|fixed_positive_bias|529.938604|524.565943|-5.372661|48/2/50|
|previous_final|Q4|minimum_radius|545.141080|538.273420|-6.867660|65/0/35|
|previous_final|Q4|offcenter_cluster|478.117330|450.757968|-27.359362|78/17/5|
|previous_final|Q4|origin_cluster|487.053518|450.520203|-36.533315|68/25/7|
|previous_final|Q4|reference_assumed|527.850473|521.701003|-6.149470|60/1/39|
|previous_final|Q4|smooth_shared_field|527.921323|523.613717|-4.307606|50/1/49|


## 可靠性、运行和身份

14项规则、79项正常物理核验、quick120与full2400均通过；同SHA复用full后实跑previous_final2400。11200叶整数连续覆盖证书重新验证通过；移除Q4新增补测时，24个平衡新开发案例与S0的10项任务字段一致（48次实际运行），Q3父源码AST一致。这是有限父行为等价验证，完整回归进一步验证两题。

R1只改变B1的_di_certified_points与默认配置。源码env属性严格只有enter/measure/clear/exit，没有测试ID/seed/scenario读取，部署自包含且仅标准库。统一180000秒切换加跨阈值覆盖、16源有限snake、21站扫描和补测费用，保守合成上界287931秒<360000秒；详细推导research/reliability.md。HTTP未改，没有执行Windows测试。

候选snapshots/r1.py，SHA256 `508ffddc556e4df6a192b30e700463956b54f8b6cc8b96778253d72c0ecea9e8`。完整比较results/r1_exposed、独立复算results/r1_paired_audit.json。执行预算8424次完整任务，5376个不同案例（576新训练开发+4800暴露）；quick与父等价复用案例不增加独立样本量。各批真实时间见execution_budget.json，不能将历史S0现实时间用于机器加速声称。

## 当前决定与后续

接受R1，立即保存提交。没有达到研究饱和，也没有按固定轮数停止。源码发现Q4尚未使用A1的16个互异频道已发现证书停止额外发现扫描，下一步在新的合法开发数据检验这种结构融合；损失补测机会也可能使它变慢。另有实际测点替代冗余覆盖站的证书方向，仍需按频道的证明和开发。

## R2：接受

全部4800局完整清除、正常退出、零异常。候选SHA256 `7d8e3b6be1140b0e42db20fc6c73b4830c98f33775250a35366c83b1410764d7`。

|对照|批次|题|对照秒/源|候选秒/源|变化|快/同/慢|源数|
|---|---|---|---:|---:|---:|---|---|
|S0|combined|Q3|238.426470616|238.426470616|+0.000000000|0/2400/0|30970/30970|
|S0|combined|Q4|524.827143981|502.699446004|-22.127697978|1571/107/722|30970/30970|
|S0|v1|Q3|237.932052825|237.932052825|+0.000000000|0/1200/0|15550/15550|
|S0|v1|Q4|521.471318659|499.029480572|-22.441838087|783/59/358|15550/15550|
|S0|previous_final|Q3|238.920888407|238.920888407|+0.000000000|0/1200/0|15420/15420|
|S0|previous_final|Q4|528.182969304|506.369411435|-21.813557868|788/48/364|15420/15420|
|previous|combined|Q3|238.426470616|238.426470616|+0.000000000|0/2400/0|30970/30970|
|previous|combined|Q4|514.876836277|502.699446004|-12.177390274|418/1975/7|30970/30970|
|previous|v1|Q3|237.932052825|237.932052825|+0.000000000|0/1200/0|15550/15550|
|previous|v1|Q4|511.818732674|499.029480572|-12.789252102|216/979/5|15550/15550|
|previous|previous_final|Q3|238.920888407|238.920888407|+0.000000000|0/1200/0|15420/15420|
|previous|previous_final|Q4|517.934939880|506.369411435|-11.565528445|202/996/2|15420/15420|

|对照|批次|题|场景|对照秒/源|候选秒/源|差值|
|---|---|---|---|---:|---:|---:|
|S0|v1|Q3|cell500_shared_field|245.224248|245.224248|+0.000000|
|S0|v1|Q3|cell50_shared_field|246.391342|246.391342|+0.000000|
|S0|v1|Q3|edge_mixed_min_radius|283.168681|283.168681|+0.000000|
|S0|v1|Q3|exactly10_sources|293.271770|293.271770|+0.000000|
|S0|v1|Q3|exactly16_sources|204.918361|204.918361|+0.000000|
|S0|v1|Q3|fixed_negative_bias|246.899431|246.899431|+0.000000|
|S0|v1|Q3|fixed_positive_bias|246.948263|246.948263|+0.000000|
|S0|v1|Q3|minimum_radius|255.627721|255.627721|+0.000000|
|S0|v1|Q3|offcenter_cluster|183.474890|183.474890|+0.000000|
|S0|v1|Q3|origin_cluster|156.863638|156.863638|+0.000000|
|S0|v1|Q3|reference_assumed|246.356771|246.356771|+0.000000|
|S0|v1|Q3|smooth_shared_field|246.039518|246.039518|+0.000000|
|S0|v1|Q4|cell500_shared_field|520.017162|507.512724|-12.504437|
|S0|v1|Q4|cell50_shared_field|521.059523|507.784324|-13.275199|
|S0|v1|Q4|edge_mixed_min_radius|589.122103|574.279262|-14.842841|
|S0|v1|Q4|exactly10_sources|655.179972|649.618377|-5.561595|
|S0|v1|Q4|exactly16_sources|407.528879|345.449659|-62.079220|
|S0|v1|Q4|fixed_negative_bias|522.635700|508.650747|-13.984953|
|S0|v1|Q4|fixed_positive_bias|518.493981|505.564227|-12.929754|
|S0|v1|Q4|minimum_radius|541.318575|528.355038|-12.963537|
|S0|v1|Q4|offcenter_cluster|464.404548|425.454193|-38.950355|
|S0|v1|Q4|origin_cluster|478.048346|422.903764|-55.144581|
|S0|v1|Q4|reference_assumed|518.918843|506.525901|-12.392942|
|S0|v1|Q4|smooth_shared_field|520.928192|506.255550|-14.672642|
|S0|previous_final|Q3|cell500_shared_field|245.721656|245.721656|+0.000000|
|S0|previous_final|Q3|cell50_shared_field|246.535552|246.535552|+0.000000|
|S0|previous_final|Q3|edge_mixed_min_radius|288.727453|288.727453|+0.000000|
|S0|previous_final|Q3|exactly10_sources|296.139951|296.139951|+0.000000|
|S0|previous_final|Q3|exactly16_sources|203.106336|203.106336|+0.000000|
|S0|previous_final|Q3|fixed_negative_bias|245.378209|245.378209|+0.000000|
|S0|previous_final|Q3|fixed_positive_bias|248.032999|248.032999|+0.000000|
|S0|previous_final|Q3|minimum_radius|255.659553|255.659553|+0.000000|
|S0|previous_final|Q3|offcenter_cluster|185.719646|185.719646|+0.000000|
|S0|previous_final|Q3|origin_cluster|158.768168|158.768168|+0.000000|
|S0|previous_final|Q3|reference_assumed|246.202675|246.202675|+0.000000|
|S0|previous_final|Q3|smooth_shared_field|247.058463|247.058463|+0.000000|
|S0|previous_final|Q4|cell500_shared_field|528.430085|516.514246|-11.915839|
|S0|previous_final|Q4|cell50_shared_field|528.003168|519.397138|-8.606031|
|S0|previous_final|Q4|edge_mixed_min_radius|597.420321|584.095025|-13.325296|
|S0|previous_final|Q4|exactly10_sources|647.444478|643.784053|-3.660424|
|S0|previous_final|Q4|exactly16_sources|410.860333|347.593651|-63.266681|
|S0|previous_final|Q4|fixed_negative_bias|530.014919|517.948468|-12.066451|
|S0|previous_final|Q4|fixed_positive_bias|529.938604|517.706252|-12.232351|
|S0|previous_final|Q4|minimum_radius|545.141080|533.713448|-11.427631|
|S0|previous_final|Q4|offcenter_cluster|478.117330|432.059516|-46.057814|
|S0|previous_final|Q4|origin_cluster|487.053518|430.521510|-56.532009|
|S0|previous_final|Q4|reference_assumed|527.850473|515.157307|-12.693166|
|S0|previous_final|Q4|smooth_shared_field|527.921323|517.942322|-9.979001|
|previous|v1|Q3|cell500_shared_field|245.224248|245.224248|+0.000000|
|previous|v1|Q3|cell50_shared_field|246.391342|246.391342|+0.000000|
|previous|v1|Q3|edge_mixed_min_radius|283.168681|283.168681|+0.000000|
|previous|v1|Q3|exactly10_sources|293.271770|293.271770|+0.000000|
|previous|v1|Q3|exactly16_sources|204.918361|204.918361|+0.000000|
|previous|v1|Q3|fixed_negative_bias|246.899431|246.899431|+0.000000|
|previous|v1|Q3|fixed_positive_bias|246.948263|246.948263|+0.000000|
|previous|v1|Q3|minimum_radius|255.627721|255.627721|+0.000000|
|previous|v1|Q3|offcenter_cluster|183.474890|183.474890|+0.000000|
|previous|v1|Q3|origin_cluster|156.863638|156.863638|+0.000000|
|previous|v1|Q3|reference_assumed|246.356771|246.356771|+0.000000|
|previous|v1|Q3|smooth_shared_field|246.039518|246.039518|+0.000000|
|previous|v1|Q4|cell500_shared_field|515.696418|507.512724|-8.183693|
|previous|v1|Q4|cell50_shared_field|515.556738|507.784324|-7.772415|
|previous|v1|Q4|edge_mixed_min_radius|576.534356|574.279262|-2.255094|
|previous|v1|Q4|exactly10_sources|649.618377|649.618377|+0.000000|
|previous|v1|Q4|exactly16_sources|402.156992|345.449659|-56.707333|
|previous|v1|Q4|fixed_negative_bias|516.113992|508.650747|-7.463245|
|previous|v1|Q4|fixed_positive_bias|513.610070|505.564227|-8.045842|
|previous|v1|Q4|minimum_radius|534.712959|528.355038|-6.357921|
|previous|v1|Q4|offcenter_cluster|441.535797|425.454193|-16.081604|
|previous|v1|Q4|origin_cluster|447.160318|422.903764|-24.256554|
|previous|v1|Q4|reference_assumed|514.619778|506.525901|-8.093877|
|previous|v1|Q4|smooth_shared_field|514.508997|506.255550|-8.253447|
|previous|previous_final|Q3|cell500_shared_field|245.721656|245.721656|+0.000000|
|previous|previous_final|Q3|cell50_shared_field|246.535552|246.535552|+0.000000|
|previous|previous_final|Q3|edge_mixed_min_radius|288.727453|288.727453|+0.000000|
|previous|previous_final|Q3|exactly10_sources|296.139951|296.139951|+0.000000|
|previous|previous_final|Q3|exactly16_sources|203.106336|203.106336|+0.000000|
|previous|previous_final|Q3|fixed_negative_bias|245.378209|245.378209|+0.000000|
|previous|previous_final|Q3|fixed_positive_bias|248.032999|248.032999|+0.000000|
|previous|previous_final|Q3|minimum_radius|255.659553|255.659553|+0.000000|
|previous|previous_final|Q3|offcenter_cluster|185.719646|185.719646|+0.000000|
|previous|previous_final|Q3|origin_cluster|158.768168|158.768168|+0.000000|
|previous|previous_final|Q3|reference_assumed|246.202675|246.202675|+0.000000|
|previous|previous_final|Q3|smooth_shared_field|247.058463|247.058463|+0.000000|
|previous|previous_final|Q4|cell500_shared_field|522.946794|516.514246|-6.432548|
|previous|previous_final|Q4|cell50_shared_field|525.954653|519.397138|-6.557515|
|previous|previous_final|Q4|edge_mixed_min_radius|586.403154|584.095025|-2.308129|
|previous|previous_final|Q4|exactly10_sources|643.784053|643.784053|+0.000000|
|previous|previous_final|Q4|exactly16_sources|403.060124|347.593651|-55.466473|
|previous|previous_final|Q4|fixed_negative_bias|523.638247|517.948468|-5.689779|
|previous|previous_final|Q4|fixed_positive_bias|524.565943|517.706252|-6.859691|
|previous|previous_final|Q4|minimum_radius|538.273420|533.713448|-4.559971|
|previous|previous_final|Q4|offcenter_cluster|450.757968|432.059516|-18.698452|
|previous|previous_final|Q4|origin_cluster|450.520203|430.521510|-19.998693|
|previous|previous_final|Q4|reference_assumed|521.701003|515.157307|-6.543696|
|previous|previous_final|Q4|smooth_shared_field|523.613717|517.942322|-5.671395|

最大单局退步与全部退步明细见results/r2_paired_audit.json。 S0分批场景退步0个；最大单局退步{'case_id': 'LOCAL-v1-q4-fixed_positive_bias-5009', 'mode': 4, 'suite': 'v1', 'group': 'fixed_positive_bias', 'source_count': 14, 'baseline': 427.05181657142856, 'candidate': 499.77061657142855, 'delta': 72.71879999999999}。 previous分批场景退步0个；最大单局退步{'case_id': 'LOCAL-final-q4-exactly16_sources-2070447935', 'mode': 4, 'suite': 'previous_final', 'group': 'exactly16_sources', 'source_count': 16, 'baseline': 433.88042225, 'candidate': 448.226765375, 'delta': 14.346343125000033}。

开发配置完整表：

|配置|训练Q3|训练Q4|开发Q3|开发Q4|
|---|---:|---:|---:|---:|
|R1|220.516179935|482.946765828|236.364881855|515.074430727|
|count|220.516179935|469.150341017|236.364881855|500.550591369|
|count_ready100|220.516179935|471.964200117|236.364881855|508.976969974|

本轮实际任务6696次，累计15120次；新独立开发案例累计1152，暴露案例仍为4800。规则14项、正常物理79项、quick120/full2400和补旧final2400均通过，源审与父等价见r2_source_audit.json。虚拟上界依据research/reliability.md。

下一步：在合法新数据上检验A1全局空间路线与R2的Q4组合，再诊断按频道动态覆盖证书能否减少必访站。
