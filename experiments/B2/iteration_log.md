## R1：accepted

R1在4800局全部全清且正常退出，Q3逐局保持C0；Q4两批均改善，combined降低0.471296秒/源（0.08769%），按协议刷新B2最佳。仍有389局更慢，收益很小。

- 候选：[r1.py](snapshots/r1.py)，SHA256 `0907ecbf2d37d8f6ba429b24edcd42b2284f443fb1fafd538065522be42639fc`。
- 全部4800局完整：True；四批次指标如下，均为已暴露回归。

|批次|题|C0秒/源|候选秒/源|差值|快/同/慢|
|---|---|---:|---:|---:|---|
|combined|Q3|271.054981087|271.054981087|+0.000000000|0/2400/0|
|combined|Q4|537.452218555|536.980922068|-0.471296487|845/1166/389|
|v1|Q3|270.531504612|270.531504612|+0.000000000|0/1200/0|
|v1|Q4|534.426811491|533.875864411|-0.550947080|422/579/199|
|previous_final|Q3|271.578457561|271.578457561|+0.000000000|0/1200/0|
|previous_final|Q4|540.477625619|540.085979726|-0.391645894|423/587/190|

四个分批/分题的所有场景：

|批次|题|场景|C0|候选|差值秒/源|
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
|v1|Q4|cell500_shared_field|535.379477|534.449585|-0.929892|
|v1|Q4|cell50_shared_field|535.283874|534.540615|-0.743259|
|v1|Q4|edge_mixed_min_radius|582.762511|582.417717|-0.344795|
|v1|Q4|exactly10_sources|673.865203|673.107573|-0.757630|
|v1|Q4|exactly16_sources|419.145651|418.813761|-0.331890|
|v1|Q4|fixed_negative_bias|533.864735|533.538026|-0.326709|
|v1|Q4|fixed_positive_bias|536.567679|536.487015|-0.080664|
|v1|Q4|minimum_radius|555.005686|554.888881|-0.116806|
|v1|Q4|offcenter_cluster|487.657690|488.513194|+0.855504|
|v1|Q4|origin_cluster|485.782943|483.606702|-2.176241|
|v1|Q4|reference_assumed|534.190736|533.316789|-0.873947|
|v1|Q4|smooth_shared_field|533.615552|532.830514|-0.785038|
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
|previous_final|Q4|cell500_shared_field|543.818907|543.389171|-0.429736|
|previous_final|Q4|cell50_shared_field|543.940867|543.570395|-0.370472|
|previous_final|Q4|edge_mixed_min_radius|586.748077|586.702874|-0.045203|
|previous_final|Q4|exactly10_sources|667.061044|666.788814|-0.272230|
|previous_final|Q4|exactly16_sources|416.600696|416.339595|-0.261101|
|previous_final|Q4|fixed_negative_bias|545.681594|545.126611|-0.554982|
|previous_final|Q4|fixed_positive_bias|545.528452|544.637201|-0.891252|
|previous_final|Q4|minimum_radius|563.835529|563.569760|-0.265769|
|previous_final|Q4|offcenter_cluster|484.840453|484.213728|-0.626725|
|previous_final|Q4|origin_cluster|500.141714|499.774652|-0.367062|
|previous_final|Q4|reference_assumed|543.133965|542.913022|-0.220943|
|previous_final|Q4|smooth_shared_field|544.400209|544.005935|-0.394274|

全部单局退步保存在[r1_regressions.json](results/r1_regressions.json)，原始4800行完整保留；最大退步前五局：
- LOCAL-v1-q4-offcenter_cluster-5067：+72.266464 秒/源。
- LOCAL-final-q4-origin_cluster-1084679581：+66.228749 秒/源。
- LOCAL-v1-q4-fixed_positive_bias-5042：+56.678723 秒/源。
- LOCAL-v1-q4-offcenter_cluster-5097：+53.812142 秒/源。
- LOCAL-v1-q4-offcenter_cluster-5094：+28.113208 秒/源。


## R2：rejected

R2全部4800局全清，但Q4 combined为537.220816363，比R1慢0.239894294秒/源；两批均比R1慢。非凸区域保留正确，凸碎片覆盖增加停点与失败尝试，保留负结果并回退R1。

- 候选：[r2.py](snapshots/r2.py)，SHA256 `9797d0681973db1652886cb4b3e847dbf7ada8bd94206b68b09f7dcb8a14d0da`。
- 全部4800局完整：True；四批次指标如下，均为已暴露回归。

|批次|题|C0秒/源|候选秒/源|差值|快/同/慢|
|---|---|---:|---:|---:|---|
|combined|Q3|271.054981087|271.054981087|+0.000000000|0/2400/0|
|combined|Q4|537.452218555|537.220816363|-0.231402193|697/1166/537|
|v1|Q3|270.531504612|270.531504612|+0.000000000|0/1200/0|
|v1|Q4|534.426811491|534.019974475|-0.406837016|361/579/260|
|previous_final|Q3|271.578457561|271.578457561|+0.000000000|0/1200/0|
|previous_final|Q4|540.477625619|540.421658250|-0.055967369|336/587/277|

四个分批/分题的所有场景：

|批次|题|场景|C0|候选|差值秒/源|
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
|v1|Q4|cell500_shared_field|535.379477|535.089202|-0.290275|
|v1|Q4|cell50_shared_field|535.283874|534.704147|-0.579727|
|v1|Q4|edge_mixed_min_radius|582.762511|582.521785|-0.240726|
|v1|Q4|exactly10_sources|673.865203|673.336043|-0.529160|
|v1|Q4|exactly16_sources|419.145651|418.654318|-0.491333|
|v1|Q4|fixed_negative_bias|533.864735|533.479851|-0.384884|
|v1|Q4|fixed_positive_bias|536.567679|535.821962|-0.745718|
|v1|Q4|minimum_radius|555.005686|554.803949|-0.201737|
|v1|Q4|offcenter_cluster|487.657690|488.602898|+0.945208|
|v1|Q4|origin_cluster|485.782943|484.406647|-1.376296|
|v1|Q4|reference_assumed|534.190736|533.781555|-0.409181|
|v1|Q4|smooth_shared_field|533.615552|533.037338|-0.578214|
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
|previous_final|Q4|cell500_shared_field|543.818907|543.649724|-0.169183|
|previous_final|Q4|cell50_shared_field|543.940867|543.757451|-0.183416|
|previous_final|Q4|edge_mixed_min_radius|586.748077|586.725644|-0.022433|
|previous_final|Q4|exactly10_sources|667.061044|666.977037|-0.084007|
|previous_final|Q4|exactly16_sources|416.600696|417.268664|+0.667968|
|previous_final|Q4|fixed_negative_bias|545.681594|545.261178|-0.420416|
|previous_final|Q4|fixed_positive_bias|545.528452|545.801078|+0.272626|
|previous_final|Q4|minimum_radius|563.835529|563.875841|+0.040312|
|previous_final|Q4|offcenter_cluster|484.840453|484.389032|-0.451421|
|previous_final|Q4|origin_cluster|500.141714|499.882870|-0.258845|
|previous_final|Q4|reference_assumed|543.133965|543.211064|+0.077100|
|previous_final|Q4|smooth_shared_field|544.400209|544.260316|-0.139893|

全部单局退步保存在[r2_regressions.json](results/r2_regressions.json)，原始4800行完整保留；最大退步前五局：
- LOCAL-final-q4-exactly16_sources-961968415：+73.452681 秒/源。
- LOCAL-v1-q4-offcenter_cluster-5067：+72.479255 秒/源。
- LOCAL-final-q4-origin_cluster-1084679581：+69.557195 秒/源。
- LOCAL-v1-q4-offcenter_cluster-5097：+55.149266 秒/源。
- LOCAL-final-q4-fixed_positive_bias-1272768060：+49.108328 秒/源。


## R3：accepted

R3在4800局全部全清且正常退出，Q3逐局保持C0；Q4两批均优于R1，combined为536.872676238，较R1减少0.108245831秒/源，较C0减少0.579542318秒/源（0.107831%）。按协议刷新最佳并进入延长；仍288局比C0更慢，收益很小。

- 候选：[r3.py](snapshots/r3.py)，SHA256 `d32722be8143b5a048d1ab7b4d130721ce478bc065f782aa88b940bbe496bb62`。
- 全部4800局完整：True；四批次指标如下，均为已暴露回归。

|批次|题|C0秒/源|候选秒/源|差值|快/同/慢|
|---|---|---:|---:|---:|---|
|combined|Q3|271.054981087|271.054981087|+0.000000000|0/2400/0|
|combined|Q4|537.452218555|536.872676238|-0.579542318|946/1166/288|
|v1|Q3|270.531504612|270.531504612|+0.000000000|0/1200/0|
|v1|Q4|534.426811491|533.715144321|-0.711667170|468/579/153|
|previous_final|Q3|271.578457561|271.578457561|+0.000000000|0/1200/0|
|previous_final|Q4|540.477625619|540.030208154|-0.447417465|478/587/135|

四个分批/分题的所有场景：

|批次|题|场景|C0|候选|差值秒/源|
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
|v1|Q4|cell500_shared_field|535.379477|534.028275|-1.351202|
|v1|Q4|cell50_shared_field|535.283874|534.395604|-0.888269|
|v1|Q4|edge_mixed_min_radius|582.762511|582.465935|-0.296576|
|v1|Q4|exactly10_sources|673.865203|673.011020|-0.854183|
|v1|Q4|exactly16_sources|419.145651|419.054818|-0.090833|
|v1|Q4|fixed_negative_bias|533.864735|533.380682|-0.484053|
|v1|Q4|fixed_positive_bias|536.567679|535.720283|-0.847397|
|v1|Q4|minimum_radius|555.005686|554.778099|-0.227587|
|v1|Q4|offcenter_cluster|487.657690|488.220647|+0.562957|
|v1|Q4|origin_cluster|485.782943|483.564725|-2.218218|
|v1|Q4|reference_assumed|534.190736|533.247034|-0.943702|
|v1|Q4|smooth_shared_field|533.615552|532.714609|-0.900943|
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
|previous_final|Q4|cell500_shared_field|543.818907|543.325984|-0.492923|
|previous_final|Q4|cell50_shared_field|543.940867|543.472286|-0.468581|
|previous_final|Q4|edge_mixed_min_radius|586.748077|586.666099|-0.081978|
|previous_final|Q4|exactly10_sources|667.061044|666.712193|-0.348852|
|previous_final|Q4|exactly16_sources|416.600696|416.299774|-0.300922|
|previous_final|Q4|fixed_negative_bias|545.681594|545.018540|-0.663054|
|previous_final|Q4|fixed_positive_bias|545.528452|545.031106|-0.497347|
|previous_final|Q4|minimum_radius|563.835529|563.493887|-0.341642|
|previous_final|Q4|offcenter_cluster|484.840453|483.889831|-0.950622|
|previous_final|Q4|origin_cluster|500.141714|499.715932|-0.425783|
|previous_final|Q4|reference_assumed|543.133965|542.812837|-0.321128|
|previous_final|Q4|smooth_shared_field|544.400209|543.924031|-0.476178|

全部单局退步保存在[r3_regressions.json](results/r3_regressions.json)，原始4800行完整保留；最大退步前五局：
- LOCAL-v1-q4-offcenter_cluster-5067：+72.266464 秒/源。
- LOCAL-final-q4-origin_cluster-1084679581：+66.639982 秒/源。
- LOCAL-v1-q4-offcenter_cluster-5097：+53.615111 秒/源。
- LOCAL-final-q4-fixed_positive_bias-1272768060：+48.839268 秒/源。
- LOCAL-v1-q4-offcenter_cluster-5094：+27.451164 秒/源。


