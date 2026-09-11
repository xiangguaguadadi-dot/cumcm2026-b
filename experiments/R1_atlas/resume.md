# 恢复入口

研究持续：用户不设优化轮数，R1持续资料支援及方向图增量。读AI_README、RESEARCH_BRIEF、research/adoption_timeline.json和本文件。写入范围仅experiments/R1_atlas；其他树只读。

当前修订已完成并通过校验，等待本次commit/push：60节点，48旧真实轮＋4本阶段冻结轮，945来源；design_parent/retained_best分开，43旧A轮严格双题best从原始均值逐轮复算全部匹配；A2R2保留R0、A6R9保留R7。旧无明确原始next记录为null，B1使用原记录。AI_README首步统一exploration_index→nodes。Mermaid分支TB并有Q3/Q4/启发。脚本refresh_atlas重建，validate_graph检查SHA、分母、DAG、索引及真实决策引用。

当前登记R2R1(c24ed9c)/R2R2(7000ef6)、R3R1(8e814c6)/R3R2(0db9b06)。root已实际复跑S0与审计，读取其冻结证据。刚通知新R3R3(b662fd8)，Q4 474.3294859035642、Q3S0、全4800；下一增量补，父R3R2+A1R8的spatial_next_task，不采route_clear_point；自己的R2仍有两批origin_cluster与533局回退。R2R3已开发完成、全评测进行，commit未到；不得提前登记成功。

第1批3篇核心新文献及迁移备忘完成并发三方。缓存只在research/cache/，PDF/逐页全文/QA图片不提交。DRD2014读1-8/9页；ASR2019v2读1-7/12-13/18-19/22-25；Fullview2013读1/4-11/26-28。literature.json有SHA、原URL和正文边界。同址clear与动态cover此前独立提出，不反向归因新论文。

R2反馈DRD启发R3开发（384fresh案例×4配置）：父239.052514336；至少2/3预测分支可认证clear=257.476365430，补测2916→921且路程升；关闭补测272.182558641；动作费用代理238.980205558（2948补测、1375clear失败，父1439）。要记录一步完成门槛损失中间信息价值；一中心假说+三误差节点，仅规划，不修改真实P；HEC未采纳。

下一检索AAAI2015 Submodular Surrogates for Value of Information（ASR reference14，DOI10.1609/aaai.v29i1.9694），/tmp/r1_voi_page.html为gzip，需解压找PDF。希望为R2找低复杂度DRD代理。Wang2013参考Kasbekar2009 Lifetime and coverage guarantees through distributed...或Carbunar2006 Redundancy and coverage detection可补动态覆盖实现；圆盘覆盖不能直接套未知半平面方向。

网络：web搜索连接失败；curl --noproxy '*' arXiv/PMLR/Crossref/PSU作者实验室可成功，部分站gzip需解压。Python必须/Users/t/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3（3.12）；系统3.9失败。不要传sandbox_permissions。R1新完整任务执行0，只重算既存行。后续依本文件续接。
