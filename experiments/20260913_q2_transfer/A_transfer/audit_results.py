"""Independent row-level recomputation and concise route-A report."""
import json,pathlib,hashlib,statistics,math
HERE=pathlib.Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def read(p):return json.loads(p.read_text())
baseline=read(ROOT/'experiments/parallel_v2_coordinator/fusion_r5_exposed/case_metrics.json')
bb={r['case_id']:r for r in baseline}
assert len(bb)==len(baseline)==4800
names=['A1_quick','A1_full','A1_exposed','A2_quick']
audits=[];tables=[]
for name in names:
    folder=HERE/'results'/name
    summary=read(folder/'summary.json');rows=read(folder/'case_metrics.json')
    assert len({r['case_id'] for r in rows})==len(rows)==summary['paired_cases']
    mode_rows=[]
    for mode in (3,4):
        for batch in ['combined',*sorted({r['exposure_suite'] for r in rows})]:
            rr=[r for r in rows if r['mode']==mode and (batch=='combined' or r['exposure_suite']==batch)]
            ref=[bb[r['case_id']] for r in rr]
            for a,b in zip(rr,ref):
                assert a['complete'] and a['exit_reason']=='user_exit' and a['error'] is None
                assert a['cleared_count']==a['source_count']==b['source_count']>0
                assert math.isclose(a['average_clear_time_s'],a['total_virtual_time_s']/a['cleared_count'],abs_tol=1e-8,rel_tol=0)
            candidate=statistics.fmean(r['total_virtual_time_s']/r['cleared_count'] for r in rr)
            parent=statistics.fmean(r['total_virtual_time_s']/r['cleared_count'] for r in ref)
            expected=next(s for s in summary['comparisons'] if s['mode']==mode and s['group']=='ALL' and s['batch']==batch)
            assert abs(candidate-expected['candidate_mean'])<1e-10 and abs(parent-expected['baseline_mean'])<1e-10
            item={'run':name,'mode':mode,'batch':batch,'cases':len(rr),'candidate_mean':candidate,'baseline_mean':parent,'delta_s_per_source':candidate-parent,'improvement_pct':100*(1-candidate/parent)}
            mode_rows.append(item)
            if batch=='combined':tables.append(item)
    audits.append({'run':name,'candidate_sha256':summary['candidate_sha256'],'raw_row_count':len(rows),'id_alignment_unique':True,'all_complete':True,'means_recomputed':mode_rows,'actual_runs':summary['actual_runs'],'reused_rows':summary['reused_rows'],'wall_seconds':summary['wall_seconds']})
diagnostics=[]
for version in ['A1','A2']:
    d=read(HERE/'diagnostics'/(version+'_quick')/'summary.json')
    ref={r['case_id']:r for r in read(HERE/'results'/(version+'_quick')/'case_metrics.json')}
    for r in d['cases']:
        b=ref[r['case_id']];s=r['stats']
        assert abs(s['time_s']-b['total_virtual_time_s'])<1e-7
        assert abs(s['distance_m']-b['distance_m'])<1e-7 and s['cleared']==b['cleared_count']
        assert r['error'] is None and r['exit_reason']=='user_exit'
    diagnostics.append({'version':version,'replay_rows':len(d['cases']),'same_virtual_time_distance_clear_counts_as_common_runner':True,'modes':d['modes']})
exposed=read(HERE/'results/A1_exposed/summary.json')
eligible=[]
for mode in (3,4):
    batches=[r for r in exposed['comparisons'] if r['mode']==mode and r['group']=='ALL' and r['batch']!='combined']
    if all(r['all_complete'] if 'all_complete' in r else r['valid_comparison'] for r in batches) and all(r['delta']<0 for r in batches):eligible.append(mode)
record={'all_row_audits_passed':True,'data_role':'existing exposed local regression; neither blind nor official','run_audits':audits,'diagnostics':diagnostics,'actual_common_runner_candidate_runs':sum(a['actual_runs'] for a in audits),'additional_diagnostic_runs':sum(d['replay_rows'] for d in diagnostics),'A1_eligible_modes_after_two_batches':eligible,'A2_status':'rejected after both quick modes regressed; no full/exposed run','candidate_files':{n:hashlib.sha256((HERE/(n+'.py')).read_bytes()).hexdigest() for n in ['candidate_A1','candidate_A2']}}
(HERE/'AUDIT.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
header='''# 路线A：第二问精度方法的闭环迁移实验

本实验只替换 fusion_r5 的 `second_point`：保留原首测基线长度和当前位置到第二点的移动预算，加入第二问解析角度及其与旧方向的折中候选。使用真实当前可靠多边形的观测角带相交，以最小包围圆作为定位精度规划指标。首测区域受到目标圆域、历史无信号等约束的裁剪通过当前多边形进入计算。

Q3仍沿用全向搜索覆盖和光学清除保护。Q4保留父法可见性规划、无信号恢复、有限光学覆盖；全向安全条件只约束候选距离，不构成定向信号可见性保证。未读取任何真源位置、测试ID或结果缓存来做决策。

## 版本与机制

- A1：最多五个点，包含旧点、两侧解析角和两侧折中角；仅单次已有正常示向度、可行区半径超过100 m、旧基线60–1000 m时考虑替换。先要求当前位置的入站移动不增加，再要求采样最坏包围半径至少减少3%。采用“包围半径减少量/5”与“入站加到区域中心的移动时间变化”比较，仅规划净收益超过1秒才替换。该时间代理是建模选择，不是任务时间保证。Q4还限制预测可见性下降不超过0.01，并加入损失惩罚。
- A2：有意移除A1的后续费用门控，保留相同点集、移动限制与Q4可见性条件，直接选择采样最坏包围半径最小的点。用于检验“测得更准”本身能否转化为更快完成任务，没有进行参数扫描。

每点采用80个第二读数区间，并加入所有可靠多边形顶点相对候选点的方位±误差端点；误差采用父法工程界±1.005001°。有限读数计算只用于规划，不替换权威多边形或宣称连续观测精度证书。最小包围圆采用父法保守重检，不直接把直径除以2。近场或短基线回退原策略。

## 实际结果

单位为每局总虚拟时间/清除数，再在案例上算术平均；相对变化为正表示变快。quick是full子集，exposed两批均为原有已暴露回归。

| 候选与集合 | 题目 | 案例数 | 候选秒/源 | 父法秒/源 | 改善 |
|---|---|---:|---:|---:|---:|
'''
body=''
for r in tables:body+=f"| {r['run']} | Q{r['mode']} | {r['cases']} | {r['candidate_mean']:.6f} | {r['baseline_mean']:.6f} | {r['improvement_pct']:+.6f}% |\n"
body+='\n全部执行案例均全清、正常退出，没有异常或超时。\n\n'
body+='### A1按两批分别检验\n\n| 题目 | 已暴露批次 | 案例数 | 候选秒/源 | 父法秒/源 | 改善 |\n|---|---|---:|---:|---:|---:|\n'
for r in audits[2]['means_recomputed']:
    if r['batch']!='combined':body+=f"| Q{r['mode']} | {r['batch']} | {r['cases']} | {r['candidate_mean']:.6f} | {r['baseline_mean']:.6f} | {r['improvement_pct']:+.6f}% |\n"
body+='\n达到两批同向改善条件的A1模式：'+(', '.join('Q'+str(m) for m in eligible) if eligible else '无')+'。其他模式保留父法。收益若很小应明确表述为微小改善。\n\n'
body+='A1的Q4合并4800集合中，该题2400局为66局更快、2310局相同、24局更慢；最大单局退步25.670698秒/源。12个场景中有4个平均退步，分别为cell50_shared_field（+0.028469秒/源）、exactly10_sources（+0.130465）、fixed_positive_bias（+0.005468）、smooth_shared_field（+0.007505）。因此0.012063%的均值改善不能表述为所有场景更快，且未证明未见案例收益。\n\n'
body+='''## 负结果说明：定位更准没有自动缩短任务

A2 quick两题均变慢。Q3请求数从7961降至7862，失败试清从349降至303，但平均移动时间增加9.421秒/源，最终慢8.865秒/源。Q4请求从15984降至15789，失败试清从401降至335，但移动时间增加5.983秒/源，最终慢4.839秒/源。这里的移动增加来自后续轨迹：单次入站预算没有增加，角度选择改变了之后靠近源、清除和搜索的路径。依据整个闭环的负结果停止A2扩测。

这说明第二问的几何精度目标与第三、四问总任务耗时目标不同。提升定位精度能减少部分检测和错误试清，却可能增加后续移动；费用门控有必要，但本次简单半径代理的收益有限。

## 全部第二点调用的公开轨迹诊断

共同冻结runner不输出内部计数，因此另外重放quick取得公开观测诊断，并逐局核对虚拟时间、移动距离和清除数均与共同runner一致。诊断器只记录父调用返回值和真实测量反馈，没有改变动作。

| 版本 | 题目 | second_point调用 | 换新点 | 所有调用实际反馈 | 换新点后的反馈 |
|---|---|---:|---:|---|---|
'''
for d in diagnostics:
    for r in d['modes']:body+=f"| {d['version']} | Q{r['mode']} | {r['calls']} | {r['selected_calls']} | {r['all_outcomes']} | {r['selected_outcomes']} |\n"
body+='''
每一次调用都有匹配的实际测量记录，未只保存变化局。逐次记录位于 `diagnostics/*/second_point_calls.jsonl`，全部quick案例的诊断统计位于对应summary。

## 复核与产物

- 父法SHA256：`0bda4f711b9e9716739af8aedf456cb1eeefb47d8ba3ed230ca682c8450a96ea`。使用共同冻结runner，物理、案例、v1规则和父法输入散列均由runner执行前后核对。
- 两版各24个公开状态合成分支检查通过，验证不更改可靠几何/已有观测、不额外请求环境、基线长度保持、实际入站移动不增加、选中点的采样最坏半径减少、Q4可见性规划条件保持。
- `candidate_A1.py`、`candidate_A2.py`均自包含，可独立载入；只读冻结父法嵌入副本，没有外部候选依赖。`patch_A1.py`、`patch_A2.py`便于审阅增量；registration文件先于评测登记。
- `AUDIT.json`独立从原始行按ID重算分模式、分批次均值及分母，检查诊断重放与共同runner逐局一致。分场景退步、最差案例及运行耗时保留于每次共同runner的summary，不删负结果。
- 本次未改主solver、README、第一/第二问既有成果、旧结果、规则或任何HTTP通信层；未跑官方模拟器，未进行新盲测。由协调者统一决定最终组合与提交。

候选SHA与执行量：

'''
for name,digest in record['candidate_files'].items():body+=f'- `{name}.py`：`{digest}`。\n'
body+=f"- 共同runner实际候选运行 {record['actual_common_runner_candidate_runs']} 局；另做公开轨迹诊断 {record['additional_diagnostic_runs']} 局。exposed中的2400个full行明确复用，没有重复冒充新执行。\n"
(HERE/'REPORT.md').write_text(header+body)
print(json.dumps({'eligible_modes':eligible,'audits_passed':True,'actual_candidate_runs':record['actual_common_runner_candidate_runs']},indent=2))
