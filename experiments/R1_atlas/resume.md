# 恢复入口

研究持续：用户不设优化轮数，R1持续资料支援及方向图增量。读AI_README、RESEARCH_BRIEF、research/adoption_timeline.json和本文件。写入范围仅experiments/R1_atlas；其他树只读。

203fe12已push并由root审阅。新一批待本次commit：62节点，48旧真实轮＋6本阶段冻结轮，951来源；index已从196K/5313行压到100K/3105行，只留ALL的7项；节点详情另有相对设计父的完整78格。

当前登记R2R1(c24ed9c)/R2R2(7000ef6)/R2R3(b085676)，R3R1(8e814c6)/R3R2(0db9b06)/R3R3(b662fd8)。R2R3 Q3=236.05265906868271，R3R3 Q4=474.3294859035642；各自另一题S0，未在本节点拼接。6轮候选和两份结果均与冻结Git blob匹配，4800行复算，原43轮真实best/DAG/索引验证通过。R2R3明确由DRD费用概念启发，未实现HEC；DIRECt资料后到。R3R3父R3R2+A1R8，仅spatial_next_task，无route_clear_point；自己的R2仍有两批原点簇及533局回退。

两位R4已开发冻结正跑，不登记为成功。R2R4 SHAd0bda0a5…；R3R4 commit尚未到。R3动态覆盖有限诊断已读未冻结：12旧开发轨迹免费加入全部未来停点，252单删站=2连续证书/96精确分离反例/154未定；不是在线策略、未证明全局不可能。待R3下个commit再登记diagnostic节点，不计完整优化轮。

第1批3篇核心新文献及迁移备忘完成并发三方。缓存只在research/cache/，PDF/逐页全文/QA图片不提交。DRD2014读1-8/9页；ASR2019v2读1-7/12-13/18-19/22-25；Fullview2013读1/4-11/26-28。literature.json有SHA、原URL和正文边界。同址clear与动态cover此前独立提出，不反向归因新论文。

第2批新增AAAI2015 Submodular Surrogates for Value of Information（DOI10.1609/aaai.v29i1.9694）。正文p1–7全部读，p4公式/图1视觉核对，p8参考检视，supp未读。官方PDF缓存research/cache/voi_chen2015.pdf，SHA354fcf5d558c404287797ffa08b0f4ce9868f3a14073cd49748d4adbe8832df0。DIRECt分决策的EC²残边Noisy-OR，给中间进展连续得分；特定构造才有自适应次模，未知先验/空间噪声/动态移动费均未满足迁移理论。第2批备忘已写research_updates/002_intermediate_decision_progress.md并发R2/root；R2计划后续以单中心费用/共享多假说费用/共享DIRECt代理独立消融，目前未实现。

R2R3开发1536行独立复算research/r2_r3_development_recomputed.json：384案例/配置，Q3每配置192；父239.052514336/补测2916；一步cert门槛257.476365430/921；费用238.980205558/2948；关闭272.182558641/0。论文只能提供与负结果一致的解释假设，不能证明退步因果。4核心论文/5版本metadata、页数与SHA验证research/literature_validation.json通过。

下一资料支援可扩大检索非短视VOI的可计算代理或有限发现路线的异质分频道调度；动态coverage目前诊断价值不足，先读两位后续反馈，不空等也不因旧轮数停止。Kasbekar2009与Carbunar2006仍仅发现项，不冒充深读。

网络：web搜索连接失败；curl --noproxy '*' arXiv/PMLR/Crossref/PSU作者实验室可成功，部分站gzip需解压。Python必须/Users/t/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3（3.12）；系统3.9失败。不要传sandbox_permissions。R1新完整任务执行0，只重算既存行。后续依本文件续接。
