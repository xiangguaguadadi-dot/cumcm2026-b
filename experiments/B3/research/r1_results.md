# B3 第1轮完整结果

候选SHA256：`02e845c7638236bd2834c9d2bf5a38a2aedb24515dc4e4e5d361bbc471b4db96`。4800/4800全清、正常退出、无异常，源数分母核对通过。旧v1及上一轮final均为暴露回归。

|批次|题|C0秒/源|候选秒/源|更快/相同/更慢|降幅|
|---|---|---:|---:|---|---:|
|combined|Q3|271.054981087|271.054981087|0/2400/0|0.0000%|
|combined|Q4|537.452218555|524.827143981|1567/0/833|2.3491%|
|v1|Q3|270.531504612|270.531504612|0/1200/0|0.0000%|
|v1|Q4|534.426811491|521.471318659|799/0/401|2.4242%|
|previous_final|Q3|271.578457561|271.578457561|0/1200/0|0.0000%|
|previous_final|Q4|540.477625619|528.182969304|768/0/432|2.2748%|

## 全部24分题场景与两个批次

|批次|题|场景|C0|候选|变化秒/源|
|---|---|---|---:|---:|---:|
|v1|Q3|cell500_shared_field|255.237996|255.237996|+0.000000|
|v1|Q3|cell50_shared_field|255.873313|255.873313|+0.000000|
|v1|Q3|edge_mixed_min_radius|307.565296|307.565296|+0.000000|
|v1|Q3|exactly10_sources|303.872993|303.872993|+0.000000|
|v1|Q3|exactly16_sources|219.210968|219.210968|+0.000000|
|v1|Q3|fixed_negative_bias|257.933154|257.933154|+0.000000|
|v1|Q3|fixed_positive_bias|256.836190|256.836190|+0.000000|
|v1|Q3|minimum_radius|269.697703|269.697703|+0.000000|
|v1|Q3|offcenter_cluster|276.183074|276.183074|+0.000000|
|v1|Q3|origin_cluster|329.443066|329.443066|+0.000000|
|v1|Q3|reference_assumed|256.740757|256.740757|+0.000000|
|v1|Q3|smooth_shared_field|257.783546|257.783546|+0.000000|
|v1|Q4|cell500_shared_field|535.379477|520.017162|-15.362316|
|v1|Q4|cell50_shared_field|535.283874|521.059523|-14.224351|
|v1|Q4|edge_mixed_min_radius|582.762511|589.122103|+6.359592|
|v1|Q4|exactly10_sources|673.865203|655.179972|-18.685231|
|v1|Q4|exactly16_sources|419.145651|407.528879|-11.616772|
|v1|Q4|fixed_negative_bias|533.864735|522.635700|-11.229035|
|v1|Q4|fixed_positive_bias|536.567679|518.493981|-18.073698|
|v1|Q4|minimum_radius|555.005686|541.318575|-13.687111|
|v1|Q4|offcenter_cluster|487.657690|464.404548|-23.253142|
|v1|Q4|origin_cluster|485.782943|478.048346|-7.734597|
|v1|Q4|reference_assumed|534.190736|518.918843|-15.271893|
|v1|Q4|smooth_shared_field|533.615552|520.928192|-12.687359|
|previous_final|Q3|cell500_shared_field|257.745564|257.745564|+0.000000|
|previous_final|Q3|cell50_shared_field|258.699356|258.699356|+0.000000|
|previous_final|Q3|edge_mixed_min_radius|315.131690|315.131690|+0.000000|
|previous_final|Q3|exactly10_sources|305.261377|305.261377|+0.000000|
|previous_final|Q3|exactly16_sources|219.379606|219.379606|+0.000000|
|previous_final|Q3|fixed_negative_bias|258.418994|258.418994|+0.000000|
|previous_final|Q3|fixed_positive_bias|259.317176|259.317176|+0.000000|
|previous_final|Q3|minimum_radius|267.732129|267.732129|+0.000000|
|previous_final|Q3|offcenter_cluster|268.788191|268.788191|+0.000000|
|previous_final|Q3|origin_cluster|331.590097|331.590097|+0.000000|
|previous_final|Q3|reference_assumed|258.451536|258.451536|+0.000000|
|previous_final|Q3|smooth_shared_field|258.425775|258.425775|+0.000000|
|previous_final|Q4|cell500_shared_field|543.818907|528.430085|-15.388823|
|previous_final|Q4|cell50_shared_field|543.940867|528.003168|-15.937699|
|previous_final|Q4|edge_mixed_min_radius|586.748077|597.420321|+10.672245|
|previous_final|Q4|exactly10_sources|667.061044|647.444478|-19.616566|
|previous_final|Q4|exactly16_sources|416.600696|410.860333|-5.740363|
|previous_final|Q4|fixed_negative_bias|545.681594|530.014919|-15.666675|
|previous_final|Q4|fixed_positive_bias|545.528452|529.938604|-15.589848|
|previous_final|Q4|minimum_radius|563.835529|545.141080|-18.694449|
|previous_final|Q4|offcenter_cluster|484.840453|478.117330|-6.723123|
|previous_final|Q4|origin_cluster|500.141714|487.053518|-13.088196|
|previous_final|Q4|reference_assumed|543.133965|527.850473|-15.283492|
|previous_final|Q4|smooth_shared_field|544.400209|527.921323|-16.478886|

## 单局负结果

- v1 Q3 最大配对退步：LOCAL-v1-q3-reference_assumed-5000；309.546165→309.546165，变化+0.000000秒/源。
- v1 Q4 最大配对退步：LOCAL-v1-q4-offcenter_cluster-5016；152.086033→370.211382，变化+218.125348秒/源。
- previous_final Q3 最大配对退步：LOCAL-final-q3-reference_assumed-1047230427；337.066119→337.066119，变化+0.000000秒/源。
- previous_final Q4 最大配对退步：LOCAL-final-q4-origin_cluster-234418089；192.911076→494.580674，变化+301.669598秒/源。

quick新增120局，full新增2400局，exposed复用同SHA的full后新增2400局；本轮暴露任务实际执行4920次，含重复quick子集。墙钟记录分别0.722/13.465/13.194秒。

选择：当前轮满足两题均不差且至少一题改善，更新本路线最佳。单局和场景退步仍保留；不宣称官方或新最终样本收益。
