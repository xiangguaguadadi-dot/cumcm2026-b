# 第三阶段：全历程方向图、新文献与两个开放突破研究者

2026-09-11用户新授权（覆盖第二阶段暂停安排）：再开三个子Agent。第一位查看全部项目进展，制作总方向图，每分支为方向、每节点为一次探索，融合有双亲/多亲边，节点说明做了什么、效果和启发，以AI易读形式保存；完成图后联网检索有价值新文章，尤其帮助当前最佳方法。另两位在当前最佳方法上自由突破，可以读新文献、结合已有方法或创新，不设迭代轮数；等待文献Agent的新材料时也可以独立探索。

## 共用目录和只读历史

主原仓库：/Users/t/ai project/数学建模2026/代码，基点5cebc9650fa45fc24c192ee4a156324c47f7486f。
本轮协调克隆：/Users/t/Documents/Codex/2026-09-10/new-chat/work/stage3/coordinator。
三专属工作树：同级R1_atlas、R2_open、R3_open；分支experiments/20260911-stage3/r1_atlas、r2_open、r3_open。第一位只写experiments/R1_atlas与自用研究资料；两位优化者只写experiments/R2_open或experiments/R3_open及自己的results输出。不可改主solver、冻结数据/环境/测试、别人的文件。所有旧工作树只读，不要恢复旧Agent任务。

先读AGENTS.md、README.md、docs/评测标准_v1.md、experiments/20260911_agent_campaign/REPORT.md、LITERATURE_MAP.md、all_rounds.json、candidate_registry.json、final_validation/comparison.json，以及experiments/20260911_breakthrough/STAGE_REPORT.md、stage_registry.json、OPTIMIZATION_JOURNEYS.md和三份B报告。旧六路线完整工作树索引在旧candidate_registry.json、assignments.json，原题文本为/Users/t/Documents/Codex/2026-09-10/new-chat/work/problem_extracted.txt。所有48轮快照、逐局结果、训练/开发/失败记录和源码可读取、程序化重算，不以读摘要替代全部证据覆盖。记录实际阅读深度、文件行数/SHA、缺项，不把全字节解析称逐轨迹人工复盘。

## 当前最强对照 S0 与诚实比较

S0以已知题号选第三问B1 R1、第四问B3 R1，源码及依赖在experiments/20260911_stage3/baseline/。这只是按题切换，不属于第三阶段新成果。旧C0=Q3 A1 R8/Q4 A4 R6已不是这轮的主基线。

全部4800已暴露局，当前S0合并Q3=238.42647062、Q4=524.82714398秒/源。v1分别237.93205282/521.47131866，previous_final分别238.92088841/528.18296930。每题每批1200局，合并每题2400局。主协调实际复跑并核对父身份，完成后通知。

exposed_cases.json与第二阶段完全相同；v1与previous_final均为已知研发回归，无新最终留出。训练/开发另外生成合法案例，避开所有已用种子并公开记录。建议R2使用42000000起、R3使用43000000起的新种子段；使用前仍要查历史排除冲突，选择方法不能按测试ID/场景/真值分支。第四问每例必须同时含全向与定向源，270个旧全定向压力开发只算诊断，不冒充题设主评测。

冻结evaluate.py先quick120再full2400验证（其历史v1基准只为冻结规则检测，不能替代S0成绩）。然后共同experiments/20260911_stage3/evaluate_exposed.py --candidate ... --out ...完成全部4800，与S0及自身/共同新best逐行比较。自包含相同SHA候选可用--v1-results精确复用v1只补2400旧final。多文件候选须--dependency-manifest明确记录全部部署依赖；若复用v1，其summary必须有deployment_dependencies且与本次绝对路径/SHA逐项一致，否则直接实际跑4800。不要为规避验证而伪造依赖证明。

新helper输出comparisons_to_S0（不是C0），以及可选--previous-rows的comparisons_to_previous。失败、异常、超时、零清除完整保留，不能只对成功局排名。全清且正常退出是效率比较前提。列出每题合并均值、4个分批分题均值、48个分批场景、快同慢、最差局、最大退步和源数分母。两题均不差且至少一题改善才刷新共同最佳；有益取舍另记，不以自造跨题加权分数掩盖退步。

## R1_atlas：总方向图先行，再主动发新文献

交付主要为JSON+Markdown+Mermaid，AI可读、链接稳定，不以图片替代结构化原图。至少覆盖旧六方向43轮和第二阶段5轮；第一二问、初始基准、安全修复与冻结评测可作为有证据的背景节点，B4取消仅列未实施状态，不能虚构实验。每个方向一个分支，迭代边连接节点，融合采用多入边，失败回退引用真实父节点。

推荐exploration_graph.json包含schema_version、directions、nodes、edges、sources、coverage_audit。节点最少包含稳定ID、方向标签/多标签、日期/轮次、真实父版本、探索内容、改动、文献/数据依据、候选路径/SHA/commit、数据角色和各题/分批效果、负例、预算、选择、启发、证据等级、未实现状态和下一候选假设。edges区分iteration、fusion、derived_from、reverts_to、inspired_by；迭代/融合子图按时间有向无环，回退关系允许单独引用。没有证据的融合边写unknown，不从主题相似推断代码采纳。

README导航与DIRECTION_MAP.md给总图和分支详图，AI_README.md说明Agent下次如何读取，兼顾小图可读与全JSON完整。校验48轮没有遗漏/重复、所有节点引用存在、快照/SHA对应、比较基线和数据角色不混淆。保留图生成/检查脚本。图的首版完成立即向root、R2_open、R3_open发送路径和结论，不必等整轮文献完毕。

随后使用automated-research-report技能，基于节点中的未解瓶颈和当前最佳结构联网检索新文章。不是只凑2026年论文；新发现的早年适用文献也可。优先一手论文正文/官方实现，记录搜索词、URL、版本、实际阅读页/节、来源强度、原文问题与保证、本题可实现迁移、验证方案、冲突与负结果。把泛泛相似、可直接试验和真正有保证的机制分开。不要求大量论文；关键材料应具体到能让优化Agent实现实验。新增资料建立literature.json、RESEARCH_BRIEF.md、research_updates/分批备忘。每完成可行动的小批次立即通过collaboration.send_message发给两位，不等全部结束。可在自己的目录接收研究者的反馈并更新总图（通过读取他人已冻结的结果），只读别人目录。

## R2_open 和 R3_open：相同开放任务，不预分配路线

两个研究者收到相同范围，完全自主提出和选择方案；不因为另一人也研究同方向而被迫换题，也不必只融合B1/B3。可深化已有组件、融合、简化、推翻结构、提出新几何或数据驱动方法，亦可联网找新机制。自行判断文献Agent资料是否有用，采纳/拒绝均记录原因。可互发结果/问题，交流不等于必须复制尚未冻结的代码。

用户明确不设迭代轮数。不得套用旧“最多3轮”或“连续2轮未刷新便自动停止”。只要仍有有证据且可执行的有价值方案，应继续；每轮都要完成后记录当前best。若暂时没有可检验的下一方案，先向root解释已排查的瓶颈、负结果与需要的新证据，再自主扩大检索/诊断；最终停止需基于实际研究饱和或用户新指令，不可单因固定轮数、墙钟时间、上下文长度而宣告收敛。

每轮先写optimization_path.md/json的实验前记录，再独立训练/开发和关键组件对照，冻结候选后规则检查、quick、full和4800完整比较。好结果即时commit/push，失败也最终保存。保存所有参数尝试和运行账本，不把多次暴露调参隐成一次。重大融合要有父法/朴素组合/新组件开发对照；区分包效果、组件条件性效果和新样本证据。可以由R1新资料产生下一轮探索，不能空等它才开始工作。

各自experiments/ID/至少维护plan.md、reading_coverage.json、literature.json、idea_log.md、optimization_path.md/json、iteration_log.md、best.json、resume.md、report.md、snapshots、results/与execution_budget.json。每节点写发现问题→依据→方案→预期→实际改变→结果/失败→选择→下一步。记录面向复查的设计和决策摘要，不要求内部逐字思维过程。主协调以后用这些结构化材料更新全历程图。

## 可靠性、运行与保存

推理只读四接口enter/measure/clear/exit，禁止读源真值、测试编号、场景标签、成绩缓存或其他工作树。新增模型/权重或第三方依赖可按用户授权获取，但必须有必要性、开销和可部署身份；优先自包含标准库快照。几何覆盖/定位/退出与100小时虚拟上界要重新合成，不能假定父保证自动穿过任意组合。HTTP/并发/重试更改需独立通信验证。不得启动官方Windows测试。

原冻结规则、第一二问与root solver保持不变。本轮所有实验路径新建，不覆盖旧数据。每次有效结果即时提交并推送自己分支到既有私有仓库xiangguaguadadi-dot/cumcm2026-b，主协调独立核验后整合。用户此前已授权每次迭代上传GitHub，且本轮继续授权提交；不需要反复询问。当前环境无沙箱权限请求，exec_command不可传sandbox_permissions。网络代理必要时git -c http.proxy= -c https.proxy= push origin 专属分支；不改全局代理、不force push、不删分支，不上传凭据/官方身份日志/二进制/PDF大文件。

两位形成最终冻结候选后，主协调登记所有候选与已用种子，再另取未见100种子×12场景×2题=2400局，同S0全量实际比较。新最终数据不反馈调参或事后选新组合；如果继续研发，需另立阶段/新最终集。图和研究报告可依据最终结果更新证据标签，不改历史决策记录。最终交付完整方向图、新文献可行动摘要、两份研究报告及优化路径、原始结果与独立审计。
