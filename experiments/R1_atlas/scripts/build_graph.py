#!/usr/bin/env python3
"""Read-only historical audit; writes only experiments/R1_atlas. No policy execution."""
import ast, collections, hashlib, json, math, pathlib, re, subprocess, time
from node_metadata import DIRECTIONS
ROOT=pathlib.Path(__file__).resolve().parents[3]
OUT=ROOT/'experiments/R1_atlas'
START=time.monotonic()
SOURCES={}; ERRORS=[]; ROW_CHECKS=[]
def sha(b): return hashlib.sha256(b).hexdigest()
def rel(p):
 p=pathlib.Path(p).resolve()
 try:return str(p.relative_to(ROOT))
 except ValueError:return str(p)
def source(p, role='historical_reference', depth=None):
 p=pathlib.Path(p).resolve(); key=rel(p)
 if key in SOURCES:
  if depth:SOURCES[key]['semantic_review']=depth
  return SOURCES[key]['id']
 b=p.read_bytes(); s={'id':'src_'+sha(key.encode())[:14], 'path':key,'absolute_path':str(p),'sha256':sha(b),'bytes':len(b),'lines':b.count(b'\n')+(bool(b) and not b.endswith(b'\n')),'data_role':role,'read_depth':'all_bytes_hashed','semantic_review':depth or 'programmatic coverage; not manual per-line/per-trajectory review'}
 try:
  txt=b.decode('utf8')
  if p.suffix=='.json':d=json.loads(txt);s['read_depth']='complete_JSON_parse';s['json_records']=len(d) if isinstance(d,list) else None;s['json_root']=type(d).__name__
  elif p.suffix=='.jsonl':
   ds=[json.loads(x) for x in txt.splitlines() if x.strip()];s['read_depth']='complete_JSONL_parse';s['json_records']=len(ds);d=ds
  elif p.suffix=='.py':t=ast.parse(txt);s['read_depth']='complete_Python_AST_parse';s['ast_functions']=[x.name for x in ast.walk(t) if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))];d=None
  else:s['read_depth']='complete_text_loaded';d=None
  if d is not None:
   stats=collections.Counter(); stack=[d]
   while stack:
    z=stack.pop()
    if isinstance(z,dict):
     if 'complete' in z and isinstance(z['complete'],bool):stats['objects_with_complete_flag']+=1;stats['objects_complete_true' if z['complete'] else 'objects_complete_false']+=1
     if 'error' in z and z['error']:stats['objects_with_nonempty_error']+=1
     if 'source_count' in z and 'cleared_count' in z:stats['objects_with_source_denominators']+=1
     stack.extend(v for v in z.values() if isinstance(v,(dict,list)))
    elif isinstance(z,list):stack.extend(z)
   s['structural_counts']=dict(stats);s['structural_count_note']='Object occurrences may repeat tasks across files or nested schemas; never independent sample counts.'
 except (UnicodeDecodeError,ValueError,SyntaxError) as e:s['parse_error']=str(e);ERRORS.append({'path':key,'error':str(e)})
 SOURCES[key]=s;return s['id']
def read(p,role='historical_reference',depth=None):source(p,role,depth);return json.loads(pathlib.Path(p).read_text())
def git_commit(worktree,p):
 try:return subprocess.check_output(['git','log','-1','--format=%H','--',str(pathlib.Path(p).relative_to(worktree))],cwd=worktree,text=True).strip() or None
 except (subprocess.SubprocessError,ValueError):return None
def functional_diff(p,q):
 def defs(f):
  t=ast.parse(pathlib.Path(f).read_text());return {n.name:ast.dump(n,include_attributes=False) for n in t.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
 a,b=defs(p),defs(q);return {'added_top_level':sorted(b.keys()-a.keys()),'removed_top_level':sorted(a.keys()-b.keys()),'changed_top_level':sorted(k for k in a.keys()&b.keys() if a[k]!=b[k]),'note':'AST structural difference, not proof of semantic equivalence; parent metadata separately states behavior ancestry.'}
def summarize(rows,base,role):
 ids=[x['case_id'] for x in rows]; assert len(ids)==len(set(ids)), 'duplicate candidate ids'
 if base is not None: assert set(ids)==set(base), 'pair identity mismatch'
 ag=[]
 suites=sorted(set(x.get('exposure_suite',role) for x in rows))
 for suite in (['combined']+suites if len(suites)>1 else suites):
  ss=rows if suite=='combined' else [r for r in rows if r.get('exposure_suite',role)==suite]
  for mode in (3,4):
   rr=[r for r in ss if r['mode']==mode]
   if not rr:continue
   for group in ['ALL']+sorted(set(r['group'] for r in rr)):
    gg=rr if group=='ALL' else [r for r in rr if r['group']==group]
    valid=all(r['complete'] and r['exit_reason']=='user_exit' and not r['error'] and r['cleared_count']==r['source_count'] and r['source_count']>0 for r in gg)
    x={'suite':suite,'mode':mode,'group':group,'cases':len(gg),'source_count':sum(r['source_count'] for r in gg),'cleared_count':sum(r['cleared_count'] for r in gg),'complete_cases':sum(r['complete'] for r in gg),'error_cases':sum(bool(r['error']) for r in gg),'zero_cleared_cases':sum(r['cleared_count']==0 for r in gg),'all_clear_and_normal':valid}
    if valid:
     vals=[r['average_clear_time_s'] for r in gg];x.update(mean_s_per_source=math.fsum(vals)/len(gg),worst_s_per_source=max(vals),worst_case_id=max(gg,key=lambda r:r['average_clear_time_s'])['case_id'],mean_movement_s_per_source=math.fsum(r['distance_m']/5/r['source_count'] for r in gg)/len(gg),mean_clear_failures_per_case=math.fsum(r['clear_failures'] for r in gg)/len(gg))
     x['mean_other_s_per_source']=x['mean_s_per_source']-x['mean_movement_s_per_source']
     if base:
      assert all(base[r['case_id']]['source_count']==r['source_count'] for r in gg)
      diff=[r['average_clear_time_s']-base[r['case_id']]['average_clear_time_s'] for r in gg]
      x.update(baseline_mean_s_per_source=math.fsum(base[r['case_id']]['average_clear_time_s'] for r in gg)/len(gg),delta_s_per_source=math.fsum(diff)/len(diff),faster=sum(v<-1e-9 for v in diff),equal=sum(abs(v)<=1e-9 for v in diff),slower=sum(v>1e-9 for v in diff),max_regression_s_per_source=max(diff),max_regression_case_id=gg[max(range(len(diff)),key=diff.__getitem__)]['case_id'])
    ag.append(x)
 return ag

campaign=ROOT/'experiments/20260911_agent_campaign'; stage=ROOT/'experiments/20260911_breakthrough'
assign=read(campaign/'assignments.json')['assignments']; old=read(campaign/'all_rounds.json'); registry=read(campaign/'candidate_registry.json'); stage_reg=read(stage/'stage_registry.json')
for p in [ROOT/'AGENTS.md',ROOT/'README.md',ROOT/'docs/评测标准_v1.md',ROOT/'docs/第一问_定稿.md',ROOT/'docs/第二问_结果与候选区域.md',ROOT/'docs/冻结交付与耗时.md',ROOT/'experiments/20260911_stage3/PROTOCOL.md',ROOT/'q1_geometry.py',ROOT/'q2_candidates.py',ROOT/'evaluation/baseline_solver.py',ROOT/'evaluation/manifest_v1.json']:
 source(p,'background_and_rules','Task/rule documents read; geometry implementation is AST-covered, not new proof or experiment.')
for d in [campaign,stage,ROOT/'experiments/B1',ROOT/'experiments/B2',ROOT/'experiments/B3',ROOT/'experiments/20260911_stage3/baseline']:
 for p in sorted(d.rglob('*')):
  if p.is_file() and p.suffix in ('.md','.json','.jsonl','.py') and '__pycache__' not in p.parts:source(p,'historical_archive')
worktrees={a['id']:pathlib.Path(a['worktree']) for a in assign}
sha_paths=collections.defaultdict(list)
for agent,wt in worktrees.items():
 for d in [wt/'experiments'/agent,wt/'results']:
  for p in sorted(d.rglob('*')):
   if p.is_file() and p.suffix in ('.md','.json','.jsonl','.py') and '__pycache__' not in p.parts:
    source(p,'legacy_training_development_or_results')
    if p.suffix=='.py':sha_paths[sha(p.read_bytes())].append(p)
 for name in ['report.md','iteration_log.md','literature.json']:
  p=wt/'experiments'/agent/name
  source(p,'legacy_interpretation','Semantic review of per-round changes, decisions, failure boundaries and literature adoption; large numeric tables independently recomputed.')

nodes=[];edges=[];directions=[]
def edge(a,b,t,evidence,note=''):
 edges.append({'source':a,'target':b,'type':t,'evidence':evidence,'confidence':'documented','note':note})
def bg(i,title,body,paths,status='background_only'):
 nodes.append({'id':i,'direction_tags':['background'],'round':None,'date':'2026-09-11','title':title,'kind':'background','status':status,'parents':[],'exploration':body,'effects':[],'evidence_level':'existing_artifact_no_new_policy_experiment','sources':[source(ROOT/p) for p in paths],'unimplemented':False})
bg('Q1_FIXED','第一问定稿','半平面定位区域、直径和等边三角形反例；直径圆不能代替最小包围圆。',['docs/第一问_定稿.md','q1_geometry.py'])
bg('Q2_SAVED','第二问结果保留','全向稳保信号的三圆盘交安全子区域；不假定第二次观测，更不直接迁移定向。',['docs/第二问_结果与候选区域.md','q2_candidates.py'])
bg('V1_FREEZE','冻结规则与基准','固定计时、全清/退出前置、quick是full子集；旧环境修正后重新冻结，不能混旧报告分数。',['docs/评测标准_v1.md','docs/冻结交付与耗时.md','evaluation/manifest_v1.json'])
bg('R0','六路线共同起点R0','LOCAL-v1 Q3=306.300434218/Q4=570.883371444秒/源，后续各路线基准一致。',['evaluation/baseline_solver.py','experiments/20260911_agent_campaign/assignments.json'])
edge('Q1_FIXED','R0','inspired_by',['docs/第一问_定稿.md'],'几何可靠性背景；不是新融合实验')
edge('Q2_SAVED','R0','inspired_by',['docs/第二问_结果与候选区域.md'],'全向动作设计背景')
edge('V1_FREEZE','R0','derived_from',['evaluation/manifest_v1.json'])
lookup={(r['agent'],r['round']):r for r in old['rounds']};node_by_id={n['id']:n for n in nodes}
for agent,(label,rounds) in DIRECTIONS.items():
 directions.append({'id':agent,'label':label,'stage':1,'round_count':len(rounds),'worktree':str(worktrees[agent]),'report':rel(worktrees[agent]/'experiments'/agent/'report.md')})
 for rn,(title,parent_no,change,decision,lesson) in enumerate(rounds,1):
  r=lookup[(agent,rn)];nodeid=f'{agent}_R{rn}';parent=f'{agent}_R{parent_no}' if parent_no else 'R0'
  candidates=sha_paths[r['candidate_sha256']];assert candidates,(nodeid,'snapshot not found')
  selected=sorted(candidates,key=lambda p:(not bool(re.search(rf'(?:r{rn}|_{rn})(?:_|\.)',p.name)), 'snapshots' not in p.parts and 'candidates' not in p.parts,len(str(p))))[0]
  commit=git_commit(worktrees[agent],selected)
  fullp=pathlib.Path(r['full_path'])/'case_metrics.json'; quickp=pathlib.Path(r['quick_path'])/'case_metrics.json'
  raw=read(fullp,'v1_exposed_regression');assert sha(fullp.read_bytes())==r['full_rows_sha256']
  cr=[x for x in raw if x['variant']=='candidate'];br={x['case_id']:x for x in raw if x['variant']!='candidate'};assert len(cr)==2400
  ag=summarize(cr,br,'v1');assert all(a['all_clear_and_normal'] for a in ag)
  for a in ag:
   if a['group']=='ALL':
    saved=next(x for x in r['modes'] if x['mode']==a['mode']);assert abs(saved['candidate_mean_s_per_source']-a['mean_s_per_source'])<1e-8
  qraw=read(quickp,'v1_quick_subset');qcr=[x for x in qraw if x['variant']=='candidate'];assert len(qcr)==120;assert set(x['case_id'] for x in qcr).issubset(x['case_id'] for x in cr)
  n={'id':nodeid,'direction_tags':[agent],'round':rn,'date':'2026-09-11','title':title,'kind':'completed_optimization_round','status':decision,'parents':[{'id':parent,'relationship':'declared_behavior_or_design_parent','certainty':'documented_by_round_log'}],'exploration':change,'changes':change,'effects':ag,'comparison_baseline':'R0','data_roles':['v1_exposed_regression','training_or_development_as_recorded_in_sources'],'negative_examples':[a for a in ag if a['group']!='ALL' and a.get('delta_s_per_source',0)>1e-9],'selection':decision,'lesson':lesson,'candidate':{'path':rel(selected),'absolute_path':str(selected),'sha256':r['candidate_sha256'],'commit':commit,'branch':next(a['branch'] for a in assign if a['id']==agent),'repository_url':f'https://github.com/xiangguaguadadi-dot/cumcm2026-b/blob/{commit}/{selected.relative_to(worktrees[agent])}' if commit else None},'budget':{'full_candidate_runs':2400,'quick_candidate_runs':120,'full_wall_s':r['full_wall_s'],'quick_wall_s':r.get('quick_wall_s'),'additional_development_budget':'See source training/development ledgers; no inferred uniform budget.'},'sources':[source(fullp),source(quickp),source(selected),source(worktrees[agent]/'experiments'/agent/'iteration_log.md'),source(worktrees[agent]/'experiments'/agent/'report.md'),source(worktrees[agent]/'experiments'/agent/'literature.json')],'literature_basis':{'mode':'inherited_prior_reading_not_re_read_in_stage3','ledger':rel(worktrees[agent]/'experiments'/agent/'literature.json'),'adoption_scope':'Use exact round/function mappings in ledger and report; topic resemblance is not evidence.'},'evidence_level':'snapshot_sha_matched_all_raw_rows_recomputed_plus_semantic_round_review','unimplemented':False,'next_hypothesis':lesson,'limitations':['All v1 rows are exposed development regression.','No new policy inference performed by atlas builder.']}
  ppath=node_by_id[parent]['candidate']['absolute_path'] if parent!='R0' else ROOT/'evaluation/baseline_solver.py'
  n['code_difference_to_parent']=functional_diff(ppath,selected)
  nodes.append(n);node_by_id[nodeid]=n;edge(parent,nodeid,'iteration',[rel(worktrees[agent]/'experiments'/agent/'iteration_log.md')])
  if decision in ('rejected','not_improved','tradeoff') and parent_no:
   edge(nodeid,parent,'reverts_to',[rel(worktrees[agent]/'experiments'/agent/'iteration_log.md')],'Decision/reference edge excluded from chronological DAG; tradeoff retained without replacing parent best.')
  ROW_CHECKS.append({'node':nodeid,'snapshot_sha_matched':True,'full_rows_sha_matched':True,'candidate_rows':2400,'baseline_rows':len(br),'quick_rows':120,'id_unique':True,'denominators_match':True,'saved_means_match':True})

# Explicit component restoration also has a real second parent, unlike thematic similarity.
for child,mode in [('A1_space_R3',4),('A2_information_R3',4),('A6_learning_R3',3)]:
 node_by_id[child]['parents'].append({'id':'R0','relationship':f'explicit_Q{mode}_behavior_restoration','certainty':'documented_by_round_log'})
 for e in edges:
  if e['target']==child and e['type']=='iteration':e['type']='fusion'
 edge('R0',child,'fusion',[node_by_id[child]['sources'][3]],f'Explicit Q{mode} restoration, combined with the existing other-mode design; no additive performance claim.')

# Later independent first-campaign batch is attached without replacing original decisions.
finalbase=read(campaign/'final_validation/baseline/case_metrics.json','previous_final_historically_new_now_exposed')
finalbase={r['case_id']:r for r in finalbase}
for c in registry['candidates']:
 p=campaign/'final_validation'/c['label']/'case_metrics.json'
 if not p.exists():continue
 rows=read(p,'previous_final_historically_new_now_exposed');ag=summarize(rows,finalbase,'previous_final')
 n=node_by_id[c['label']];n['later_validation']={'historical_role':'new_seed_final_at_stage1_freeze','current_role':'exposed_regression_since_stage2','selection_not_retroactively_changed':True,'aggregates':ag,'row_source':source(p),'code_identity_verified':sha((ROOT/c['candidate_path']).read_bytes())==n['candidate']['sha256']}

bg('C0','第二阶段强对照C0','按已知题号采用Q3 A1 R8和Q4 A4 R6，仅模式分派，不是第二阶段新增改善。',['experiments/20260911_breakthrough/baseline/C0.py','experiments/20260911_breakthrough/baseline/equivalence/case_metrics.json'])
node_by_id['C0']=nodes[-1]
for parent in ['A1_space_R8','A4_directional_R6']:edge(parent,'C0','fusion',['experiments/20260911_breakthrough/STAGE_REPORT.md'],'Mode dispatch only; no claim of additive gain.')
c0rows=read(stage/'baseline/equivalence/case_metrics.json','4800_exposed_control');c0base={x['case_id']:x for x in c0rows}
node_by_id['C0']['effects']=summarize(c0rows,None,'exposed')
B_META={
'B1 R1':('协同补测、可见性与三假说门控',['C0','A3_coordination_R2'],'强A1/A4父行为加入定位途中真实收费补测；Q3中心60米收益门槛，Q4三位置收益×可见概率60米。','朴素融合有收益；Q4可见性有开发组件证据，三假说仅0.0602秒/源增益且Q3更慢。','重新将半径代理转换为可检验的任务价值；同址已可认证clear机会。'),
'B2 R1':('光学区域自适应凸分块',['C0'],'沿示向度分成≤28米横带、最小包围圆≤19.9999米凸块，以服务圆完整覆盖。','减少格点不保证闭环更快，平均收益仅约0.088%。','研究访问顺序而非只减点数。'),
'B2 R2':('失败clear之后保留非凸碎片',['B2_R1'],'用失败圆内接12边形安全排除并重分凸碎片。','几何正确但碎片增加停点，开发与回归更慢；回退R1。','负信息应与服务成本联动，不默认越紧越好。'),
'B2 R3':('左右双向分区与失败假说权重',['B2_R1'],'左右两套完整覆盖；失败clear只删规划假说，用预计首次命中成本选择。','相对R1微小收益，失败权重仅此决策上的条件性证据。','可在当前强父法上独立检验，但需明确小收益与尾部。'),
'B3 R1':('21点连续方向覆盖证书',['C0'],'原点+8个999米内环+12个1864米外环；11200四叉树叶共同近邻凸包整数证书。','20点和小内环构型失败；新21点总体快但两批边缘最小半径都退步。','由合法观测选择各自认证布局，须保留扫描坐标身份和统一退出保证。')}
for agent in ('B1','B2','B3'):
 directions.append({'id':agent,'stage':2,'label':{'B1':'强父法融合与机会测量','B2':'局部光学覆盖与相位','B3':'连续定向发现覆盖'}[agent],'round_count':sum(c['agent']==agent for c in stage_reg['candidates'].values()),'report':f'experiments/{agent}/report.md'})
for label,c in stage_reg['candidates'].items():
 nodeid=label.replace(' ','_'); title,parents,change,lesson,nxt=B_META[label];rows=read(ROOT/c['result_dir']/'case_metrics.json','4800_exposed_regression');assert len(rows)==4800;assert sha((ROOT/c['candidate']).read_bytes())==c['candidate_sha256'];assert sha((ROOT/c['result_dir']/'case_metrics.json').read_bytes())==c['rows_sha256']
 ag=summarize(rows,c0base,'exposed');assert all(a['all_clear_and_normal'] for a in ag)
 for a in ag:
  if a['group']=='ALL':
   s=next(v for v in c['aggregates'] if v['suite']==a['suite'] and v['mode']==a['mode']);assert abs(s['candidate_mean_s_per_source']-a['mean_s_per_source'])<1e-8
 agent=c['agent'];bp=ROOT/f'experiments/{agent}/execution_budget.json'
 budget=read(bp) if bp.exists() else read(ROOT/f'experiments/{agent}/best.json').get('budget',{'reference':'experiments/B3/report.md'})
 if agent=='B2':budget=next(x for x in budget['rounds'] if x['round']==c['round'])
 n={'id':nodeid,'direction_tags':[agent],'round':c['round'],'date':'2026-09-11','title':title,'kind':'completed_optimization_round','status':c['decision'],'parents':[{'id':p,'relationship':'documented_fusion' if len(parents)>1 else 'documented_parent'} for p in parents],'exploration':change,'changes':change,'effects':ag,'comparison_baseline':'C0','data_roles':['v1_exposed_regression','previous_final_exposed_regression','legal_new_training_development_as_recorded'],'negative_examples':[a for a in ag if a['group']!='ALL' and a.get('delta_s_per_source',0)>1e-9],'selection':c['decision'],'lesson':lesson,'next_hypothesis':nxt,'candidate':{'path':c['candidate'],'absolute_path':str(ROOT/c['candidate']),'sha256':c['candidate_sha256'],'commit':c['code_commit'],'dependencies':c['dependencies']},'budget':budget,'sources':[source(ROOT/c['candidate']),source(ROOT/c['result_dir']/'case_metrics.json'),source(ROOT/f'experiments/{agent}/report.md'),source(ROOT/f'experiments/{agent}/optimization_path.json'),source(ROOT/f'experiments/{agent}/literature.json')],'literature_basis':{'mode':'inherited_stage2_explicit_reread_ranges','ledger':f'experiments/{agent}/literature.json'},'evidence_level':'all_4800_raw_rows_recomputed_and_snapshot_matched; inherited_geometry_checks','unimplemented':False}
 nodes.append(n);node_by_id[nodeid]=n
 for p in parents:edge(p,nodeid,'fusion' if len(parents)>1 else 'iteration',[f'experiments/{agent}/optimization_path.json',f'experiments/{agent}/report.md'])
 if nodeid=='B2_R2':edge(nodeid,'B2_R1','reverts_to',['experiments/B2/optimization_path.json'])
 ROW_CHECKS.append({'node':nodeid,'snapshot_sha_matched':True,'full_rows_sha_matched':True,'candidate_rows':4800,'baseline_rows':4800,'id_unique':True,'denominators_match':True,'saved_means_match':True})
edge('A2_information_R8','B2_R2','inspired_by',['experiments/B2/optimization_path.json'],'Failed-clear constraint idea cited, not whole-code fusion.')
edge('B2_R2','B2_R3','inspired_by',['experiments/B2/optimization_path.json'],'Negative-result diagnosis; actual implementation parent R1.')
edge('A4_directional_R6','B2_R3','inspired_by',['experiments/B2/optimization_path.json'],'Expected-first-hit ordering mechanism; C0 already carries A4 parent.')
bg('B3_GEOMETRY','B3几何构型开发','18个几何构型：9个20点和6个小内环21点失败；仅旋转0的999/1864结构做连续认证及任务验证。',['experiments/B3/research/geometry_probe.json','experiments/B3/research/certificate_21_999_1864.json'],'geometry_exploration_not_policy_round')
edge('C0','B3_GEOMETRY','derived_from',['experiments/B3/optimization_path.json']);edge('B3_GEOMETRY','B3_R1','derived_from',['experiments/B3/optimization_path.json'])
bg('B4_CANCELLED','B4取消未实施','只有初步阅读；没有候选、没有实验，不计入48轮。',['experiments/20260911_breakthrough/STAGE_REPORT.md'],'cancelled_before_implementation');nodes[-1]['unimplemented']=True
bg('S0','第三阶段起点S0','Q3 B1 R1/Q4 B3 R1按题分派，合并均值238.426470616/524.827143981秒/源；原4800局均已暴露。',['experiments/20260911_stage3/baseline/provenance.json','experiments/20260911_stage3/baseline/expected_rows.json'])
s0rows=read(ROOT/'experiments/20260911_stage3/baseline/expected_rows.json','4800_exposed_S0_parent_rows');nodes[-1]['effects']=summarize(s0rows,None,'exposed');nodes[-1]['verification_note']='Expected parent rows independently recomputed here; stage3 coordinator actual rerun status is separate.'
for p in ['B1_R1','B3_R1']:edge(p,'S0','fusion',['experiments/20260911_stage3/baseline/provenance.json'],'Known mode dispatch only, not new stage3 improvement.')

# Structural audit: decision references/reverts are not temporal implementation edges.
ids={n['id'] for n in nodes};assert len(ids)==len(nodes)
for e in edges:assert e['source'] in ids and e['target'] in ids
adj=collections.defaultdict(list);degree={i:0 for i in ids}
for e in edges:
 if e['type'] in ('iteration','fusion','derived_from'):
  adj[e['source']].append(e['target']);degree[e['target']]+=1
queue=[k for k,v in degree.items() if not v];visited=[]
while queue:
 k=queue.pop();visited.append(k)
 for c in adj[k]:
  degree[c]-=1
  if not degree[c]:queue.append(c)
assert len(visited)==len(ids),'implementation DAG cycle'
completed=[n for n in nodes if n['kind']=='completed_optimization_round'];assert len(completed)==48
expected={f"{r['agent']}_R{r['round']}" for r in old['rounds']}|{k.replace(' ','_') for k in stage_reg['candidates']}
assert {n['id'] for n in completed}==expected
coverage={'expected_rounds':48,'observed_rounds':48,'stage1_rounds':43,'stage2_rounds':5,'unique_completed_ids':48,'candidate_full_rows_recomputed':103200+24000,'quick_candidate_rows_checked':5160,'later_final_candidates':10,'later_final_candidate_rows_recomputed':24000,'new_policy_executions':0,'sources_count':len(SOURCES),'source_bytes':sum(s['bytes'] for s in SOURCES.values()),'source_lines':sum(s['lines'] for s in SOURCES.values()),'source_parse_errors':ERRORS,'implementation_subgraph_acyclic':True,'all_node_refs_exist':True,'snapshot_and_means_checks':ROW_CHECKS,'reading_boundary':'Every accessible indexed file was loaded in full and structured formats parsed; every round outcome was reviewed and recomputed. This is not manual action-by-action replay of all trajectories or rereading all cited PDFs. Historical ledgers with only summaries cannot manufacture missing trajectories.','missing_scope':['Official Windows behavior and official performance not tested.','Not all historical PDFs re-read in stage3.','No pre-freeze exploratory experiment invented from background artifacts.','Detailed deployment and geometry proofs inherited where explicitly stated, not independently re-proved by graph builder.']}
graph={'schema_version':'1.0','date':'2026-09-11','purpose':'Complete enumerated 48-round history plus background; stage3 live work added only after frozen evidence.','metric_definition':'Arithmetic mean of per-case total_virtual_time_s / cleared_count after all-clear and normal-exit checks; Q3 and Q4 never combined into weighted score.','data_role_policy':{'v1':'exposed regression','previous_final':'new at first-campaign freeze; exposed regression since stage2','new_training_development':'selection data, never final holdout','official':'not tested'},'directions':directions,'nodes':nodes,'edges':edges,'sources':list(SOURCES.values()),'coverage_audit':coverage}
(OUT/'exploration_graph.json').write_text(json.dumps(graph,ensure_ascii=False,indent=2)+'\n')
(OUT/'reading_coverage.json').write_text(json.dumps({'schema_version':1,'coverage_audit':coverage,'files':list(SOURCES.values())},ensure_ascii=False,indent=2)+'\n')
(OUT/'research/raw_row_audit.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2)+'\n')
# Compact navigation; full graphs broken into directions to avoid an unreadable wall.
lines=['# 全历程方向图','',f'截至2026-09-11，六路线43轮＋第二阶段5轮，合计48个真实优化轮次；另有背景、几何开发和取消节点。全部数字为本地结果。','', 'S0按题选Q3 B1 R1、Q4 B3 R1，合并238.426471/524.827144秒/源。两批4800局均已暴露；该分派不是第三阶段新收益。','', '## 总览','', '```mermaid','flowchart LR','  R0["R0 冻结基准"]']
for agent,(label,rounds) in DIRECTIONS.items():
 best={'A1_space':8,'A2_information':8,'A3_coordination':2,'A4_directional':6,'A5_learning':2,'A6_learning':7}[agent]; lines.append(f'  R0 --> {agent}_R{best}["{label}：{len(rounds)}轮 / 保留R{best}"]')
lines += ['  A1_space_R8 --> C0["C0：Q3 A1 R8 / Q4 A4 R6"]','  A4_directional_R6 --> C0','  C0 --> B1_R1["B1 R1：强父法＋协同门控"]','  A3_coordination_R2 --> B1_R1','  C0 --> B2_R1["B2 R1：凸分区"]','  B2_R1 --> B2_R2["B2 R2：碎片失败"]','  B2_R1 --> B2_R3["B2 R3：双相位微益"]','  B2_R2 -. "失败启发" .-> B2_R3','  C0 --> B3_R1["B3 R1：21点连续证书"]','  B1_R1 --> S0["S0：Q3 B1 / Q4 B3"]','  B3_R1 --> S0','```','', '## 如何读数','', '旧A节点主表是v1每题1200局，对照R0；B节点主表是两批合并每题2400局，对照C0。它们不能跨表直接相减当成同批提升。十个A冻结候选的历史新样本放在JSON的later_validation；不回写原有选择。每节点effects保留全部题/批/场景、分母、快同慢、最大退步、最差局和移动/动作分解。','']
for direction in directions:
 dn=[n for n in completed if direction['id'] in n['direction_tags']]
 lines += [f"## {direction['id']} · {direction['label']}",'','```mermaid','flowchart LR']
 for n in dn:
  lines.append(f'  {n["id"]}["R{n["round"]} {n["title"]}<br/>{n["status"]}"]')
  for p in n['parents']:lines.append(f'  {p["id"]} --> {n["id"]}')
  for e in edges:
   if e['source']==n['id'] and e['type']=='reverts_to':lines.append(f'  {n["id"]} -. "回退/保留父最佳" .-> {e["target"]}')
 lines+=['```','','|节点|做了什么|Q3 / Q4 秒/源|选择与启发|','|---|---|---|---|']
 for n in dn:
  suite='combined' if direction['stage']==2 else 'v1'; m=[next(a['mean_s_per_source'] for a in n['effects'] if a['suite']==suite and a['mode']==k and a['group']=='ALL') for k in (3,4)]
  lines.append(f'|{n["id"]}|{n["exploration"]}|{m[0]:.6f} / {m[1]:.6f}|{n["selection"]}；{n["lesson"]}|')
 lines += ['']
lines+=['## 有证据的融合与边界','','- C0：A1 R8的Q3与A4 R6的Q4；S0：B1 R1的Q3与B3 R1的Q4，均只是题号分派。','- B1 R1：C0与A3 R2的定位停点协同结构，新增可见性/假说/门槛有明确开发对照。','- B2 R2由R1继续，A2失败clear约束属于inspired_by；B2 R3实际恢复R1，仅吸取R2失败诊断。','- 同主题文献、相同模块名称或读取另一份报告，不自动产生fusion边；未确认关系保留在来源账本，不画实线。','- A6 R6、R9分别与既有快照字节相同，但真实执行了新训练/开发；它们是探索节点，不是新增算法收益。','','## 覆盖审计','',f'解析{len(SOURCES)}份文件、{coverage["source_lines"]:,}行文本；完整复算127,200行历史优化候选full记录，以及24,000行旧final候选记录。重复读取、缓存对照和结构对象计数不是独立样本。48轮唯一性、引用、候选SHA和已存均值核对均通过。','', '实际阅读深度与限制见[reading_coverage.json](reading_coverage.json)，逐行复算审计见[raw_row_audit.json](research/raw_row_audit.json)。没有把程序全字节解析称为逐动作人工复盘，没有重新执行这些策略，没有重新通读所有旧论文。']
(OUT/'DIRECTION_MAP.md').write_text('\n'.join(lines)+'\n')
track=['# 统一v1效果轨道','','所有48轮均有同一v1回归轨道，每题1200局。B轮另外保存4800合并效果，但不混入这张同批表。R0均值306.300434218/570.883371444；仍是暴露回归，不是独立最终验证。','','|节点|v1 Q3 秒/源|v1 Q4 秒/源|原决定|','|---|---:|---:|---|']
for n in completed:
 m=[next(a['mean_s_per_source'] for a in n['effects'] if a['suite']=='v1' and a['mode']==k and a['group']=='ALL') for k in (3,4)]
 track.append(f'|{n["id"]}|{m[0]:.9f}|{m[1]:.9f}|{n["selection"]}|')
(OUT/'V1_COMPARABLE_TRACK.md').write_text('\n'.join(track)+'\n')
(OUT/'AI_README.md').write_text('''# Agent读取协议

1. 先读DIRECTION_MAP.md、第三阶段PROTOCOL.md和RESEARCH_BRIEF.md（出现后）。读取exploration_graph.json的coverage_audit确认枚举完整性。
2. nodes按id访问；kind=completed_optimization_round才计入48轮。background与cancelled节点不能算实验。
3. effects包含当前轮原判定口径；comparison_baseline明确R0或C0。later_validation另载旧final，当时是新样本、当前已暴露。S0只是按题分派，第三阶段比较须对S0。
4. iteration/fusion/derived_from构成DAG。reverts_to只是决策引用，可以逆时，不参与拓扑排序；inspired_by不能冒充代码采纳。parents分清行为父与结构来源，AST差异不是语义等价证明。
5. candidate给精确SHA、提交和路径。六路线旧文件在只读旧工作树；repository_url可回到同一私有仓库的固定提交。sources给每文件散列/行数/实际处理深度，沿source id追溯。
6. 需要进一步判断失败，先取negative_examples与effects中的max_regression_case_id，再打开对应case_metrics.json，必要时在合法独立新样本重跑；图本身没有逐动作新推理。
7. 新文献以literature.json为主，research_updates存具体实现/验证备忘。actual_reading与transfer_boundary分别约束可声称的阅读和迁移保证。
8. 增量节点须有冻结快照、完整结果、真实父关系、失败及预算；保持旧节点的历史决策。只有新增证据后更新，不依据未完成口头进度登记“成功”。

运行scripts/build_graph.py可从列明的只读来源重建首版；它仅写本目录。运行scripts/validate_graph.py做离线结构/散列检查，不运行求解器。
''')
(OUT/'README.md').write_text('''# R1 全历程方向图与文献支援

- [可读方向图](DIRECTION_MAP.md)：总图、九条方向、48轮变化与失败。
- [机器可读原图](exploration_graph.json)：逐节点结果/父关系/来源/身份/预算。
- [Agent续读入口](AI_README.md)、[读取覆盖](reading_coverage.json)、[独立原始行复算](research/raw_row_audit.json)。
- [计划](plan.md)、[恢复点](resume.md)、[预算](execution_budget.json)。
- 文献首批完成后新增RESEARCH_BRIEF.md、literature.json和research_updates/，按批立即共享。

本图覆盖一个可枚举的48轮历史集合，不能解释为“全部相关研究”。第一二问、冻结规则与B4取消仅为背景。当前全部4800固定局是已暴露研发回归；不冒称新留出或官方成绩。
''')
(OUT/'research/build_budget.json').write_text(json.dumps({'wall_s':time.monotonic()-START,'new_policy_executions':0,'source_files':len(SOURCES),'parsed_bytes':coverage['source_bytes'],'note':'Historical file processing and result arithmetic only.'},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'nodes':len(nodes),'rounds':48,'edges':len(edges),'sources':len(SOURCES),'parse_errors':len(ERRORS),'wall_s':time.monotonic()-START},ensure_ascii=False))
