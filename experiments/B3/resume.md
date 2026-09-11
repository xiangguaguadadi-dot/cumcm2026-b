# B3 恢复入口

当前R1已完成全部测试和代码提交，代码commit 4aab7c27c791877ac220e3fe78ba7028764d935e；路线还需R2/R3，不能把调度暂停当收敛。

工作树B3、分支experiments/20260911-breakthrough/b3。读本目录report.md、optimization_path.json、best.json和research/coverage_proof.md。R1自包含快照snapshots/r1_solver.py，SHA256 02e845c7638236bd2834c9d2bf5a38a2aedb24515dc4e4e5d361bbc471b4db96。v1与exposed结果在根results/B3_r1_*。R1只改Q4点集，Q3与C0逐局相同，Q4合并524.827144秒/源，相对C0 -2.3491%；边缘场景退步。

新Q4点集为原点+8内环999m+12外环1864m共21点；certificate_21_999_1864.json的11200方格以整数核验连续覆盖。root独立实现审计亦通过。20点初始构型反例全部保留。核心旧报告/文献已完整读，原始记录已程序复算；阅读台账751文件。只对旧论文2211.05891另外阅读PDF第3–5/7–8页。

下一方向：R2在原点扫描后若无任何正观测/清除、且未扫过非原点站，则改用原22点认证结构；有正观测继续21点。两套均完整，不能把Q4 no_signal当距离排除。点数变化21→22后必须同步todo，并保持scanned索引在切换前只有0。需先写实验前记录，独立开发两种方案；不修改R1快照。初始三轮与后续停止规则见协议。

开发脚本development/evaluate_dev.py用冻结生成函数AST只读生成合法12组新种子；seed 33001000–33001011已用，下轮改33002000段；不得碰root之后生成的新最终样本。脚本无需外部工作树运行依赖。共同evaluate_exposed.py的root修正预期带入本分支，勿回退。
