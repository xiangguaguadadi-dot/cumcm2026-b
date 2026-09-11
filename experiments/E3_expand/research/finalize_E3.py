"""Finalize E3 from saved evidence only; never execute a solver."""
from pathlib import Path
from statistics import mean
import ast, hashlib, json, runpy
OUT=Path(__file__).resolve().parent.parent
def read(p): return json.loads((OUT/p).read_text())
def write(p,x): (OUT/p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def complete(r): return r['complete'] and r['cleared_count']==r['source_count'] and r.get('error') is None and r['exit_reason']=='user_exit'

def main():
    folders=['r1_development','r2_development','r3_development','r3_extended_development','r4_development','r4_confirmation','r4_guarded_development']
    batches=[];dev=[];table=[];keys=set();seeds=set();hashes={}
    for folder in folders:
        p=OUT/'results'/folder;b=json.loads((p/'budget.json').read_text());rows=[]
        for f in sorted(p.glob('*_rows.json')):
            values=json.loads(f.read_text());assert all(complete(r) for r in values),f
            rows+=values;hashes[str(f.relative_to(OUT))]=sha(f)
            table.append(dict(batch=folder,variant=f.stem.removesuffix('_rows'),runs=len(values),mean=mean(r['average_clear_time_s'] for r in values)))
        assert len(rows)==b['actual_runs'];dev+=rows;batches.append(dict(batch=folder,**b))
        if (p/'cases.json').exists():
            for c in json.loads((p/'cases.json').read_text()):
                key=(c['mode'],c['group'],c['seed']);assert key not in keys
                keys.add(key);seeds.add(c['seed'])
    assert len(dev)==2112 and len(keys)==432 and len(seeds)==36
    assert sum(r.get('variant')=='S1' for r in dev)==432
    rounds=read('optimization_path.json')[:3]
    rounds[2]['status']='final_E3_component_against_S1; integration_owned_by_coordinator'
    rounds.append(dict(id='E3_R4',mechanism='conditioned finite hypothetical observation tree',status='rejected_development_after_reversal_and_all_guards_negative',parent='S1',development='results/r4_development',confirmation='results/r4_confirmation',guarded_development='results/r4_guarded_development',snapshot='snapshots/r4_development.py',guarded_snapshot='snapshots/r4_guarded.py',source='IROS2011; CDC2016; finite task adaptation, not EKF/pruning reproduction',sha256=sha(OUT/'snapshots/r4_development.py'),guarded_sha256=sha(OUT/'snapshots/r4_guarded.py'),full=None))
    full=[];quick=[];quickwall=0.
    for number in (1,3):
        f=OUT/f'results/r{number}_exposed/case_metrics.json';values=json.loads(f.read_text());s=read(f'results/r{number}_exposed/summary.json')
        assert len(values)==4800 and all(complete(r) for r in values)
        for mode in (3,4):
            value=mean(r['average_clear_time_s'] for r in values if r['mode']==mode)
            claim=next(x['candidate_mean_s_per_source'] for x in s['comparisons_to_S1'] if x['suite']=='combined' and x['group']=='ALL' and x['mode']==mode)
            assert abs(value-claim)<1e-9
        full+=values;hashes[str(f.relative_to(OUT))]=sha(f)
        values=read(f'results/r{number}_quick/case_metrics.json');s=read(f'results/r{number}_quick/summary.json')
        selected=[r for r in values if r['variant']=='candidate']
        assert len(selected)==120 and all(complete(r) for r in selected)
        quick+=selected;quickwall+=s['wall_seconds']
    assert len(dev)+len(full)+len(quick)==11952
    budget=dict(state='final; no environment execution during finalization',actual_environment_runs=11952,development_environment_runs=2112,development_distinct_cases=432,development_distinct_seeds=36,development_seed_interval=[min(seeds),max(seeds)],actual_S1_development_runs=432,actual_candidate_runs=11520,development_candidate_runs=1680,quick_candidate_runs=240,full_candidate_runs=9600,full_distinct_cases=4800,quick_is_full_subset=True,cache_comparison_rows=9600,cached_quick_baseline_rows=240,reused_development_reference_cases=192,reused_development_paired_comparisons=384,cache_rows_are_not_new_executions=True,geometry_fixture_checks=8000,geometry_fixtures_are_not_strategy_episodes=True,development_wall_s=sum(x['wall_s'] for x in batches),quick_wall_s=quickwall,full_wall_s=sum(x['wall_s'] for x in rounds if x.get('full')),all_recorded_environment_runs_complete=True,completed_source_events=sum(r['source_count'] for r in dev+quick+full),source_events_are_repeated_executions_not_unique_sources=True,development_batches=batches)
    budget['recorded_execution_wall_s']=budget['development_wall_s']+quickwall+budget['full_wall_s']
    write('execution_budget.json',budget);write('optimization_path.json',rounds)
    write('mechanism_tree.json',dict(objective='paid complete clearing; mean episode virtual seconds per cleared source',implemented_rounds=[x['id'] for x in rounds],branches=[
        dict(name='reliable feasible set',sources=['ICRA2013','TRO2015'],rounds=['E3_R3'],caveat='R3 independently derived before ICRA2013 report recovery'),
        dict(name='conditional information action',sources=['IROS2011','CDC2016'],rounds=['E3_R4']),
        dict(name='discovery and cross-target coordination',sources=['ISER2013','ATL2020','ISRR2015_family'],rounds=['E3_R1','E3_R2'],caveat='R2 existing mechanism recheck'),
        dict(name='not transferred',sources=['ICRA2012','JFR2014','TRO2015','ICRA2013','ISRR2015_family','ICRA2017_FOV'],reasons=['probabilistic EKF differs','no parallel robots or communication constraint','static grid lacks receive range/travel/unknown-source guarantee','static identified channels have no birth/death/data association'])]))
    best=read('best.json');best['status']='final_E3_component_against_S1; coordinator_owns_any_fusion';best['source_code_commit']='03e7be614622293e564f812295d17aaced4e0a61';best['boundary']='4800 exposed regression cases; no new holdout or official Windows test'
    assert best['sha256']==sha(OUT/best['snapshot']);write('best.json',best)
    runpy.run_path(str(OUT/'research/build_literature.py'),run_name='__main__')
    from pypdf import PdfReader
    literature=read('literature.json')
    paths=dict(IROS2011=['iros2011.pdf'],ICRA2012=['icra2012.pdf'],ICRA2013=['icra2013_api.pdf'],ISER2013=['iser2013.pdf'],JFR2014=['jfr2014.pdf'],TRO2015=['tro2015.pdf'],ISRR2015_family=['isrr2017.pdf','ijrr2018.pdf'],ATL2020=['wafr2020.pdf'],CDC2016=['nonmyopic2016.pdf'],ICRA2017_FOV=['fov2017.pdf'])
    manifest=[]
    for r in literature['records']:
        files=[]
        for name in paths[r['id']]:
            f=OUT/'research/cache'/name;assert f.read_bytes().startswith(b'%PDF')
            files.append(dict(local_cache_filename=name,sha256=sha(f),bytes=f.stat().st_size,pages=len(PdfReader(f).pages),cache_not_committed=True))
        manifest.append(dict(id=r['id'],source_url=r['primary_url'],reading_scope=r['reading_scope'],versions=r['versions'],files=files))
    write('research/source_reading_manifest.json',dict(status='final reading/version state; original download manifests retain download-time status',records=manifest,excluded_downloads=[dict(filename='icra2013.pdf',reason='HTML challenge, not a paper PDF',sha256=sha(OUT/'research/cache/icra2013.pdf')),dict(filename='tokekar_dissertation.pdf',reason='downloaded but unread; excluded from source count')]))
    old=(OUT/'report.md').read_text()
    proof=old.split('## R3为什么不排除真实源\n\n')[1].split('\n## ')[0].split('\n\nICRA2013技术报告')[0].strip()
    proof=proof.replace('最终clear仍沿用所有顶点20m条件与完整覆盖退出', '认证清除仍用所有顶点20m条件；S1已有的启发式清除尝试以真实成功返回为准，完整覆盖退出条件保留')
    report=['# E3 文献扩展与方法研究最终报告','',
        'E3四轮研究已收束。独立保留R3凸接收域负观测约束：固定S1的Q4从473.897493降至473.620439秒/源，降低0.277054秒/源（0.05846%）；4800暴露回归任务全部正常清除，Q3逐局相同。效果很小且并非各场景都改善，交协调者决定融合；本报告不把它称为共同最佳。','',
        '阅读覆盖用户8条线索与2条引用扩展，按版本去重并标出实际页码。来源到改动见[阅读简报](RESEARCH_BRIEF.md)、[来源账本](literature.json)、[机制树](mechanism_tree.md)。R1/R3/R4有新增实现，R2明确是旧跨目标测点机制在S1的复测。','',
        '## 四轮选择结果','','|轮次|机制|开发证据|完整暴露回归|决定|','|---|---|---|---|---|',
        '|R1|停靠点付费探测未知频道|两批96微益；600m密集探测退步|4800全清，Q4 475.131767，比S1慢0.26045%|拒绝|',
        '|R2|两侧二测点跨目标收益|新96上三权重0.5/1/3均负|未晋级|拒绝；旧机制复测|',
        '|R3|正负接收点的凸楔排除|新96微益；近距离锥扩展退步|4800全清，Q4 473.620439，两批回归同向|保留基础组件|',
        '|R4|条件化有限观测树|首48正；第二96三版负；同96三门槛仍负|未晋级|按当前假设饱和停止|','',
        '## R4实现与开发反转','',
        'S1按真实历史条件化的位置、方向和半径假设被按权重分位压缩为9个代表；半径取各可行区间中点预测可见性。第一测点含父法与12个前进/侧向组合，共13个。逐代表预测无信号、近距离接收、方位误差−0.8°/0/+0.8°以及清除成功/失败的付费代价，展开1/2层。第二层测点按模拟区域中心固定推进，不再穷举全部动作。三误差分支取平均或局部最大，9个物理代表仍取平均；这不是整个±1°区间或全部接收参数的最坏情况证明。','',
        '假想观测只排序真实下一动作，不写入可靠多边形；实际状态仍只接收真实测量。叶成本与无信号回退成本为有限启发式，未复现论文EKF/POMDP、剪枝定理或误差界。首48例S1=484.013412，深度1/深度2/深度2局部最大=479.119906/480.381387/481.712585；第二96例S1=455.117726，三者反升456.016885/456.495784/456.374229。','',
        '最后仅检查预测至少省6秒的成本门槛、预测可见性不低于父法的门槛及两者并用。同一第二批96例复用S1行，分别456.148033、456.546069、456.605801，仍全部负；平均请求数从273.2604升至274.9792/275.3958/275.4896。首批收益未在新开发批保持，现有分支与叶代价不足以支持晋级；结果不证明所有观测树方法无效。','',
        '## R3为什么不排除真实源','',proof,'',
        'ICRA2013技术报告在R3冻结后才取得，只用于事后理论对照，不声称它触发了这项推导。R3扩展额外使用1000m最小接收半径，但原96开发退步，未晋级。3000基础与5000扩展几何夹具是性质检查，不是策略任务成功率证据。','',
        '## 全部开发变体','','指标为每局总虚拟时间/该局清除源数再取跨局平均，不是源首次清除时刻均值或汇总时间/汇总源数。不同批绝对均值不能直接比较。','',
        '|批次|变体|执行局数|Q4秒/源|','|---|---|---:|---:|']
    report += [f"|{r['batch']}|{r['variant']}|{r['runs']}|{r['mean']:.6f}|" for r in table]
    report += ['','所有开发变体正常全清。R3扩展复用r3_development的96例与S1行；R4门槛复用r4_confirmation的96例与S1行，均无新增独立案例。配置和逐局记录保存在results各目录。','','## 回归退步与边界','']
    for number in (1,3):
        s=read(f'results/r{number}_exposed/summary.json')
        c=next(x for x in s['comparisons_to_S1'] if x['suite']=='combined' and x['group']=='ALL' and x['mode']==4)
        regress=[x for x in s['comparisons_to_S1'] if x['suite']=='combined' and x['group']!='ALL' and x['mode']==4 and x['delta_s_per_source']>1e-8]
        report.append(f"- R{number}：Q4 2400局、30970源全清，快/同/慢={c['faster']}/{c['equal']}/{c['slower']}。场景均值退步："+'；'.join(f"{x['group']} +{x['delta_s_per_source']:.6f}秒/源" for x in regress)+'。')
    report += ['','每个full含Q3/Q4各2400例，共61940源事件；两次full均全清。案例为既有v1与前期final，已暴露且用于研发；quick是其子集。quick工具内置旧原版缓存只作基础运行检查，不把其均值当S1对照。没有新增留出，也没有Windows官方执行。','','## 执行预算与复现','',
        '实际环境执行11952次＝开发2112＋quick候选240＋full候选9600，其中S1实际开发432次、候选合计11520次，全部记录正常全清。开发仅432个不同案例、36个seed（46000000–46000035）；两次full复用同4800案例，11952不是独立样本量。另有full比较缓存9600行、quick旧基线缓存240行、开发额外复用192个基准案例（384次成对比较），不计新执行；8000几何夹具另列。','',
        f"已记录执行墙钟合计{budget['recorded_execution_wall_s']:.3f}秒：开发{budget['development_wall_s']:.3f}、quick {quickwall:.3f}、full {budget['full_wall_s']:.3f}。未含阅读、编程、下载、协调时间，不与历史缓存速度作排名。详细分母见[execution_budget.json](execution_budget.json)。",'',
        '原开发入口为research/develop_r*.py与confirm_r4.py。R3扩展和R4门槛原先以内联程序执行，现补research/replay_supplemental.py，按保存案例、源码与配置在新输出目录重放。该补写入口只做语法检查，收尾没有重跑环境，原始行仍是执行证据。','',
        '交付[snapshots/r3.py](snapshots/r3.py)及[依赖散列](snapshots/r1_dependencies.json)，SHA256为7d113e5262d52eaca7e0287ea062e3221b0cadf33340f3536b2b1adbe8f7ec27，早期代码提交03e7be6。本阶段已按负结果与当前假设饱和收束，不宣称数学收敛或机制穷尽；共同最佳与融合结果由主协调报告给出。']
    (OUT/'report.md').write_text('\n'.join(report)+'\n')
    p=OUT/'optimization_path.md';text=p.read_text().split('\n## R4：有限未来观测树')[0]
    text+='\n## R4：有限未来观测树\n\n来源IROS2011与CDC2016；13个第一动作、9个条件化物理代表、3个误差分支，1/2层付费代价，仅排序真实动作。首48个新Q4开发（46000024–46000027）三版均正；随后96个新Q4开发（46000028–46000035）全部反转，未晋级full。最后成本优势6秒与可见性三种门槛在同96例仍负，按协调约定停止，不继续深度或权重扫描。全部数值见report.md和results/r4*。\n\nR3扩展与R4门槛原先为内联执行，收尾补replay_supplemental.py且未重跑。最终环境执行11952，432不同开发案例/36seed。R3仅是固定S1上的微益组件，融合由协调者处理；全部当前E3算法工作已收束。\n'
    p.write_text(text)
    (OUT/'resume.md').write_text('# E3最终状态：实验已收束\n\n仅写experiments/E3_expand；分支experiments/20260911-stage4/e3_expand。\n四轮完成：R1共享发现full反转；R2旧机制三权重复测负；R3凸负接收楔形保留；R4首48正、第二96及三门槛全负，按约定收束。无运行session。\nR3 SHA7d113e5262d52eaca7e0287ea062e3221b0cadf33340f3536b2b1adbe8f7ec27，早期代码提交03e7be6；Q4 473.620439 vs S1 473.897493，4800全清，Q3逐局相同。融合归root。\n预算11952实际执行：开发2112、quick240、full9600；432不同开发例、36seed；另8000几何夹具。无新增留出或官方执行。\nfinalize_E3.py由保存行生成文档并检查计数，不跑环境；replay_supplemental.py为事后补写入口，只语法检查。勿重跑开发或覆盖原结果。\n10条阅读覆盖8线索+2扩展。ICRA2013实际是2012 TR12-006技术报告32页，R3冻结后读指定页，非camera-ready；dames2018是16页书章非期刊。PDF/全文缓存不提交。\n当前仅剩检查变更、commit/push并将精确head报告root；完成后无需继续本路线。\n')
    syntax=[]
    for name in ['finalize_E3.py','replay_supplemental.py','build_literature.py','develop_r4.py','confirm_r4.py']:
        ast.parse((OUT/'research'/name).read_text());syntax.append('research/'+name)
    for name in ['r4_development.py','r4_guarded.py']:
        ast.parse((OUT/'snapshots'/name).read_text());syntax.append('snapshots/'+name)
    write('research/finalization_checks.json',dict(environment_runs_started=0,recorded_runs_verified=11952,all_saved_execution_rows_complete=True,development_unique_case_keys=432,full_means_recomputed_against_summary=True,best_source_sha256_unchanged=True,syntax_checked=syntax,supplemental_replay_executed=False,raw_row_hashes=hashes))
    print(json.dumps(dict(actual_runs=11952,development_cases=432,seed_count=36,literature_records=10,retained_sha256=best['sha256']),indent=2))
if __name__=='__main__': main()
