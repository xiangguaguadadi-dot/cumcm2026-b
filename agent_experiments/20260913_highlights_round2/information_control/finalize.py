"""Independent aggregation and artifact hashing for the two Q3 ablations."""
from __future__ import annotations
import hashlib, json, math, statistics
from pathlib import Path

HERE=Path(__file__).resolve().parent
def load(p): return json.loads(Path(p).read_text())
def save(p,x): Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+"\n")
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def arm(name):
    raw=load(HERE/name/"summary.json"); pairs=load(HERE/name/"pairs.json")
    groups=[]
    for group in sorted({p["group"] for p in pairs}):
        z=[p for p in pairs if p["group"]==group]; ds=[p["delta_s_per_source"] for p in z]
        groups.append({"group":group,"cases":len(z),"candidate_minus_b3_mean_s_per_source":statistics.fmean(ds),
                       "faster":sum(d < -1e-8 for d in ds),"equal":sum(abs(d)<=1e-8 for d in ds),"slower":sum(d>1e-8 for d in ds)})
    return {"actual_runs":raw["actual_runs"],"sources":raw["sources"],"all_complete":raw["all_candidate_complete"] and raw["all_parent_complete"],
            "candidate_mean_s_per_source":raw["candidate_mean_s_per_source"],"b3_mean_s_per_source":raw["b3_mean_s_per_source"],
            "candidate_minus_b3_mean_s_per_source":raw["candidate_minus_b3_mean_s_per_source"],
            "b3_saving_vs_ablation_s_per_source":raw["candidate_minus_b3_mean_s_per_source"],
            "b3_saving_vs_ablation_pct":100*raw["candidate_minus_b3_mean_s_per_source"]/raw["candidate_mean_s_per_source"],
            "cluster_bootstrap_95pct_candidate_minus_b3":raw["cluster_bootstrap_95pct_delta"],
            "faster":raw["faster"],"equal":raw["equal"],"slower":raw["slower"],
            "request_delta_candidate_minus_b3":raw["candidate_requests"]-raw["b3_requests"],
            "distance_delta_m_candidate_minus_b3":raw["candidate_distance_m"]-raw["b3_distance_m"],
            "failed_clear_delta_candidate_minus_b3":raw["candidate_clear_failures"]-raw["b3_clear_failures"],
            "candidate_sha256":raw["candidate_sha256"],"groups":groups}

reg=load(HERE/"registration.json")
for x in reg["inputs"].values(): assert sha(HERE.parents[2]/x["path"])==x["sha256"]
for name,x in reg["candidates"].items(): assert sha(HERE/x["path"])==x["sha256"]
assert sha(HERE/reg["runner"]["path"])==reg["runner"]["sha256"]
summary={"evidence":"existing exposed LOCAL-v1 Q3 regression; not blind and not official Windows testing",
         "comparisons_are_paired_to":"frozen saved B3 rows on identical case IDs and physical worlds",
         "station_retest_gate":arm("full_gate_off"),"preemptive_replanning":arm("full_replan_off"),
         "total_new_full_strategy_runs":2400,"total_new_quick_strategy_runs":120,
         "multiplicity_note":"Intervals are ordinary preregistered 95% seed-cluster bootstraps for these two comparisons; no cross-agent Holm adjustment is claimed here.",
         "raw_field_note":"Raw full summaries contain a misnamed b3_improvement_s_per_source field with reversed sign; candidate_minus_b3_mean_s_per_source is authoritative and this aggregate reports B3 saving with the correct positive sign."}
save(HERE/"summary.json",summary)

lines=["# 信息价值门控与可中断滚动服务：Q3当前B3单因素消融","",
"本轮在当前B3上实际关闭两个不同组件，各执行60局quick和1200局full。两项full均清除15550个源、1200/1200局正常全清。比较逐案例复用已核验的B3保存行，案例ID、真源世界与误差场完全一致；这些世界已经暴露，结果不是盲测或官方Windows成绩。","",
"## 结论","",
"| 当前B3中保留的机制 | 关闭后的秒/源 | B3秒/源 | B3节省 | 关闭−B3的簇bootstrap 95%区间 | 更快/相同/更慢（关闭臂） |","|---|---:|---:|---:|---:|---:|" ]
for title,key in [("站内已知频道的信息价值/费用门控","station_retest_gate"),("单轮服务后全局重规划","preemptive_replanning")]:
    a=summary[key]; lines.append(f"| {title} | {a['candidate_mean_s_per_source']:.6f} | {a['b3_mean_s_per_source']:.6f} | {a['b3_saving_vs_ablation_s_per_source']:.6f}秒/源（{a['b3_saving_vs_ablation_pct']:.3f}%） | [{a['cluster_bootstrap_95pct_candidate_minus_b3'][0]:.6f}, {a['cluster_bootstrap_95pct_candidate_minus_b3'][1]:.6f}] | {a['faster']}/{a['equal']}/{a['slower']} |")
lines += ["",
"### 新亮点A：给顺路复测加信息价值/费用门控","",
"扫描站已经付出到站移动费后，旧规则会对所有可接收的已知频道顺手复测。B3先检查位置域是否已经能认证清除，再用公开可行域上的后续费用估计判断一次复测是否仍有正价值。关闭门控后多发出6014个请求，虽然总路程反而少10416.854米、失败试清少314次，完整费用仍增加2.269462秒/源。这说明只统计路程或失败清除会得出相反结论；5秒测向费与频道切换费必须共同进入决策。","",
"证据等级：当前完整策略的同世界、单开关、本地暴露回归。它支持该门控在这1200个Q3世界中的条件贡献；门控中的未来收益仍是规划近似，不是任意未知分布下的最优停止定理。","",
"### 新亮点B：一次只服务一轮信息，再回到全局队列","",
"每个频道保留累计定位进度，但一次只执行一轮定位动作，随后让全局路线重新比较所有待处理频道和搜索站。关闭该机制时，同一频道会连续服务到清除或轮数上限。关闭臂少742个请求，却额外移动190060.317米、增加204次失败试清，最终多2.189767秒/源。这个反例直接表明“请求更少”不等于“完整任务更快”；可中断服务的价值来自避免长期绑定当前频道。","",
"证据等级：当前完整策略的同世界、单方法覆盖消融、本地暴露回归。该开关替换的是Q3的localize控制范围；几何、B3第二测点、搜索覆盖与物理规则保持相同。","",
"## 严格边界与负例","",
"- 门控关闭臂仍有16局更快、291局相同；重规划关闭臂仍有260局更快、252局相同。不能写成逐局支配。","- full是quick的超集，两者不能合并成1260个独立案例。full结论使用1200局。","- 两个普通95%区间尚未与其他子Agent的比较合并做Holm校正；总报告若宣称多重检验显著性，应统一校正。","- 原始full summary里的`b3_improvement_s_per_source`字段命名与符号相反；正确差值以`candidate_minus_b3_mean_s_per_source`为准，本汇总已改用正的B3节省量。","",
"## 复现命令","","见 `COMMANDS.md`。输入及候选在执行前登记于`registration.json`，逐局结果、配对差值和分场景结果完整保留。","" ]
(HERE/"RESULTS.md").write_text("\n".join(lines))

# Hash all finalized artifacts except the manifest itself.
files=[]
for p in sorted(HERE.rglob("*")):
    if p.is_file() and p.name not in {"artifact_manifest.json"} and "__pycache__" not in p.parts:
        files.append({"path":str(p.relative_to(HERE)),"sha256":sha(p),"bytes":p.stat().st_size})
save(HERE/"artifact_manifest.json",{"files":files,"file_count":len(files)})
print(json.dumps({"ok":True,"file_count":len(files),"runs":2520},ensure_ascii=False))
