"""Recompute final report from case rows; not a solver or a new evaluation."""
import argparse,csv,datetime,hashlib,json,statistics
from pathlib import Path
HERE=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--winner',default='finite_r7');p.add_argument('--stopped',action='store_true');args=p.parse_args()
winner=args.winner
rows=read(HERE/'results'/f'{winner}_exposed/case_metrics.json')
base=read(HERE/'reference/results/r2_exposed/case_metrics.json');ib={r['case_id']:r for r in base}
assert len(rows)==len(base)==4800 and len(ib)==4800 and set(ib)=={r['case_id'] for r in rows}
assert all(r[k]==ib[r['case_id']][k] for r in rows if r['mode']==3 for k in ['complete','cleared_count','source_count','total_virtual_time_s','requests','distance_m','clear_failures'])
metrics=[]
for suite in ['combined','v1','previous_final']:
 for mode in [3,4]:
  for group in ['ALL']+sorted({r['group'] for r in rows}):
   a=[r for r in rows if r['mode']==mode and (suite=='combined' or r['exposure_suite']==suite) and (group=='ALL' or r['group']==group)];b=[ib[r['case_id']] for r in a]
   assert all(r['complete'] and r['exit_reason']=='user_exit' and r['error'] is None and r['cleared_count']==r['source_count'] for r in a+b)
   delta=[r['average_clear_time_s']-v['average_clear_time_s'] for r,v in zip(a,b)]
   lo=min(range(len(a)),key=lambda i:delta[i]);hi=max(range(len(a)),key=lambda i:delta[i]);runtime=sorted(r['program_runtime_s'] for r in a)
   metrics.append(dict(suite=suite,mode=mode,group=group,cases=len(a),cleared=sum(r['cleared_count'] for r in a),sources=sum(r['source_count'] for r in a),all_complete=True,mean=statistics.mean(r['average_clear_time_s'] for r in a),baseline_mean=statistics.mean(r['average_clear_time_s'] for r in b),delta=statistics.mean(delta),faster=sum(d<-1e-8 for d in delta),equal=sum(abs(d)<=1e-8 for d in delta),slower=sum(d>1e-8 for d in delta),worst_regression_id=a[hi]['case_id'],worst_regression_delta=delta[hi],best_improvement_id=a[lo]['case_id'],best_improvement_delta=delta[lo],runtime_median=statistics.median(runtime),runtime_p95=runtime[int(.95*(len(runtime)-1))],runtime_max=max(runtime)))
(HERE/'selected_vs_base.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2)+'\n')
stages=read(HERE/'iteration_ledger.json');rounds=read(HERE/'raw_row_audit.json')
stops=[dict(direction='执行位置一致路线',latest='base',nonpromoting=['route_r1','route_r2','route_r3'],stopped=True),dict(direction='连续朝向积分',latest='base',nonpromoting=['visibility_r1','visibility_r2','visibility_r3'],stopped=True),dict(direction='六边覆盖portfolio',latest='hex_r6',nonpromoting=['hex_r7','hex_r8','hex_r9'],stopped=True),dict(direction='最小接收半径负信息',latest='hex_r3',nonpromoting=['minradius_r1','minradius_r2','minradius_r3'],stopped=True),dict(direction='完整有限光学计划',latest=winner,nonpromoting=['finite_r8','finite_r9','finite_r10'] if args.stopped else [],stopped=args.stopped)]
stop_record=dict(policy='每次完成的候选都与当时最新保留者比较；从旧父构造仍计未晋级。非全量候选的淘汰是筛选结果，不证明全部未测案例无效。',directions=stops,excluded_after_policy_clarification=['finite_r11','finite_r12'],note='r11/r12 quick在协调者澄清计数前已启动；只保存探索记录，不追加全量、不参与后续选优。',last_winner=winner)
review=[]
for order,(candidate,stage,construction_parent) in enumerate([('finite_r8','exposed','finite_r6'),('finite_r9','full','finite_r6'),('finite_r10','full','finite_r7')],1):
 path=HERE/'results'/f'{candidate}_{stage}'/'case_metrics.json'
 if not path.exists():continue
 a=read(path);b=read(HERE/'results'/f'finite_r7_{stage}'/'case_metrics.json')
 a=[r for r in a if r['mode']==4 and r.get('variant','candidate')=='candidate'];b=[r for r in b if r['mode']==4 and r.get('variant','candidate')=='candidate']
 assert {r['case_id'] for r in a}=={r['case_id'] for r in b}
 mean=statistics.mean(r['average_clear_time_s'] for r in a);reference=statistics.mean(r['average_clear_time_s'] for r in b)
 review.append(dict(review_order_after_r7=order,candidate=candidate,construction_parent=construction_parent,incumbent_at_review='finite_r7',comparison_stage=stage,cases=len(a),candidate_mean=mean,incumbent_mean=reference,delta=mean-reference,promoted=False,raw_output_mtime_utc=datetime.datetime.fromtimestamp(path.stat().st_mtime,datetime.timezone.utc).isoformat(),decision_basis='r8 lost on combined exposed; r9/r10 failed full-v1 screening against incumbent.'))
stop_record.update(finite_review_sequence=review,audit_created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),timestamp_scope='Output mtimes identify raw artifact completion, not a claimed preregistration or exact decision timestamp; review_order records the agreed selection sequence.')
(HERE/'stopping_ledger.json').write_text(json.dumps(stop_record,ensure_ascii=False,indent=2)+'\n')
q4=next(r for r in metrics if r['suite']=='combined' and r['mode']==4 and r['group']=='ALL')
q3=next(r for r in metrics if r['suite']=='combined' and r['mode']==3 and r['group']=='ALL')
lines=['# A2并行第二轮实验报告','',f'保留候选：`snapshots/{winner}.py`；SHA256 `{sha(HERE/"snapshots"/f"{winner}.py")}`。', '',f'4800个已暴露本地案例全部清除且正常退出；Q4为2400局、{q4["cleared"]}/{q4["sources"]}个源，Q3为2400局、{q3["cleared"]}/{q3["sources"]}个源。Q3动作统计与本分支基线相同。Q4每局秒/源再取算术均值由{q4["baseline_mean"]:.9f}降至{q4["mean"]:.9f}，差{q4["delta"]:.9f}秒/源。该合并均值仅用于已登记研发选择，不是官方总分；逐场景结果在下表。','',f'相对本分支起点BEST_R2，Q4逐局更快/相等/更慢为{q4["faster"]}/{q4["equal"]}/{q4["slower"]}。最差退步案例`{q4["worst_regression_id"]}`增加{q4["worst_regression_delta"]:.6f}秒/源；所有退步行均保留。', '', '## 证据层级与计算', '', '这是接口动作真实执行的本地模拟评测。v1为2400个案例，旧previous_final为另2400个案例；二者均已在此前暴露。quick 120局是v1子集，不作独立重复证据；exposed复用候选散列严格相同的v1结果，只新跑旧previous_final部分。未增加盲测案例，未接触官方服务，不宣称官方成绩。', '', '官方逐局字段平均定位清除时间=本局总虚拟耗时/本局清除数；跨局使用算术均值。没有把源总数聚合后的总时间/总源数混称为该均值，也没有加入自造加权评分。原始行检查同时核对ID集合、完整清除、正常退出、异常字段和每局分母。', '', '## 分组结果', '', '|集|Q4局数|基线秒/源|候选秒/源|差值|','|---|---:|---:|---:|---:|']
for r in metrics:
 if r['mode']==4 and r['group']=='ALL':lines.append(f'|{r["suite"]}|{r["cases"]}|{r["baseline_mean"]:.6f}|{r["mean"]:.6f}|{r["delta"]:+.6f}|')
lines+=['','|已暴露合并场景|局数|基线秒/源|候选秒/源|差值|','|---|---:|---:|---:|---:|']
for r in metrics:
 if r['mode']==4 and r['suite']=='combined' and r['group']!='ALL':lines.append(f'|{r["group"]}|{r["cases"]}|{r["baseline_mean"]:.6f}|{r["mean"]:.6f}|{r["delta"]:+.6f}|')
lines+=['','## 算法与迁移边界','','1. 保留A2原始认证发现路线与一次统一旋转。新增六边Voronoi光学cover，与原square及两种相位、四种角度之间选整份完整cover；失败clear只能通过凸片全部顶点认证排除格。','2. 从同批A1迁移完整2/3/多盘服务操作符，再适配Q4。将保守凸定位域分成闭凸条，每条认证能在20米内清除；固定点集的首次命中期望费用由子集DP计算。保留者还扩大可用盘数；数量与门槛见快照。','3. 规划分布、可见概率和standoff只做动作选择，不当成官方真分布，也不代替连续覆盖证明。没有迁移Q3专属的no_signal排除1000米整圆假设。','4. `_protected_clear_plan`包围完整clear列表，防止融合学习组件改写未certified的中间点。守卫异常路径恢复与2400局逐字段一致检查均通过。父协调者负责融合后的独立评测。','','完整证明和数值余量见`PROOF.md`。本文没有声称路线全局最优或论文近似界适用于本题。','', '## 研究来源与实际阅读', '', '实际获取与阅读范围见`literature/READING.md`，涵盖guaranteed IPP、lawn mowing、bearing-only MaxEnt与circle-neighborhood TSP的方法段落。全文保存不等于全文通读；前两项曾在旧工作出现，本次是继续深读而非首次发现。三份A1组件的原路径与散列见`finite_provenance.json`。本分支六边格与连续朝向积分是本题的独立实现，有限光学几何/DP明确归属于A1迁移来源。', '', '## 每轮执行记录', '', '以下都是事后执行审计，不把事后ledger称为预注册。基准列对应实现父候选；是否晋级另按当时最新保留者判断，特别是r8虽然胜过其构造父r6，却未胜过当时保留者r7。', '', '|候选|阶段|Q4局数|秒/源|与实现父差|全清|','|---|---|---:|---:|---:|---|']
for v in stages:
 for stage in ['quick','full','exposed']:
  rr=[r for r in rounds if r['candidate']==v['candidate'] and r['stage']==stage and r['mode']==4 and r['group']=='ALL' and (stage!='exposed' or r['scope']=='combined')]
  if rr:
   r=rr[0];lines.append(f'|{r["candidate"]}|{stage}|{r["cases"]}|{r["mean_s_per_source"]:.6f}|{r["delta"]:+.6f}|{r["all_complete"]}|')
lines+=['',f'归档{len(stages)}份候选快照（含一次守卫等价修复）；ledger记载Python3.12有效候选执行总计{sum(v["runs"] for s in stages for v in s["stages"].values())}局次。这是包含quick/full重复运行的工作量，不是独立案例数；冻结基准缓存不计作本轮推理。最初Python3.9还发生120次worker_crash（0/120完成），原因是冻结环境需要Python3.10+的类型语法；这些全部失败行另记environment_failure_ledger.json并保留，不作性能比较。规则导入失败和未经-S的site启动告警日志也保留，但不纳入成功验证；最终使用Python3.12 -S -B清洁启动。', '', '## 停止与验证', '']
for s in stops:lines.append(f'- {s["direction"]}：最新保留{s["latest"]}；连续未晋级{", ".join(s["nonpromoting"]) or "待判定"}；停止={s["stopped"]}。')
lines+=['','r11/r12只保留澄清停止口径前已经启动的quick结果，没有追加full，不把这些未完成确认的探索候选作为正式保留者。','', '冻结manifest SHA256：`431210a6d96e721d23c31698aa389702ea87dcffe8fee6250f71ce6e902be140`。最终14项规则/指标单元检查、名义物理校验与manifest校验通过；有限盘DP与3–6点全排列最优代理相符，缺失规划假说守卫通过，连续格/条的实现随机诊断通过。这些采样检查不替代PROOF中的连续推导。', '', f'保留者已暴露Q4的本次程序现实时间中位数/P95/最大值为{q4["runtime_median"]:.6f}/{q4["runtime_p95"]:.6f}/{q4["runtime_max"]:.6f}秒。现实时间受同时运行任务影响，基准时间为旧缓存，不能据两者声称运行速度加速。没有改通信层，Windows官方通信与正式测试仍未在本分支执行。', '', '所有31份快照都以相同归档BEST_R2为精确前缀；新增后缀AST没有文件/动态执行调用或直接env属性读取。该检查只说明新增代码的静态边界，不宣称Python封装是安全沙箱。完整输出见`results/source_interface_inspection.json`。', '', '## 重现', '', '在隔离仓库根目录执行；所有输出路径应换为新目录。', '', '```sh', 'python3.12 -S -B evaluate.py --verify-only',f'python3.12 -S -B evaluate.py --candidate experiments/parallel_v2_a2/snapshots/{winner}.py --suite full --out /tmp/a2_fresh_full', f'python3.12 -S -B experiments/20260911_stage4/evaluate_exposed.py --candidate experiments/parallel_v2_a2/snapshots/{winner}.py --v1-results /tmp/a2_fresh_full --out /tmp/a2_fresh_exposed', 'python3.12 -S -B experiments/parallel_v2_a2/audit.py',f'python3.12 -S -B experiments/parallel_v2_a2/build_report.py --winner {winner}'+(' --stopped' if args.stopped else ''),'```','']
(HERE/'REPORT.md').write_text('\n'.join(lines))
print(winner,q4['mean'],q4['delta'],'stopped',args.stopped)
