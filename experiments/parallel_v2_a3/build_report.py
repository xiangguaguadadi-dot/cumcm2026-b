"""Render final local research report and machine-readable round decisions."""
import hashlib,json
from pathlib import Path
H=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
cost=read(H/'execution_ledger.json');audit=read(H/'results/final_paired_audit.json');corpus=read(H/'research/corpus.json')
descriptions={
 'r1':('角残差加权最小二乘直接试清','开发比起点慢2.968889，淘汰'),
 'r2':('真实单次clear反事实标签加30秒失败代理、线性岭门控','开发改善；full保留为中间候选，未独立完成4800'),
 'r3':('以选定频道清除完毕的真实局部回报训练门控','最终残差候选；使用r3_guard安全版本'),
 'r4':('修正WLS多边形内插线搜索后重新采样训练','开发退化，不晋级1'),
 'r5':('用已选R3策略采样，降低教师与部署状态分布差异','未超R3开发，不晋级2'),
 'r6':('在可恢复调度边界分叉、以整局真实秒/源回报训练双头门控','五个校准阈值实际优势均负；未建部署，不晋级3，停止'),
 'b1':('成功clear区域上的21格共享角偏差profile似然','全量改善；使用b1_safe保留保护上下文成功学习'),
 'b2_safe':('共享与各频道独立profile模型证据检验','全量晋级；改名safe是安全修正，不另算优化轮'),
 'b3_safe':('以MAP替代偏差后验均值','开发未超B2，不晋级'),
 'b4_safe':('积分各偏差对应的profile位置，最大化20米清除盘原子质量','全量晋级；最终冻结'),
 'b5_safe':('跨频道留一MAP符号稳定性','未超B4，不晋级1'),
 'b6_safe':('等权共享/污染似然混合后再做后验盘规划','开发与起点相同，不晋级2'),
 'b7_safe':('共享/非共享profile证据模型平均清除点','未超B4，不晋级3，停止')}
rounds=[]
for name,(method,decision) in descriptions.items():
    d=H/f'results/{name}_development/summary.json';training=next((r for r in cost['training'] if r['round']==name),None)
    rounds.append(dict(round=name,method=method,decision=decision,development=read(d) if d.exists() else None,training=training,
        candidate_sha256=sha(H/f'snapshots/{name}.py') if (H/f'snapshots/{name}.py').exists() else None))
ledger=dict(scope='two mechanism directions; safety corrections are not optimization rounds',rounds=rounds,
    stopping=dict(residual='R4/R5/R6 three consecutive nonpromotions after R3',bias='B5/B6/B7 three consecutive nonpromotions after B4'),
    safety_revisions=['r3_guard preserves cover_polygon/protected plans and failed-clear follow-up coordinates',
        'b1_guard is superseded: its early return dropped calibration from protected successes',
        'b1_safe and later bias snapshots preserve calibration and derive clear-disk center from actual public trace',
        'training R2-R6 occurred before the coverage-context fix; no retraining or universal behavioral equivalence is claimed'])
(H/'iteration_ledger.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2))

lines=['# A3：新规划与学习方法实施结果','',
'本轮在隔离分支完成两条机制路线、13轮实质方法实验及安全修正。最终冻结 **B4_safe**：第四问2400局、30970个源全部正常清除，按逐局“总虚拟时间/清除数”再取算术均值为 **455.196130759秒/源**。同ID起点A2 R2为455.434476124，改善0.238345365秒/源（0.0523336%）；快/同/慢为376/1944/80。最大单局退化14.967453秒/源，不能写成逐局都改善。第三问完整继承A1 R2，A3没有新增第三问收益。','',
'这些都是本地开发与既有暴露回归，未运行官方Windows模拟器，也不是新的盲测。本轮起点已经包含其他会话先前的A1 R2/A2 R2改善，未冒领这些改进。协调者在所有候选冻结后另做独立确认；A3没有查看该确认种子。','',
'## 机制与安全边界','',
'B4只在未获几何证书的普通中心试清时改变位置。由已经成功清除的频道得到20米盘（只有实际同点near才用5米盘），在原可靠bearing多边形与该盘的保守外接多边形交集中拟合21个角偏差的profile位置。由累计profile损失形成规划权重；对当前频道列出中心、插件位置、加权位置均值和21个profile位置，选择20米内原子权重最高者，同权重时缩短真实下一步移动。','',
'这些原子和指数权重是近似规划模型，成功清除盘不等于精确源坐标，profile分数也不是经过统计校准的后验概率。它们不收缩可靠几何域、不替代±1度边界、不把试清标成必成功；所有失败照常计费并保留有限兜底。覆盖执行上下文与协调者的`_protected_clear_plan`禁止改点及补测redirect，但仍从实际成功clear轨迹学习。父层若改写请求点，学习盘心也以实际轨迹为准。','',
'此前`b1_guard`早退漏掉保护上下文的成功学习，已标为废弃。`b1_safe`的4800行任务字段与原B1完全一致；`r3_guard`亦与原R3的4800任务字段完全一致，排除两种现实runtime。此处证明保存行相等，未声称所有动作轨迹或任意未来输入都相等。R2-R6训练发生在覆盖上下文修正前；保留旧标签及该限制，没有把已训练标签包装成修正后重新采集。','',
'## 各轮决定','',
'|轮次|实质机制|96开发局均值相对起点变化（秒/源）|结果|','|---|---|---:|---|']
for r in rounds:
    dev=r['development'];delta=f"{dev['delta_mean']:.6f}" if dev else '未部署；独立校准淘汰'
    lines.append(f"|{r['round']}|{r['method']}|{delta}|{r['decision']}|")
lines+=['','R1-R6为同一残差/回报学习方向；B1-B7为共享误差在线规划方向。R6明确从单源局部回报改成整局实际回报，先验证未改策略的续跑与真实整局总虚拟时间精确相等（284个分叉状态），再拟合。5个校准阈值均为负优势，因此没有把它部署到开发集或挑选负结果中相对最好者声称改进。','',
'## 逐批次配对复算','', '|候选|v1 1200局|旧第二批1200局|合并2400局|相对本轮起点改善|','|---|---:|---:|---:|---:|']
for name,a in audit.items():
    g={x['suite']:x for x in a['groups'] if x['mode']==4 and x['group']=='ALL'}
    lines.append(f"|{name}|{g['v1']['candidate_mean']:.9f}|{g['previous_final']['candidate_mean']:.9f}|{g['combined']['candidate_mean']:.9f}|{g['combined']['improvement_pct']:.6f}%|")
lines+=['','每候选全量文件共有4800行（两题各2400局）。`results/final_paired_audit.json`逐一核对全部case_id、mode/group、源数分母、正常退出、clear成功数及秒/源公式，并保存每题每场景每批次结果。quick是v1 full子集；旧第二批也早已暴露。','',
'## 真实训练与运行成本','',
f"种子去重为1296个训练/校准world（fit 864、calibration 432）加96个反复使用的开发world，共1392个新world。四轮288及一轮144的训练配方互不重叠，模型没有共用同一套训练world再重复计数。",'',
'|训练轮|fit/cal world|fit/cal状态样本|完整教师roll-in|反事实分支|分支范围|', '|---|---:|---:|---:|---:|---|']
for r in cost['training']:
    lines.append(f"|{r['round']}|{r['fit_worlds']}/{r['calibration_worlds']}|{r['fit_samples']}/{r['calibration_samples']}|{r['completed_rollin_episodes']}|{r['counterfactual_branches']}|{r['branch_kind']}|")
lines+=['',f"已保存账本证明1296次完整教师roll-in、9994次反事实分支，训练业务调用499594次；完整评估部署35688次、评估业务调用7158156次。评估含开发双策略2688次、quick 1800次、full 16800次及旧第二批14400次。完整roll-in加评估共36984次；反事实从克隆前缀开始，不能再算独立world或完整从enter部署。以上业务调用含enter/exit，分类明细和计算脚本见execution_ledger.json与final_audit.py。",'',
'另保留两项失败成本：一次Python3.9启动的120个worker均在环境导入前失败，完整部署0；改用Python3.12重跑。R6首个G0因提取错嵌入父类而拒绝参考续跑，接受标签0；按保留控制流与相同首world状态可推断1次教师roll-in和6次续跑，但没有完整原始请求账本，因此不混入上述精确总数。没有删除这些失败目录。各进程墙钟共享机器负载且并发，不能相加充当用户等待时长。','',
'冻结v1散列保持不变；14项规则单元测试及79/79名义夹具通过。每个最终bias安全版本另有9个动作契约夹具（共7×9），验证实际盘心、近邻坐标一致性、保护上下文及异常时状态恢复。这些夹具不是新源场景或官方测试。','',
'## 交付','',
'- 最终单文件：`snapshots/b4_safe.py`；融合组件：`bias_component_b4_safe.py`与`bias_helpers.py`。',
'- 备选残差：`snapshots/r3_guard.py`、`point_component_guard.py`、`r3_config.json`。',
'- 候选与组件散列、融合绑定及训练边界：`DELIVERY.json`。',
'- 精简去重种子：`new_world_seeds.json`；配方来源和散列：`all_new_worlds_manifest.json`。',
'- 各轮状态：`iteration_ledger.json`；执行成本：`execution_ledger.json`。',
'- 15篇逐篇来源、阅读深度、机制和迁移限制：`LITERATURE.md`及`research/corpus.json`。',
'- 原主目录与正式入口未修改；实验分支只提交本目录成果。']
(H/'REPORT.md').write_text('\n'.join(lines)+'\n')
lit=['# 文献机制图谱与实际阅读账本','',
'检索截至2026-09-12。本目录收录15篇有一手页面或原文依据的机制候选：7篇定向阅读方法/实验或边界章节，8篇扩展阅读。没有声称穷尽领域、15篇全部全文精读或逐条复现。源码侧继承的文献缓存与本轮新获取页面分别标注；最新页面身份不意味着审稿接收状态。','',
'分类采用“更新对象或决策结构→机制→论文”：belief/model adaptation、controller structure、policy learning signal、planning and representation四条主线。只把有实际实现的R1-R6/B1-B7称为本轮成果。','']
for e in corpus['entries']:
    lit.extend([f"## {e['id']} · {e['title']}",'',f"来源：[一手页面]({e['source_url']})；获取记录：{e['verification']}。",'',
        f"实际阅读：{e['reading_scope']}。层级：{e['tier']}。",'',f"分类：{' → '.join(e['primary_path'])}。",'',
        f"原文方法：{e['method']}",'',f"原文实验范围：{e['benchmark_scope']}",'',
        f"迁移边界：{e['limitations']}",'',f"本地对应：{e['local_transfer']}",'',f"本地身份页面：`{e['source_path']}`；SHA256 `{e['sha256']}`。",''])
    if e.get('reading_sources'):
        lit.extend(['实际方法阅读原文存档：'+ '；'.join(f"`{r['path']}`（{r['role']}，SHA256 `{r['sha256']}`）" for r in e['reading_sources'])+'。',''])
lit+=['共享偏差方法中的后验、模型证据和污染混合是本地profile规划构造，没有重现原论文的动态模型、Gaussian假设或理论保证。B3/B4/B5/B6/B7分别是点估计、后验盘规划、跨频道稳定性、污染混合及模型平均的机制后继，而非把同一阈值扫描重命名成新方向。']
(H/'LITERATURE.md').write_text('\n'.join(lit)+'\n')
delivery=dict(frozen=True,recommended='b4_safe',main= 'snapshots/b4_safe.py',sha256=sha(H/'snapshots/b4_safe.py'),
    component='bias_component_b4_safe.py',component_sha256=sha(H/'bias_component_b4_safe.py'),helpers='bias_helpers.py',helpers_sha256=sha(H/'bias_helpers.py'),
    required_config=dict(eb_sigma=.35,eb_min_channels=2,eb_min_bias=.5,eb_max_sd=.25),
    integration='Rebind _A3_ORIGINAL_Q4 to guarded parent; provide existing _C7._Q4 geometric functions and _a3_inside helper. Keep cover_polygon and _protected_clear_plan flags respected. Do not stack another coordinate-rewriting learner without action-level integration checks.',
    alternate=dict(name='r3_guard',snapshot_sha256=sha(H/'snapshots/r3_guard.py'),component='point_component_guard.py',config='r3_config.json'),
    deployment_reads_only='public action and observation state; no source truth/recipe/seed/group/source count',
    evidence='local development and old exposed regression only; coordinator owns new confirmation')
(H/'DELIVERY.json').write_text(json.dumps(delivery,ensure_ascii=False,indent=2))
print(json.dumps(delivery,ensure_ascii=False,indent=2))
