# RL 证据一致性检查

本轮已由协调者实际完成[完整原始轨迹审计](full_audit_v1/REPORT.md)：12,609份存档全部读取，`consistent_complete`，错误、待完成项和未知成本均为0；192对C7/teacher请求语义及虚拟费用全部相同。本文末尾的“本次交付验证”保留脚本初次开发时点，不代表最终未执行。

`audit_evidence.py` 仅使用 Python 标准库，只读已保存证据。不导入求解器、模拟器、PyTorch 或训练模块；不执行 world、不更新模型、不反序列化 `.pt`、不恢复账本，也不删除或重写原始轨迹。

在 `20260911_rl_execution` 目录运行，使用尚不存在的输出目录：

```sh
python3 verification/audit_evidence.py --metadata-only --out verification/reports/metadata_001
python3 verification/audit_evidence.py --archives --require-complete --out verification/reports/archives_001
```

从其他目录运行时添加 `--root /absolute/path/to/20260911_rl_execution`。不指定 `--out` 时，完整 JSON 写入标准输出。重复核验必须换输出目录；旧报告保留。

## 两层范围

| 范围 | `--metadata-only`（默认） | `--archives` |
|---|---|---|
| 注册 world ID、recipe、split seed 重叠与场景数 | 检查注册文件与逐局索引 | 再逐份对照完整 archive recipe |
| G0/G1 与共享示范 | 检查逐局记录、汇总、预算、文件索引 | 再核终局、逐请求物理费用与原始散列 |
| 三次初始化的共同示范 | 每个 manifest 绑定同一份 512 局账本与摘要；BC 8 遍、Q MC 4 遍 | 读取共享轨迹一次，逐决策核 pure teacher 与在线输入 |
| PPO/Q 训练 | 每算法/初始化最多 1024 局、1,000,000 次调用；逐局成本重加 | 再核账本与 archive 一致性、实际调用与 accepted 事件 |
| Checkpoint | 仅 128/256/512/1024、最多 4 个；索引身份、已完成位置、文件 SHA | 相同；不加载权重内部状态 |
| Q replay | 更新日志只能引用共享示范或本初始化已完成训练局，无重复的 8 条路径 | 相同；数值与策略理由由 `q_diagnostics.py` 另查 |
| 选择评估 | 核 `data/selection_freeze.json`、基线/模型 manifest、每模型 192 局、冻结权重/运行代码 | 再核 archive 的 `frozen_model`、recipe、标签和费用 |
| 在线源数泄露 | 不作完整轨迹结论 | 遍历 snapshot/payload 禁用字段，重建观测可得特征，检查上一宏动作输入为物理秒数，不能包含 T/N reward |

选择布局与实际 runner 对齐：`results/g2_selection/models/<model_id>/` 存 PPO/Q；`results/g2_selection/baselines/<model_id>/` 存 original C7、teacher、greedy、BC。原 C7 保留自身 summary schema，通过 `baseline_primitive_log` 核逐请求费用，不伪造 macro decisions。

完整检查另将 original C7 与 teacher wrapper 在同一选择 world 的接受请求逐条比较 `action/request/response`，只移除 response 的 `real_timestamp_ms`、`remaining_real_duration_s` 两项现实钟字段。虚拟费用、终局标签和实际尝试调用数分别比较，不比较 wall time。192 对齐全后才可能报告 `all_equal`；不足记 `partial_equal`，有差异记 `different`，JSON 保留第一个不同请求。行为差异单列为 warning，不能据此宣称接口等价，也不把合法策略差异混写为原始证据损坏。不重新执行 world。

同一个选择 world 上三个初始化的结果是配对重复测量。报告始终单列 **192 个不同 world、每题 96 个**与实际模型执行次数，不把 3×192 当作独立样本。`known_cost_totals` 按互不重复的阶段累加；不会把选择模型子表与选择汇总再加一次。

## 历史与当前代码来源

原 `g2_plan.json` 保持不变。仅 `runners/common.py` 与 `runners/collect_demo.py` 相对该原计划的修复，且 `runtime_dependency_freeze.json` 明确声明了 orchestration amendment 时，作为已披露历史差异单列。算法、网络、core 和其他计划代码散列仍逐个严格核验；实际训练 common/runner 以每个 initialization manifest 为准。物理规则和场景生成器以 dependency freeze 为准；选择以 selection freeze 为准。这不会将任意新的代码改变自动视为允许。

## 未完成与成本

没有生成的后续 summary、checkpoint 或选择目录记为 `pending`。训练因预留完整 episode 的调用额度而提前结束时，未到达的 checkpoint 记为 `not_reached`，不是伪造四份模型。若 summary 宣称已完成但其必需行缺失，记为不一致。

`*.started.json` 的未完成环境尝试、`pending_update.json`、`interrupted_compute.jsonl` 与无索引完整 archive 单列。预留调用数是上限，不是实测成本；未知值不填零。完整 orphan archive 可在完整检查中读出其已知成本，但脚本不替 runner 修复索引。运行中的文件若改变，报告提示重新在写入结束后核验。

终局失败本身不等于证据不一致：训练或选择的失败行必须保留，汇总会列出失败数。共享纯教师示范和 G0 的成功门槛则明确检查。性能晋级、bootstrap 或排序不在这个脚本中执行。

## 输出和退出码

每次指定 `--out` 产生：

- `audit.json`：完整检查次数、问题、阶段计数、未知成本、实际读取的文件散列。
- `REPORT.md`：短报告。
- `local_only_trajectory_manifest.json`：原始轨迹路径、字节数、压缩/内容 SHA 与 `local_only_trajectory: true`。

轨迹清单中 `digest_status` 明确区分重新读取计算、仅转录原有索引和未读取。原 G0 的 60 份大 JSON 没有逐文件冻结散列，完整检查会补算当前整体 SHA，原始文件保留；新增散列不冒充其执行时已经冻结的散列。

退出码 `0` 表示当前读取范围无一致性错误，可能仍为 `consistent_partial`；`1` 表示不一致；加 `--require-complete` 后，尚未完成或成本仍未知返回 `2`。历史中断计算的实际耗时/步数无法恢复时，严格完整条件不会被自动视作满足。

这是本地、已注册研发证据的核对。散列对照不是独立真实性证明；snapshot 字段及特征重建不是形式化信息流证明；`.pt` 文件散列不是内部 trainer 状态审查。报告不声称 blind final、官方验证或已自动替换 C7。

## 本次交付验证

只进行了语法与命令行入口检查。未在尚未完成的训练/选择结果上执行本脚本，未增加任何环境执行或新测试 world。完整证据检查由协调者在结果保存完成后调用。
