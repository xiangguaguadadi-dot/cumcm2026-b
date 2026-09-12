"""Independent row-level checks and evidence-bounded information report."""
import collections,decimal,hashlib,json,math,statistics,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def lines(p):return [json.loads(l) for l in p.read_text().splitlines()]
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def point_inside(poly,p):
    values=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        length=math.dist(a,b)
        if length>1e-7:values.append(((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]))/length)
    return all(v>=-1e-6 for v in values) or all(v<=1e-6 for v in values)
def audit_q2(rows):
    assert len(rows)==160 and len({r['condition_id'] for r in rows})==160
    witnesses=0;failures=[];source_probes=0;probe_failures=[]
    for r in rows:
        delta=math.radians(r['error_halfwidth_deg']);target=r['target_center_local'];budget=r['budget_m']
        assert {m['method'] for m in r['methods']}=={'fixed','analytic','actual_prior_search'}
        for m in r['methods']:
            q=m['q'];move=math.hypot(*q)
            centers=[(0.,0.),(1000*math.cos(delta),1000*math.sin(delta)),(1000*math.cos(delta),-1000*math.sin(delta))]
            if move>budget+1e-6 or any(math.dist(q,c)>1000+1e-6 for c in centers):failures.append([r['condition_id'],m['method'],'unsafe'])
            w=m['witness']
            if w:
                witnesses+=1;pair=w['pair'];z=math.radians(w['common_second_reading_deg'])
                for p in pair:
                    ok=(5.<math.hypot(*p)<=1500+1e-6 and 5.<math.dist(p,q)<=1500+1e-6 and math.dist(p,target)<=1800+1e-6
                        and abs(math.atan2(p[1],p[0]))<=delta+1e-9
                        and abs(math.remainder(math.atan2(p[1]-q[1],p[0]-q[0])-z,2*math.pi))<=delta+1e-9)
                    if not ok:failures.append([r['condition_id'],m['method'],'illegal_source_pair',p])
                if abs(math.dist(*pair)/2-m['radius_lower_legal_pair_m'])>1e-7:failures.append([r['condition_id'],m['method'],'pair_lower_mismatch'])
            if m['radius_lower_legal_pair_m']>m['radius_upper_continuous_enclosure_m']+1e-6:failures.append([r['condition_id'],m['method'],'reversed_bounds'])
        # Direct circle/ray intersections generate legal sources without using
        # the clipping implementation; each must belong to the outer prior.
        for factor in (-1.,-.5,0.,.5,1.):
            ang=delta*factor;u=(math.cos(ang),math.sin(ang));dot=u[0]*target[0]+u[1]*target[1]
            radmax=min(1500.,dot+math.sqrt(dot*dot+1800**2-target[0]**2-target[1]**2))
            for frac in (.001,.25,.5,.75,.999):
                rad=5.+(radmax-5.)*frac;p=(rad*u[0],rad*u[1]);source_probes+=1
                if not point_inside(r['outer_prior'],p):probe_failures.append(dict(condition_id=r['condition_id'],source=p))
    decimal.getcontext().prec=60;DD=decimal.Decimal
    pi=DD('3.1415926535897932384626433832795028841971693993751058209749445923');x=pi/180;term=x;s=x
    for k in range(1,20):term*=-(x*x)/(DD(2*k)*DD(2*k+1));s+=term
    exact=1500*s/(1+s)
    return dict(condition_rows=160,method_rows=480,legal_pair_witnesses_checked=witnesses,failures=failures,
        independent_circle_ray_outer_prior_probes=source_probes,outer_prior_probe_failures=probe_failures,
        theoretical_radius_decimal_60digits=str(exact),ordinary_float_numeric_limits='All geometry is double precision except this independent scalar Decimal check; no interval arithmetic')
def main():
    q4=read(HERE/'q4_full/summary.json');stress=read(HERE/'q4_stress/summary.json');q2=read(HERE/'q2_all_bounds/summary.json')
    coarse=read(HERE/'q2_coarse/summary.json');rows=lines(HERE/'q2_all_bounds/condition_rows.jsonl');audit=audit_q2(rows)
    assert not audit['failures'] and not audit['outer_prior_probe_failures']
    write(HERE/'FINAL_AUDIT.json',audit)
    extra={}
    for d in (1.,1.005001):
        rr=[r for r in rows if r['error_halfwidth_deg']==d];short=[r for r in rr if r['methods'][-1]['move_m']<r['budget_m']-1e-6]
        def relation(a,b):
            return 'better' if a['radius_upper_continuous_enclosure_m']<b['radius_lower_legal_pair_m'] else 'worse' if a['radius_lower_legal_pair_m']>b['radius_upper_continuous_enclosure_m'] else 'unresolved_or_equal'
        extra[str(d)]=dict(shorter_optimized_moves=len(short),equal_full_budget_moves=len(rr)-len(short),
            equal_full_budget_separated_better=sum(r['optimized_vs_fixed']=='certified_better' for r in rr if r not in short),
            analytic_vs_fixed=dict(collections.Counter(relation(r['methods'][1],r['methods'][0]) for r in rr)),
            unresolved_conditions=[dict(condition_id=r['condition_id'],first_station_radius_m=r['first_station_radius_m'],first_bearing_relative_deg=r['first_bearing_relative_deg'],budget_m=r['budget_m'],methods=r['methods']) for r in rr if r['optimized_vs_fixed']!='certified_better'],
            thresholds_by_method={name:{str(t):dict(collections.Counter(m['thresholds'][str(t)] for r in rr for m in r['methods'] if m['method']==name)) for t in (20,50,100)} for name in ('fixed','analytic','actual_prior_search')})
    q4events=lines(HERE/'q4_quick/same_state_events.jsonl')+lines(HERE/'q4_remaining/same_state_events.jsonl')
    bins={}
    for label,predicate in [('1 negative',lambda e:e['negative_observations']==1),('2-3 negatives',lambda e:2<=e['negative_observations']<=3),('4-7 negatives',lambda e:4<=e['negative_observations']<=7),('8+ negatives',lambda e:e['negative_observations']>=8)]:
        part=[e for e in q4events if predicate(e)];bins[label]=dict(updates=len(part),shrinks=sum(e['area_removed_m2']>1e-6 for e in part),mean_fractional_shrink=statistics.mean(e['fractional_shrink'] for e in part) if part else None)
    summary=dict(label='Actual scoped experiment group C; LOCAL Q4 execution plus constructed Q2 geometry, not official scores',
        frozen_candidate_sha256=sha(ROOT/'最佳方法/代码/solver.py'),q4=q4,q4_stress=stress,q4_same_state_by_negative_count=bins,
        q2_coarse=coarse,q2_continuous_full=q2,q2_detailed=extra,independent_audit=audit,
        failures_and_limits=['Original Q4 observer had 2 false positives from approximately duplicate edges; preserved and corrected with 2 actual confirmation executions.',
            'Q4 quick worsened; full paired confidence interval crosses zero, so independent speed benefit is not established.',
            'Three Q2 conditions per error bound are unresolved or equal; all are retained.',
            'Q2 optimized search uses the same movement cap, but selects a shorter actual movement in 18/80 conditions per error bound.',
            'Q2 continuous reading coverage is geometric and computed in ordinary double precision, not interval-certified arithmetic or continuous-q global optimization.',
            'The conservative 5 m upper bound for the near branch is included even when impossible; it may dominate and widen small-radius intervals.',
            'Two error bounds are sensitivity models on the same 80 geometries, not 160 independent sampled worlds.'])
    write(HERE/'summary.json',summary)
    q=q4['overall'];ci=q4['seed_cluster_bootstrap_95ci_delta_s_per_source'];ss=q4['same_state']
    f=lambda x:f'{x:.6f}'
    text=['# 实验C：负反馈几何与第二问精度','',
        '本次实际完成Q4开启/关闭无信号楔约束的2400个同世界配对，以及Q2的80条件×2误差界×3方法的粗筛与连续读数包络。未修改当前solver、冻结evaluation或主汇总；全部结果属于本地模型或构造几何，不是官方测试。','',
        '## 主要结果','',
        f'- **Q4几何机制成立，但独立提速未被分辨。** 开启 {f(q["on"]["average_clear_time_s"])}、关闭 {f(q["off"]["average_clear_time_s"])} 秒/源；开启−关闭为 {f(q["mean_delta_s_per_source"])}，200个种子簇bootstrap 95%区间 [{f(ci[0])}, {f(ci[1])}] 跨0。',
        '- **Q2两种误差界各自均有77/80条件分辨出精度优势，0个分辨出退步，3个相同或区间重叠。** 判据是新点的连续读数上界小于固定方向的合法点对下界，不是比较两个随机最大值。',
        '- **两測25.729567米信息下界已独立复算。** 它否定全部合法首测情形下的统一两测20米保证；不是紧最优值，也不表示每个首测情形都无法达到20米。','',
        '## Q4：只切换无信号楔约束','',
        '父策略为当前B3，SHA256 `e6a0666d644ceaa1d7ae69f19042b9ca022379f3e5a57d927e52bcf1a09360bd`。两臂唯一决策配置差异为 `convex_no_signal=True/False`；都保留失败清除格排除、原测点和清除策略。关闭臂没有借用Q3的1000米无信号排除圆。',
        '',
        '| 指标 | 开启楔约束 | 关闭楔约束 |','|---|---:|---:|',
        f'| 任务数 / 全清数 | 2400 / 2400 | 2400 / 2400 |',
        '| 源总数 | 30970 | 30970 |',
        f'| 案例平均秒/源 | {f(q["on"]["average_clear_time_s"])} | {f(q["off"]["average_clear_time_s"])} |',
        f'| 每局测向次数 | {q["on"]["measures"]:.4f} | {q["off"]["measures"]:.4f} |',
        f'| 每局试清次数 | {q["on"]["clear_attempts"]:.4f} | {q["off"]["clear_attempts"]:.4f} |',
        f'| 每局失败试清次数 | {q["on"]["clear_failures"]:.4f} | {q["off"]["clear_failures"]:.4f} |',
        f'| 每局移动米数 | {q["on"]["distance_m"]:.4f} | {q["off"]["distance_m"]:.4f} |',
        '',
        f'逐案例1173更快、103相同、1124更慢；原60对quick中开启反而慢0.616171秒/源，保留该负结果。完整12场景逐组结果在 `q4_full/summary.json`。计时指标先按每局总虚拟时间/实际清除数，再对局取均值；不会把它称为官方未公开总分。',
        '',
        f'在关闭臂的真实观测轨迹上，对可靠多边形副本应用同一楔函数：{ss["eligible_updates"]}个满足前提的状态中，{ss["effective_shrinks"]}次收缩，涉及{ss["affected_cases"]}局；有效收缩状态平均减少{100*ss["mean_fractional_shrink_effective_updates"]:.3f}%面积，最大{100*ss["max_fractional_shrink"]:.3f}%。这些事件重复使用同局历史，不能视为独立统计样本。评测观察器读取真源核查包含关系；真源从未传入决策器。',
        '',
        '物理几何压力集共1036夹具：1018个满足两个接收点加一个无信号点，0真源误排；5个近共线退化跳过。18个边界点按实际闭半平面/接收容差仍有信号，所以未伪作负观测应用。夹具多边形是声明的真源外包，未冒称完整策略后验；构造核查不能替代凸性证明。',
        '',
        '观察器勘误：原quick日志报告2次误排，均来自关闭臂 `LOCAL-v1-q4-minimum_radius-5003` 的频道20。连续重复顶点的边长为9.17e−13和1.60e−12米，归一化抵消误差生成了错误半平面方向；有效边对真源最小内部裕量为0.296246米。修正仅在评测包含检查中忽略远小于容差的退化边，同案例两臂重跑均全清且误排0。原脚本与原结果均保留，详见 `observer_correction.json`；汇总标明原2个观察器假阳性。实际执行总数4802，其中重复确认2次不计入2400对性能统计。',
        '',
        '## Q2：80条件与连续误差上包络','',
        '首测点(r,0)，r=0、600、1200、1750；非圆心首方向相对向外径向为0°、45°、90°、135°、180°，圆心仅0°，共16几何。移动上限300、500、√450000、850、1000米，共80条件。±1°与±1.005001°各自完整运行，不合并成独立样本。',
        '',
        '三种方法为固定600/300方向、局部条带公式生成的解析候选、实际首测相容区域上的有限候选搜索。三者共用三圆盘保守接收安全域；真实区域为1800米目标圆盘、首测角带与1500米接收圆盘的交，并处理正常读数距源>5米。每条件粗筛88个点，再做有界局部细化；原固定点和解析点均保留。',
        '',
        '**这里的同预算是相同移动上限。** 每种误差界中，实际区域搜索有18/80条件选择更短移动，62/80条件用满预算；在这62个等实际距离条件中仍有59个区间分离优势。不能把全部77个优势解释成仅改变方向的作用。',
        '',
        '| 误差半角 | 条件 | 新上界 < 固定下界 | 分辨出退步 | 相同/不可分辨 | 非法点对 |','|---|---:|---:|---:|---:|---:|','| 1° | 80 | 77 | 0 | 3 | 0 |','| 1.005001° | 80 | 77 | 0 | 3 | 0 |',
        '',
        '每个入选点均使用步长不超过0.01°的完整连续读数包络：每个读数单元的中点角带扩大为δ+h/2，首测圆弧采用外包多边形，取所有单元的包围半径最大值作为上界；每个下界保存两个满足目标圆域、两次接收、两次非near及角误差条件的具体源点。同读数点对距离/2只是最小包围圆半径的下界，不冒充精确半径。',
        '',
        '普通浮点计算附显式几何裕量，未使用区间算术；因此属于有连续覆盖论证的数值包络，不宣称形式化算术认证。第二点只在有限候选中选择，未证明连续点位域全局最优。粗筛160条件全部完成；先跑40代表包络后又完整跑160条件，代表结果不另计为新条件。',
        '',
        '圆心首测、理论±1°结果如下。区间为几何上下界，端点向外保留三位小数，不是置信区间：','',
        '| 移动上限m | 固定方向半径区间m | 解析候选半径区间m | 实际区域选点半径区间m |','|---|---:|---:|---:|']
    for r in rows:
        if r['error_halfwidth_deg']==1. and r['first_station_radius_m']==0:
            bounds=['['+f'{math.floor(m["radius_lower_legal_pair_m"]*1000)/1000:.3f}, {math.ceil(m["radius_upper_continuous_enclosure_m"]*1000)/1000:.3f}'+']' for m in r['methods']]
            text.append('| '+f'{r["budget_m"]:.3f}'+' | '+' | '.join(bounds)+' |')
    text += ['',
        '两种误差界的三个未分辨条件相同：r=600、θ=45°、上限1000米；r=1200、θ=90°、上限1000米；r=1750、θ=90°、上限300米。前两个实际搜索保留固定候选，后一个仅有很小差异、包络重叠。解析公式在这些截断首测区域上还可能比固定方向差；所有结果均保留在 `summary.json` 和逐条件原始行。',
        '',
        '作为阈值可行性示例，每种误差界下，固定方向7/80、解析候选10/80、实际区域候选22/80满足上界≤20米。这只是这些构造初始条件及入选点上的最坏精度保证，并不与圆心完整扇区的信息下界矛盾。近场分支统一保守上界5米，有些实际不可能near的点也被包含，因此小半径区间可能偏宽。',
        '',
        '两测下界复核：近源(5+ε,0)、接收半径1000迫使任意稳保第二点满足||q||≤1005。首测扇区包含圆心a=1500/(1+sinδ)、半径r=a sinδ的圆盘；q在圆外，沿q到圆心方向取直径两端，它们首测均可读0、第二测有完全相同方位，且均非near并可采用合法共同接收半径1500。间距2r迫使任何包围半径≥r。独立60位Decimal复算δ=1°给出 r='+audit['theoretical_radius_decimal_60digits']+'米。',
        '',
        '## 复核与文件','',
        '- `registration.json`：执行前登记。',
        '- `q4_full/summary.json`、`case_metrics.json`：完整2400配对；`q4_quick/`与`q4_remaining/`保留4800次实际执行原行。',
        '- `q4_quick/same_state_events.jsonl`、`q4_remaining/same_state_events.jsonl`：42296次副本几何比较；quick还保存具体多边形示例。',
        '- `q4_stress/fixtures.jsonl`：全部1036压力夹具及实际正负判定。',
        '- `q2_coarse/condition_rows.jsonl`：160条件全部候选与细化记录；`lower_theorem_recheck.json`：下界数值与不可区分点对。',
        '- `q2_all_bounds/condition_rows.jsonl`：160条件、480个方法点的连续上下界、实际移动与合法点对。',
        '- `FINAL_AUDIT.json`：独立核对480个点对与接收域，并用直接圆/射线求交生成4000个源点检查外包，无失败。',
        '- 各阶段 `invocation.json`：实际命令、脚本和输入散列；`ARTIFACT_MANIFEST.json`：最终产物散列。',
        '',
        '运行使用 `/opt/homebrew/bin/python3.12 -I -S`，只依赖标准库，跳过本机既有site测试残留；未修改环境。冻结v1散列已在执行前后核验。Q4开启臂全部2400行复现保存B3的虚拟时间与清除数，说明观察器没有改变该臂决策。']
    (HERE/'RESULTS.md').write_text('\n'.join(text)+'\n')
    manifest=read(ROOT/'最佳方法/代码/evaluation/manifest_v1.json')
    frozen={f:sha(ROOT/'最佳方法/代码'/f)==h for f,h in manifest['sha256'].items()};assert all(frozen.values())
    write(HERE/'FINAL_FROZEN_CHECK.json',dict(all_unchanged=True,files=frozen,candidate_sha256=sha(ROOT/'最佳方法/代码/solver.py')))
    # The shell is still writing finalize.log while this process runs; omit
    # that transient console file from the sealed deterministic manifest.
    files={str(p.relative_to(HERE)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(HERE.rglob('*')) if p.is_file() and p.name not in ('ARTIFACT_MANIFEST.json','finalize.log') and '__pycache__' not in p.parts}
    write(HERE/'ARTIFACT_MANIFEST.json',dict(files=files,total_files=len(files)))
    print(json.dumps(dict(result_file=str(HERE/'RESULTS.md'),summary_file=str(HERE/'summary.json'),q2_audit_failures=len(audit['failures']),q4_all_complete=q4['all_complete'],files=len(files)),ensure_ascii=False))
if __name__=='__main__':main()
