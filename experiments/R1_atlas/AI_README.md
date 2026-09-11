# Agent读取协议

1. 先读DIRECTION_MAP.md、第三阶段PROTOCOL.md和RESEARCH_BRIEF.md（出现后）。读取exploration_graph.json的coverage_audit确认枚举完整性。
2. nodes按id访问；kind=completed_optimization_round才计入48轮。background与cancelled节点不能算实验。
3. effects包含当前轮原判定口径；comparison_baseline明确R0或C0。later_validation另载旧final，当时是新样本、当前已暴露。S0只是按题分派，第三阶段比较须对S0。
4. iteration/fusion/derived_from构成DAG。reverts_to只是决策引用，可以逆时，不参与拓扑排序；inspired_by不能冒充代码采纳。parents分清行为父与结构来源，AST差异不是语义等价证明。
5. candidate给精确SHA、提交和路径。六路线旧文件在只读旧工作树；repository_url可回到同一私有仓库的固定提交。sources给每文件散列/行数/实际处理深度，沿source id追溯。
6. 需要进一步判断失败，先取negative_examples与effects中的max_regression_case_id，再打开对应case_metrics.json，必要时在合法独立新样本重跑；图本身没有逐动作新推理。
7. 新文献以literature.json为主，research_updates存具体实现/验证备忘。actual_reading与transfer_boundary分别约束可声称的阅读和迁移保证。
8. 增量节点须有冻结快照、完整结果、真实父关系、失败及预算；保持旧节点的历史决策。只有新增证据后更新，不依据未完成口头进度登记“成功”。

运行scripts/build_graph.py可从列明的只读来源重建首版；它仅写本目录。运行scripts/validate_graph.py做离线结构/散列检查，不运行求解器。
