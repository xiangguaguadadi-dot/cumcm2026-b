"""Build traceable research metadata from acquired primary-source metadata.

No simulator, solver, training package, or network is imported or executed.
Run from any directory with python3.12 -S -B <this file>.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent.parent / "20260911_rl_research" / "literature_merged.json"

# Curated reading notes: scopes describe this round, not every downloaded page.
NOTES = {
    "S01_dagger": dict(
        short="DAgger", core=True,
        path=["真实任务损失驱动的策略改进", "诱导状态分布", "数据聚合动作示范"],
        reading="正文§1–4的方法和实验；未逐项复核附录定理",
        problem="行为克隆部署时遇到自身错误诱导的输入分布，固定专家数据存在分布偏移。",
        method="迭代以当前/混合策略roll-in，查询专家动作并聚合数据，以no-regret学习器更新策略。",
        update="将学习策略诱导的状态纳入后续训练；其标签仍为专家动作而非成本差。",
        benchmarks=["Super Tux Kart", "Super Mario", "OCR"],
        protocol="比较监督学习及迭代模仿基线；任务与评价不同，不构成本题秒/源对照。",
        results="正文展示聚合数据改善顺序预测；本报告不跨图读取单一综合改善百分比。",
        limits="不能仅靠动作模仿保证超过教师；理论依赖no-regret等条件，本提案小网络不自动满足。",
        transfer="仅借诱导状态采样；本题主标签改为真实完整配对剩余费用。"),
    "S02_lols": dict(
        short="LOLS", core=True,
        path=["真实任务损失驱动的策略改进", "roll-in与roll-out解耦", "参考及学得策略续局混合"],
        reading="正文§2–5，算法1、roll-in/roll-out比较与实验表；非附录逐行证明审计",
        problem="次优reference及不匹配roll-in/roll-out使训练忽略学得策略真实访问或复合错误。",
        method="在学得策略产生的状态评估不同动作，以reference/learned混合续局得到结构化预测损失。",
        update="区分状态访问分布与后续策略；比较及混合二者以获得局部改进性质。",
        benchmarks=["POS tagging", "dependency parsing"],
        protocol="改变reference质量及roll-in/roll-out组合；局部结果依任务而异。",
        results="次优reference依存分析条件learned/mixture为90.2 UAS，learned/reference为87.1；POS条件reference续局有优势。",
        limits="非处处优于reference；结构化损失与有限宏操作部分观测控制不同，不迁移定理。",
        transfer="明确当前π_j roll-in/tail；首版不用混合tail，避免标签语义多版本。"),
    "S03_aggrevated": dict(
        short="AggreVaTeD", core=True,
        path=["真实任务损失驱动的策略改进", "cost-to-go策略优化", "可微策略更新"],
        reading="正文引言、算法/梯度推导与实验章节；未独立核所有理论证明",
        problem="仅模仿专家动作忽略动作损失差，难利用可查询cost-to-go的训练信号。",
        method="将cost-to-go oracle用于可微模仿学习，提出相应随机梯度及自然梯度更新。",
        update="可用专家未来成本指导连续/高维策略，不必从随机奖励探索开始。",
        benchmarks=["robotic control", "partially observed control", "dependency parsing"],
        protocol="比较行为克隆、模仿/强化学习方法；有可供查询的oracle条件。",
        results="报告多任务性能和样本效率改善；本报告未将曲线视觉读数转作本题预期提升。",
        limits="训练oracle可得性和质量是关键；C7续局不等于论文近最优oracle。",
        transfer="借完整未来损失查询，不照搬natural gradient；本题先配对回报回归。"),
    "S04_spibb": dict(
        short="SPIBB", core=True,
        path=["限制统计/执行风险", "低数据支持约束", "复制基线概率质量"],
        reading="正文§2–4：Π_b-SPIBB定义、保证条件与实验；区分理论版和放松版",
        problem="固定数据离线策略改进可能在低支持状态动作上发生外推并劣于基线。",
        method="对不够支持的state-action复制基线策略概率，在有支持区域进行改进。",
        update="以baseline bootstrapping约束策略类；理论分析与深度伪计数实验分层。",
        benchmarks=["random MDP", "stochastic grid world", "helicopter navigation"],
        protocol="有限折扣MDP理论与连续深度实验不是同一保证；比较数据规模/风险表现。",
        results="支持基线约束有助降低不安全改进风险；不引用为本题经验分位数的保证。",
        limits="有限MDP、覆盖/误差条件不能直接用于本题压缩历史和分布改变后的门控。",
        transfer="仅借不足支持回基线原则；本题用经验裕量，明示不是SPIBB实现。",
        code=["https://github.com/RomainLaroche/SPIBB", "https://github.com/rems75/SPIBB-DQN"]),
    "S05_residual": dict(
        short="Residual RL", core=True,
        path=["控制对象的分解", "保留解析控制", "学习连续动作残差"],
        reading="正文方法与simulation/real robot实验，Fig.3及实体块装配结果",
        problem="已知反馈控制可处理大部分物理，但接触摩擦残差难建模且手调脆弱。",
        method="将传统控制器信号与学得连续残差信号叠加，使用off-policy RL训练残差。",
        update="保留解析先验，把学习容量用于模型不擅长的控制部分。",
        benchmarks=["MuJoCo control", "real-world block assembly"],
        protocol="手工控制、纯学习/残差在特定控制和错位块装配条件比较。",
        results="Fig.3错位实体块实验为残差15/20、手工控制2/20成功；小样本任务限定。",
        limits="本题不是连续扭矩叠加；不能迁移机器人训练时间、稳定性或样本效率。",
        transfer="采用保留强控制器、限制改变范围的原则；动作改为离散整段服务替换。",
        project=["https://residualrl.github.io"]),
    "S06_aggrevate": dict(
        short="NRPI / AggreVaTe", core=True,
        path=["真实任务损失驱动的策略改进", "cost-to-go策略优化", "当前策略完整续局标签"],
        reading="§2 AggreVaTe，§2.5专家续局反例，§3 NRPI算法及理论条件；非全文证明复核",
        problem="动作模仿不利用任务成本；以不适合的专家tail估计动作价值会过于乐观。",
        method="AggreVaTe查询专家cost-to-go；NRPI查询当前策略cost-to-go，将策略改进规约为交互no-regret学习。",
        update="训练标签依据冻结当前策略完整续局，更新后重新采样相应状态及cost-to-go。",
        benchmarks=[],
        protocol="以理论框架、算法和窄路反例为主；不当作本题或现代神经网络基准成绩。",
        results="提供近似策略迭代/no-regret分析；§2.5说明专家tail不能无条件代表学习策略未来。",
        limits="分布覆盖、损失/学习器等假设不可自动由有限样本非凸回归满足。",
        transfer="本提案最近机制祖先；γ=1变长operation、预算b及部分观測均是本题另立合同。"),
    "S07_catnipp": dict(
        short="CAtNIPP", core=True,
        path=["主动信息决策的表示与动作约束", "显式空间候选表示", "GP图与预算mask"],
        reading="正文§3–5：GP图、注意力/LSTM/Pointer/PPO、奖励与仿真/机器人实验",
        problem="连续信息路径规划需同时考虑预测不确定性、空间结构及剩余预算。",
        method="GP增强图输入注意力网络、LSTM与Pointer；PPO选择图中下一点，mask保留返程可行性。",
        update="将belief和预算约束纳入候选表示与动作选择，不是本文原创的注意力+循环组合。",
        benchmarks=["Gaussian random field IPP", "TurtleBot3 printed grayscale maps"],
        protocol="每预算30个实例×10次试验；机器人灰度图实验另列。",
        results="展示信息收集与路径规划性能；动态归一化信息奖励和原目标仍有偏差。",
        limits="到终点及信息质量不等于未知多频道全部清除；GP也不描述本题固定测角/可见性。",
        transfer="借显式候选及预算mask，拒绝把熵/面积下降直接代替秒/源。",
        code=["https://github.com/marmotlab/CAtNIPP"]),
    "S08_offripp": dict(
        short="OffRIPP", core=True,
        path=["主动信息决策的表示与动作约束", "离线数据支持", "行为约束候选Q"],
        reading="正文方法Eq.4与实验Table I；2D/3D设置及数据/成本范围",
        problem="IPP在线收集训练数据昂贵，离线Q又会外推到缺乏行为支持的候选。",
        method="拟合行为分布，在行为支持内使用batch-constrained Q选择信息路径候选。",
        update="以数据支持约束Q选择；与当前提案可fork获得真实counterfactual的条件不同。",
        benchmarks=["2D light-intensity IPP", "3D fruit recognition IPP"],
        protocol="各50测试实例，expert/greedy/random数据条件；CAtNIPP对照是naive offline PPO。",
        results="Table I expert数据预算10：covariance trace行为3.73、OffRIPP3.96、BC7.02（低好）；未超过行为专家。",
        limits="Eq.4不等号与τ端点文字冲突；不能推出Q普遍优于正确on-policy PPO；论文算力不移植。",
        transfer="作为旧约束Q近祖和负面边界，首版不继续将支持内宏排序Q当主突破口。"),
    "S09_rf": dict(
        short="RF active sensing", core=False,
        path=["主动信息决策的表示与动作约束", "RF部分观测表示", "高维IQ与循环策略"],
        reading="v1正文输入/网络/实验指定章节；只作扩展邻近任务，不新增核心结论",
        problem="多径环境中单RF观测难确定发射源位置，需要主动移动和历史信息。",
        method="2×2天线IQ、深度特征和可选循环模块，比较DQN/PPO及环境迁移。",
        update="通过主动观测与记忆处理RF多径歧义。",
        benchmarks=["Sionna industrial hall emitter localization"],
        protocol="单静态源、多天线IQ；PPO/DQN折扣和环境并行不同，测试N未在本轮落实。",
        results="论文报告80.1%定位成功；不同信息/配置，不作本题RL选型因果依据。",
        limits="current/goal输入的部署可得性和对比配置不一致；本题多源离散接口不匹配。",
        transfer="提醒部分观测表示问题；不因此认定必须PPO/LSTM。"),
    "S10_multistep": dict(
        short="Multi-step PPI", core=False,
        path=["真实任务损失驱动的策略改进", "离线actor优化", "重定中心近端多步改进"],
        reading="2026-09-03 v1摘要、引言、目录；未深读实验和证明",
        problem="离线actor需保留数据支持，又希望获得超过单步近端更新的改进。",
        method="顺序重定中心的proximal policy improvement，可用于确定性或高斯策略。",
        update="区分多个重定中心步和同一固定目标下更多优化步。",
        benchmarks=["D4RL (abstract claim only)"],
        protocol="摘要提及TD3+BC/ReBRAC/IQL；本轮未核完整配置/分母。",
        results="仅记录摘要主张若干任务改善；不引用其数字或普遍效力。",
        limits="v1明确未经同行评审；仍依赖critic误差，未解决本题缺完整反事实标签。",
        transfer="作为近期竞争优化机制扩展，暂不采用。"),
    "S11_shield": dict(
        short="Shielding", core=True,
        path=["限制统计/执行风险", "执行约束", "形式规格前置与后置屏障"],
        reading="正文安全规格、shield构造、前置/后置方案与实验边界；不复核全部证明",
        problem="只最大化奖励的RL可能在训练或执行期违背安全规格。",
        method="依据环境抽象及temporal-logic规格合成shield，预先给安全动作或事后修正违规动作。",
        update="将安全约束的执行层与奖励学习分离。",
        benchmarks=["9x9 and 15x9 robot grid worlds", "self-driving car", "Atari Seaquest", "water tank"],
        protocol="具有给定抽象/规格条件的shield实验；本轮不建立统一数值榜。",
        results="展示不同RL场景下屏障作用；本题无直接部署试验。",
        limits="safety fragment不自动证明最终全部清除的liveness；可靠抽象是前提。",
        transfer="保留四接口、几何证书、有限进展及独立fallback，不以统计阈值代替。",
        code=["https://github.com/safe-rl/safe-rl-shielding"]),
    "S12_robust_ipp": dict(
        short="DyPNIPP", core=False,
        path=["主动信息决策的表示与动作约束", "环境变化适应", "动态预测context与域随机化"],
        reading="本轮只读arXiv元数据/摘要；尝试HTML v2返回404，未取得所请求正文",
        problem="IPP在时空动态不同的环境间缺乏鲁棒性。",
        method="摘要描述domain randomization与dynamics prediction model辅助策略。",
        update="以context适应不同环境动态（仅摘要层）。",
        benchmarks=["wildfire environment (abstract)"],
        protocol="本轮未核正文设置/数据规模，不复用旧轮深读标签。",
        results="仅摘要声称鲁棒性提高；本轮不报告数值。",
        limits="本题源静态；HTML获取失败不等于全文不存在，当前机制证据深度有限。",
        transfer="作为将来域变化路线，不引入本题没有的移动源。"),
    "S13_recurrent": dict(
        short="RESeL", core=False,
        path=["主动信息决策的表示与动作约束", "历史记忆训练", "context编码器独立学习率"],
        reading="本轮只读元数据/摘要；尝试HTML v3返回404，未复读旧轮正文",
        problem="recurrent off-policy RL的context编码器与MLP共同学习率可能不稳定。",
        method="对context encoder采用更低学习率，集成现有off-policy方法。",
        update="分离表示学习和决策网络的优化尺度（摘要）。",
        benchmarks=["18 POMDP tasks (abstract)", "5 MDP locomotion tasks (abstract)"],
        protocol="本轮没有核正文表格和实验超参。",
        results="摘要报告稳定性/性能改善；本轮不作精确效果比较。",
        limits="循环结构不保证本题收益，获取的摘要不能替代复现或证明。",
        transfer="提醒GRU不能当无代价修补；首版先简单集合编码。"),
    "S14_tdmpc2": dict(
        short="TD-MPC2", core=False,
        path=["控制对象的分解", "学习预测模型", "隐式世界模型局部规划"],
        reading="本轮arXiv摘要/元数据；未重新下载正文",
        problem="连续控制世界模型和规划的鲁棒性/跨任务可扩展性。",
        method="隐式latent world model中作局部轨迹优化并预测价值。",
        update="TD-MPC系列改进，扩展跨任务模型规模（摘要）。",
        benchmarks=["104 online RL tasks, 4 domains (abstract)"],
        protocol="摘要说明统一超参及规模实验；本轮未核正文可比性。",
        results="摘要报告104任务和317M参数80任务模型；只是来源背景，不是本题算力要求。",
        limits="重学已知移动物理可能浪费；离散可见性边界难以无误差学习。",
        transfer="暂不采用完整世界模型；先用真实模拟器生成成本标签。",
        project=["https://tdmpc2.com"]),
    "S15_fql": dict(
        short="FQL", core=False,
        path=["主动信息决策的表示与动作约束", "连续动作分布", "flow行为模型与一步Q策略"],
        reading="本轮arXiv元数据/摘要；未重新深读方法正文",
        problem="复杂离线动作分布难用简单策略表示，迭代flow的RL优化昂贵。",
        method="flow-matching行为表示配合一步策略接受Q学习，避免反复反传迭代flow。",
        update="将表达性行为模型与快速一步动作策略分开（摘要）。",
        benchmarks=["73 OGBench/D4RL tasks (abstract)"],
        protocol="state/pixel、offline/offline-to-online多设置；本轮无公平数值比较。",
        results="仅保留摘要跨任务主张，不预测本题增益。",
        limits="本题有限离散候选未证明需连续多峰生成器；不核代码即不声称可运行。",
        transfer="连续落点若后续确为瓶颈再比较；首版不使用flow。",
        project=["https://seohong.me/projects/fql/"]),
    "S16_cids": dict(
        short="C-IDS", core=False,
        path=["主动信息决策的表示与动作约束", "信息与任务回报联合", "context互信息目标"],
        reading="本轮arXiv元数据/摘要；不重述旧轮未独立核通过的证明为已验证",
        problem="未知latent context的POMDP中同时优化奖励和context识别。",
        method="加入context与观测的互信息，构造information-directed目标。",
        update="以拉格朗日形式关联信息ratio与策略目标（摘要）。",
        benchmarks=["continuous Light-Dark (abstract)"],
        protocol="上下文假设及Bayesian regret证明本轮未独立核验。",
        results="仅保留摘要方法与实验主张，不采用理论保证。",
        limits="ensemble分歧不等于互信息；本题需另行定义context与观测模型。",
        transfer="不把本题Q差和预测残差命名为真实information ratio。"),
}


def norm_title(title):
    return re.sub(r"\W+", "", title.lower())


def build():
    acquired = json.loads((ROOT / "sources/acquisition.json").read_text())
    old = json.loads(OLD.read_text())
    old_titles = {norm_title(r["title"]): r["id"] for r in old["records"]}
    records = []
    for entry in acquired["sources"]:
        sid = entry["id"]
        note = NOTES[sid]
        meta = entry["metadata"]
        title = meta["citation_title"][0]
        date = (meta.get("citation_publication_date") or meta.get("citation_date"))[0]
        primary = entry["acquisitions"][0]["url"]
        arxiv = (meta.get("citation_arxiv_id") or [None])[0]
        stable = f"arxiv:{arxiv}" if arxiv else "pmlr:" + primary.split("press/")[1].replace(".html", "")
        venue = (meta.get("citation_inbook_title") or ["arXiv preprint; formal venue not independently verified this round"])[0]
        if sid == "S07_catnipp":
            venue = "CoRL 2022; PMLR volume 205 published 2023-03-06"
        if sid == "S10_multistep":
            venue = "arXiv v1; manuscript explicitly states not peer-reviewed"
        path = ["利用强基线改善部分可观测控制"] + note["path"]
        body = entry["acquisitions"][1:]
        records.append({
            "id": sid, "stable_id": stable, "short_name": note["short"],
            "title": title, "authors": meta["citation_author"],
            "year": int(date[:4]), "publication_date": date.replace("/", "-"),
            "latest_metadata_date": (meta.get("citation_online_date") or [date])[0].replace("/", "-"),
            "venue_or_public_status": venue,
            "presentation_award_status": "not checked; no Oral/Spotlight/Award claim",
            "paper_url": primary, "fulltext_urls": [a["url"] for a in body],
            "project_urls": note.get("project", []), "code_urls": note.get("code", []),
            "data_urls": [],
            "code_data_verification": "source-linked URLs only where present; not cloned, executed or independently audited this round; absent URLs mean not established, not nonexistent",
            "source_tier": "primary", "corpus_layer": "core" if note["core"] else "extended",
            "identity_verification": "primary publisher/arXiv metadata retrieved with date, bytes and SHA256",
            "reading_scope": note["reading"],
            "body_retrieval_status": "retrieved" if body and all(a["returncode"] == 0 for a in body) else ("attempted_body_failed" if body else "not_requested"),
            "problem": note["problem"], "core_method": note["method"],
            "update_mechanism": note["update"], "datasets_benchmarks": note["benchmarks"],
            "experiment_comparison_protocol": note["protocol"], "reported_results": note["results"],
            "limitations_and_unproved": note["limits"], "transfer_to_this_project": note["transfer"],
            "transfer_status": "research hypothesis; no project effectiveness run",
            "primary_classification_path": path,
            "secondary_tags": ["counterfactual proposal relevance" if note["core"] else "alternative or boundary", "no cross-paper SOTA claim"],
            "classification_confidence": "high" if note["core"] else "medium: reading scope limited",
            "previous_corpus_match": old_titles.get(norm_title(title)),
            "acquisition_evidence": entry["acquisitions"],
        })
    counts = {
        "this_round_unique": len(records),
        "core_specified_sections": sum(r["corpus_layer"] == "core" for r in records),
        "extended": sum(r["corpus_layer"] == "extended" for r in records),
        "previous_unique": len(old["records"]),
        "overlap_previous": sum(r["previous_corpus_match"] is not None for r in records),
        "new_identities": sum(r["previous_corpus_match"] is None for r in records),
    }
    counts["union_with_previous"] = counts["previous_unique"] + counts["new_identities"]
    manifest = {
        "schema": "bc-rpi-research-corpus-v1", "as_of": "2026-09-12",
        "status": "research proposal only; no training/simulator/policy runs",
        "scope": "Targeted mechanism expansion after local BC/PPO/Q negative results; main recent window 2024-01-01 through 2026-09-12 plus mechanism ancestors from 2011; not exhaustive novelty search.",
        "counts": counts,
        "deduplication": "This corpus uses arXiv base ID or PMLR stable ID. Cross-round identity matches normalized exact title against preserved 41-record corpus; inspect match IDs, not counts alone.",
        "prior_corpus": str(OLD.relative_to(ROOT.parent.parent)),
        "prior_corpus_sha256": hashlib.sha256(OLD.read_bytes()).hexdigest(),
        "records": records,
    }
    (ROOT / "literature.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    lines = ["# 本轮16篇来源：分类与逐篇阅读边界", "", "从 [literature.json](literature.json) 生成；只生成索引，不替代原文核验。9篇核心指定章节阅读，7篇扩展；本轮与旧41篇重叠9篇，新增身份7篇，并集48篇。", ""]
    # Keep the same main-branch order as the proposal; each paper appears once.
    branch_order = ["控制对象的分解", "真实任务损失驱动的策略改进", "主动信息决策的表示与动作约束", "限制统计/执行风险"]
    for branch in branch_order:
        lines += [f"## {branch}", ""]
        for r in records:
            if r["primary_classification_path"][1] != branch:
                continue
            lines += [f"### {r['id']} · [{r['title']}]({r['paper_url']})", "",
                      f"主路径：{' → '.join(r['primary_classification_path'][1:])}。", "",
                      f"身份：{r['publication_date']}；{r['venue_or_public_status']}。层级：{r['corpus_layer']}。", "",
                      f"实际阅读：{r['reading_scope']}。", "",
                      f"问题：{r['problem']}", "", f"机制：{r['core_method']}", "",
                      f"实验/效果：{r['experiment_comparison_protocol']} {r['reported_results']}", "",
                      f"边界：{r['limitations_and_unproved']}", "",
                      f"本题取舍：{r['transfer_to_this_project']}", ""]
    (ROOT / "LITERATURE_MAP.md").write_text("\n".join(lines))
    print(json.dumps(counts, ensure_ascii=False))


if __name__ == "__main__":
    build()
