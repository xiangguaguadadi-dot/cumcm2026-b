"""Build the final narrative from saved evidence, without executing any world."""
from __future__ import annotations
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return json.loads((ROOT/path).read_text())

def rows(path):
    return [json.loads(line) for line in (ROOT/path).read_text().splitlines()]

def number(value, digits=3):
    return '—' if value is None else f'{value:,.{digits}f}'

def sha(path):
    return hashlib.sha256((ROOT/path).read_bytes()).hexdigest()

def ledger_summary(records):
    return dict(executions=len(records), unique_worlds=len({r['world_id'] for r in records}),
        calls=sum(r['business_primitives'] for r in records),
        successes=sum(bool(r['success']) for r in records),
        cleared=sum(r['cleared'] for r in records), source_denominator=sum(r['n'] for r in records),
        fallback_episodes=sum(bool(r['fallback_reason']) for r in records),
        decisions=sum(r['decisions'] for r in records),
        teacher_matches=sum(r['teacher_matches'] for r in records),
        execution_wall_s=sum(r['execution_wall_s'] for r in records),
        gzip_bytes=sum(r.get('storage',{}).get('gzip_bytes',0) for r in records),
        storage_wall_s=sum(sum(r.get('storage',{}).get(k,0) for k in ('json_encode_s','gzip_s','write_s')) for r in records))

def main():
    plan=read('data/g2_plan.json')
    selection=read('analysis/selection_result/selection_summary.json')
    audit=read('verification/full_audit_v1/audit.json')
    if not selection['inputs_collection_complete'] or audit['status']!='consistent_complete' or audit['mode']!='archives':
        raise RuntimeError('Complete saved analysis and evidence audit required before final narrative')
    if sha('data/g2_plan.json')!=selection['provenance']['plan_sha256']:
        raise RuntimeError('Plan changed after selection statistics')
    seeds=plan['initialization_seeds']
    records={'shared_demo':rows('results/g2_shared_demo/rows.jsonl')}
    training={}
    for seed in seeds:
        for algorithm in ('ppo','q'):
            key=f'{algorithm}_init{seed}'
            records[key]=rows(f'results/g2/init_{seed}/{algorithm}/rows.jsonl')
            training[key]=read(f'results/g2/init_{seed}/{algorithm}/summary.json')
    for key,part in selection['parts'].items():
        path=f"results/g2_selection/{part['category']}/{key}/rows.jsonl"
        if sha(path)!=part['input']['sha256']:
            raise RuntimeError('Selection ledger changed after statistics: '+key)
        records[key]=rows(path)
    costs={key:ledger_summary(value) for key,value in records.items()}
    select_records=[r for key,part in selection['parts'].items() for r in records[key]]
    select_cost=ledger_summary(select_records)
    totals=audit['known_cost_totals']
    passes=[f"{a.upper()} Q{q}" for a,modes in selection['algorithms'].items()
            for q,result in modes.items() if result['meets_preregistered_selection_gate']]
    lines=['# 第五阶段：BC、PPO与约束Q真实实施及选择评估', '',
        '2026-09-11。本轮由共同控制器、PPO/BC、约束Q三位子Agent实施并交叉审计，协调者统一数据、运行、统计与提交。', '',
        ('**选择结论：'+('、'.join(passes)+'满足预登记的本地选择门槛；仍未授权默认替换。' if passes else 'PPO和约束Q均未满足第三、四问的预登记晋级门槛，保留C7。')+'**'), '',
        f"G0/G1、共享示范、六条训练运行及全部选择评估合计实际执行 **{totals['indexed_episode_executions']:,}局**，涉及 **{totals['unique_executed_world_ids']:,}个不同world**、**{totals['indexed_business_primitives']:,}次业务调用**。旧v1教师回归的2,520次执行另计。完整性审计结果为`{audit['status']}`，未知成本记录{audit['unknown_cost_records']}条。", '',
        '这是本地预登记检查点选择证据，包含选择偏差。未新开最终密封测试，未执行Windows官方演练或正式测试，也未修改主目录solver.py、固定物理环境、旧评测或原C7。', '',
        '## 主要结果', '',
        '单位均为每局总虚拟时间除以清除数，再对登记场景取算术平均；越小越好。百分比为100×(对照均值−候选均值)/对照均值，负数表示更慢。每题96个共同场景，三个初始化在同一场景内先取均值。', '',
        '|算法|题目|秒/源|相对C7改善|相对BC改善|候选−C7的95%区间|同时优于两对照的初始化|门槛|',
        '|---|---:|---:|---:|---:|---|---:|---|']
    for algorithm,modes in selection['algorithms'].items():
        for mode,result in modes.items():
            aggregate=result['aggregate']
            if aggregate:
                c7=aggregate['comparisons']['original_c7'];bc=aggregate['comparisons']['corresponding_bc']
                ci=c7['difference_ci95_s_per_source']
                lines.append(f"|{algorithm.upper()}|{mode}|{number(c7['candidate_mean_s_per_source'])}|{number(c7['improvement_percent'])}%|{number(bc['improvement_percent'])}%|[{number(ci[0])}, {number(ci[1])}]|{result['promotion_checks']['initializations_improving_both_baselines']}/3|{'通过' if result['meets_preregistered_selection_gate'] else '未通过'}|")
            else:lines.append(f'|{algorithm.upper()}|{mode}|—|—|—|无完整配对|—|未通过|')
    lines += ['', '预登记门槛同时要求：部署正常全清；相对C7及对应BC均至少改善2%；两组配对差95%区间上界小于0；至少两个相同初始化同时优于两个对照。完整逐初始化、两种区间、场景退步及全部布尔门槛见[统计报告](analysis/selection_result/REPORT.md)。区间按12场景分层、10,000次bootstrap计算，随机种子84771，不重采样初始化；没有修正检查点选择与多重比较。', '',
        '本轮主要缺口在效率。BC本身已慢于C7；PPO在Q4的选择均值比对应BC改善约1.01%，但仍低于2%门槛且慢于C7。三份PPO的1,024局检查点在两题上都慢于各自128局检查点，当前证据没有显示继续训练的稳定收益。结论限定于本轮候选表示、轻量网络、优化配置和固定预算，更大预算及新结构尚无本轮证据。', '',
        'Q的全部12个部署检查点共69,512次决策，其中69,236次为支持集合内Q评分最大值选择，276次为经验范围回退；部署探索和整局兜底均为0。但28,632次决策的支持集合只有teacher（占全部41.19%），进入argmax不意味着每次都有多个选择。48,760次动作与当时teacher相同（70.15%），另20,752次在多候选支持集合中选择了非teacher动作。训练有8,854次探索、1,177/3,072局接管；这1,177次均由显式探索选择fallback候选直接触发，兜底尾段占训练总虚拟时间55.46%。这些是保存行为的分解，并未通过独立消融证明退步的单一原因或取消探索的反事实收益。详细分母和按初始化/题目/检查点诊断见[Q诊断](verification/q_diagnostics_v1/READOUT.md)。', '',
        '## 所有对照与检查点', '',
        '本表包含所有预登记位置，不删除落选项。Q3、Q4可选择不同训练位置；这不是重新拼接或追加训练。', '',
        '|模型|Q3秒/源|Q4秒/源|正常全清局/执行局|清除源/源分母|兜底局|业务调用|',
        '|---|---:|---:|---:|---:|---:|---:|']
    for key,part in selection['parts'].items():
        c=costs[key];q=part['questions']
        lines.append(f"|{key}|{number(q['3']['mean_seconds_per_source'])}|{number(q['4']['mean_seconds_per_source'])}|{c['successes']}/{c['executions']}|{c['cleared']}/{c['source_denominator']}|{c['fallback_episodes']}|{c['calls']:,}|")
    lines += ['', '所有逐局ID、失败和分母均可在[完整机器可读统计](analysis/selection_result/selection_summary.json)及`results/g2_selection/`的行账本核对。兜底成功属于系统全清，不等于学习策略独立完成；兜底后的全部时间与调用均进入成绩。', '',
        '## 训练与采样成本', '',
        '共享512局C7示范只实际采集一次。每个初始化独立训练一份BC，并将同一份BC作为该初始化PPO和Q的共同起点。两算法使用相同的对应训练场景配方，但真实执行、探索轨迹和调用各自计费。G1诊断数据与模型不进入G2。', '',
        '|阶段|独特world|执行局|正常全清局|调用|决策数|教师一致决策|兜底局|',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for key in ['shared_demo']+[f'{a}_init{s}' for s in seeds for a in ('ppo','q')]:
        c=costs[key]
        lines.append(f"|{key}|{c['unique_worlds']}|{c['executions']}|{c['successes']}|{c['calls']:,}|{c['decisions']:,}|{c['teacher_matches']:,}|{c['fallback_episodes']}|")
    lines += [f"|选择合计|{select_cost['unique_worlds']}|{select_cost['executions']}|{select_cost['successes']}|{select_cost['calls']:,}|{select_cost['decisions']:,}|{select_cost['teacher_matches']:,}|{select_cost['fallback_episodes']}|", '',
        '教师一致率的分母是该策略真实遇到的snapshot，不能把不同策略访问的状态逐动作对齐。原C7保留自身接口日志，没有伪造宏决策记录。Q训练前缀含显式探索及持续更新的策略，与冻结部署结果分开解释；[Q行为诊断](verification/q_diagnostics_v1/Q_DIAGNOSTICS.md)进一步分解支持集合、经验范围回退和探索。', '',
        '|初始化|BC更新/加载训练秒|PPO更新/优化秒|Q MC更新/加载更新秒|Q TD更新/加载转换优化秒|最后一次运行调用墙钟秒|峰值MiB|',
        '|---:|---:|---:|---:|---:|---:|---:|']
    for seed in seeds:
        base=f'results/g2/init_{seed}';bc=read(base+'/bc/summary.json');mc=read(base+'/q/mc_summary.json')
        ppo=training[f'ppo_init{seed}'];q=training[f'q_init{seed}'];complete=read(base+'/complete.json')
        lines.append(f"|{seed}|{bc['optimizer_steps']} / {number(bc['load_and_training_wall_s'],2)}|{ppo['optimizer_steps']} / {number(ppo['optimizer_wall_s'],2)}|{mc['optimizer_steps']} / {number(mc['load_and_update_wall_s'],2)}|{q['td_optimizer_steps']} / {number(q['load_convert_optimizer_wall_s'],2)}|{number(complete['wall_time_this_invocation_s'],2)}|{number(complete['peak_process_mib'],2)}|")
    lines += ['', '三份初始化并行运行；最后一次运行调用墙钟在本轮无中断的G2中覆盖完整初始化，但恢复运行时仅覆盖该次调用，且不可相加后称为用户等待时间。各阶段加载、训练和优化列计时范围不同，不作为受控算法速度排名。新增episode上限1,024及调用上限1,000,000均按算法、初始化独立执行，包含完整尾费用。模型只在128、256、512、1,024局保存候选；未因选择结果追加预算、结构或轮次。', '',
        '## 部署计算与记录开销', '',
        '|模型|执行墙钟和/秒|候选构建至动作前P95/P99 ms|进程峰值MiB|gzip MB|编码压缩写盘秒|',
        '|---|---:|---:|---:|---:|---:|']
    for key,part in selection['parts'].items():
        c=costs[key];s=read(f"results/g2_selection/{part['category']}/{key}/summary.json")
        timing=s['timing_ms']['prepare_to_macro_s']
        lines.append(f"|{key}|{number(c['execution_wall_s'],2)}|{number(timing['p95'],2)} / {number(timing['p99'],2)}|{number(s['peak_process_mib'],2)}|{number(c['gzip_bytes']/1e6,2)}|{number(c['storage_wall_s'],2)}|")
    lines += ['', '计时包括真实CPU执行的候选构建和网络选择，不仅是tensor前向；但这是本机直接函数环境及并行负载下的测量，不包含官方网络。原C7没有共同snapshot阶段，故该列为空；同一进程连续评估模型时，峰值内存是进程历史高水位，不是该模型独占增量。gzip为十进制MB。编码、压缩及写盘在执行墙钟之外另列。', '',
        '## 实现、验证与证据边界', '',
        '实现是轻量候选打分网络，C7提供宏动作候选和教师，神经网络选择调度顺序。共同控制器、费用单位、终端、Q时钟范围v2及恢复语义见[实现说明](IMPLEMENTATION.md)。训练归一采用终局N，N不进入在线特征；这不是原始POMDP的完整状态证明，也不是网络从零发现全套几何算法。', '',
        'G0的40个新world共120次执行、79,153次调用；G1的24个新world共73次执行、15,593次调用。79/80个独特合成夹具覆盖控制器、PPO、Q、共享网络、恢复及统计；重复运行不增加夹具数。教师包装通过旧quick120/full2400，以及14项原规则与79项nominal检查；旧全测Q3/Q4=235.235583/452.760907秒/源，这些是教师暴露回归成绩，不是学习增益。', '',
        f"完整审计遍历G0/G1、示范、训练与选择的全部保存轨迹，耗时{audit['elapsed_wall_s']:.2f}秒，状态`{audit['status']}`，错误{audit['errors']}、未决项{audit['pending_findings']}、未知成本记录{audit['unknown_cost_records']}。192个共同场景的原C7与teacher包装请求语义和虚拟费用全部相等，只在回复比较时去除两项现实时间字段。具体检查范围及逐对记录见[证据审计](verification/full_audit_v1/REPORT.md)。虚拟兜底保证依赖理想接口物理规则，未知网络和计算时间不支持官方现实期限内无条件保证。", '',
        '另行完成[27份权重内部状态复核](verification/checkpoint_review.md)，424个保存状态检查均通过。12份Q支持网络逐张量精确等于各自初始化的BC；从3,584份示范及Q训练存档独立复算的范围极值、快照数、revision和历史与12份Q权重完全一致。该检查没有运行模型或环境，也不能由权重证明所有梯度正确或排除未留痕的额外读取。', '',
        '[独立统计复算](verification/selection_independent_review.md)未导入原统计helper，重新核对5,760行、75,600次重复源分母及其清除、12个分题选择、60个分题均值、720个分组均值和32个配对区间。结果一致，最大浮点差1.14e−13；这是对相同保存证据的复算，不增加独立实验样本。', '',
        'G1首份轨迹在保存后遇到路径显示异常，随后直接恢复，没有重执行；该份存储耗时未知，73局执行耗时仍完整。G2原计划保持原散列，之后协调代码仅修复保存/恢复/成本登记；实际训练代码由各初始化manifest冻结，物理规则另有依赖冻结，选择前再次冻结全部模型和运行代码。历史差异明确保留，不事后覆盖计划。', '',
        '没有因本轮学习结果再新增旧回归筛选：教师适配器已完成所需兼容性回归；学习候选是否达到保留门槛以上表为准。所有算法代码、各检查点及负结果保留供复核，不把保存权重等同晋级。', '',
        '## 文件与复核', '',
        '- [实际执行协议](EXECUTION_PROTOCOL.md)与[实现说明](IMPLEMENTATION.md)。',
        '- [41篇来源的统一研究审阅稿](../20260911_rl_research/RESEARCH_PROPOSAL.md)，保留研究时的修订和未执行边界。',
        '- `results/g2/init_<seed>/bc/final.pt`、`ppo/checkpoints/`和`q/checkpoints/`为真实训练权重，索引绑定SHA256。',
        '- [选择冻结](data/selection_freeze.json)、[统计机器数据](analysis/selection_result/selection_summary.json)、[完整证据审计](verification/full_audit_v1/audit.json)。',
        '- [本地原始轨迹清单](verification/full_audit_v1/local_only_trajectory_manifest.json)：Git保留配方、权重、行账本与散列；大体积完整轨迹仅本地保留。',
        '', 'Git中的散列不能替代被排除的原始文件。仅下载仓库可以重算保存行的统计；完整逐动作审计需要本地原始轨迹。物理场景可以从保存配方重建，真实时钟仍作为模型输入，因此换机器重执行不保证逐bit重现同一动作序列。运行命令和安全复核入口见[README](README.md)。', '']
    (ROOT/'REPORT.md').write_text('\n'.join(lines))
    payload=dict(selection_gates={a:{q:r['meets_preregistered_selection_gate'] for q,r in modes.items()}
        for a,modes in selection['algorithms'].items()},phase_costs=costs,selection_cost=select_cost,
        audited_cost_totals=totals,report_sha256=hashlib.sha256((ROOT/'REPORT.md').read_bytes()).hexdigest(),
        evidence_scope='local preregistered checkpoint selection; not blind final or official',default_solver_replaced=False)
    (ROOT/'analysis/delivery_summary.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(report=str(ROOT/'REPORT.md'),gates=payload['selection_gates']),ensure_ascii=False))

if __name__=='__main__':main()
