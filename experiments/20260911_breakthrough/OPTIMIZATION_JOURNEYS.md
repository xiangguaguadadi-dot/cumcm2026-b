# 四位研究者的优化演变记录

本页是第二阶段研究路径的入口。候选尚在研究，不将设想写成已取得的效果。每位自行选择方向；这里记录其报告的阶段选择，不给四人预分算法路线。

## 共同起点

上一阶段六条路线、43轮正负结果、文献阅读与实现映射、组件消融、旧最终验证和独立审计均可共享阅读。两批共4800个案例从本阶段起属于已知研发数据。

强对照C0按题选择上一轮最佳：第三问A1 R8、第四问A4 R6。已实际复跑4800局，全部全清，与父方法15项任务字段逐项相同；它本身不计作新算法成果。记录见[对照核验](baseline/equivalence/audit.json)。

## 按研究者追踪

各链接指向持续更新的本机研究记录；第四位正在等待并发槽，路径将在实际启动后建立。最终报告会补精确提交版本的仓库链接。

|研究者|阶段性自主判断（未验证）|优化路径|初始计划|
|---|---|---|---|
|B1|将机会补测与路径/可见性决策组合，检验额外信息是否抵得过检测成本|[时间线与分支图](</Users/t/Documents/Codex/2026-09-10/new-chat/work/breakthrough/B1/experiments/B1/optimization_path.md>)|[计划](</Users/t/Documents/Codex/2026-09-10/new-chat/work/breakthrough/B1/experiments/B1/plan.md>)|
|B2|用有几何证书的自适应凸分区覆盖，减少狭长候选区域中的冗余光学停点|[时间线与分支图](</Users/t/Documents/Codex/2026-09-10/new-chat/work/breakthrough/B2/experiments/B2/optimization_path.md>)|[计划](</Users/t/Documents/Codex/2026-09-10/new-chat/work/breakthrough/B2/experiments/B2/plan.md>)|
|B3|研究更紧凑的第四问搜索点和连续覆盖结构|启动后的记录待更新|启动后的计划待更新|
|B4|尚未启动，不预设方向|等待并发槽|等待并发槽|

## 每个节点记录什么

实验前：时间、问题与来源、父版本和散列、候选方案、预计作用、失败条件及接受标准。

实验后：实际代码快照、结果文件、数据角色与分母、时间和计算预算、退步/失败、保留/回退/取舍决定及下一步。将文献原结论、本题设计推断和实测效果分开。图中失败分支不删除，融合连线标注来源，未实测的想法明确标为待验证。

```mermaid
flowchart LR
  Prior["六路线已有代码、全部数据与文献"] --> Read["四位各自阅读并形成判断"]
  Read --> Idea["自主提出新方案 / 深挖 / 融合"]
  Idea --> Before["实验前记录假设与父版本"]
  Before --> Dev["独立开发与组件对照"]
  Dev --> Frozen["冻结候选与完整回归"]
  Frozen --> Keep["保留改善或有价值取舍"]
  Frozen --> Fail["保存失败并回退 / 改方向"]
  Keep --> Idea
  Fail --> Idea
  Keep --> Final["四位定稿后统一新样本检验"]
```

这里呈现的是可复查的设计依据、实验决策和版本演变。共同规则见[开放探索协议](PROTOCOL.md)，最终检验见[预登记计划](FINAL_VALIDATION_PLAN.md)。
