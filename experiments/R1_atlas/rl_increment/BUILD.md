# RL 增量构建器

最终增量已构建并核验，入口为[README.md](README.md)和[index.json](index.json)，结果见[FINAL_BUILD_CHECK.json](FINAL_BUILD_CHECK.json)。主报告引用已绑定最终SHA；第一次未绑定报告的五份生成文件原字节保留在`initial_build_before_report/`。以下“脚本交付”段落描述首次开发时点，运行方法仍适用。

此目录当前交付 `build_increment.py`。最终选择分析齐备后再构建 README、index 和 PPO/Q 节点；脚本不运行 world、fixture、策略、训练或 Git，也不修改 runtime、旧 atlas、AI_README、DIRECTION_MAP 或研究文献状态。

在代码仓库根目录检查输入（不写输出）：

```sh
python3 experiments/R1_atlas/rl_increment/build_increment.py
```

所有可执行模型评估和最终统计保存后生成：

```sh
python3 experiments/R1_atlas/rl_increment/build_increment.py --write
```

可显式传 `--repo-root`、`--execution-root`。默认输出为 `experiments/R1_atlas/rl_increment`；`--out` 只能指向该目录内部的新位置，已存在的生成文件不会覆盖。`index.json` 最后写入，作为整批完成标记。缺失、不一致或尚在变化的输入返回退出码 2，不登记成功增量。

必需输入为 `20260911_rl_execution/analysis/selection_result/selection_summary.json`、`IMPLEMENTATION.md`、注册 plan、selection freeze、三份初始化 complete/manifest/summary、所有已冻结可执行模型的 192 局结果及对应权重。最终主 REPORT 是可选引用：存在时保存构建时散列，不存在时明确标为待协调者写入，避免主报告与图谱相互等待。原 RESEARCH_PROPOSAL 和历史 C7 节点作为只读引用。

24 个计划 checkpoint 位置全部保留。训练因既定预算而未到达的 checkpoint，只能在最终训练摘要和选择分析均明确解释缺失、且没有声称该模型被执行时登记为不可用。其逐题值仍为 null；存在失败的已完成 checkpoint 保留失败 world 和缺失排名均值，不用成功子集替代。

脚本生成：

- `README.md`：两路线逐题门槛、3 初始化 × 4 位置完整矩阵和证据边界。
- `index.json`：2 个学习路线节点、3 个支持性 BC 父记录、C7/BC 父关系和计数说明。
- `nodes/RL_PPO.json`、`nodes/RL_Q.json`：每个 checkpoint 的真实逐题值、失败、完整性门槛、被选状态、对应权重和来源；路线整体晋级门槛与单 checkpoint 门槛分开。
- `source_manifest.json`：当前读取的代码、模型、逐局行、摘要、研究/实现引用路径、字节数和 SHA256。

每题 96 个不同选择 world；同一个 world 的 3 初始化是配对重复测量。24 位置是 2 路线 × 3 初始化 × 4 训练位置，不是 24 优化轮次或 24 独立训练。BC 父分别对应同一初始化；C7 是候选/执行组件及示范源。节点不把原 41 篇文献自动标记为采纳，也不改变其审阅状态。

构建会从保存的逐局指标行复核 ID、失败、分母和逐题均值，并核对应文件散列；不重算 bootstrap、不反序列化 `.pt`、不读取完整轨迹体。完整逐动作证据由 RL execution 的独立 audit 负责。路线门槛与区间复制自最终分析，并核其选择规则、布尔门槛和 96-world 推断口径。

本次脚本交付仅进行语法、命令行和静态导入检查，尚未构建最终增量。入口顶部链接由协调者在资料齐备后另行添加。
