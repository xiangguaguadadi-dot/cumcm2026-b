"""Record source identity and actual reading, not an automatic full-read claim."""
import json,hashlib
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
S=[
('ars','Simple random search provides a competitive approach to reinforcement learning',['Horia Mania','Aurelia Guy','Benjamin Recht'],2018,'arXiv:1803.07055v1','https://arxiv.org/pdf/1803.07055','core','1-12','正文1-3；4.1-4.2方法及比较表；未读完附录与其余统计图','策略学习/参数空间/低维随机方向',
'将完整轨迹回报看作策略参数的黑箱函数；成对扰动估计改进方向，ARS再以回报标准差缩放、归一化状态，并可筛掉弱方向。',
'MuJoCo及LQR实验；正文也强调小样本随机种子评估和超参数造成高方差，静态线性策略并非在所有环境均压倒其他方法。',
'任务时间可作为整局反馈，先训练小而可解释的策略，不必先假定深网必要。',
'直接进入三轮训练器的参数空间采样及物理特征归一化；本实现采用精英保留搜索，不是ARS梯度更新复刻。'),
('dagger','A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning',['Stéphane Ross','Geoffrey J. Gordon','J. Andrew Bagnell'],2011,'AISTATS 2011; arXiv:1011.0686v3','https://arxiv.org/pdf/1011.0686','core','1-7（部分第4节）','细读1-3、算法3.1、定理条件和第5节两项游戏实验；第4节证明只读部分，不宣称证明全复核','策略学习/模仿学习/数据聚合',
'在学习者诱导的状态分布上查询专家标签，将新数据聚合后重新训练；缓解行为克隆只见专家轨迹导致的错误累积。',
'赛车、Mario和OCR；无遗憾界要求损失、专家额外代价等条件，不等价于任务必胜。Mario专家能访问游戏内部状态。',
'必须在每个候选自己的轨迹上计算整局代价，不能只回归基线动作后便宣称提升。',
'作为训练协议启发，未实现DAgger：没有可靠优于基线且不泄漏特权信息的教师；整局直接搜索避开专家标签需求。'),
('attention','Attention, Learn to Solve Routing Problems!',['Wouter Kool','Herke van Hoof','Max Welling'],2019,'ICLR 2019; arXiv:1803.08475v3','https://arxiv.org/pdf/1803.08475','core','1-7','细读模型、掩码和上下文、REINFORCE rollout baseline算法及第5节评测协议/表1；不声称已读25页附录全部','策略学习/组合决策/集合上下文',
'注意力编码点集合，解码器结合当前路线上下文和合法节点mask逐点选择；用冻结的贪心rollout降低REINFORCE方差，并以独立实例更新基线。',
'TSP、VRP、OP、PCTSP，生成20/50/100节点；训练与测试采样/贪心的预算不同，论文也区分精确求解器与学得启发式。',
'同一候选集合的相对关系比只看最近目标更有价值；和当前最佳在同一自建实例配对比较。',
'第2轮观测集合的密度与后续站距离特征、每轮配对开发选择；未移植注意力模型，因为本题源位置未知且节点动态出现，预训练TSP坐标输入越界。'),
('shield','Safe Reinforcement Learning via Shielding',['Mohammed Alshiekh','Roderick Bloem','Rüdiger Ehlers','Bettina Könighofer','Scott Niekum','Ufuk Topcu'],2017,'arXiv:1708.08611v2（读取此2017版本；不额外声称正式录用身份）','https://arxiv.org/pdf/1708.08611','core','1-9,17-18','细读问题、抽象与安全规范、前置/后置shield框架、网格实验；未完整重演合成算法证明','可靠性/符号约束/学习与正确性分离',
'从保守环境抽象和安全自动机构造shield，前置过滤不安全动作或后置纠正动作；安全依赖抽象对真实动力学的保守性。',
'网格、驾驶、Seaquest、水箱；节选网格实验展示合成和学习。不能由奖励惩罚推导绝对安全，规范复杂度会放大shield。',
'学习负责效率，独立解析覆盖负责完整性；不让学得概率提前判定频道不存在。',
'所有轮保留certified_points、run退出证书、cover_polygon和预算切换。没有实现LTL合成，属于设计原则迁移。'),
('es','Evolution Strategies as a Scalable Alternative to Reinforcement Learning',['Tim Salimans','Jonathan Ho','Xi Chen','Szymon Sidor','Ilya Sutskever'],2017,'arXiv:1703.03864v2','https://arxiv.org/pdf/1703.03864','extended','1,3-4','身份、引言、ES算法1/2、镜像扰动/秩变换、策略参数化；未深读全部实验','策略学习/参数空间/演化策略',
'用高斯参数扰动的整局回报估计平滑目标梯度，镜像采样和共享随机数支持并行，排名变换抑制离群回报。',
'MuJoCo与Atari；大量CPU并行的现实加速不等于低样本数，也不提供本题可靠性。',
'动作频率和长时延回报不会阻止参数空间学习；适合既有确定求解器。',
'训练器采用候选参数扰动和整局反馈；未复刻通信噪声表、Adam或大型网络。'),
('ppo','Proximal Policy Optimization Algorithms',['John Schulman','Filip Wolski','Prafulla Dhariwal','Alec Radford','Oleg Klimov'],2017,'arXiv:1707.06347v2','https://arxiv.org/pdf/1707.06347','extended','1,3','身份、引言及第3节裁剪目标公式/解释；未完整阅读实验','策略学习/动作空间/策略梯度',
'以新旧动作概率比与优势函数构造裁剪代理目标，用同批轨迹多轮更新抑制过大策略变化。',
'论文评测机器人控制与Atari；裁剪改善优化稳定性不等于硬约束保证。',
'端到端学习可行但需处理动作混合、信用分配及有效状态表达。',
'未采用：当前低维参数可直接整局搜索，增加actor-critic和动作分布训练的工程预算未获必要性证据。'),
('bo','Practical Bayesian Optimization of Machine Learning Algorithms',['Jasper Snoek','Hugo Larochelle','Ryan P. Adams'],2012,'arXiv:1206.2944v2','https://arxiv.org/pdf/1206.2944','extended','1,3','身份、问题及2.1-2.2 GP/PI/EI/UCB机制；不冒充全文深读','自动搜索/代理模型/高斯过程',
'以GP后验拟合昂贵未知评价函数，EI等采集函数平衡低预测均值和不确定性，决定下一组参数。',
'机器学习超参数调优；平稳核和噪声模型要匹配任务，非光滑策略切换可能不符合易建模假设。',
'搜索本身可自适应集中预算，而非手调看v1结果。',
'未实现GP BO：单局模拟便宜，额外核拟合/采集优化开销与非平滑目标下的必要性不明确。用更简单精英搜索。'),
('pilco','PILCO: A Model-Based and Data-Efficient Approach to Policy Search',['Marc Peter Deisenroth','Carl Edward Rasmussen'],2011,'ICML 2011（PDF首页）','https://mlg.eng.cam.ac.uk/pub/pdf/DeiRas11.pdf','extended','1-3','身份、GP动力学、不确定输入矩匹配和长期策略评价；未读全部实验','策略学习/模型学习/概率动力学',
'学习GP动力学后传播模型及状态不确定性，以近似矩匹配和解析梯度优化长期策略代价。',
'面向连续控制且数据昂贵；概率传播仍受高斯近似与模型偏差约束。',
'本题运动是已知直线和固定速度，未知部分主要是源和固定误差场；不应重复学习已知运动规则。',
'未采用：动力学模型学习解决的核心困难在本题不突出，定向失信号是非连续观测，模型风险需额外校准。'),
('neural_co','Neural Combinatorial Optimization with Reinforcement Learning',['Irwan Bello','Hieu Pham','Quoc V. Le','Mohammad Norouzi','Samy Bengio'],2017,'arXiv:1611.09940v3; 首页为ICLR 2017 under review，不声称正式主会录用','https://arxiv.org/pdf/1611.09940','extended','1,3-4','引言、Pointer Network与REINFORCE目标；未读全部实验与附录','策略学习/组合决策/指针网络',
'把路线表示为点序列，指针网络给出节点分布，用路线长度直接训练；区分跨实例预训练与单实例active search。',
'TSP/背包的图实例有已知坐标或物品值；本题不能在部署时访问真实目标坐标。',
'直接用任务代价训练，比模仿一份并非最优的路线标签更贴合目标。',
'整局直接目标进入训练器；未实现指针网络，亦不在v1上做单实例active search。'),
('gp_sensor','Near-Optimal Sensor Placements in Gaussian Processes: Theory, Efficient Algorithms and Empirical Studies',['Andreas Krause','Ajit Singh','Carlos Guestrin'],2008,'JMLR 9:235-284, 2008','https://www.jmlr.org/papers/volume9/krause08a/krause08a.pdf','extended','1,3-4,6-7','身份、贡献、GP条件方差、非平稳核与熵准则；未完整阅读50页，未核验全部近似定理','主动观测/信息准则/GP传感器选择',
'在候选传感器集合间优化信息指标，利用GP条件方差和互信息结构；强调非平稳相关场对布点的影响。',
'真实温度与降雨数据；子模近似保证依赖其集合目标条件，不自动适用于机器人移动加清除成本。',
'误差相关性和测点几何需纳入开发分布，减少重复同址测量；信息量不是唯一任务目标。',
'训练生成混合有界误差场并保留固定同址误差；未实现GP地图或互信息优化，避免把协方差假设硬套为覆盖证书。')]
records=[]
for id,title,authors,year,version,url,tier,pages,scope,path,mechanism,evidence,inspiration,implementation in S:
 f=BASE/'literature_cache'/f'{id}.pdf'
 records.append(dict(id=id,title=title,authors=authors,year=year,version=version,original_url=url,retrieved_date='2026-09-11',tier=tier,read_pages=pages,actual_reading=scope,identity_verified='original PDF title/authors/version header',source_level='primary',pdf_sha256=hashlib.sha256(f.read_bytes()).hexdigest(),main_path=path,problem=path.split('/')[0],mechanism=mechanism,paper_evidence_and_limits=evidence,inspiration=inspiration,implementation_mapping=implementation,empirical_support='待实际每轮实验完成后在report和round_links中核对',round_links=[],classification_confidence='high'))
obj=dict(cutoff='2026-09-11',scope='以可迁移机制为主的目的性广泛检索，不声称系统覆盖2026全部新文献',core_count=4,extended_count=6,queries=['learning active sensing bearing only target localization policy optimization','learning to optimize cross entropy method direct policy search algorithm configuration','safe reinforcement learning model predictive control shielding safety layer','ARS references -> ES/PPO','attention routing references -> neural combinatorial optimization','GP active sensing vs motion cost'],access_log=['web search tool: connection failed, no snippets used','arXiv PDF direct curl --noproxy: successful; original papers actually read as recorded','PMLR guessed PILCO URL returned 404, replaced with author academic Cambridge PDF','raw PDFs/extracted text excluded from git; URLs, hashes, ranges retained'],papers=records)
(BASE/'literature.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
