"""Audit rows and summarize the registered coverage experiment; no environments run."""
from collections import Counter, defaultdict
import gzip
import json
import math
from pathlib import Path
import random
import statistics
from common import HERE, dump, sha, frozen_check


def rows_at(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def world_identity(cases):
    # Scenario labels and case IDs are reporting metadata, not simulator inputs.
    index=defaultdict(list)
    inputs={}
    for case in cases:
        key=json.dumps({name:case[name] for name in ('mode','seed','noise','sources')},sort_keys=True,separators=(',',':'))
        index[key].append(case['case_id'])
        inputs[key]=case
    return dict(case_ids=len(cases),distinct_input_worlds=len(index),
                duplicate_input_extra_case_ids=len(cases)-len(index),
                duplicate_groups=[ids for ids in index.values() if len(ids)>1],
                distinct_input_world_source_instances=sum(len(case['sources']) for case in inputs.values()),
                key_fields=['mode','seed','noise','sources'])


def quantile(values, probability):
    values = sorted(values)
    at = (len(values)-1)*probability
    lo = math.floor(at)
    return values[lo] + (values[min(lo+1, len(values)-1)]-values[lo])*(at-lo)


def confidence_interval(pairs, seed=913902, repeats=20000):
    # Same original seed across all scenario groups is one resampling cluster.
    by_seed = defaultdict(list)
    for row in pairs:
        by_seed[row['seed']].append(row['difference_s_per_source'])
    clusters = [values for _, values in sorted(by_seed.items())]
    assert len({len(values) for values in clusters}) == 1
    means = [statistics.mean(values) for values in clusters]
    rng = random.Random(seed)
    boot = sorted(sum(rng.choices(means, k=len(means)))/len(means) for _ in range(repeats))
    return dict(method='paired seed-cluster percentile bootstrap', clusters=len(clusters),
                case_ids_per_cluster=len(clusters[0]), replicates=repeats, random_seed=seed,
                confidence=0.95, low=quantile(boot, .025), high=quantile(boot, .975),
                limitation='Exposed local generated cases; conditional sampling variability, not a blind-test or official guarantee.')


def arm_metrics(rows):
    values = [row['average_clear_time_s'] for row in rows]
    complete = all(row['complete'] for row in rows)
    return dict(case_ids=len(rows), complete=sum(row['complete'] for row in rows),
                errors=sum(row['error'] is not None for row in rows),
                source_instances=sum(row['source_count'] for row in rows),
                cleared_instances=sum(row['cleared_count'] for row in rows),
                mean_s_per_source=statistics.mean(values) if complete else None,
                median_s_per_source=statistics.median(values) if complete else None,
                p95_s_per_source=quantile(values, .95) if complete else None,
                p99_s_per_source=quantile(values, .99) if complete else None,
                worst_s_per_source=max(values) if complete else None,
                worst_case_id=max(rows, key=lambda row: row['average_clear_time_s'])['case_id'] if complete else None,
                requests=sum(row['requests'] for row in rows),
                measures=sum(row['measures'] for row in rows),
                clear_attempts=sum(row['clear_attempts'] for row in rows),
                clear_failures=sum(row['clear_failures'] for row in rows),
                switches=sum(row['switches'] for row in rows),
                distance_m=sum(row['distance_m'] for row in rows),
                mean_visited_stations=statistics.mean(len(row['visited_stations']) for row in rows),
                certificate_type_counts=dict(Counter(row['certificate_type'] for row in rows)),
                known16_pending_worlds=sum(row['known16_observed_while_pending'] for row in rows),
                mean_components_s_per_source={
                    'movement': statistics.mean(row['distance_m']/5/row['source_count'] for row in rows),
                    'measure': statistics.mean(5*row['measures']/row['source_count'] for row in rows),
                    'switch': statistics.mean(row['switches']/row['source_count'] for row in rows),
                    'clear': statistics.mean((3*row['clear_attempts']+2*row['cleared_count'])/row['source_count'] for row in rows),
                })


def audit_suite(name):
    path = HERE/name
    registration = json.loads((path/'registration.json').read_text())
    summary = json.loads((path/'summary.json').read_text())
    cases = json.loads((path/'cases.json').read_text())
    rows = rows_at(path/'rows.jsonl')
    assert summary['status'] == 'complete'
    assert len(cases) == registration['worlds'] == summary['worlds']
    assert len(rows) == len(cases)*len(registration['arms']) == summary['executions']
    assert sha(path/'cases.json') == registration['cases_sha256']
    assert sha(path/'rows.jsonl') == summary['rows_sha256']
    assert sha(HERE/'run_closed_loop.py') == registration['runner_sha256']
    case_index = {case['case_id']:case for case in cases}
    assert len(case_index) == len(cases)
    expected = {(case['case_id'], arm) for case in cases for arm in registration['arms']}
    actual = {(row['case_id'], row['arm']) for row in rows}
    assert expected == actual and len(actual) == len(rows)
    max_formula_error = 0.
    for row in rows:
        case = case_index[row['case_id']]
        assert row['mode'] == case['mode'] and row['group'] == case['group'] and row['seed'] == case['seed']
        assert row['source_count'] == len(case['sources'])
        assert row['candidate_sha256'] == registration['candidates'][row['arm']]
        assert sha(HERE/'snapshots'/f"{row['arm']}.py") == row['candidate_sha256']
        assert row['complete'] == (row['cleared_count'] == row['source_count'] and row['exit_reason']=='user_exit' and row['error'] is None)
        assert row['average_clear_time_s'] == row['total_virtual_time_s']/row['cleared_count']
        formula = row['distance_m']/5+5*row['measures']+row['switches']+3*row['clear_attempts']+2*row['cleared_count']
        max_formula_error = max(max_formula_error, abs(formula-row['total_virtual_time_s']))
        assert abs(formula-row['total_virtual_time_s']) < .001
        assert row['requests'] == row['measures']+row['clear_attempts']+2
        assert not row['pending_channels_after_run']
    for arm in registration['arms']:
        part = [row for row in rows if row['arm']==arm]
        expected_summary = summary['groups'][arm]
        assert len(part) == expected_summary['cases']
        assert sum(row['requests'] for row in part) == expected_summary['requests']
        assert sum(row['source_count'] for row in part) == expected_summary['source_count']
        if all(row['complete'] for row in part):
            assert statistics.mean(row['average_clear_time_s'] for row in part) == expected_summary['mean_s_per_source']
    assert all(row['complete'] for row in rows)
    return rows, cases, dict(status='pass', rows=len(rows), case_ids=len(cases),
                            pairs_unique=True, id_sets_match=True, source_and_runner_hashes_match=True,
                            denominators_recomputed=True, max_time_formula_error_s=max_formula_error,
                            rows_sha256=sha(path/'rows.jsonl'), registration_sha256=sha(path/'registration.json'))


def compare(rows, candidate, baseline, groups):
    left={row['case_id']:row for row in rows if row['arm']==candidate}
    right={row['case_id']:row for row in rows if row['arm']==baseline}
    assert set(left)==set(right)
    pairs=[]
    for cid in sorted(left):
        a,b=left[cid],right[cid]
        assert (a['mode'],a['group'],a['seed'],a['source_count']) == (b['mode'],b['group'],b['seed'],b['source_count'])
        pairs.append(dict(case_id=cid, group=a['group'], seed=a['seed'], source_count=a['source_count'],
                          candidate_s_per_source=a['average_clear_time_s'], baseline_s_per_source=b['average_clear_time_s'],
                          difference_s_per_source=a['average_clear_time_s']-b['average_clear_time_s']))
    def summary(part, percentage):
        ds=[row['difference_s_per_source'] for row in part]
        out=dict(pairs=len(part), candidate=candidate, baseline=baseline,
                 sign='negative means candidate uses less time',
                 mean_difference_s_per_source=statistics.mean(ds),
                 improved=sum(d < -1e-9 for d in ds), tied=sum(abs(d)<=1e-9 for d in ds),
                 regressed=sum(d > 1e-9 for d in ds), ci95=confidence_interval(part),
                 largest_regression=max(part,key=lambda row:row['difference_s_per_source']),
                 largest_improvement=min(part,key=lambda row:row['difference_s_per_source']))
        if percentage:
            base=statistics.mean(row['baseline_s_per_source'] for row in part)
            out['relative_time_reduction_percent']=-out['mean_difference_s_per_source']/base*100
        return out
    result=summary(pairs,False)
    result['groups']={group:summary([row for row in pairs if row['group']==group],True) for group in groups}
    result['overall_scope']='Equal-weight descriptive mean across the fixed 12 groups; no combined percentage improvement.'
    pair_path=HERE/f'{candidate}_minus_{baseline}_pairs.jsonl'
    with pair_path.open('w') as stream:
        for row in pairs:stream.write(json.dumps(row,separators=(',',':'))+'\n')
    regression_path=HERE/f'{candidate}_minus_{baseline}_regressions.json'
    dump(regression_path,sorted((row for row in pairs if row['difference_s_per_source']>1e-9),
                                key=lambda row:row['difference_s_per_source'],reverse=True))
    result['all_pairs_file']=pair_path.name;result['all_regressions_file']=regression_path.name
    return result


def audit_pure_traces(rows):
    checks=[]
    for row in rows:
        path=HERE/'pure_pressure_v1/traces'/f"{row['case_id']}__{row['arm']}.json.gz"
        with gzip.open(path,'rt') as stream:trace=json.load(stream)
        known=set();cleared=set();first_pending16=None
        for index,event in enumerate(trace):
            if event['action']=='measure' and event['result'] in ('direction','near'):known.add(event['channel'])
            if event['action']=='clear' and event['result']=='success':known.add(event['channel']);cleared.add(event['channel'])
            if len(known)>=16 and len(cleared)<16 and first_pending16 is None:first_pending16=index
        assert len(cleared)==row['cleared_count']
        assert row['pure_geometry_audit'] and row['geometric_certificate']
        assert row['certificate_type']=='complete_geometric_coverage'
        assert (first_pending16 is not None)==row['known16_observed_while_pending']
        assert len(row['visited_stations'])==row['station_count']
        for absent in row['absence_channel_checks']:
            assert absent['all_sites_physically_measured_no_signal'] and absent['no_positive_observation'] and absent['true_absent']
        checks.append(dict(case_id=row['case_id'],arm=row['arm'],trace_sha256=sha(path),
                           first_known16_pending_trace_index=first_pending16,
                           later_successful_clears=sum(event['action']=='clear' and event['result']=='success'
                               for event in trace[first_pending16+1:]) if first_pending16 is not None else None,
                           absence_channels=len(row['absence_channel_checks']),
                           all_stations_visited=True,complete_geometric_exit=True))
    dump(HERE/'pure_pressure_trace_audit.json',checks)
    return dict(status='pass',traces=len(checks),known16_pending_traces=sum(row['first_known16_pending_trace_index'] is not None for row in checks),
                all_final_certificates_geometric=True,all_unresolved_channels_actually_scanned_no_signal=True,
                trace_checks_file='pure_pressure_trace_audit.json')


def write_report(result):
    metrics=result['full_metrics'];primary=result['primary'];rotation=result['rotation_extension'];ledger=result['execution_ledger']
    def ci(value):return f"[{value['ci95']['low']:.3f}, {value['ci95']['high']:.3f}]"
    lines=[
        '# 亮点2：近邻测点凸包覆盖与可靠结束的实验结果',
        '',
        '## 结论与证据范围',
        '',
        '固定21点和固定22点都通过对实际binary64坐标的整数覆盖检查：在半径1800米的连续源域内，任何源位置、任何闭半平面发射朝向，都有至少一个站点位于1000米内且在发射半平面中。这是有限布局的连续发现保证；不依赖抽样源朝向。',
        '',
        f"固定Q4 full的1200个已暴露本地案例ID（1187个不同实际输入world）中，三臂共3600次全部正常全清。固定21点均值{metrics['fixed21']['mean_s_per_source']:.6f}秒/源，固定22点{metrics['fixed22']['mean_s_per_source']:.6f}秒/源；配对差（21减22）{primary['mean_difference_s_per_source']:.6f}秒/源，95%种子簇bootstrap区间{ci(primary)}。这是相同清除器下发现布局的主要比较。整体均值仅是12个固定场景的等权描述汇总，不报跨场景合并提升率。",
        '',
        f"旋转21点是扩展比较：均值{metrics['rotating21']['mean_s_per_source']:.6f}秒/源，相对固定21的配对差{rotation['mean_difference_s_per_source']:.6f}秒/源，区间{ci(rotation)}。理想实数旋转保持覆盖；本次整数证书未逐一认证运行时生成的浮点旋转坐标，因此不把该扩展并入固定布局的整数证书结论。",
        '',
        '这些实验不证明21点是全局最少站点数，不单靠发现覆盖证明定位清除的时间上界，也不替代Windows官方模拟器执行。没有新增训练、盲测或参数选择。',
        '',
        '## 覆盖条件与可检查证书',
        '',
        '令源位置为g，站点集为P，近邻站点为N(g)={p∈P: ||p−g||≤1000}。在有限站点、闭发射半平面的物理模型中，所有发射朝向均能检出，当且仅当g∈conv N(g)：若g在凸包内，任何通过g的闭半平面都包含一个近邻点；若g在凸包外，严格分离线可给出一个没有任何近邻点的发射朝向。',
        '',
        '验证器将每个实际float坐标用as_integer_ratio转换为二进制有理数，统一分母后，只用整数比较决定通过。四叉树叶无重复、无祖先重叠、面积和等于整根正方形；域外叶的最小距离严格超过1800米。每个域内叶的四角均在所选近邻站点凸包内，且所有见证站点与所有四角的距离严格小于1000米。凸性把角点检查延伸到整个叶区域。浮点仅用于展示余量。',
        '',
        '| 固定布局 | 站点数 | 总叶/覆盖叶/域外叶 | 最小接收距离余量（米，近似展示） | 最小凸包余量（米，近似展示） |',
        '|---|---:|---:|---:|---:|',
    ]
    for arm in ('fixed21','fixed22'):
        cert=result['certificates'][arm]
        lines.append(f"| {arm} | {cert['station_count']} | {cert['leaf_count']} / {cert['covered_leaves']} / {cert['outside_leaves']} | {cert['min_range_slack_m_approx']:.9f} | {cert['min_hull_slack_m_approx']:.9f} |")
    lines += [
        '',
        '21点为原点、999米八点内环与1864米十二点外环。22点为原点、999.5米七点内环、1999米七点外环与七个外边中点；理想构造的28个三角形最大边999.5米，外七边形内切半径约1801.036767米。本次22点的接受仍依据实际浮点坐标独立整数检查，而非直接接受构造公式或生成器标志。',
        '',
        '证书与逐叶记录：[复核汇总](certificate_checks_v1/summary.json)、[21点逐叶](certificate_checks_v1/21_leaf_checks.jsonl)、[22点逐叶](certificate_checks_v1/22_leaf_checks.jsonl)、[独立验证器](verify_certificates.py)。',
        '',
        '## 单频道反例压力：距离覆盖不足以支持不存在判断',
        '',
        '360个构造world均为合法10源混合Q4，但只扫描一个目标频道，其余9源不参与本诊断清除。目标接收半径固定1000米；源域半径取1800、1799.999、1750米，24个极角，5个相对发射朝向（含向外及半平面边界两侧）。四布局实际调用冻结接口，共1440次扫描。',
        '',
        '| 布局 | 检出/360 | 漏检 | 用途 |',
        '|---|---:|---:|---|',
    ]
    for arm,item in result['scan_pressure']['groups'].items():
        lines.append(f"| {arm} | {item['detected']}/360 | {item['missed']} | {'有效布局覆盖诊断' if arm in metrics else '失败反例，不参与任务速度排名'} |")
    lines += [
        '',
        '一个明确反例是源位于(1800,0)、接收半径1000米、向+x发射：distance_only_21和delete_outer_9的全部站点都返回no_signal。前者最近站点仅距源241.154273米，但全部站点都在源的背向半平面；后者也失去外环提供的向外接收位置。因此这些扫描记录不能证明源不存在。全部240条漏检记录保存在[scan_counterexamples.json](scan_counterexamples.json)。',
        '',
        '## 纯几何结束：关闭全部16数量捷径',
        '',
        'pure21/pure22均关闭stop_discovered、upper_bound_stop、all_sources_discovered与最终count_certificate；保持相同的定位、恢复、光学覆盖和待清除队列。24个构造完整world含10或16源、边界位置、最小接收半径及向外/半平面边界两侧朝向。两臂各24/24全部清除，分别清除312源；48次最终证书全部是complete_geometric_coverage。',
        '',
        '每条压力轨迹均复核：全部站点被访问；每个最终未清除频道确实在每个站点测得no_signal，且从未有阳性观测；这些频道在评测真值中也确实不存在。24条16源臂次均曾出现“已发现16但仍有待清除源”，随后继续成功清除并正常退出。这验证了发现结束与任务结束的区别。',
        '',
        '仅完成无信号几何扫描不能结束有阳性观测但尚未清除的频道。完整结束需要所有已发现源完成清除，同时其余频道有全布局无信号证据；允许数量上界时，还可用16个不同频道均已清除的独立证据。实际物理扫描复核见[pure_pressure_trace_audit.json](pure_pressure_trace_audit.json)，48份完整公开动作轨迹见[pure_pressure_v1/traces](pure_pressure_v1/traces)。',
        '',
        '## 统一闭环：固定21对固定22为主比较',
        '',
        '三臂都嵌入同一个B3父法，仅改变认证发现布局或整体旋转。固定v1的1200个Q4案例ID按每局轮换臂顺序、单worker实际执行；主定位与清除方法不变。按mode、seed、noise、sources去重为1187个不同实际输入world；13个输入在不同场景ID重复，保留全部冻结行，不事后改变评测权重。重复映射见[world_identity_audit.json](world_identity_audit.json)。quick的60案例是full子集，quick额外180次是实际执行次数，不能重复算独立验证world。',
        '',
        '每局指标t_i=本局总虚拟时间/本局实际清除数；以下均值为mean(t_i)，没有改为总时间/总源数。只有两臂全部正常全清才比较耗时。差值固定为fixed21−fixed22，负值表示21点较快。每组100个相同case_id严格配对。',
        '',
        '| 场景 | 固定21 秒/源 | 固定22 秒/源 | 配对差 秒/源 | 差值95%区间 | 21更快/持平/更慢 |',
        '|---|---:|---:|---:|---|---:|',
    ]
    for group,values in result['full_groups'].items():
        item=primary['groups'][group]
        lines.append(f"| {group} | {values['fixed21']['mean_s_per_source']:.3f} | {values['fixed22']['mean_s_per_source']:.3f} | {item['mean_difference_s_per_source']:.3f} | {ci(item)} | {item['improved']}/{item['tied']}/{item['regressed']} |")
    lines += [
        '',
        f"整体配对：21点更快{primary['improved']}局、持平{primary['tied']}局、更慢{primary['regressed']}局；没有删除退步案例。[全部1200配对](fixed21_minus_fixed22_pairs.jsonl)、[全部退步](fixed21_minus_fixed22_regressions.json)。最大退步为{primary['largest_regression']['case_id']}，增加{primary['largest_regression']['difference_s_per_source']:.3f}秒/源。",
        '',
        '场景结论有例外：exactly16_sources中固定21点均值更慢4.983秒/源，区间跨0；origin_cluster虽均值较快，区间也跨0。旋转扩展整体区间跨0，不能称为稳定改善。',
        '',
        '| 布局 | 全清/1200 | 源实例数 | 均值 秒/源 | P95 | P99 | 最差局 | 平均访问站点 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for arm,item in metrics.items():
        lines.append(f"| {arm} | {item['complete']}/1200 | {item['source_instances']} | {item['mean_s_per_source']:.3f} | {item['p95_s_per_source']:.3f} | {item['p99_s_per_source']:.3f} | {item['worst_s_per_source']:.3f} | {item['mean_visited_stations']:.3f} |")
    lines += [
        '',
        '区间采用20000次确定随机种子的配对percentile bootstrap；同一原始seed在12场景中的所有案例作为一个簇共同重采样，主汇总100簇，每簇12例。每组区间各100种子。区间只描述给定本地生成分布下的条件抽样变动；这批案例早已暴露，不提供新留出/官方泛化结论，也不作多重比较校正。',
        '',
        '## 旋转21点扩展',
        '',
        '差值定义为rotating21−fixed21，负值表示旋转较快。保持与固定布局主比较分开。',
        '',
        '| 场景 | 旋转21 秒/源 | 相对固定21差值 | 95%区间 | 旋转更快/持平/更慢 |',
        '|---|---:|---:|---|---:|',
    ]
    for group,values in result['full_groups'].items():
        item=rotation['groups'][group]
        lines.append(f"| {group} | {values['rotating21']['mean_s_per_source']:.3f} | {item['mean_difference_s_per_source']:.3f} | {ci(item)} | {item['improved']}/{item['tied']}/{item['regressed']} |")
    lines += [
        '',
        f"整体旋转更快{rotation['improved']}局、持平{rotation['tied']}局、更慢{rotation['regressed']}局。全部数据见[旋转配对](rotating21_minus_fixed21_pairs.jsonl)、[旋转退步](rotating21_minus_fixed21_regressions.json)。固定布局主结果不能被旋转臂的较好或较坏结果替代。",
        '',
        '## 执行量、散列与复现',
        '',
        f"完整策略实际执行{ledger['full_policy_executions']}次：full 3600、quick 180、纯几何压力48；均正常全清，无缓存/历史行复用。完整案例ID共{ledger['unique_full_policy_case_ids']}个（1200回归+24压力），按实际输入去重为{ledger['distinct_full_policy_worlds']}个world，含{ledger['distinct_full_policy_world_source_instances']}个源；重复臂次及quick合计处理并清除{ledger['complete_policy_cleared_instances']}个源实例。另有360个只扫目标频道的world、1440次扫描，不能算成完成任务。两类合计{ledger['unique_case_ids_all_runs']}个案例ID、{ledger['distinct_worlds_all_runs']}个不同实际输入world。不同world也不等同统计独立world；同seed跨场景仍按簇处理。",
        '',
        f"完整策略请求{ledger['complete_policy_requests']}次，单频道扫描请求{ledger['scan_only_requests']}次，总请求{ledger['all_requests']}次；其中measure/clear动作{ledger['measure_clear_actions']}次，enter/exit调用{ledger['enter_exit_calls']}次。源数分母、唯一ID集合、源码/runner/cases/rows散列及每动作计时公式均重新核对，最大总时间公式差{max(item['max_time_formula_error_s'] for item in result['audits'].values()):.9f}秒，来自逐动作微秒舍入。",
        '',
        f"以上请求数统计有逐行记录的策略与扫描执行；辅助nominal规则检查为{result['nominal_checks']['passed']}/{result['nominal_checks']['total']}通过，其内部调用未混入任务请求ledger。证书生成和汇总审计不执行策略环境。",
        '',
        'Python3.12仅用标准库。原始注册在[registration.json](registration.json)，各次运行在quick_v1/full_v1/pure_pressure_v1的registration.json及rows.jsonl；总机器可读结果为[summary.json](summary.json)。重新汇总（不执行环境）：',
        '',
        '```bash',
        'python3.12 -S agent_experiments/20260913_highlights/coverage/finalize_results.py',
        '```',
        '',
        f"父法SHA256：`{result['physics']['parent_sha256']}`。冻结manifest SHA256：`{result['physics']['manifest_sha256']}`。",
        '',
        '本目录以外的主solver、Q1/Q2既有成果、物理规则、案例与基准均未修改。所有散列与逐局记录保留。',
    ]
    (HERE/'RESULTS.md').write_text('\n'.join(lines)+'\n')


def main():
    frozen=frozen_check()
    quick,qcases,qaudit=audit_suite('quick_v1')
    full,fcases,faudit=audit_suite('full_v1')
    pure,pcases,paudit=audit_suite('pure_pressure_v1')
    assert {case['case_id'] for case in qcases} < {case['case_id'] for case in fcases}
    groups=list(dict.fromkeys(case['group'] for case in fcases))
    assert len(groups)==12
    metrics={arm:arm_metrics([row for row in full if row['arm']==arm]) for arm in ('fixed21','fixed22','rotating21')}
    per_group={group:{arm:arm_metrics([row for row in full if row['arm']==arm and row['group']==group]) for arm in metrics} for group in groups}
    primary=compare(full,'fixed21','fixed22',groups)
    secondary=compare(full,'rotating21','fixed21',groups)
    certificate=json.loads((HERE/'certificate_checks_v1/summary.json').read_text())
    scan=json.loads((HERE/'scan_pressure_v1/summary.json').read_text())
    scanrows=rows_at(HERE/'scan_pressure_v1/rows.jsonl')
    nominal=json.loads((HERE/'rules_nominal_v1.json').read_text())
    assert nominal['passed']==nominal['total'] and all(item['passed'] for item in nominal['checks'])
    scases=json.loads((HERE/'scan_pressure_v1/cases.json').read_text())
    identities=dict(full=world_identity(fcases),quick=world_identity(qcases),pure=world_identity(pcases),
                    complete_policy=world_identity(fcases+pcases),scan_only=world_identity(scases),
                    all=world_identity(fcases+pcases+scases))
    full_index={(row['case_id'],row['arm']):row for row in full}
    duplicate_fields=('total_virtual_time_s','cleared_count','distance_m','measures','switches','clear_attempts','clear_failures')
    for duplicate in identities['full']['duplicate_groups']:
        for arm in metrics:
            reference=tuple(full_index[(duplicate[0],arm)][field] for field in duplicate_fields)
            assert all(tuple(full_index[(cid,arm)][field] for field in duplicate_fields)==reference for cid in duplicate)
    identities['full']['duplicate_input_outcomes_identical_within_each_arm']=True
    identities['full']['duplicate_input_outcome_fields']=list(duplicate_fields)
    dump(HERE/'world_identity_audit.json',identities)
    assert sha(HERE/'scan_pressure_v1/rows.jsonl')==scan['rows_sha256']
    assert len(scanrows)==scan['scan_executions']
    for arm,part in scan['groups'].items():
        found=[row for row in scanrows if row['layout']==arm]
        assert len(found)==part['fixtures'] and sum(row['received'] for row in found)==part['detected']
        assert sum(not row['received'] for row in found)==part['missed']
    dump(HERE/'scan_counterexamples.json',[row for row in scanrows if not row['received']])
    result=dict(status='complete',scope='Coverage-only isolated ablation; no main solver or frozen evaluation edits.',
                evidence_levels=['continuous integer coverage certificate for fixed sites','constructed interface scan counterexamples',
                                 'constructed complete-world pure-geometry termination','exposed frozen local Q4 closed-loop regression'],
                physics=frozen,certificates=certificate['certificates'],scan_pressure=scan,
                pure_geometry={arm:arm_metrics([row for row in pure if row['arm']==arm]) for arm in ('pure21','pure22')},
                pure_geometry_trace_audit=audit_pure_traces(pure),
                full_metrics=metrics,full_groups=per_group,primary=primary,rotation_extension=secondary,
                world_identity=identities,
                nominal_checks=dict(passed=nominal['passed'],total=nominal['total'],sha256=sha(HERE/'rules_nominal_v1.json')),
                audits=dict(quick=qaudit,full=faudit,pure_pressure=paudit),
                execution_ledger=dict(full_policy_executions=len(full)+len(quick)+len(pure),
                    scope='Recorded complete-policy and target-channel scan executions; nominal rule-check internal calls excluded.',
                    full_v1_policy_executions=len(full),quick_v1_policy_executions=len(quick),pure_pressure_policy_executions=len(pure),
                    unique_full_policy_case_ids=len(fcases)+len(pcases),
                    distinct_full_policy_worlds=identities['complete_policy']['distinct_input_worlds'],quick_is_full_subset=True,
                    scan_only_executions=scan['scan_executions'],scan_only_worlds=scan['distinct_worlds'],
                    unique_case_ids_all_runs=len(fcases)+len(pcases)+scan['distinct_worlds'],
                    distinct_worlds_all_runs=identities['all']['distinct_input_worlds'],
                    complete_policy_source_instances=sum(row['source_count'] for row in full+quick+pure),
                    complete_policy_cleared_instances=sum(row['cleared_count'] for row in full+quick+pure),
                    unique_case_id_full_policy_source_instances=sum(len(case['sources']) for case in fcases+pcases),
                    distinct_full_policy_world_source_instances=identities['complete_policy']['distinct_input_world_source_instances'],
                    targeted_scan_source_instances=len(scanrows),targeted_scan_unique_sources=scan['unique_target_sources'],
                    complete_policy_requests=sum(row['requests'] for row in full+quick+pure),
                    scan_only_requests=scan['total_requests'],
                    all_requests=sum(row['requests'] for row in full+quick+pure)+scan['total_requests'],
                    measure_clear_actions=sum(row['measures']+row['clear_attempts'] for row in full+quick+pure)+sum(row['measurements'] for row in scanrows),
                    enter_exit_calls=2*(len(full)+len(quick)+len(pure)+len(scanrows)),
                    cached_or_replayed_policy_runs=0,failures=sum(not row['complete'] for row in full+quick+pure)),
                limitations=['No global minimality claim for the 21-site layout.',
                             'Integer certificate applies to fixed binary64 coordinates; the runtime floating-point rotated coordinates are not individually recertified.',
                             'Geometry ensures detection coverage, not bounded localization/clearing time by itself.',
                             'All source-position and error-field distributions in closed-loop cases are local modeling choices.',
                             'No new blind test, training, or Windows official execution.'],
                finalizer_sha256=sha(__file__))
    dump(HERE/'summary.json',result)
    write_report(result)
    print(json.dumps(dict(status='complete',full_metrics=metrics,primary_mean=primary['mean_difference_s_per_source'],
                          primary_ci=primary['ci95'],rotation_mean=secondary['mean_difference_s_per_source'],
                          rotation_ci=secondary['ci95'],ledger=result['execution_ledger']),ensure_ascii=False))


if __name__=='__main__':main()
