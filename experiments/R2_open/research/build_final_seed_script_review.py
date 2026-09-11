"""Read-only audit of frozen source/seed inventory; never imports task code."""
from pathlib import Path
import ast,collections,datetime,hashlib,json,re
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'experiments/R2_open/research'
COORD=ROOT.parent/'coordinator'
INV=COORD/'experiments/20260911_stage3/audit/seed_inventory_final/inventory.json'
SEEDS=INV.with_name('seeds.json')
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
d=read(INV);allseeds=set(read(SEEDS));src=read(OUT/'final_seed_review_sources.json')
aliases=collections.defaultdict(list)
for f in d['files']:aliases[f['sha256']].append(f['path'])
# Every entry below is a reviewed, explicit assignment. There is no default classification.
meta={}
def add(ids,category,rule,assessment):
 for i in ids:
  assert i not in meta
  meta[i]=dict(category=category,seed_rule=rule,assessment=assessment)
add([1,9,14],'existing_case_runner','Uses case[seed] from saved frozen cases.','No new seed selection; all saved values remain excluded.')
add([2],'fixed_case_generator','range(5000,5100); sources(seed,mode,scenario).','All 100 seeds covered by [0,100000000).')
add([3,5,8,11,21,36,37,38,39,40,74,75],'saved_evidence_audit','Inspects seed fields/identifiers in saved data or source AST.','No source generation or new seed selection.')
add([4],'saved_bootstrap_audit','random.Random(110926) draws bootstrap indices from saved clusters.','Bootstrap seed is an analysis RNG, conservatively excluded under low range.')
add([6,19,23,29,30,53,54,55,58,68,69,72,77],'saved_report_or_finalization','Copies or summarizes recorded seeds; no new seed draw.','Seed mentions are historical metadata; any source execution would have to be in a separately reviewed runner.')
add([7],'historical_system_random_generator','SystemRandom().sample(range(10**8,2**31),args.seeds), default 100.','Old stage-one final: retain exact 100 saved draws. Do not exclude its entire potential domain. Manifest and saved cases independently checked below.')
add([10],'unused_later_final_generator','SystemRandom().randrange(10**8,2**31) until requested distinct seeds outside exclusion.','Second-stage generator was prepared but final stage cancelled; scanned inventory contains no second-stage final case/manifest output. Static absence alone is not execution proof; coordinator history supplies unused status.')
add([12],'existing_case_pipeline_check','Reuses first v1 seed (5000) for 24 smoke tasks; synthetic paired row arithmetic.','No new source seed; previous real smoke runs are distinct from this read-only audit.')
add([13,31],'inventory_scanner','Parses recorded seed fields and Python expressions as data.','Does not execute expressions or draw cases; no new seed selection.')
add([15],'existing_case_runner_and_bootstrap','Accepts cases file; analysis RNG random.Random(110926) samples cluster indices.','No source seed generation; stage-three draw occurs only in separately reviewed generate_final.py.')
add([16],'not_yet_run_final_generator','SystemRandom().randrange(10**8,2**31), rejects exact seeds and half-open ranges.','Current stage-three generator; coordinator freeze says not invoked before audit. Its potential future domain is not historical exposure. This audit never calls it.')
add([17],'task_case_generator','train start=3101000; development start=3102000; range(start,start+6).','Both fixed ranges below 1e8; serialized before strategy runs.')
add([18],'existing_case_replay','Selects saved B1 train case seed==3101000.','No new seed; replay only.')
add([20],'task_case_generator_high_offsets','a.start+mode*100000+i*1000+j*100+k; 7 scenes,6 noises,k in range(a.seeds), default8.','High-offset B2 R2/R3 reconstruct exactly to all 336 cases each. Full details and recommended conservative million-block ranges below.')
add([22],'task_case_generator_cli','range(a.start,a.start+a.seeds); defaults start33001000,seeds12.','Saved B3 development domain lies below1e8. Arbitrary CLI values are possible in source; all historical saved draws are independently in inventory.')
add([24],'geometry_rng','random.Random(42000999); 2000 synthetic geometric regions.','No task source generation; literal conservatively excluded.')
add([25],'geometry_rng','random.Random(42001999); 1000 synthetic action regions.','No task source generation; literal conservatively excluded.')
add([26,27],'deterministic_geometry_check','No RNG and no task source generation.','Seed appears only in explanatory text.')
add([28],'task_case_generator_cli','range(a.start,a.start+a.seeds); defaults42000000 and8.','Frozen R2 studies used42000000..42000067; all below1e8 and explicitly recorded, including repeated failed/corrected R5.')
add([32,33,34,35,41,42,43],'preregistration_writer','Writes planned seed endpoints to experiment metadata.','Does not generate cases; actual generation and saved cases covered by separate development scripts.')
add([44],'geometry_rng','random.Random(9531); 1000 synthetic lens transfer states.','No source-search task runs; geometry literal conservatively excluded.')
for rnd,i in enumerate([45,46,47,48,49],1):
 start=43000000+(rnd-1)*2000
 add([i],'task_case_generator',f'train {start}..{start+11}; development {start+1000}..{start+1011}.','Fixed12 seeds per split; all below1e8; each cases.json written before strategy execution.')
add([50,51,52],'existing_case_diagnostic_replay','Reads r3_development/cases.json; selects one Q4 case per group, 12 in total.','Does not generate new seed; existing R3 development seeds (43005000 first by source order).')
add([56,86],'caller_seed_case_factory_and_environment','make_case(seed,...) uses Random(seed); LocalEnv default seed=0; noise hashes seed/coordinates.','Defines caller-driven case factory/environment, not an independent seed draw. Callers reviewed separately; deterministic noise hash is not a fresh seed.')
add([57,87],'fixed_environment_rule_check','LocalEnv handcrafted source with keyword seed=719.','No new random case generator; fixed environment RNG input covered by low range.')
add([59],'geometry_and_handcrafted_environment','random.Random(928631) synthetic route disks; handcrafted LocalEnv(seed=781243).','No random task source placement; both literal inputs are below1e8.')
add([60],'task_case_generator_cli','a.seed+i, i in range(a.n); defaults62000 and20.','Saved A1 rows cover blocks62000..70019; generator permits CLI values but archived histories are low and explicitly inventoried.')
add([61],'geometry_rng','random.Random(831148); synthetic optical exclusion polygons.','Geometry only; conservatively excluded.')
add([62],'geometry_rng','random.Random(831150); hypothetical target/prediction containment checks.','Geometry only; conservatively excluded.')
add([63],'geometry_rng','random.Random(931204); synthetic tightening checks.','Geometry only; conservatively excluded.')
add([64],'task_case_generator_cli','a.start+k, k in range(a.n); defaults910000 and10.','Archived A2 task cases remain below1e8; same saved IDs retained including diagnostics.')
add([65],'fixed_task_diagnostic_generator','range(910300,910310).','Watchdog creates complete source-search tasks, including error cases; all10 seeds excluded.')
add([66],'task_case_generator_cli','range(a.start,a.start+a.count); defaults62000 and5.','Saved train62000..62004 and dev63000..63009, reused across rounds; no high draw.')
add([67],'task_case_generator_cli','range(a.start,a.start+a.seeds); defaults81000 and6.','Saved A4 ranges below1e8; CLI is not a universal upper bound but saved output inventory covers observed values.')
add([70],'geometry_rng','random.Random(91004); synthetic station geometry.','No complete generated task source search; conservatively excluded.')
add([71,76],'literature_metadata_writer','Mentions external-paper seeds or case function names in citation text.','No RNG/case generation in script.')
add([73],'training_case_generator','offset=700000+round*100000+mode*10000; train offset+i; dev offset+20000+i; optimizer Random(920000+round).','Saved A5 rounds1..3 low seed domains, cases serialized before optimization. Optimizer RNG also conservatively excluded; do not interpret hypothetical arbitrary round arguments as executed.')
add([78,79],'training_case_generator','6600000+round*100000+mode*10000+off+i; off=0(train),5000(dev); optimizer Random(660000+round).','Saved A6 rounds1..9 and replays low seed domains, cases serialized before optimization; count/round endpoints also conservatively excluded.')
add([80],'initial_benchmark_generator','range(1000,1000+args.count); stress range(2000,2000+args.stress_count); defaults200/30.','Old benchmark task generation; saved ranges low, including repeated tuning/control tasks.')
add([81],'case_generator_code_builder','Writes source code containing range(5000,5100) to evaluation/generate_cases.py; does not itself invoke that generated script.','Its output is reviewed as source2; no independent seed domain.')
add([82,84,89],'geometry_and_fixed_environment_probes','Random(seed), seed in range100; one-source fallback LocalEnv seeds0..15.','Finite geometry and handcrafted source checks; all low inputs excluded.')
add([83,85],'fixed_adversarial_task_generator','noise maps positive->0, negative->1, smooth->2, uniform->3, passed into make_case.','Complete adversarial tasks use only0..3; no high seed selection.')
add([88],'sensitivity_task_generator_cli','range(5000,5000+args.count), default100.','Sources use caller seed and noise field hashes; saved sensitivity tasks low; no nested fresh source seed.')
assert set(meta)==set(range(1,90)),set(range(1,90))-set(meta)
all_py={}
for f in d['files']:
 if f['path'].endswith('.py') and f['sha256'] not in all_py:all_py[f['sha256']]=f['path']
literal=[]
for h,v in d['source_contents'].items():
 if 'python_rng_literal' in v['formats'] and not v['python_seed_lines']:
  literal.append(dict(id=len(src)+len(literal)+1,sha256=h,path=aliases[h][0],aliases=aliases[h],seed_lines=[],extracted_seeds=v['seeds']))
assert len(literal)==6
for r in literal:
 rule='random.Random('+','.join(map(str,r['extracted_seeds']))+')'
 add([r['id']],'geometry_or_route_rng_without_seed_text',rule,'No seed keyword lines; AST literal scanner still captured these values. Geometry/route construction only, not source-search cases.')
src+=literal
# Supplement the inventory text filter by inspecting every Python AST without importing it.
reviewed={r['sha256'] for r in src};outside=[]
for h,p in all_py.items():
 if h in reviewed:continue
 s=Path(p).read_text();tree=ast.parse(s);calls=[];large=[]
 for n in ast.walk(tree):
  if isinstance(n,ast.Call):
   name=ast.unparse(n.func)
   if any(t in name for t in ['random','rng','Random','LocalEnv','make_case','make_training_case','randint','randrange','default_rng','SeedSequence']):calls.append(dict(line=n.lineno,text=ast.get_source_segment(s,n)))
  if isinstance(n,ast.Constant) and type(n.value)==int and 100000000<=n.value<2**31:large.append(dict(line=n.lineno,value=n.value))
 if calls or large:outside.append(dict(sha256=h,path=p,aliases=aliases[h],calls=calls,high_integer_constants=large))
assert len(outside)==1 and outside[0]['path'].endswith('/tests/test_rules.py') and not outside[0]['high_integer_constants']
r=outside[0];r.update(id=96,seed_lines=r['calls'],extracted_seeds=[0]);src.append(r)
add([96],'fixed_default_environment_rule_check','LocalEnv(items) or LocalEnv([]), no explicit seed; default0 from local_env.py.','No random case maker or high seed; finite rule tests, default0 conservatively excluded.')
rows=[];alias_errors=[];identity_updates=[]
allowed_updates={15:'bfebd9e98372b4aaaf717933a3a11fcad52b97ebe42422a7b050a416e41619f4',23:'39be603f8d229d8d42b986ff597fc0adb3247b2d85afb3ea7bfa7d7c51129f93'}
for r in src:
 p=Path(r['path']);s=p.read_text();current_sha=sha(p)
 if current_sha!=r['sha256']:
  assert allowed_updates.get(r['id'])==current_sha,f'unreviewed source change {p}'
  calls=[ast.unparse(n) for n in ast.walk(ast.parse(s)) if isinstance(n,ast.Call) and any(t in ast.unparse(n.func) for t in ['Random','rng','random','make_case','make_training_case'])]
  assert calls==(['random.Random(110926)','rng.choices(range(len(seeds)), k=len(seeds))'] if r['id']==15 else [])
  identity_updates.append(dict(source_id=r['id'],path=str(p),inventory_sha256=r['sha256'],reviewed_current_sha256=current_sha,random_related_calls=calls,adds_source_seed_generation=False,reason='Coordinator final pipeline shape/failure checks' if r['id']==15 else 'Coordinator merged updated literature/graph metadata',followup='Coordinator will refresh inventory after all review artifacts are committed; preserve both identities.'))
 for q in r['aliases']:
  if sha(q) not in {r['sha256'],allowed_updates.get(r['id'])}:alias_errors.append(q)
 indices={i for i,line in enumerate(s.splitlines(),1) if re.search(r'seed|make_case|make_training_case|SystemRandom',line,re.I)}
 for i,line in enumerate(s.splitlines(),1):
  if re.search(r'Random\(|random\.|\.randrange\(|offset\s*=|start\s*=|add_argument|make_case\(|make_training_case\(|["\']cases\.json',line):indices.add(i)
 lines=s.splitlines()
 rows.append(dict(id=r['id'],path=str(p),inventory_sha256=r['sha256'],reviewed_current_sha256=current_sha,alias_count=len(r['aliases']),**meta[r['id']],inventory_extracted_seeds=r['extracted_seeds'],inventory_seed_lines=r['seed_lines'],current_context_lines=[dict(line=i,text=lines[i-1]) for i in sorted(indices)],review_scope='seed expressions plus caller/default/serialization context; AST-only supplemental scan, no task code import'))
assert not alias_errors,alias_errors
# High-domain complete reconstruction from saved artifacts; no cases are generated.
high=set(x for x in allseeds if x>=100000000)
oldp=COORD/'experiments/20260911_agent_campaign/final_validation/manifest.json'
old=read(oldp);oldcasesp=oldp.with_name('cases.json');oldcases=read(oldcasesp)
oldseeds=set(old['seeds']);assert len(oldseeds)==100 and {c['seed'] for c in oldcases}==oldseeds
assert len(oldcases)==2400 and sha(oldcasesp)==old['cases_sha256']
assert set(collections.Counter(c['seed'] for c in oldcases).values())=={24}
scene=['area','edge','origin','offcenter','minimum','count10','count16'];noise=['uniform','positive','negative','smooth_shared','cell_50','cell_500']
b2=[];b2high=set()
for rnd in [1,2,3]:
 p=COORD/f'experiments/B2/development/r{rnd}/cases.json';cs=read(p);vals={c['seed'] for c in cs};start=min(vals)-400000
 expected={(start+400000+i*1000+j*100+k,'4',sc,no) for i,sc in enumerate(scene) for j,no in enumerate(noise) for k in range(8)}
 observed={(c['seed'],str(c['mode']),c['scene'],c['noise']) for c in cs}
 assert len(cs)==len(vals)==336 and expected==observed
 ep=p.with_name('episodes.jsonl');episode_ids={json.loads(l)['seed'] for l in ep.read_text().splitlines() if l.strip()};assert episode_ids==vals
 assert vals<=allseeds
 b2.append(dict(round=rnd,saved_cases=str(p),cases_sha256=sha(p),episodes_file=str(ep),episodes_sha256=sha(ep),distinct_cases=336,distinct_seeds=336,inferred_cli_start=start,mode=4,scene_count=7,noise_count=6,seeds_per_slot=8,actual_inclusive_range=[min(vals),max(vals)],reconstructed_formula_equals_all_case_tuples=True,episode_seed_set_equals_case_seed_set=True,missing_from_inventory=[],new_seed_draws_in_this_audit=0))
 b2high|={x for x in vals if x>=100000000}
geometry={998211234};expectedhigh=oldseeds|b2high|geometry
assert len(high)==773 and high==expectedhigh,(sorted(high-expectedhigh),sorted(expectedhigh-high))
# Observed historical random-draw outputs in the snapshot, not the current filesystem.
future_artifacts=[f['path'] for f in d['files'] if any(x in f['path'] for x in ['/experiments/20260911_breakthrough/final_validation/','/experiments/20260911_stage3/final_validation/'])]
assert not future_artifacts
result=dict(status='pass_for_recorded_inventory_with_required_exact_and_range_exclusions',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),audit_policy_executions=0,audit_case_generation=0,audit_task_code_imports=0,audit_rng_draws=0,inventory=dict(path=str(INV),sha256=sha(INV),snapshot_created_utc=d['created_utc'],scanned_files=len(d['files']),unique_contents=d['unique_parsed_contents'],extracted_seed_count=d['extracted_seed_count'],scanner_errors=d['errors'],seed_file=str(SEEDS),seed_file_sha256=sha(SEEDS)),review_coverage=dict(seed_text_sources=89,literal_only_rng_sources=6,additional_default_environment_source=1,reviewed_sources=96,total_unique_python_sources=len(all_py),remaining_python_sources_without_seed_rng_env_calls_or_high_integer_literals=len(all_py)-96,reviewed_source_aliases=sum(len(r['aliases']) for r in src),source_identity_errors=alias_errors,documented_non_seed_source_updates=identity_updates,post_review_inventory_refresh_required=True,all_requested_source_ids_reviewed=True),required_exclusions=dict(all_exact_inventory_seeds_must_be_retained=True,exact_seed_count=len(allseeds),recommended_half_open_ranges=[[0,100000000],[721000000,722000000],[731000000,732000000]],high_range_rationale='B2 known high seed formulas occupy 721M and731M blocks; whole million-block exclusion is deliberately broader than the observed336 slots per round. It is extra conservatism, not evidence that every excluded seed was used.',old_random_seed_domain_must_not_be_excluded_wholesale=[100000000,2147483648]),high_domain_reconciliation=dict(inventory_high_seed_count=len(high),historical_system_random_draws=dict(count=100,manifest=str(oldp),manifest_sha256=sha(oldp),cases=str(oldcasesp),cases_sha256=sha(oldcasesp),case_count=2400,each_seed_case_count=24,all_in_inventory=oldseeds<=allseeds),b2_high_draws=672,geometry_only_seeds=[998211234],high_union_matches_inventory_exactly=True,unexplained_high_seeds=[],missing_formula_seeds=[]),b2_formula_reconstruction=b2,unused_generators=dict(source_ids=[10,16],matching_final_output_paths_in_inventory=future_artifacts,status_basis='Coordinator freeze/history says second-stage final cancelled and current-stage final not started before inventory. No matching final output in frozen scanned inventory; static filesystem evidence alone cannot prove a past process never drew an unsaved integer.'),evidence_limits=['This checks the recorded inventory and source formulas, not unknown deleted files or unsaved arbitrary CLI invocations.','The broad low interval and both conservative high blocks reduce risk around recorded deterministic development domains; they are not proof about unrecorded execution.','Historical final seeds are currently exposed regression seeds and remain exact exclusions. No new final case or strategy result was read for this review.','Random bootstrap indices and synthetic geometry RNG inputs are conservatively excluded even though they are not mission seed exposure.'],source_reviews=rows)
assert d['extracted_seed_count']==len(allseeds)==10466 and len(rows)==96
(OUT/'final_seed_script_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
lines=['# 最终种子源码独立复核','',f'结论：给定冻结清单中的 {len(allseeds)} 个具体种子必须全部保留为排除项；仅排除 `[0, 100000000)` 不够。建议额外排除两个完整百万区间 `[721000000, 722000000)`、`[731000000, 732000000)`。本审计没有生成案例、抽取随机数、导入任务代码或运行策略。','',f'清单：`{INV}`，SHA256 `{sha(INV)}`。它包含3279文件、1421种内容、10466个抽取值，扫描错误0。审计覆盖89份有seed文本的不同Python源码，补充6份仅有Random字面量的几何/路线源码，再补1份默认seed=0规则测试。全部265份不同Python内容做了静态补查，其余169份未发现额外随机/环境种子调用或高段整数。已逐一核验96份源码及其全部别名；94份与清单SHA一致，2份协调期间发生明确记录的不新增种子修订（final_review.py与build_graph.py），旧/新SHA及静态调用证据均在JSON保留。主协调会在审查提交后刷新清单。','','## 高段773个值全部有来源','','| 来源 | 不同种子 | 已核验事实 |','|---|---:|---|','| 第一阶段旧final |100|manifest与2400案例一致，每种子24案例，全部已在排除清单|','| B2 R2开发 |336|721400000–721406507，逐场景/误差/槽位公式完全匹配|','| B2 R3开发 |336|731400000–731406507，逐场景/误差/槽位公式完全匹配|','| B2残差几何检查 |1|Random(998211234)，仅几何；仍保守排除|','','四类并集与清单中全部773个≥1亿的种子精确相等，未解释的高段种子0、公式漏项0。旧final生成器的潜在域是`[1亿, 2**31)`，应排除已实际保存的100次抽取，不能把整个潜在域视为全部暴露。','','## B2公式核验','','`seed = start + mode*100000 + i*1000 + j*100 + k`。源码固定7场景、6误差，保存数据每槽8种子且mode=4。由保存案例重建的start分别为92100000、721000000、731000000；这是公式反推的调用参数，不冒称命令日志。每轮336个完整(种子,题号,场景,误差)元组均与公式相同，episodes文件种子集合也相同。R1全部低于1亿；R2/R3所建议百万区间是主动扩大排除，区间空隙并不代表曾实际运行。','','## 未运行生成器与证据边界','','第二阶段与本阶段的最终生成器源码均抽取高段种子。协调记录说明第二阶段最终验证已取消，本阶段尚未启动；冻结清单也没有这两阶段的final_validation案例/manifest。仅凭文件不存在不能证明过去某个进程从未抽取未保存的整数，因此这个状态明确依赖协调记录。此次审计不运行生成器、不读取新final、不修改已冻结策略。','','任意CLI脚本理论上可以被未保存命令传入其他范围；静态源码与现存记录不能证明不存在被删除或未保存的运行。此处结论限于完整保留的清单与已记录公式，不作无限范围证明。几何RNG、优化器RNG和bootstrap RNG即使不是任务种子，也保守排除。','','## 逐源码复核索引','','完整源码行证据、SHA256、别名数、分类及种子公式均在同名JSON中。下表的编号1–89与原始抽取列表完全对应，90–95是额外字面量来源，96是默认环境规则测试。','','| ID | 分类 | 源码 | 公式/状态 |','|---:|---|---|---|']
for r in rows:
 relative=r['path'].split('/experiments/',1)[-1] if '/experiments/' in r['path'] else '/'.join(Path(r['path']).parts[-2:])
 rule=r['seed_rule'].replace('|','/').replace('\n',' ')
 lines.append(f"| {r['id']} | {r['category']} | `{relative}` | {rule} |")
(OUT/'final_seed_script_review.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(dict(status=result['status'],reviewed_sources=len(rows),high_count=len(high),missing_formula_seeds=0,required_exact_seed_count=len(allseeds),recommended_ranges=result['required_exclusions']['recommended_half_open_ranges']),ensure_ascii=False))
