# 数学建模2026 B题代码

主要迭代第三、四问；第一问固定，第二问已保存为文档与候选点函数。Python 3.10及以上，仅需标准库。官方Windows模拟器不放入此代码目录。

- `docs/评测标准_v1.md`：与题目/公开协议对齐的指标、计时、分布假设和冻结约定。
- `local_env.py`、`evaluation/`、`evaluate.py`、`tests/`：固定v1环境、2400个具体案例、冻结基准与回归检查。
- `solver.py`：后续修改此求解器；只通过enter、measure、clear、exit读取观测。
- `http_client.py`：Windows官方环境的实际接入入口。
- `docs/第一问_定稿.md`、`docs/第二问_结果与候选区域.md`：前两问的固定结果。

在此目录运行（Windows可能使用`py -3`，Mac可能使用`python3`替代`python`）：

```bash
python -m unittest discover -s tests -v
python evaluate.py --verify-only
python evaluate.py --suite quick --out results/iteration_001_quick
python evaluate.py --suite full --out results/iteration_001_full
```

输出目录必须尚不存在，防止覆盖旧迭代。每次保存逐案例JSON、官方指标同列的本地CSV和分场景汇总。默认复用已验证的基准缓存，快测实际跑120次候选，全测2400次；添加`--rerun-baseline`会分别跑240次或4800次。候选与冻结基准使用相同具体案例和相同误差场。初始两者代码相同，虚拟指标应完全相等。

正常规则79项复核：

```bash
python tests/check_nominal.py --package . --out results/nominal_rerun.json
```

Windows官方模拟器启动并显示接口就绪后：

```bash
python http_client.py --robot-id YOUR_TEAM_ID --mode 3 --log private_logs/q3_client.jsonl
python http_client.py --robot-id YOUR_TEAM_ID --mode 4 --log private_logs/q4_client.jsonl
```

团队身份填写当前登录的真实队号。程序日志只是客户端记录，不能替代官方加密日志。正式测试须按题目要求各做3次，不从本地CSV伪造官方成绩。

每次迭代先检查完整性和失败行，再看虚拟耗时。涉及HTTP、超时或重试的改动须另做通信验证；本地函数模拟器无法验收真实服务端通信。详见评测标准。

GitHub工作流：每次有明确的算法变更并完成快测/全测后，提交候选与对应结果，推送到已确认的项目仓库。不能把未跑过的策略标记为验证通过；不得随策略变更修改冻结评测以改善分数。专用私有仓库：https://github.com/xiangguaguadadi-dot/cumcm2026-b 。首次冻结验证与实测耗时见docs/冻结交付与耗时.md。
