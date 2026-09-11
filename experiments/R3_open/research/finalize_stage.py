"""Read raw rows, validate identities/budgets, and publish a frozen researcher handoff."""
from pathlib import Path
import json,hashlib,statistics,math,datetime,sys
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'experiments/R3_open';sys.path.insert(0,str(ROOT))
import evaluate
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
save=lambda p,x:Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2))
evaluate.verify();best=read(OUT/'best.json');assert best['round']==5
exposed=read(ROOT/'experiments/20260911_stage3/exposed_cases.json');byid={c['case_id']:c for c in exposed};assert len(byid)==4800
s0=read(ROOT/'experiments/20260911_stage3/baseline/expected_rows.json');s0id={r['case_id']:r for r in s0}
rounds=[];alltraincases=[];case_files=[];budget=read(OUT/'execution_budget.json');expected_runs=0
valid=lambda r:r['complete'] and r['exit_reason']=='user_exit' and not r['error'] and r['cleared_count']==r['source_count']
for rnd in range(1,6):
 snapshot=OUT/f'snapshots/r{rnd}.py';rows=read(OUT/f'results/r{rnd}_exposed/case_metrics.json');summary=read(OUT/f'results/r{rnd}_exposed/summary.json')
 assert len(rows)==len({r['case_id'] for r in rows})==4800 and set(byid)=={r['case_id'] for r in rows}
 assert sha(snapshot)==summary['candidate_sha256'];assert all(valid(r) for r in rows)
 for r in rows:
  c=byid[r['case_id']];assert (r['mode'],r['group'],r['source_count'])==(c['mode'],c['group'],len(c['sources']))
 checks=0;maxerror=0.
 for label in ('S0','previous'):
  cells=summary.get('comparisons_to_'+label)
  if cells is None:continue
  ref=s0id if label=='S0' else {x['case_id']:x for x in read(Path(read(OUT/f'results/best_before_r{rnd}.json')['results'])/'case_metrics.json')}
  assert set(ref)==set(byid)
  for cell in cells:
   part=[r for r in rows if r['mode']==cell['mode'] and (cell['suite']=='combined' or r['exposure_suite']==cell['suite']) and (cell['group']=='ALL' or r['group']==cell['group'])];base=[ref[r['case_id']] for r in part]
   assert all(valid(b) for b in base)
   ds=[r['average_clear_time_s']-b['average_clear_time_s'] for r,b in zip(part,base)];am=statistics.mean(b['average_clear_time_s'] for b in base);bm=statistics.mean(r['average_clear_time_s'] for r in part)
   fields=dict(cases=len(part),candidate_complete=len(part),baseline_complete=len(base),candidate_cleared=sum(r['cleared_count'] for r in part),source_count=sum(r['source_count'] for r in part),candidate_errors=0,baseline_mean_s_per_source=am,candidate_mean_s_per_source=bm,delta_s_per_source=bm-am,reduction_fraction=1-bm/am,faster=sum(v<-1e-8 for v in ds),equal=sum(abs(v)<=1e-8 for v in ds),slower=sum(v>1e-8 for v in ds),worst_s_per_source=max(r['average_clear_time_s'] for r in part),max_virtual_s=max(r['total_virtual_time_s'] for r in part),mean_runtime_s=statistics.mean(r['program_runtime_s'] for r in part))
   for k,v in fields.items():
    error=abs(v-cell[k]);maxerror=max(maxerror,error);assert error<1e-10,(rnd,label,cell['suite'],cell['mode'],cell['group'],k,v,cell[k]);checks+=1
  assert len(cells)==78
 nruns=0
 for split in ('train','development'):
  folder=OUT/f'results/r{rnd}_{split}';cases=read(folder/'cases.json');caseid={c['case_id']:c for c in cases};assert len(cases)==len(caseid)==288
  for c in cases:
   assert 10<=len(c['sources'])<=16 and len({s['channel'] for s in c['sources']})==len(c['sources'])
   assert all(math.hypot(s['x'],s['y'])<=1800+1e-8 and 1000<=s['radius']<=1500 for s in c['sources'])
   if c['mode']==4:assert 0<sum(s['direction'] is not None for s in c['sources'])<len(c['sources'])
  alltraincases+=cases;case_files.append(dict(path=str((folder/'cases.json').relative_to(ROOT)),sha256=sha(folder/'cases.json'),cases=288,seeds=sorted({c['seed'] for c in cases})))
  study=read(folder/'summary.json');runs=0
  for name,item in study.items():
   rr=read(folder/(name+'_rows.json'));assert len(rr)==288 and {r['case_id'] for r in rr}==set(caseid) and all(valid(r) for r in rr);runs+=len(rr)
  assert runs==read(folder/'budget.json')['actual_runs'];nruns+=runs
 for kind in ('quick','full'):
  summ=read(OUT/f'results/r{rnd}_{kind}/summary.json');assert summ['all_complete'] and summ['candidate_sha256']==sha(snapshot);nruns+=summ['runs']
 nruns+=summary['new_runs'];sa=read(OUT/f'results/r{rnd}_source_audit.json');assert sa['candidate_sha256']==sha(snapshot);nruns+=sa['finite_parent_equivalence']['actual_runs']
 expected_runs+=nruns
 combined=[c for c in summary['comparisons_to_S0'] if c['suite']=='combined' and c['group']=='ALL'];prev=[c for c in summary.get('comparisons_to_previous',[]) if c['suite']=='combined' and c['group']=='ALL']
 rounds.append(dict(round=rnd,candidate=str(snapshot.relative_to(ROOT)),sha256=sha(snapshot),raw_rows_sha256=sha(OUT/f'results/r{rnd}_exposed/case_metrics.json'),all_complete=True,actual_runs=nruns,recomputed_scalar_checks=checks,max_aggregate_difference=maxerror,totals=combined,previous=prev))
assert len(alltraincases)==len({c['case_id'] for c in alltraincases})==2880
assert not {c['seed'] for c in alltraincases}&{c['seed'] for c in exposed}
for suffix in ('','_v2','_v3'):expected_runs+=read(OUT/f'results/dynamic_coverage_probe{suffix}.json')['actual_runs']
assert expected_runs==sum(e['actual_runs'] for e in budget['entries'])==budget['actual_runs']==35244
assert budget['unique_training_development_cases']==2880
budget.update(research_status='closed_after_user_near_convergence_guidance',completed_rounds=5,fixed_round_limit=None);save(OUT/'execution_budget.json',budget)
seeds=dict(status='frozen_before_new_final',mission_seed_count=len({c['seed'] for c in alltraincases}),mission_seeds=sorted({c['seed'] for c in alltraincases}),new_source_case_count=2880,training_development_files=case_files,exposed_cases_file='experiments/20260911_stage3/exposed_cases.json',exposed_cases_sha256=sha(ROOT/'experiments/20260911_stage3/exposed_cases.json'),exposed_seed_count=len({c['seed'] for c in exposed}),exposed_seeds=sorted({c['seed'] for c in exposed}),geometry_rng_seeds=[9531],geometry_seed_role='1000 synthetic action-region checks, not source generation',no_new_final_cases_created_here=True)
save(OUT/'used_seeds.json',seeds)
rows=read(OUT/'results/r5_exposed/case_metrics.json');summary=read(OUT/'results/r5_exposed/summary.json');q4=next(c for c in rounds[-1]['totals'] if c['mode']==4);q3=next(c for c in rounds[-1]['totals'] if c['mode']==3)
percentile=lambda xs,p:sorted(xs)[max(0,math.ceil(p*len(xs))-1)]
runtime=[]
for mode in (3,4):
 xs=[r['worker_runtime_s'] for r in rows if r['mode']==mode];runtime.append(dict(mode=mode,unit='seconds',cases=len(xs),mean=statistics.mean(xs),p50=percentile(xs,.5),p95=percentile(xs,.95),p99=percentile(xs,.99),maximum=max(xs)))
audit=dict(passed=True,frozen_rules_unchanged=True,rounds=rounds,actual_runs_recomputed=expected_runs,unique_new_training_development_cases=2880,unique_exposed_cases=4800,independent_case_count=7680,all_round_task_completion=True,latest_worker_runtime=runtime,runtime_boundary='Worker timer includes Solver construction and run against local environment; excludes process startup, import, case environment construction and network. Not real official simulator timing.',dynamic_coverage=read(OUT/'results/dynamic_probe_exact_audit.json'),no_new_final_generated=True)
save(OUT/'results/final_stage_audit.json',audit)
meta=dict(status='research_frozen_ready_for_coordinator_new_final',frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),best=best,deployable_candidate='experiments/R3_open/snapshots/r5.py',candidate_sha256=sha(OUT/'snapshots/r5.py'),deployment_dependencies={},used_seeds='experiments/R3_open/used_seeds.json',stage_audit='experiments/R3_open/results/final_stage_audit.json',actual_runs=expected_runs,new_training_development_cases=2880,exposed_cases=4800,stopping_reason='User allowed near-convergence wrap-up; major R3 improvement followed by small R4/R5 gains and unstable batch/variant rankings. Dynamic coverage diagnostic offered little certifiable fixed-trajectory deletion potential.',not_claimed=['Global optimum','Official Windows score','New held-out final score','No per-case regressions'],next_unimplemented=['Q4 task-cost supplemental-information gate with visibility and no-signal region unchanged','Joint continuous service-point optimization over a fixed route','Conditionally removable discovery stations in the route proxy'])
save(OUT/'stage_final.json',meta)
path=read(OUT/'optimization_path.json');path['research_status']=meta['status'];path['near_convergence_reason']=meta['stopping_reason'];path['diagnostics']=[dict(id='R3_dynamic_coverage',parents=['R3_R3','B3_R1'],literature=['WangCao2013_fullview'],status='not_deployed_after_optimistic_diagnostic',source='experiments/R3_open/research/dynamic_coverage_findings.md',exact_audit='experiments/R3_open/results/dynamic_probe_exact_audit.json',station_case_pairs=252,positive_certificates=2,separation_witnesses=96,undecided=154)];path['unimplemented_followups']=meta['next_unimplemented'];save(OUT/'optimization_path.json',path)
text='# R3_open 第三阶段冻结研究报告\n\n'
text+=f'2026-09-11。最终冻结R5；4800个已暴露完整任务全部清除、正常退出、零异常。Q3={q3["candidate_mean_s_per_source"]:.9f}秒/源，与S0逐局一致；Q4={q4["candidate_mean_s_per_source"]:.9f}秒/源，对固定S0 {q4["baseline_mean_s_per_source"]:.9f}降低{100*q4["reduction_fraction"]:.5f}%。不是新的留出或官方成绩。\n\n'
text+='采用逐案例T_i/n_i后再对案例等权平均的原指标；每题2400例，真实清除30970/30970个源，只有全清且正常退出才比较效率。Q4相对S0快/同/慢='+f'{q4["faster"]}/{q4["equal"]}/{q4["slower"]}。完整48个分批场景与单局回退在results/r5_paired_audit.json及report.md。\n\n'
text+='## 路线与每轮真实效果\n\n|版本|实际改变|Q4秒/源|相对前版下降秒/源|\n|---|---|---:|---:|\n'
changes=['B1可见性机会补测×B3连续认证21站','观测满16互异频道后取消剩余发现站','A1多起点联合站/源路径；直接路线胜半径门控','后继路线优化安全圆盘内clear落点','R2_open R4全顶点动作交集路线×A2最近进入点对照']
prior=q4['baseline_mean_s_per_source']
for rr,change in zip(rounds,changes):
 v=next(c['candidate_mean_s_per_source'] for c in rr['totals'] if c['mode']==4);text+=f'|R{rr["round"]}|{change}|{v:.9f}|{prior-v:.9f}|\n';prior=v
text+='\n各轮均保持Q3源码和行为不变。本研究者的Q3隔离对照不能替代root整合R2路线后的Q3成绩。R5采用真实R2组件c62ffb9f…4104与A2源函数，未重复引用论文性能或相加父算法降幅。完整来源、变换及采纳时点见research/r5_build_provenance.json；所有方案与选择时点见optimization_path.json。\n\n'
text+='## 选择不稳定性与近收敛判断\n\nR3联合路径带来28.369960100秒/源增益，此后R4与R5只有0.121554807和0.310438097秒/源。R4旧final分批退步；R5训练nearest胜route、开发nearest却回退。R5相对R4有6个分批场景均值回退及281个单局变慢，最大49.920633313秒/源；相对S0无分批场景均值回退，仍有226个单局变慢，最大98.2803042秒/源。局部收益趋平且方案排序不稳定，结合用户允许接近收敛收尾，冻结当前best；这不是全局最优或统计显著性证明。\n\n'
text+='## 动态覆盖与未实施方向\n\n12条已见开发Q4轨迹，乐观赋予未知频道所有未来停点且不计检测费用；252个单删站组合中2个通过精确连续证书，96个有精确距离/半平面分离反例，154个未定。三版诊断共36次真实复跑，仍只12个重复案例。结论仅针对固定增强轨迹，既不是实际节省，也不是动态方法的全局不可能性证明。详见research/dynamic_coverage_findings.md。\n\nQ4任务费用信息门控、固定顺序多个服务区域的连续路径及带条件发现终止的路由代理均未启动，列为后续想法；没有冒充失败轮或为了达到固定轮数继续执行。DRD正文只读页2–4、8，用于之后想法审查，不回溯归因给已注册R5。Full-view正文只读页4–11；180度端点由本题自己的闭半平面/凸包证明承担。来源与阅读深度在literature.json。\n\n'
text+='## 可靠性、费用与交付身份\n\n5轮每轮14条规则、79条物理核验、120 quick、2400 full及补2400旧final均通过；每轮24个平衡开发案例在关闭新增组件后与父法十项任务字段精确一致。11200叶连续发现证书以整数重验，R5几何另检1000例并核对移植AST。策略只使用四接口，单文件且无第三方部署依赖；HTTP和官方Windows程序未执行。连续真实多边形承担清除证书，规划假说从不收紧真实区域。每轮组合后均重新说明287931秒<360000秒的宽松虚拟上界，见research/reliability.md。\n\n'
text+=f'共{expected_runs}次真实完整任务执行，2880个新增训练/开发案例与4800个既有暴露案例；重复quick、父等价和诊断不增加独立样本数。训练/开发使用120个不同种子、12场景、两题，Q4每例混合全向与定向；逐文件哈希与全部已用种子在used_seeds.json，root可据此排除新留出重叠。累计数由原始行、每批运行日志和预算独立复算，见results/final_stage_audit.json。\n\n'
text+='|题|本地worker均值秒|P50|P95|P99|最大|\n|---|---:|---:|---:|---:|---:|\n'
for r in runtime:text+=f'|Q{r["mode"]}|{r["mean"]:.6f}|{r["p50"]:.6f}|{r["p95"]:.6f}|{r["p99"]:.6f}|{r["maximum"]:.6f}|\n'
text+='\n计时含Solver构造及本地run，排除进程启动、导入、案例环境构造及网络，不代表官方机器现实耗时。各批墙钟保留，未将模拟器速度称任务虚拟时间节省。\n\n'
text+='最终候选`snapshots/r5.py`，SHA256 `'+sha(OUT/'snapshots/r5.py')+'`。交付入口stage_final.json；完整历史report.md、iteration_log.md、optimization_path.md/json、execution_budget.json、snapshots/与results/均保留。由root冻结双方候选后另生成2400新留出与S0比较，本研究者不参与其调参。\n'
(OUT/'FINAL_RESEARCH_REPORT.md').write_text(text)
report=(OUT/'report.md').read_text();first=report.index('\n\n');report=report[:first]+'\n\n最终已冻结R5：Q4=473.897492999644秒/源，较S0降低9.70408%；Q3逐局同S0。完整收尾、近收敛与预算见FINAL_RESEARCH_REPORT.md；下文是按实际时点保存的历史记录。'+report[first:];(OUT/'report.md').write_text(report)
(OUT/'resume.md').write_text('# R3_open 已冻结\n\n用户允许近收敛收尾。5轮全部完成，最终best R5，SHA256 '+sha(OUT/'snapshots/r5.py')+'。不再新建开发或调参，等待root新留出；原始新种子清单used_seeds.json，最终研究报告FINAL_RESEARCH_REPORT.md，交付入口stage_final.json。\n')
with (OUT/'plan.md').open('a') as f:f.write('\n最终状态：用户允许近收敛收尾，R5完整验证后冻结；未启动的DRD/联合连续路径/条件终止路线单列后续，不继续研发。\n')
print(json.dumps(dict(passed=True,actual_runs=expected_runs,new_training_development_cases=2880,mission_seeds=seeds['mission_seed_count'],best=meta['candidate_sha256'],runtime=runtime),ensure_ascii=False))
