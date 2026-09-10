"""Build a self-contained report from preserved raw-result summaries and source notes."""
import hashlib
import json
import pathlib
import statistics

ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT/'experiments/A4_directional'
comparison = json.loads((P/'comparison.json').read_text())
best = json.loads((P/'best.json').read_text())
best.update(total_rounds=8, status='complete', stop_reason='R7 and R8 did not improve R6; two consecutive non-improvements after authorized extension; empirical stop, not global optimality', extension_no_improvement_streak=2)
best['configuration']['visibility_quadrature'] = 'arithmetic vertex center plus 0.75*vertex+0.25*center samples'
best['configuration']['base_optimized_config'] = dict(advance_fraction=.60, lateral_fraction=.15, clear_trial_radius=100, route_optimization=True, upper_bound_stop=True, rescue_initial_clear=False, joint_scheduling=True, source_priority_by_mode={'3':1.55,'4':1.60}, clear_standoff=True)
best['configuration']['virtual_safe_switch_seconds'] = 180000
best['configuration']['convex_recovery'] = 'not present in R6'
best['configuration']['optical_modal_mode'] = 'fixed radius threshold; R7 cost switch not present'
best['configuration_sha256'] = hashlib.sha256(json.dumps(best['configuration'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
(P/'best.json').write_text(json.dumps(best, ensure_ascii=False, indent=2))

literature = json.loads((P/'literature.json').read_text())
sources = {s['id']:s for s in literature['sources']}
radio = sources['2011.10474v2']
radio['implementation'] = [
    dict(round='R1', functions=['visibility_hypotheses','predicted_visibility','second_point','rescue_bearing'], role='原创简化迁移：离散位置/方向与解析半径积分，仅排序，不复现论文运动粒子模型'),
    dict(round='R2–R3', functions=['rescue_bearing','optical_points','optical_route'], role='RF/光学互补启发；R2提前有限光学覆盖，R3由位置假设选择完整路线，均已完成开发与full'),
    dict(round='R4', functions=['visibility_hypotheses','clear'], role='失败clear只更新离散位置权重的自拟消融；full退步，最终未采用'),
    dict(round='R6', functions=['rescue_bearing'], role='用同一可见性估计门控自拟镜像点；小幅full改善但三个场景退步'),
    dict(round='R7', functions=['expected_optical_time','rescue_bearing'], role='近似RF/光学成本切换；full退步，最终未采用')]
radio['experimental_support'] = 'R1 Q4较原版改善0.32064%，但5/12场景退步；R2、R3改善，R4、R7失败，R6仅小幅均值改善。支持本地排序/模态互补的用途，不证明论文似然在本题校准，也不把逐轮组合差异归因于单一论文。'
multimodal = sources['2209.07660v1']
multimodal['implementation'] = [
    dict(round='R1',functions=['rescue_bearing'],role='移动/检测成本除以预测可见概率的自拟近似排序；未复现MCTS'),
    dict(round='R2–R3',functions=['rescue_bearing','optical_route'],role='以任务成本选择光学搜索及两条完整路线；成本模型为自己的实现'),
    dict(round='R6',functions=['rescue_bearing'],role='以预测成本门控镜像一次恢复；自拟有限动作选择'),
    dict(round='R7',functions=['expected_optical_time','rescue_bearing'],role='显式RF/光学预计成本比较消融；full退步，不纳入R6'),
    dict(round='R8',functions=['rescue_bearing'],role='用移动/检测成本决定是否进入已可见点连线；凸性方案自己的推导，full退步')]
multimodal['experimental_support'] = '成本要与信息共同考虑的原则得到实现，但复杂成本近似R7和保证可见的R8均失败；不能声称更复杂规划必然更快。R2对照含snake端点变化，非单变量因果消融。'
set_source=sources['2603.04867v1']
set_source['implementation'] = [
    dict(round='R1–R8',functions=['add_bearing','cover_polygon','run'],role='基准已有有界误差外包/覆盖/停止证据，全部保留；未移植论文距离差分或SDP'),
    dict(round='R2–R3',functions=['optical_points','optical_route'],role='在小集合内提前覆盖并重排；完整性由本题网格距离证明'),
    dict(round='R5、R8',functions=['rescue_bearing'],role='接收圆盘/半圆的凸性是本题直接数学推导；受集合思维启发，不是这篇论文提出的恢复算法')]
set_source['experimental_support'] = '八轮所有本地回归全清且原几何证书保留；R5改善、R8退步，说明正确几何性质不必然带来效率提升。有限样本不替代可靠性证明。'
geometry = sources['2606.09188v1']
geometry['implementation'] = [x for x in geometry['implementation'] if x['round'] != 'R5–R8']
geometry['implementation'].append(dict(round='R5–R8',functions=['rescue_bearing'],role='交会几何只作设计警示；折返/镜像/凸包点均是自己的启发式，未复现其FIM或PSO'))
geometry['experimental_support']='R1改变第二点左右选择但保留横向基线；R8保证可见而full退步，符合信息几何不能只看可见性的警示。未做本题FIM/PSO对照，不把该现象当作论文机制的因果验证。'
for s in literature['sources']:
    if 'experimental_support' not in s:
        s['experimental_support'] = '只采用任务目标的概念性区分，没有单独算法消融，不能分配本题提升归因。' if s['id']=='1206.6406v1' else '未实现对应论文算法，因此没有本题实验支持；未采用理由见implementation与limitations。'
literature['original_design_extensions'] = [
    dict(round='R3',mechanism='从最近格点向两侧展开的两条完整snake，以假设位置首次覆盖成本选序',provenance='自己的路线构造与三角不等式证明；多模态成本文献为概念启发',outcome='相对R2 full Q4减少3.29758424秒/源，12组不退步'),
    dict(round='R5',mechanism='可见点到失联点的线段二分，最多两次',provenance='直接利用本题接收圆盘与半平面交集的凸性；非任何所列论文现成算法',outcome='相对R3 full减少7.38184018秒/源，12组不退步'),
    dict(round='R6',mechanism='关于最后测向中心线镜像失联点，按预测可见成本门控一次',provenance='自己的镜像启发式；概率成本建模沿用R1，镜像不保证可见',outcome='相对R5减少0.32382947秒/源，3组退步'),
    dict(round='R7',mechanism='近似预计清除时间选择RF或光学',provenance='多模态规划启发下自拟单步成本模型，非MCTS复现',outcome='相对R6增加0.74836566秒/源，10组退步，淘汰'),
    dict(round='R8',mechanism='已可见点连线内部提供确定可见点，按成本门控',provenance='自己的凸性推导；确定可见不保证测向信息增益',outcome='相对R6增加0.78533692秒/源，8组退步，淘汰')]
literature['final_status']='completed; 8 rounds; best R6; two consecutive non-improving extensions'
(P/'literature.json').write_text(json.dumps(literature,ensure_ascii=False,indent=2))

rounds=comparison['rounds']; r6=next(r for r in rounds if r['round']==6)
rows=json.loads((P/'results/r6_full/case_metrics.json').read_text())
baseline={str(m):statistics.mean(r['average_clear_time_s'] for r in rows if r['variant']=='frozen_baseline' and r['mode']==m) for m in [3,4]}
reduction=(baseline['4']-r6['metrics']['4']['mean_s_per_source'])/baseline['4']*100
audit=json.loads((P/'results/final_audit.json').read_text()) if (P/'results/final_audit.json').exists() else None
out=[]
def add(text=''):out.append(text)
add('# A4 定向发射与信号可见性：独立研究与八轮实验报告')
add('\n2026-09-11 完成。第一、二问维持冻结；本路线独立修改第四问的动作决策。所有成绩均为 **LOCAL-evaluation-v1 固定回归**，不是官方 Windows 模拟器结果，也不是新的盲测。')
add(f'\n最终保留 **R6**：Q3 **{r6["metrics"]["3"]["mean_s_per_source"]:.8f} 秒/源**，Q4 **{r6["metrics"]["4"]["mean_s_per_source"]:.8f} 秒/源**；每题 **1200/1200 全清、正常退出、零异常**。Q3逐局与原版相同；Q4较原版均值减少 **{baseline["4"]-r6["metrics"]["4"]["mean_s_per_source"]:.8f} 秒/源（{reduction:.5f}%）**，十二个Q4场景均值均改善。Q4逐局仍有退步，详见后文，不以总体改善掩盖。')
add('\nR2与R3连续刷新后进入已授权延长阶段。R4失败，R5/R6刷新，R7/R8连续两轮未刷新，因此在八轮后经验停止。这是本次研发停止条件，不是全局最优证明。')
add('\n## 1. 题目结构、代价与信息边界')
add('\n源位置在1800米圆域、数量10–16、频道互异且1–20。Q4兼有全向与定向源。定向可接收区是1000–1500米圆盘与过源闭半平面的交集；朝向和半径未知。测量误差有界±1度且同址固定，示向度保留两位小数。`clear`在20米内必成功，不受发射方向影响。')
add('\n动作虚拟成本为：`measure` = 移动距离/5 + 换频道×1 + 5秒；`clear` = 移动距离/5 + 3 + 成功×2秒。只有停止位置有观测，移动途中不测量。每局评价量是本局总虚拟时间/实际清除数，再在完整场景内求算术均值；没有自造加权官方总分。现实20分钟和虚拟100小时另作完整性约束。')
add('\n原版已具备保守示向度多边形、22个Q4发现站点、有限光学覆盖、16源数量上界及扫描完备退出。本路线原始瓶颈是：第二测点跨过发射半平面后失联，原恢复环可能产生长距离返回；即使已有较小位置集合，仍可能继续花费射频恢复成本。')
add('\n在线代码只调用`enter/measure/clear/exit`。开发评测层使用自建源真值算清除比例和耗时，策略不读真值、case ID、场景名或回归缓存。未训练权重、未下载运行模型、未修改HTTP。四个标准库依赖为json/math/os/time。')
add('\n## 2. 文献检索、阅读范围与逐篇迁移')
add('\n检索日期2026-09-11，先用广义方向覆盖、negative information、bearing-only localization、set membership和informative path planning等查询区分方法族。一次web搜索连接失败，随后用arXiv API和PDF直连。实际发现并整理10个一手来源：4篇关键正文定向阅读，4篇扩展局部阅读，2篇仅作者摘要/元数据。没有把下载当作通读，也没有声称穷尽全部数据库或SOTA。版本、查询词、访问失败与作者信息完整保留于[literature.json](literature.json)，下载散列见[research/downloads.json](research/downloads.json)。')
for s in literature['sources']:
    add(f'\n### {s["id"]}：{s["title"]}')
    add(f'\n作者：{", ".join(s["authors"])}；{s["year"]}年，arXiv v{s["version"]}。[原文]({s["url"]})。类别：{s["primary_classification"]}。')
    add(f'\n**实际读取**：{s["actual_reading_scope"]}')
    add(f'\n**论文做了什么**：{s["problem"]} {s["method"]}')
    add(f'\n**论文证据与边界**：{s["evidence"]} {s["limitations"]}')
    add(f'\n**本题启发**：{s["inspiration"]}')
    add('\n**进入代码与否**：'+'；'.join(f'{x["round"] or "未采用"} / {", ".join(x["functions"]) or "无对应实现函数"}：{x["role"]}' for x in s['implementation'])+'。')
    add(f'\n**本题实验是否支持**：{s["experimental_support"]}')
add('\n### 自己提出的扩展与文献贡献分界')
for item in literature['original_design_extensions']:
    add(f'\n- **{item["round"]}**：{item["mechanism"]}。来源：{item["provenance"]}。结果：{item["outcome"]}。')
add('\n## 3. 最终R6如何工作')
add('\n维护两个层次的状态。保证层是每条示向度的±1.005001度半平面交集及保守接收半径外包，必须包含真源。规划层从多边形取算术顶点中心及向中心收缩25%的顶点样本；每个位置配36个等角方向与一种全向假设。全向先验0.5、方向先验合计0.5、接收半径在1000–1500米均匀，是自拟近似，并非官方给出的分布。')
add('\n对位置s、方向n，正观测点决定可行半径下界；位于方向正侧的无信号点决定半径上界，背侧无信号不限制半径。有效区间长度乘方向先验产生权重。查询点q的可见概率由区间内满足距离条件的长度解析积分，再对有限位置/方向求和。无有效离散假设时退回0.5；这些近似永不裁掉保证层。')
add('\n决策顺序：')
add('\n1. 保留原第二测点的横向几何，在左右候选中用移动与600米尺度的失联惩罚排序。\n2. 失联且多边形最小包围圆半径≤300米时，直接进入完整光学覆盖。\n3. 否则评估失联点相对测向中心线的镜像；只在偏移≥5米、距原点≤3500米、未重复、预测成本优于线段中点时尝试一次。\n4. 未恢复则朝旧可见点二分折返，最多两次；仍失败使用原救援环，环内按移动/检测成本除以预测可见概率排序。\n5. 光学覆盖保留全部25米格点；小集合从最近格点出发，比较先去左端或右端两条完整路线的预计首次清除成本。预算到180000秒后用原snake并有限完成剩余任务。')
add('\nR4的面积积分/clear失败离散样本排除、R7的成本模态切换、R8的凸包内恢复均被淘汰，未混入R6。R2同时包含更近snake端点这个基础改动，其开发对照不是字节相同R1，因此不能把全部R2增益归因于300米阈值。逐轮改进是组合策略的局部研发证据，未做全部因子组合的因果消融。')
add('\n## 4. 开发与回归设计')
add('\n每轮内层仅使用自己生成的开发数据：四种几何情境×三种误差×六个种子=72局/配置；最多六配置，全部尝试保留。另两个种子给出24局开发验证，用于安全核验，未据其二次调参。开发参数选择后固定一个候选，先14项规则与manifest校验，再quick120；保留者同一快照full2400。v1的5000–5099种子未用于开发集，但v1已经公开且反复暴露，不能称盲测；quick是full子集。')
add('\n| 轮次 | 开发种子 | 配置数/开发局数 | 验证种子/局数 | 独立候选Q4 quick | Q4 full | 对前最佳变化 | 完整性 |')
add('|---|---|---:|---|---:|---:|---:|---|')
for r in rounds:
    d=r['development'];add(f'| R{r["round"]} | {d["seeds"][0]}–{d["seeds"][-1]} | {d["config_trials"]}/{d["case_runs"]} | {d["validation_seeds"][0]}–{d["validation_seeds"][-1]}/{d["validation_case_runs"]} | {r["quick"]["4"]["mean_s_per_source"]:.8f} | {r["metrics"]["4"]["mean_s_per_source"]:.8f} | {r["paired_vs_previous_best"]["4"]["mean_change"]:+.8f} | 2400/2400 |')
add('\n单位均为秒/源；负变化表示更快。八轮Q3 full均为306.30043421816345且逐局与原版完全相同。每轮全测的正常退出、错误数、源数分母、最差局、请求数、移动距离及现实时间均从原始行重算，见[comparison.json](comparison.json)；完整正负开发排序与选择理由在[iteration_log.md](iteration_log.md)。')
add('\nR1的quick略差但独立开发有收益且完整性通过，故保留冻结候选继续full。R4和R7的quick改善而full退步，说明不能把快测当作独立成功证明。R8内缩配置开发与R6打平，作为凸性探索继续验证，未声称已发现开发提升；full仅12局变差而没有一局改善，故明确淘汰。')
add('\n## 5. 最佳版本按场景与逐局比较')
add('\n| Q4场景（各100局） | 原版秒/源 | R6秒/源 | 变化秒/源 | 降幅 |')
add('|---|---:|---:|---:|---:|')
for g in r6['groups']:
    if g['mode']==4:add(f'| {g["group"]} | {g["baseline"]:.8f} | {g["candidate"]:.8f} | {g["candidate"]-g["baseline"]:+.8f} | {g["reduction_vs_baseline"]*100:.5f}% |')
if audit:
    p=audit['paired_rows']['4'];add(f'\n按case_id和mode精确配对，R6的Q4为**{p["improved"]}局改善、{p["worsened"]}局退步、{p["tied"]}局相同**，分母1200。每题累计清除15550/15550个源。逐场景均值均改善不代表每局都改善。')
add('\n### 每轮相对当时最佳的场景退步')
add('\n以下单列所有Q4场景均值退步；没有退步也明确列出。完整配对行均保留，不删除失败或退步数据。')
for r in rounds:
    regress=[g for g in r['groups'] if g['mode']==4 and g['change_vs_previous_best']>1e-8]
    add(f'\n- **R{r["round"]}对R{r["previous_best_round"]}**：'+('；'.join(f'{g["group"]} +{g["change_vs_previous_best"]:.8f}' for g in regress) if regress else '十二个场景均无均值退步')+(' 秒/源。' if regress else '。'))
add('\nR6只比R5改善0.32382947秒/源，且有三个场景退步。选择依据是两题完整性通过、两题均值不差且Q4有改善的预先比较规则；这一很小的差额不能声称稳健泛化。没有用自造权重将Q3/Q4合并。')
add('\n## 6. 可靠性与时间')
add('\n保留原22个Q4覆盖点与扫描所有未排除频道的逻辑。每个目标位于一个边长<1000米的覆盖三角形内；过目标的任意闭半平面至少包含该三角形一个顶点，因此任意方向都可发现。退出依旧只依赖16源上界或全部几何覆盖。')
add('\n真源始终属于保守多边形。25米网格方格中心到方格任意点≤25/√2<20米，因此保留全部相交格点就保证最终清除。R3的路线顺序没有删点，内部长度≤原snake两倍，超预算时退回原snake。R5的折返和R6镜像仅是有限恢复尝试，不承担完整性。')
add('\n动作点半径≤3500米、首次楔形网格最多62列×3行、原snake单源覆盖<4000秒、中心展开覆盖<6000秒。显式计入一条可能跨越180000秒阈值的完整覆盖，再为所有剩余源与扫描保留预算，得到保守界：**180000+6000+16×4000+27000=277000秒<360000秒**。完整推导和适用条件见[reliability.md](reliability.md)。实际网络阻塞不由几何证明约束，HTTP未改，仍需Windows官方演练。')
add('\n14项规则每轮通过；R3另保留79项正常规则检查和400随机几何×4性质断言。后续几何覆盖代码未删减。最终审计验证10个冻结文件散列、最佳快照与运行结果散列、2400个唯一候选ID与缓存基准一一配对、Q3逐局相同、四接口边界。该源审与有限性质测试都不是恶意反射防护的安全证明。')
add('\n| 轮次 | full现实总耗时/秒 | Q4平均每局现实/秒 | Q4最慢局现实/秒 | Q4最大虚拟/秒 |')
add('|---|---:|---:|---:|---:|')
for r in rounds:
    s=r['metrics']['4'];add(f'| R{r["round"]} | {r["full_wall_seconds"]:.6f} | {s["mean_real_s"]:.6f} | {s["max_real_s"]:.6f} | {s["max_virtual_s"]:.6f} |')
devwall=sum(json.loads((P/f'results/r{r["round"]}_{kind}.json').read_text())['wall_seconds'] for r in rounds for kind in ['development','dev_validation'])
quickwall=sum(json.loads((P/f'results/r{r["round"]}_quick/summary.json').read_text())['wall_seconds'] for r in rounds)
add(f'\n共39组开发配置、2808局开发+192局验证=**3000局**；quick **960局**、full **19200局**，实际候选回归合计**20160局**。缓存基准行随文件保存但未重复执行，不能把它们算作新运行。记录的开发/验证执行约{devwall:.3f}秒、quick约{quickwall:.3f}秒、full约{comparison["total_full_wall_seconds"]:.3f}秒；这些是本地程序计时，不包含研究阅读、下载、编辑、排队及全部人工墙钟时间。缓存原版的现实时间是历史值，不能拿来声称机器运行加速。')
add('\n## 7. 快照、复现与交付')
add(f'\n最终独立文件：[candidates/r6_solver.py](candidates/r6_solver.py)；工作树根solver.py已恢复同字节。SHA256：`{best["solver_sha256"]}`。代码与R6结果提交：`{best["code_commit"]}`。冻结manifest SHA256：`{best["manifest_sha256"]}`。运行参数、配置散列及绝对路径见[best.json](best.json)。无需权重或辅助文件；若旁边存在coverage_points.json，仍必须与解析覆盖证书一致。')
add('\n在本工作树根目录使用Python 3.10+（实验为3.12.14），输出目录须不存在：')
add('\n```sh\npython -m unittest discover -s tests -v\npython evaluate.py --verify-only\npython evaluate.py --suite quick --candidate experiments/A4_directional/candidates/r6_solver.py --out results/A4_reproduce_quick_new\npython evaluate.py --suite full --candidate experiments/A4_directional/candidates/r6_solver.py --out results/A4_reproduce_full_new\npython experiments/A4_directional/final_audit.py\n```')
add('\n开发复现示例（保持原种子/配置；输出使用新目录）：')
add('\n```sh\npython experiments/A4_directional/develop.py --variants r6 --candidate experiments/A4_directional/candidates/r6_solver.py --start 92000 --seeds 6 --out results/A4_reproduce_r6_development_new.json\npython experiments/A4_directional/research/retrieve.py\n```')
add('\n其他轮次的variants名称和种子见表；候选快照分别为candidates/r1_solver.py至r8_solver.py。下载脚本只恢复忽略的论文缓存并核验SHA256，不是策略运行依赖。每轮结果目录rN_full与rN_quick均含逐局JSON、官方指标同列LOCAL CSV和汇总；没有改写或覆盖旧结果。')
add('\n| 轮次 | 候选SHA256 | 代码/结果提交 |')
add('|---|---|---|')
for r in rounds:add(f'| R{r["round"]} | `{r["candidate_sha256"]}` | `{r["code_commit"]}` |')
add('\n## 8. 结论的适用范围')
add('\n可支持的结论是：在冻结本地模型和完整v1回归上，R6保持Q3与全清/正常退出，Q4均值改善且所有场景均值改善；前三轮与延长轮的正负结果可以复查。无法支持的结论包括：官方成绩已改善、未知噪声/方向分布仍同样改善、所有单局都更快、概率已正确校准、R6或路线方向全局最优。')
add('\n共同新样本由主协调在各路线独立最佳冻结后检验，样本不返给本路线调参；该验证仍属本地分布，不替代官方Windows模拟器。正式第三/四问各三次官方测试及官方日志不在本报告范围内。')
(P/'report.md').write_text('\n'.join(out)+'\n')
print('Final report, literature-to-code mapping, and completed best metadata written.')
