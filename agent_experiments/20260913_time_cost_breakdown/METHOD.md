# Q3、Q4 平均任务费用五项分解方法

## 数据范围

- 当前方法：B3（`B3_local_refinement.py`）保存的完整 `B3_exposed` 候选行。
- 输入：`experiments/20260913_q2_transfer/B_improved/results/B3_exposed/case_metrics.json`。
- 输入 SHA256：`41cf71a5ed2c8eb2da6fe1d977da3fd32d8e3647aa344d362fcb13c381212702`。
- `最佳方法/实验记录/B_improved/results/B3_exposed/case_metrics.json` 的 SHA256 相同，确认为等价归档副本。
- Q3、Q4 各 2,400 例、30,970 个源；4,800 例全部清除并正常退出。
- 这是已暴露的本地模拟回归数据，不是盲测，也不是官方 Windows 成绩。本次只读已有记录，没有重新运行策略。

## 五项定义

对每个案例分别计算：

\[
T_{\mathrm{move}}=D/5,
\quad T_{\mathrm{bearing}}=5N_m,
\quad T_{\mathrm{switch}}=N_s,
\quad T_{\mathrm{optical}}=3N_c,
\quad T_{\mathrm{laser}}=2N_{\mathrm{success}}.
\]

这里，`D` 是累计移动距离，`N_m` 是测向次数，`N_s` 是测向时频道发生变化的次数，`N_c` 是所有 `clear` 尝试数，包括成功和失败，`N_success` 是成功清除数。`enter` 与 `exit` 不增加虚拟时间。

汇总口径与仓库固定评测一致：先用每例的五项费用分别除以该例成功清除数，再对同一问题的 2,400 个案例取算术平均。不能用全部时间除以全部源数替代，因为后者会按案例源数加权。

## 被评测结果省略的计数如何恢复

`local_env.py` 的 `stats()` 直接累计 `measures`、`switches`、`clear_attempts` 和 `successes`，但 `evaluate.py` 写入 `case_metrics.json` 时只保留 `requests` 与 `clear_failures`。现有字段仍足以唯一恢复：

1. 每行均完整且正常退出，因此包含一次 `enter` 和一次 `exit`；
2. `clear_attempts = cleared_count + clear_failures`；
3. `evaluate.py` 明确定义 `requests = measures + clear_attempts + enter + exit`，所以 `measures = requests - clear_attempts - 2`；
4. `local_env.py` 明确定义总时间为五项之和，并规定频道只在 `measure` 时改变。因此从已知四项中扣除后，剩余量的唯一邻近整数就是 `switches`。

第4步不是无依据地用残差凑数：换频次数按定义是整数，且不得超过测向次数；逐动作计时只会引入微秒舍入差。4,800行的恢复值全部为非负整数且不超过测向数，五项和与保存总时间的最大绝对误差为 `8.237785e-6 s`，远小于 `0.5 s` 的整数唯一性间隔。冻结计时实现及写出逻辑的散列保存在 `provenance.json`。

## 产物

- `chart_data.csv` / `chart_data.json`：绘图所用的“问题×费用项”10行数据及占比。
- `question_summary.csv`：逐题宽表和五项加和结果。
- `per_case_costs.csv`：4,800行逐例计数、费用与核算误差。
- `time_cost_breakdown_q3_q4.svg`：论文可编辑矢量图。
- `time_cost_breakdown_q3_q4.png`：3024×2088高分辨率位图。
- `build_artifacts.py`：从已有记录重建全部数据和图片，不导入或执行求解器。
- `validate.py` / `VALIDATION.json`：独立散列、分母、计数、加和与图片检查。
