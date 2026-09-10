import json,pathlib
p=pathlib.Path(__file__).resolve().parent
d=json.loads((p/'research/discovery.json').read_text());idx={x['id'].split('/abs/')[-1]:x for x in d['sources']}
rows=[]
def add(aid,tier,read,cls,problem,method,evidence,limits,inspiration,adoption,code=None):
 x=idx[aid];rows.append(dict(id=aid,title=x['title'].replace('\n',' '),authors=x['authors'],year=int(x['published'][:4]),published=x['published'],version=aid.split('v')[-1],status='arXiv原文核验；正式出版状态除特别注明者外未独立核验',url='https://arxiv.org/abs/'+aid,pdf_url='https://arxiv.org/pdf/'+aid,source_level='primary',collection=tier,actual_reading_scope=read,primary_classification=cls,secondary_tags=[],problem=problem,method=method,evidence=evidence,limitations=limits,inspiration=inspiration,implementation=adoption,code_url=code,query=x['query'],access_date='2026-09-11',classification_confidence='high'))
add('2011.10474v2','core','正文PDF第1–3页；第5–6页数值实验、表I与结论；第4页只读部分定理，不声称完整校验全部证明。','状态建模/可见性与无检测似然/多模态粒子贝叶斯',
'带无线电接收机和云台相机的UAV搜寻并跟踪发射目标；方向性相机和低精度RSSI互补。',
'用粒子滤波递归贝叶斯更新位置分布；公式15区分FoV内外、检测/未检测。未检测在FoV内的似然为1−检测概率，FoV外为1；RF与视觉似然相乘。控制平台位置和云台姿态。',
'作者Python合成环境150次、每次100迭代；表I给出RF+V 77%、RF 55%、V 26%、2RF 64%检测成功率。位置/云台固定消融39%和29%。这是移动目标检测比例，不是本题全清时间。',
'RF假设目标总在接收范围，使用可得RSSI、高斯噪声和移动目标模型；本题只给有界示向度，方向性在发射端，不能照搬似然数值。控制代价自己承认纯利用、不显式节能。',
'有/无信号都更新位置、发射方向、接收半径联合假设；不能把无信号直接改成位置排除。RF与光学各有边界，应成本敏感切换。',
[dict(round='R1',functions=['visibility_hypotheses','predicted_visibility','second_point','rescue_bearing'],role='原创简化与迁移：离散位置/方向+解析半径积分，不复现论文粒子运动模型'),dict(round='R2',functions=['rescue_bearing','optical_points'],role='光学清除与RF测向的模态选择启发；R2实施后补实测')])
add('2209.07660v1','core','PDF第1–5页，§III–IV、算法1、ISRS表I与p=1退步说明；第5页Rover设置；未完整阅读第6–8页。','决策规划/多模态动作成本/信念MDP与在线树搜索',
'未知环境中有不同成本/精度传感器，移动和检测共同消耗预算；仅规划移动不够。',
'GP表示环境信念；belief MDP奖励组合任务奖励与近似互信息（协方差迹下降），MCTS-DPW处理连续信念并剪除预算不可行动作。',
'ISRS每格报告50次模拟，比较POMCP、POMCP-GCB、POMCPOW-GCB。原文明确p=1全部好岩石时额外感知反而不如贪心；坏岩石惩罚−10，与前作协议不同。',
'知道岩石坐标、GP空间相关与高斯噪声；互信息不是清除时间。原文负结果说明更多信息可能浪费行动成本，不能照搬总奖励。',
'选择一次RF恢复或一段有限光学覆盖，比较真实移动/5+动作耗时；不无限追求定位信息。',
[dict(round='R1',functions=['rescue_bearing'],role='成本除以预测可见概率的近似排序'),dict(round='R2',functions=['rescue_bearing','optical_points'],role='小集合内切换光学搜索')],code='https://github.com/sisl/SBO_AIPPMS')
add('2603.04867v1','core','PDF第1–3页；§3.1–3.3第7–10页；§5.1及5.1.1第14–15页；§7第19–20页实验设置。抽取含OCR错字，未完整核验SDP公式及全部证明。','可靠性保证/集合成员/保守外包区域',
'从未知但有界误差的距离测量，求保证包含目标的位置集合，而非仅点估计。',
'平方距离方程两两相减消去二次项，构造差分多面体，再与距离球相交形成凸外包；SOCP求方向极值/包围盒，SDP求包围椭球。',
'论文正文自述已被SIAM Journal on Optimization接受，未独立确认最终卷期；二维/三维、3–10锚点、每配置100随机实验、三档相对误差，CVX/Mosek；正文明确未给外包紧度形式保证。',
'观测为距离非示向度，直接移植差分方程不合法；概率近似和内接椭球不保证包住真值。',
'保留全部有界测向多边形作为确定性证据；离散可见性模型永不裁掉这个多边形；小多边形可用保守光学格点覆盖。',
[dict(round='R1–R3',functions=['add_bearing','cover_polygon','run'],role='原版已有集合思想，本路线保留而不冒称新实现'),dict(round='R2',functions=['optical_points'],role='有限覆盖成本可控时提前采用原保证机制')])
add('2606.09188v1','core','PDF第1–5页含§3.1–3.2；§4.1第9–10页与表2；§5第13–15页。未深读§3.3–3.4优化器细节、双机全部图表。','观测几何/主动测向/信息矩阵与轨迹优化',
'单/双UAV对移动目标bearing-only定位，退化交会导致误差大。',
'以FIM评价几何，把det改成logdet，另加双机交会角正弦；改进PSO加入运动约束和粒子归一化。原文承认log是单调变换，不改变正定域内最优点。',
'单UAV100次Monte Carlo；表2中D+PSO中位误差587.97m，S+PSO587.82m，D+IPSO4.94m，S+IPSO4.63m。大部分增益来自改进优化器，不能把99.21%归因于FIM换式。',
'三维移动目标、高斯观测/姿态噪声、10Hz连贯观测；本题二维固定源、行动间不能测、同址误差固定。初始观测不足与突变运动均可能不收敛。',
'候选应保持交会几何；只移动到更可见的同侧并不必然缩小范围，因此不取消横向baseline。消融必须分开，不能只报组合最好。',
[dict(round='R1',functions=['second_point'],role='保留原±横向点，只用可见性改变左右选择；未复现FIM/PSO')])
add('2203.12830v2','extended','PDF第1–2页导言、贡献和相关工作；未深读算法与实验。','决策规划/连续空间规划/信息引导采样树',
'大空间、高维运动约束下预算有限的信息路径规划。','TIGRIS优先采样高信息子空间，奖励计入边的信息；固定翼前向相机案例。','摘要声称较采样基线18.0%，本报告未核验该数值完整实验，不用于本题改善推断。','连续飞行边上可获得信息，本题移动中不能检测；树复杂度与已有22点覆盖相比收益不明。','将回程/后续访问成本考虑入动作，但停止检测点才有观测。',[dict(round=None,functions=[],role='未采用全局采样树；本路线可见性问题更直接，且边观测假设不符')],code='https://github.com/castacks/tigris')
add('1206.6406v1','extended','PDF第1–2页任务定义与导言；仅浏览部分后续段落，不标为深读。','目标定义/主动搜索/任务效用与非短视策略',
'主动搜寻尽量多的正类对象，以及估计正类比例的surveying，区别于模型泛化误差。','贝叶斯决策论定义任务效用；分析多步lookahead与针对特定分类器的精确剪枝。','正文首页标注ICML2012；摘要/导言提出较少短视可以任意优于更短视策略，未完整审计证明。','分类池数据非几何黑盒机器人，查询无本题移动时间，不能直接成为保证或运行成绩。','优化清除任务耗时而非定位均方误差或模型熵。',[dict(round='R1–R3',functions=[],role='决策/评价原则采用；不复现分类器规划器')])
add('2307.00696v1','extended','PDF第1页及第2页开头的系统模型；未深读后半优化器和实验。','覆盖规划/方向调节/群智能离散优化',
'给定目标和定向传感器位置，调整传感器方向提高覆盖率。','离散army-ant群智能算法在有限可选扇区中调整方向。','正文及arXiv元数据可核验IEEE Sensors Letters 6(4), 2022, DOI10.1109/LSENS.2022.3158274；2023上传arXiv。','原文明确不讨论定位与路径；知道目标位置且可控制传感器方向，本题源方向不可控制且位置未知。','扇区几何要显式建模，但不能把本題发射方向当成可调决策变量。',[dict(round=None,functions=[],role='未采用：信息和控制权限不同')])
add('2605.11116v1','extended','PDF第1页摘要/导言；下载了全文但未读后续方法和实验证明。','状态建模/分布重加权/最大熵与D最优设计',
'多源bearing-only传感器放置前，粒子等权可能关注错误区域。','KL最小重加权满足分布准确性约束，再按重加权FIM选传感器位置。','摘要称两个噪声水平、多源模拟；本次没有核验完整表格，不引用提升数。','准确性目标来源与本题未知源是否兼容未核验；不应以主观重加权删除真值可能性。','概率权重仅作调度参考，和确定性支持集合分离。',[dict(round=None,functions=[],role='未采用该重加权方法：所需准确性约束未建立')])
add('2010.13110v1','extended','仅arXiv API元数据及作者摘要；未下载/阅读正文。','覆盖规划/方向调节/多智能体强化学习',
'定向传感器网络中学习协调以改善覆盖。','摘要层面发现多智能体学习路线；不声称掌握全部机制。','仅作者摘要，未验证实验。','本题单机器人，训练与控制对象不同；本路线无训练模型。','学习可作后续竞争路线，但本次以可解释几何模型为主。',[dict(round=None,functions=[],role='未采用：需额外训练分布与保证设计，保留扩展入口')])
add('1512.07332v1','extended','仅arXiv API元数据及作者摘要；未下载/阅读正文。','覆盖规划/重复可见性/平衡k覆盖',
'视觉传感器网络中的平衡重复覆盖。','在方向受限条件下分配覆盖次数，详机制未核验。','摘要发现，未引用论文实验数。','多次覆盖不等于本题发现所有未知定向源的几何证书。','必须区别有限方向采样的覆盖率与对任意源方向的覆盖保证。',[dict(round=None,functions=[],role='未采用：原覆盖证书已可用，改站点需另证')])
out=dict(research_cutoff='2026-09-11',primary_sources=10,core_count=4,extended_count=6,search_queries=d['queries'],retrieval_notes=['web__run连接失败一次，未返回搜索结果；改用arXiv API与PDF直连。','保留逐查询XML和结构化元数据在本地research缓存；下载本身不算阅读。','未检索全部数据库，未宣称覆盖全部文献或SOTA；同论文arXiv版本去重。'],sources=rows)
(p/'literature.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
