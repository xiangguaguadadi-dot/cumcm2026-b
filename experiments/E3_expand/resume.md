# E3最终状态：实验已收束

仅写experiments/E3_expand；分支experiments/20260911-stage4/e3_expand。
四轮完成：R1共享发现full反转；R2旧机制三权重复测负；R3凸负接收楔形保留；R4首48正、第二96及三门槛全负，按约定收束。无运行session。
R3 SHA7d113e5262d52eaca7e0287ea062e3221b0cadf33340f3536b2b1adbe8f7ec27，早期代码提交03e7be6；Q4 473.620439 vs S1 473.897493，4800全清，Q3逐局相同。融合归root。
预算11952实际执行：开发2112、quick240、full9600；432不同开发例、36seed；另8000几何夹具。无新增留出或官方执行。
finalize_E3.py由保存行生成文档并检查计数，不跑环境；replay_supplemental.py为事后补写入口，只语法检查。勿重跑开发或覆盖原结果。
10条阅读覆盖8线索+2扩展。ICRA2013实际是2012 TR12-006技术报告32页，R3冻结后读指定页，非camera-ready；dames2018是16页书章非期刊。PDF/全文缓存不提交。
当前仅剩检查变更、commit/push并将精确head报告root；完成后无需继续本路线。
