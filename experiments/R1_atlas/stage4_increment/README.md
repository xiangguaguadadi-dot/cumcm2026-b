# 第四阶段方向图增量

先读上一级原有 exploration_index.json，再读本目录 index.json；旧节点与旧结论保留。所有新ID用S4_前缀。关闭开关、原样父法回放和接线检查不计新研究轮次。

completed_stage4_candidate表示已保存4800回归记录且当前候选/依赖身份匹配；发展性变体只列development_effects，未完成部分标pending。失败和场景退步保留，未知清除数不会补成零或成功。均值来自保存的summary，脚本没有重算全量指标或运行策略。

manifest.json保留每个原始文件路径、SHA256和作用。原始文件后续变化时重跑可更新此增量；只以当前index列出的节点为准，脚本不删除先前生成而本次未列出的文件。

脚本移动到repo后仍可显式运行：

`python3 -B atlas_stage4_update.py --repo-root /absolute/repository --write`

优先使用仓库中已合并的experiments/E1_refine、E2_refine、E3_expand；显式--stage4-root时才有原并行目录作为缺失路线的备选。绝对路径保留本次来源，repo_relative_path与href_from_increment用于下载仓库后的定位。
