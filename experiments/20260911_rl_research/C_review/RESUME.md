# 当前任务：RL研究 C 评议，2026-09-11

仅执行RL研究任务；旧E1/E2/E3已结束，不再读其resume或运行。当前输出仅为 /Users/t/ai project/数学建模2026/代码/experiments/20260911_rl_research/C_review/。root已要求按顺序重读PROTOCOL.md、PRE_REVIEW.md和source_checks.json，本窗口已完成。用户要求核实后先审阅是否执行；本轮0策略实现、0训练、0环境执行，不做Git提交、不安装软件。

A=/root/audit（A_user_method）核用户CBG-PPO；B=/root/geometry（B_frontier）独立前沿；我=/root/solver为C。B的PROPOSAL.md已有R0，立即阅读后写REVIEW_R1_B.md并直接向geometry发具体修改请求。A初稿随后到，再写REVIEW_R1_A.md。两条路线至少一轮实质修订后写REVIEW_FINAL.md、decision_matrix.json；兼容共同协议另产REVIEW_R1.md索引。root整合供用户审阅。

已完成可复用：PRE_REVIEW.md、review_rubric.json和source_checks.json；7项针对性来源RF、mask、Ng shaping、SB3 Maskable/Recurrent/device、OffRIPP已核，不重查。C7完整候选payload须含route_successor和服务版本，buffer保存采样时候选快照。A纸面49站+每源304光学格兜底虚拟<52000秒已核，5844次measure/clear还需EXIT；现实保证需每请求确定上界，P99不够，返回站必须合法付费，不重发enter。

B首轮重点：4.1 r=-ΔT/T0的Qtarget优化T；4.2仅MC/策略按1/N加权与“TD须检查”等价没有闭合。必须给明确label/target/episode采样权重、argmax含义及N只训练不入actor；也可明确降格为代理目标，不能标已解决。区分硬deadline真失败与采样截断bootstrap；fallback必须在提案中给纸面可执行上界/条件；离线行为支持/C7动作反事实不能自动保证Q可靠；需清晰探索和与PPO同预算。保留C7内合法启发式clear，不能只保留认证clear。

B新消息：C-IDS2602.03939的跨episodecontext设定与regret固定context疑有不一致；Lemma3.6 Eq19仅因episode有限就声称存在通用η使H(C|H)≤I(C;Y|H)/η，H>0/I=0即可反例。B会标证明步骤未核通过，不采用理论保证；本轮不另开证明修复。此前OffRIPP已查Eq4门控端点说明矛盾、表Iexpert不胜teacher且PPO是naiveoffline。

当前窗口01a08fcd-e2df-7162-a56b-6142a1102391。notes/history故障，可使用本RL当前resume恢复。写研究目录需exec_command require_escalated，经正常自动审核，勿改他人目录。

本窗口更新：已完整读B R0，写REVIEW_R1_B.md（B1目标label/target/actor隔离，B2真失败与截断，B3纸面有限fallback，B4行为支持/Q与PPO预算，B5C7合法clear与重复请求例外，B6来源完整），已直接发geometry与root。REVIEW_R1.md索引已写。A尚无PROPOSAL文件，已发正式评议前预提醒。已读本轮COORDINATOR_FINDINGS，无重复旧策略执行。

本窗口后续：A初稿自标R1已在work/rl_research_cache/A/deliverable/PROPOSAL.md全文读（A目标目录复制审核遇阻，正按正确具体目标重试）；C已写REVIEW_R1_A.md并发audit做文稿R2。A1MC/PPO完整归一回报/episode等权求和；A2真terminal/失败label；A3F含absent时alive空≠全F矛盾；A4primitive费用与较早现实deadline；A5建议预算与门槛；A6账本。R1索引已更新。
root特别要求有限-M不等价成功概率优先词典序，已发A/B；最终区分训练代理、硬守卫责任、选择完整性。B准备box4000给fallback<53000，next<2300，RL300000，合计355300；纸面算式已认可，但box不自动覆盖全部C7，须原C7独立对照及wrapper改变报告，已请求A/B统一。
待办：等A R2/B R1实质修订+全部来源账本；分别全文复核后才能REVIEW_FINAL.md/decision_matrix.json。不得把前置review当终评。

后续统一：root总稿草案已统一4000/53000/2300/300000、T0=1000、失败一次-100非词典序，原C7独立与wrapper条件等价；共享512纯C7示范及每算法×初始化1024完整训练局/1M primitive建议上限，具体G0等预算等终稿读取。A拟完整episode MC PPO，仅学习选择器实际抽样决策有logprob，fallback成本并入return不造梯度；B归一MC/TD完整定义。A/B未完成文件修订时不得提前终评。

C已读A/B literature和source_claims当前版本：A29/B21，9个ID重叠，共41去重；两边核心重叠3，14篇至少一方关键正文、27仅扩展（不是全部全文）。根目录合并索引/root已做好。已请求A/B最终PROPOSAL与revision_log落盘后暂稳并通知；C将hash并全文复核，输出REVIEW_FINAL.md和decision_matrix.json。A source_claims旧1.005/52000已提醒同步。root最终总稿在work/rl_research_cache/root/RESEARCH_PROPOSAL_DRAFT.md，本轮已读并反馈原C7不可误称共享新守卫，root已修正。

当前任务已完成：REVIEW_FINAL.md与decision_matrix.json已落盘，13门槛，无未闭合提案定义阻断。C全文复评A-R2/B-R1后，又核最后共同32无进展决策/10000学习请求、A按题晋级、Bfolded tail d1不bootstrap/双计。最终PROPOSAL SHA：A ecdbd154d6373cca1bd9c549df0cf62f87ca3692f3298f6a93799c23e2ee80eb；B444217bdedafaf92fa44364fc6df6dc2bcc67b910b53a34abce75568f33fdddf。revision：A f492df252372a56018b133841609a25ad14603fecea447da99cac03fa055ba5e；B d9180707c8871df6c4dac9e55c2956c4e54675483341d5089952c9e9e6f2691b。已独立核SHA、六个来源JSON可解析、decision13项；已通知root及两位停止正文编辑，由root做manifest交付。
结论仅方案质量可交用户审阅；0策略实现0训练0环境运行，现实界/代码可靠性/学习效果/新颖性仍未验证。没有待跑工作，不再扩展搜索或理论任务。root主稿和交付收尾由其负责。
