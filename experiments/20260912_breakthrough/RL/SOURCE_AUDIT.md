# 来源与证据审计

研究截止与获取日期：2026-09-12。该目录是第六阶段RL**方案交付**，不是算法实现、训练或实验结果包。源码检查和合成公式测试不产生真实任务收益证据。

## 1. 可重算规模

|集合|数量|证据深度|
|---|---:|---|
|本轮去重来源|16|逐条原始身份元数据、一手链接、获取时间、字节数与SHA256|
|核心指定章节阅读|9|S01–S08及S11；方法/实验关键章节，不声称逐页精读所有附录|
|扩展来源|7|S09、S10、S12–S16；阅读范围按条目区分，不能与核心混算|
|与旧41篇同身份|9|S07、S08、S09、S11、S12、S13、S14、S15、S16|
|本轮新增身份|7|S01 DAgger、S02 LOLS、S03 AggreVaTeD、S04 SPIBB、S05 Residual RL、S06 NRPI/AggreVaTe、S10 Multi-step PPI|
|旧稿与本稿身份并集|48|41+16−9；不是48篇全部本轮深读|

结构化账本：[literature.json](literature.json)。逐篇分类/问题/方法/实验/边界：[LITERATURE_MAP.md](LITERATURE_MAP.md)。本轮核心主树与提案第7节同构；扩展论文在同一个机制轴下另有明确主路径，不重复计数。生成器用规范题名匹配保留的旧41条账本，记录每篇旧ID；本轮稳定ID则使用arXiv去版本号或PMLR ID。现有16条均唯一，尚未声称整个文献领域已穷尽。

## 2. 范围、查询与访问边界

围绕旧PPO/Q退步后的新学习对象，主要检索/跟踪概念为：rollout policy improvement、cost-to-go imitation、AggreVaTe/NRPI、LOLS、residual reinforcement learning、safe policy improvement、informative path planning、active sensing、recurrent off-policy、world models、flow Q-learning、information-directed objectives。主要近期窗口是2024-01-01至2026-09-12；为机制来源追溯到2011。

来源取得沿“旧已知核心 → 引文/方法祖先 → 指定一手页面”展开，主要是PMLR出版页、arXiv摘要/正文。搜索访问工具曾不可用，最终使用直连HTTP取得一手页面/PDF；精确成功/失败请求、时间和内容hash见本地 `sources/acquisition.json`。这里的概念清单是检索范围说明，不冒充逐条完整搜索日志；没有完成所有数据库/顶会全量扫描、前向引用普查或首创新颖性证明。

本轮论文代码只记录原文明确指向的链接（例如SPIBB、CAtNIPP、Shielding）；未克隆/训练/复现任何论文仓库。不把项目链接存在说成代码验证通过。S14/S15的项目地址来自本轮摘要，不冒充已审查项目代码。未建立的数据链接明确为空，不代表数据不存在。

## 3. 全文获取与阅读不是一回事

|来源|本轮正文获取|实际使用|
|---|---|---|
|S01–S08、S11|PDF成功|核心指定方法/实验章节；定位详见账本及第4节|
|S09 RF|v1 HTML成功|指定输入/实验章节，保留扩展身份；不以单源RF成功率指导本题算法胜负|
|S10 Multi-step PPI|v1 HTML成功|只读摘要、引言和目录；不援引未读实验数字/证明|
|S12 DyPNIPP|请求HTML v2返回404|本轮仅元数据/摘要；不把旧轮读过等同本轮复读|
|S13 RESeL|请求HTML v3返回404|本轮仅元数据/摘要；404不等于论文全文不存在|
|S14 TD-MPC2、S15 FQL、S16 C-IDS|只请求摘要页|仅元数据/摘要层方法，不新增理论保证或精确效果结论|

全部16篇身份页获取成功；正文请求13次，成功11次、失败2次。下载完整PDF本身不等于全部页已读。PMLR正式出版身份已核；只核arXiv者保留预印本/正式venue未独立核验的表述，不根据页首IEEE字样或旧报告猜测录用。CAtNIPP是CoRL2022、PMLR2023出版，两个年份不混淆。S10于2026-09-03发布，正文明确未经同行评审。不提出Oral、Spotlight或奖项主张。

来源PDF/HTML、提取全文及隔离PDF解析wheel均仅用于本地阅读，已由协调者从Git发布范围排除；可分享的是链接、必要元数据、限量方法摘要和访问审计，不把全文复制进报告。

## 4. 关键主张逐项边界

|本稿主张|原文定位|结论与限制|
|---|---|---|
|DAgger修正学得策略诱导状态分布|[DAgger正文§2–4](https://proceedings.mlr.press/v15/ross11a.html)|动作示范聚合，不自动超过教师；本题改成完整成本差标签|
|AggreVaTe与NRPI的tail不同|[Ross/Bagnell §2、§2.5、§3](https://arxiv.org/abs/1406.5979)|expert cost-to-go与current-policy cost-to-go须区分；窄路反例说明tail重要|
|LOLS混合续局并非处处优胜|[LOLS实验roll-in/roll-out表](https://proceedings.mlr.press/v37/changb15.html)|次优reference依存分析90.2/87.1 UAS；POS中reference tail可更好，不泛化为所有控制任务|
|AggreVaTeD利用可微cost-to-go信号|[AggreVaTeD方法与实验](https://proceedings.mlr.press/v70/sun17d.html)|存在oracle条件；本题C7不当近最优oracle|
|保留解析控制并学习残差|[Residual RL §IV、Fig.3](https://arxiv.org/abs/1812.03201v2)|TD3类连续残差；错位实体块15/20 vs2/20。不是本题服务替换的实测|
|CAtNIPP注意力/LSTM/Pointer/PPO与预算mask已有|[CAtNIPP §4–5、Table1](https://proceedings.mlr.press/v205/cao23b.html)|每预算30实例×10试验；动态信息奖励存在目标偏差；不等价未知多源全清|
|OffRIPP未必超过生成数据的强专家|[OffRIPP Eq.4、Table I](https://arxiv.org/abs/2409.16830)|expert数据预算10的trace：3.73行为、3.96 OffRIPP、7.02 BC；低好。阈值端点表述疑点保留|
|SPIBB安全条件不能直接套本题|[SPIBB §2–4](https://proceedings.mlr.press/v97/laroche19a.html)|有限MDP/数据支持条件与深度实验分开；本题经验裕量不是SPIBB保证|
|Shielding不单独证明最终全清|[Shielding §4–8](https://arxiv.org/abs/1708.08611)|安全规格和环境抽象有前提；liveness需本题有限进展、期限和独立兜底|

没有共同任务、观测协议、训练数据、算力或指标，故没有跨论文SOTA排行榜。论文结果、本题迁移假设、本地旧实验三类证据始终分开；本次未实测新方案，不能把文献数字转成预期2%改善。

## 5. 本地旧结果与本轮测试

旧RL/基线数字来自已有报告和已保存审计，本轮未重新训练或评测。C7的内容hash及继承方法摘录在 `source_methods.json`；后者是读源码辅助，不是对真实`teacher0`/fork实现的运行验收。最新A1/A2对照由协调者最终冻结，提案不能静默只比较旧C7。

本轮实际执行的 [25项合成合同测试](contract_check_results.json)通过：参数/张量算术、归一损失、成本单位/前缀、每分支槽位、near两请求计费、station/source公共结算、未知费用非零、玩具公开状态复制、候选十进制身份、分位秩、事件年龄、world等权、fit/fit_val永久角色、预算算术、未决行保留、玩具分支时钟、单模型打分及16条账本一致性；第二视角后新增空patch也只提交一次、guard/时钟预算恢复、partial station/失败A0保留义务及仅完整返回结算4项夹具。

这些测试不导入solver、模拟器、训练框架或业务API；所有轨迹/事件/得分为构造夹具。**环境任务0、反事实训练分支0、模型更新0。** 通过它们仅说明指定公式和玩具合同自洽，不说明真实G0等价、clone正确、H1余量、闭环收益或100ms目标已通过。

复算命令（从代码目录）：

```bash
python3.12 -S -B experiments/20260912_breakthrough/RL/build_research_artifacts.py
python3.12 -S -B experiments/20260912_breakthrough/RL/run_contract_checks.py
```

`-S -B`用于隔离本机site初始化并避免产生字节码；只用标准库和现有读取材料，不启动环境或拟合。本轮没有新增模型权重、训练数据、Git提交或官方请求。
