# A当前任务接续点（R2优先）

本轮唯一任务是核实用户CBG-PPO草案、文献调研、纸面提案与C交叉评议。不实现、不训练、不运行策略环境、不提交Git。root负责统一报告。入口../PROTOCOL.md；不要返回旧E1任务。

2026-09-11：A R2已完成，等待C最终复评；只写A_user_method/，缓存work/rl_research_cache/A/deliverable。正式文件PROPOSAL.md、revision_log.md、literature.json、source_claims.json、taxonomy.md、search_log.json已全部有内容。

A来源29去重/9核心关键正文/20扩展；IRIS准确身份已核（Liu等、PatternRecognition172:112400、DOI10.1016/j.patcog.2025.112400、2026-04），正文仍未得，DQN/Pointer未核。RF2605.12569v1正文VI百分比80.1/76.3已核但异任务/异gamma；v2元数据有记录但未逐页核v2。C-IDS仅引policy-gradient机制，全部证明未核，B对Lemma3.6/Eq19与context条件的疑问不写成证伪。AID2512.02535是diffusion多agentIPP，不冒认AID-RL。

R2实质回应C-R1 A1–A6，详revision_log：F_alive/absent拆分、整体空是不一致；1.005001度；γ1完整episode MC PPO，T0=1000s，失败−100无量纲（非词典序），episode等权内部真实学习决策求和，fallback成本入return且不赋伪logprob；三类terminal/截断明确，无GAE、无shaping。

共同纸面contract：学习box[-4000,4000]^2，49站/304格fallback<52196取53000秒，next primitive<2300，RL虚拟阈值300000，总<355300；现实deadline=min(enter+1200秒,25min窗口)，5844请求+exit费用与确定延迟上界条件。原C7全部恢复动作是否在box及恒选wrapper等价尚未验证，必须独立报告原C7及wrapper差异。

A/B统一建议预算：G0≤80夹具+40新完整局，G1≤24局/100k primitive，G2共享512 C7示范；每算法每3初始化各≤1024新训练局或1M primitive，192选择局每模型≤4 checkpoints。拟零失败、按声称改进的题独立验证相对C7/BC改善≥2%、配对CI上界<0、2/3初始化同向，可只保留通过的Q4分支而Q3用C7；纯待用户批准。A个人优先PPO但同G2与B的Q公平比较。

下一步：通知solver可最终复评并保持文件稳定；仅根据其具体反馈修正研究文件。无本轮实验，不许把用户“核实后审阅是否执行”理解成可跑小原型。
