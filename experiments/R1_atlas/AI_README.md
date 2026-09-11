最新第四阶段：先读[stage4_increment/index.json](stage4_increment/index.json)和[第四阶段说明](stage4_increment/README.md)，再按节点读取详情；人工阅读见[STAGE4_PROGRESS.md](STAGE4_PROGRESS.md)。新增39条记录包含11完整候选、14开发节点、13对照及1背景，不能称39个新研究方向。三位共13轮研究，主协调另做3批融合；当前入口与全部4800回归结果见[阶段报告](../20260911_stage4/REPORT.md)。全部是已暴露本地回归，无新增最终留出。

以下保留第三阶段及更早历史读取协议：[FINAL_REPORT.md](FINAL_REPORT.md)。原70节点、48历史＋9第三阶段完整回归及开发/诊断/未实施分型保持不变。

# Agent读取协议

1. 先读exploration_index.json，再按问题选择nodes/<id>.json；无需先载入整张图。DIRECTION_MAP.md供人浏览，第三阶段PROTOCOL.md定义当前研究边界，RESEARCH_BRIEF.md提供新文献。research/graph_validation.json提供枚举与散列检查结论。
2. kind=completed_optimization_round计入48个历史完整轮次；completed_stage3_round另计当前4800全回归轮。development_only是真实开发探索，geometry_development/geometry_diagnostic为几何试验或诊断，均不计全回归轮；unimplemented_direction与cancelled_before_implementation没有策略实验。需要全量场景矩阵、全部边或所有来源清单时再读exploration_graph.json。
3. effects包含当前轮原判定口径；comparison_baseline明确R0或C0。later_validation另载旧final，当时是新样本、当前已暴露。S0只是按题分派，第三阶段比较须对S0。
4. iteration/fusion/derived_from构成DAG。reverts_to只是决策引用，可以逆时，不参与拓扑排序；inspired_by不能冒充代码采纳。parents分清行为父与结构来源，AST差异不是语义等价证明。
5. candidate给精确SHA、提交和路径。六路线旧文件在只读旧工作树；repository_url可回到同一私有仓库的固定提交。sources给每文件散列/行数/实际处理深度，沿source id追溯。
6. 需要进一步判断失败，先取negative_examples与effects中的max_regression_case_id，再打开对应case_metrics.json，必要时在合法独立新样本重跑；图本身没有逐动作新推理。
7. 新文献以literature.json为主，research_updates存具体实现/验证备忘。actual_reading与transfer_boundary分别约束可声称的阅读和迁移保证。
8. 增量节点须有冻结快照、完整结果、真实父关系、失败及预算；保持旧节点的历史决策。只有新增证据后更新，不依据未完成口头进度登记“成功”。

运行scripts/build_graph.py可从列明的只读来源重建首版；它仅写本目录。运行scripts/validate_graph.py做离线结构/散列检查，不运行求解器。

优先读取exploration_index.json，每节点details指向nodes/<id>.json；无需先载入完整所有场景矩阵。design_parent表示设计来源，retained_best_after_round表示当时实际保留最佳，两者不能混淆。refresh_atlas.py依登记表重建历史并合入已冻结第三阶段节点；validate_graph.py验证结果。新论文与先前独立想法的关系存research/adoption_timeline.json，不能反向归因。
