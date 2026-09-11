# 已授权执行：G0/G1与条件性G2

2026-09-11。用户在收到统一审阅稿后明确要求：“你开3个子Agent来执行你这个任务。”这是本轮实施、依赖准备、验证和预算内训练的授权，覆盖旧研究协议中的“等待用户审阅”状态；旧研究文档保持为历史，不改成已执行。用户未要求新Codex任务，使用当前任务内3位子Agent。root负责协调、共同运行时、数据协议、整合评测与Git；三位只写各自目录。

项目：/Users/t/ai project/数学建模2026/代码。先读AGENTS.md、README.md、docs/评测标准_v1.md，以及../20260911_rl_research/RESEARCH_PROPOSAL.md和C_review/decision_matrix.json。当前原C7仍是强对照，solver.py、local_env.py、evaluation/及规则文件不得更改。第一二问不动。此前41篇文献调研不延长；这次要得到真实可复核的实施/验证/实验结果。

## 角色与文件所有权

- geometry：G0共同控制器与证书，独占core/与tests/test_core*.py。C7调度包装、不可变候选payload、事件记录、可观察特征、teacher条件等价、primitive守卫与独立49站/304格兜底。先最小可导入API和schema说明，再完整检查。允许在G0额度内执行自己登记的夹具/案例。
- audit：PPO/BC路线，独占ppo/与tests/test_ppo*.py。依照A-R2实现轻量、完整episode MC masked PPO和BC；先用合成数学夹具检查更新/候选mask/终端/权重，准备对接共同core。G0/G1通过且root协调放行前，不开始真实训练采集。
- solver：约束Q路线及独立数学/终端审计，独占q_learning/与tests/test_q*.py。依照B-R1实现BC支持模型、MC预拟合、同单位Double-Q、候选快照重放与训练专用探索；先数学夹具，准备对接core。G0/G1通过且root协调放行前，不开始真实训练采集。
- root：runtime、共同网络/特征schema协调、data/、runners/、budget、结果整合、主报告和所有Git操作。不得让两位各装依赖或各生成一份“共享”示范。

三位发现独立问题直接互发消息，不得改他人目录或旧阶段E1/E2/E3。每位维护自身RESUME.md，首行写本次rl_execution和自己的当前任务，避免上下文切换后恢复旧研究。仅root提交/推送。

## 共同实现合同

仅接口enter/measure/clear/exit给在线策略信息。源真N只在整局终止后给训练标签与评测，不能进入候选/actor/Q/critic输入/mask/GRU/previous_reward。真实clear success与原始时间增量可读。禁止固定案例/seed/真源坐标/类型/成绩读取。环境接口封装不是恶意反射安全沙箱，但必须做数据流审计。

原C7独立保留；新wrapper内teacher、同候选非学习、BC、PPO、Q共享候选/执行语义。候选含route_successor、服务状态与版本，不可因枚举留下副作用。原C7端点越box或守卫触发时记录wrapper变化，不能静默裁坐标后声称等价。保留合法启发式clear、付费同址复测、幂等传输重试语义。

共同守卫：学习端点box±4000m；独立fallback取53000虚拟秒储备；单学习primitive<2300；学习时间阈值300000；最多10000学习measure/clear，连续32学习调度决策无有效进展则不可逆接管。每primitive前后检查，可中断宏动作，不再enter。49站与304光学格每源保证需数值/接口验证；现实1200秒/25分钟较早截止仅条件性，未知网络确定界不能冒称完成保证。

共同学习单位T0=1000、gamma=1、r=-实际宏动作时间/(1000N)，真实失败终端额外一次-100；这不是词典序数学保证。失败全保留、真实终端不bootstrap。fallback后全部成本进return，折叠完整tail时d=1且不双计；不为确定性fallback伪造PPO logprob。N不重复归一。

首版无Graph Transformer/GRU/IDS/世界模型；轻量共享候选打分网络，容量级别相同。root与core先发布可观察snapshot schema，PPO/Q各自实现可接收该snapshot的selector，不能各发明不同候选。建议执行模式为imperative C7包装+每调度边界selector(snapshot)回调，整局收集实际宏动作序列；若采用其他API，三方先统一再接入。在线snapshot不得包含训练标签。

## 执行门槛和全程预算

G0≤80控制/几何夹具＋40个新独特完整world；同world多策略执行次数与primitive均另计，不伪称新world。G1≤24新独特world且100000primitive先到。root统一world登记，子Agent先声明所需额度，避免相互重复。

G0正确性与G1资源通过后，root在已授权范围内自主继续G2，无需重复请用户批准：共享512纯C7示范（Q3/Q4各256）；PPO/Q各3初始化，每算法每初始化≤1024新训练局或1000000新增primitive先到。Q最早128局受控探索属于该额度。选择192新world（各题96），每模型≤4预登记checkpoint。采集、兜底、重试、重复world执行、选择评估均记录成本。预算含完成储备，不在局中丢弃尾费用掩盖超支。

分题晋级：部署评估全部正常全清；相对原C7和BC配对秒/源至少改善2%，95%配对差区间上界<0，至少2/3初始化同向。选择CI只属选择证据；未过题保留C7。未达到则如实报告、停止扩展，不靠追加Graph/GRU或扩大预算碰结果。G3/G4额外结构、大训练、默认替换、新最终密封验证不在本轮自动扩展范围。旧4800仅暴露回归，必要规则/quick/full依AGENTS执行，不称新盲测或官方结果。

每位完成后交实现、实测检查、运行命令/依赖、逐项剩余限制、结果文件和简短报告；root整合，按既有授权工作流提交推送经检查的代码/结果，排除凭据、官方日志、可执行官方模拟器与论文缓存。
