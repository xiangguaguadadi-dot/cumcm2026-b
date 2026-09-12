# 实际阅读与迁移边界

本轮重新联网取得3篇一手全文，HTML与SHA256见fetch_manifest.json。web工具两次连接失败，默认沙箱curl无法解析；经授权的网络沙箱提升后成功。只称机制段落阅读，下载全文不等于通读；也不把此前A2已引用过的论文算成首次发现。第3位Agent承担广泛新路线调研，这里聚焦本分支可实现机制。

| 一手来源 | 本轮实际阅读 | 影响本轮设计 | 不可迁移部分 |
|---|---|---|---|
| [Informative Path Planning with Guaranteed Estimation Uncertainty, v3](https://arxiv.org/abs/2602.05198v3) | 引言、III–IV定义、V-D选择/路由边际费用、VI-A评估、VII限制；原始文本原档第1–155及230–330行 | 联合计算移动与动作价值；检查计划路径和实际动作位置偏差。route_r1–r3为本题自己的混合路点代理，不是GCBCover复现 | GP条件方差有限网格证书、核模型与31.6%条件近似界均不适用于本题；论文实验有已收350次pilot观测 |
| [A Closer Cut: Computing Near-Optimal Lawn Mowing Tours](https://arxiv.org/abs/2211.05891) | 摘要/引言、4.1–4.2见证/连续保证、4.3–4.4方法概述；本轮current文本第345–445行深读 | 用连续剖分证书约束格点提速，避免把采样覆盖当成真实保证；hex_r1–r5属于独立格覆盖构造 | 原文是可连续割草闭合巡回，本题停点clear单次收费，不继承原文CETSP下界或近似比；未复现原文SOCP/分支定界 |
| [Maximum Entropy Reweighting for Bearing-Only Sensor Placement](https://arxiv.org/abs/2605.11116v1) | II-B/C的FIM、KL重加权与真实Bayes更新分离，III解释，IV实验/负结果；原档第90–190和current第185–265行 | 严格分离排序分布与真约束，尝试消除朝向离散近似和面积积分误差。visibility_r1–r3为独立连续朝向积分，不是MaxEnt实现 | 原文多传感器8°/15°高斯噪声、RMSE，与本题单移动机±1°固定误差/秒每源不一致；不能把重加权当真实观测缩小可行域 |

最直接新实现为定向朝向半圆端点的精确积分与六边Voronoi光学格。两者没有套用原文保证或实验提升；正确性另见PROOF.md，性能只看真实接口动作全清的同ID结果。

## 本轮跨Agent实现来源

有限2/3/4–6盘操作符来自同批A1新实现的`twodisk_component.py`、`three_disk_component.py`、`multidisk_component.py`，逐文件SHA与原路径见finite_provenance.json。A1已在Q3完整回归验证，不能据此推断Q4效果。这里重新适配Q4接口、成本比较试点、失败点属性和DP覆盖守卫，并实际跑Q4。不是把相同组件重新归为本分支独立原创；几何/DP结构与Q4触发门控分别列明。

## 新补读的圆邻域路线论文

[Robot Path Planning by Traveling Salesman Problem with Circle Neighborhood](https://arxiv.org/abs/2003.06712)，本轮重新下载14页PDF，并实际读第1–8页，重点2.1的访问位置连续变量和2.2的先求离散访问次序/扇区、再优化坐标。此前本仓库仅摘要阅读，本次提升到方法段落。原文用Cplex/Knitro等求解封闭巡回，实验数百至数千秒；不能把其求解器结果的“最优”表述移植为本题全局保证。

迁移假设：MultiDisk先固定所有点朝入场位置standoff，再DP选顺序；选完顺序后，后续落点还有在所属认证小盘内移动的余地。本轮拟做2次“DP顺序→沿顺序逐盘standoff→固定新点重做DP”，保留更小代理成本的完整序列，逐顶点重新认证。本题优化首次命中期望动作费用而非原文闭合巡回长度，因此是独立有界交替启发式，不是原文两阶段算法复现。
