# 恒选teacher包装：冻结v1暴露回归

本次为AGENTS要求的既有回归；不是新的G0 world、选择集、神经模型或官方测试。仅新增teacher_adapter.py，已有core实现/C7/冻结环境未修改。适配器对raw.success=false明确抛异常，避免环境已退出但包装失败被误记通过；正常返回观测coverage_complete。

冻结文件散列执行前后通过，全部core/C7/适配器依赖SHA与manifest一致。适配器SHA：6e68b2eb64cac262ae9b0d3b6a4c4b909598048809022367fb1d50771a2ea679。

|检查|实际执行|结果|接受的业务请求|
|---|---:|---|---:|
|原规则/指标unittest|14方法|14通过；56次调用尝试，含预期拒绝/异常|36|
|nominal公开协议核查|79断言|79通过；129调用尝试|129|
|旧v1 quick|120候选整局|全部正常全清|23901|
|旧v1 full|2400候选整局|全部正常全清|475563|

quick是full子集，120例在两轮重复执行。因此实际候选2520次整局、独特旧案例2400、新world=0。基准2520行只从冻结缓存读取，没有重新执行基准；评测工具输出中的baseline runs不代表新增运行。候选共499464接受请求，连同规则/nominal共499629接受请求、499649调用尝试。全部成本单列，不占新的G0/G1 world额度，也不能隐去请求开销。

|全测题目|案例|源分母/清除|平均秒/源|接受请求|
|---|---:|---:|---:|---:|
|Q3|1200|15550/15550|235.235582543|160368|
|Q4|1200|15550/15550|452.760906820|315195|

这是各局T/N的算术平均，不用源数加权重算另一指标；没有学习模型改进归因。快测计时14.012176秒，全测289.014686秒；与其他进程并行期间的本地运行时间，不用于受控硬件排名。

完整逐案例结果、分组与官方字段同列CSV在quick/和full/；规则stdout/stderr、nominal.json及只读调用计数在本目录。调用量由sys.setprofile观察原LocalEnv函数的call/return，未替换方法或修改冻结文件。final_checks.json为所有原始行再核后的汇总。

重现命令（共享venv Python；输出目录必须新建）：

```bash
python evaluate.py --verify-only
python -m unittest discover -s tests -v
python tests/check_nominal.py --package . --out NEW_NOMINAL.json
python evaluate.py --candidate experiments/20260911_rl_execution/core/teacher_adapter.py --suite quick --out NEW_QUICK_DIRECTORY
python evaluate.py --candidate experiments/20260911_rl_execution/core/teacher_adapter.py --suite full --out NEW_FULL_DIRECTORY
```

当前回归已全部完成，不需重跑；将来重跑须另计执行成本。正式网络/Windows和学习策略最终效果不由这些旧v1结果证明。
