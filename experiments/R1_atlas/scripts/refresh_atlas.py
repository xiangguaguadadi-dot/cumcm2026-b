#!/usr/bin/env python3
"""Rebuild historical graph, add only registered frozen stage3 rows, export small indexes."""
import hashlib,json,math,pathlib,runpy,subprocess,sys
HERE=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));ctx=runpy.run_path(str(HERE/'build_graph.py'));OUT=ctx['OUT'];ROOT=ctx['ROOT'];base=ROOT.parent
j=lambda p:json.loads(pathlib.Path(p).read_text())
g=j(OUT/'exploration_graph.json');reg=j(OUT/'research/stage3_frozen_registry.json');byid={n['id']:n for n in g['nodes']};s0=j(ROOT/'experiments/20260911_stage3/baseline/expected_rows.json');s0={r['case_id']:r for r in s0};stage_checks=[];stage_rows={'S0':s0}
for r in reg['rounds']:
 wt=base/r['agent'];ad=wt/'experiments'/r['agent'];cp=ad/r['candidate'];rp=ad/r['results'];raw=ctx['read'](rp/'case_metrics.json','stage3_4800_exposed_regression');summary=ctx['read'](rp/'summary.json','stage3_4800_exposed_summary');ctx['source'](cp,'stage3_frozen_candidate','SHA matched immutable registered candidate; no policy execution by atlas')
 assert hashlib.sha256(cp.read_bytes()).hexdigest()==r['sha256']==summary['candidate_sha256'];assert len(raw)==4800
 commit=subprocess.check_output(['git','rev-parse',r['commit']],cwd=wt,text=True).strip();blob=subprocess.check_output(['git','show',f'{commit}:experiments/{r["agent"]}/{r["candidate"]}'],cwd=wt);assert hashlib.sha256(blob).hexdigest()==r['sha256']
 for frozen_file in (rp/'case_metrics.json',rp/'summary.json'):
  frozen_blob=subprocess.check_output(['git','show',f'{commit}:{frozen_file.relative_to(wt)}'],cwd=wt)
  assert hashlib.sha256(frozen_blob).digest()==hashlib.sha256(frozen_file.read_bytes()).digest(),frozen_file
 effects=ctx['summarize'](raw,s0,'exposed')
 for a in effects:
  if a['group']=='ALL':
   old=next(x for x in summary['comparisons_to_S0'] if x['suite']==a['suite'] and x['mode']==a['mode'] and x['group']=='ALL');assert abs(a['mean_s_per_source']-old['candidate_mean_s_per_source'])<1e-8
 n={'id':r['id'],'direction_tags':[r['agent']],'round':r['round'],'date':'2026-09-11','title':r['title'],'kind':'completed_stage3_round','status':r['selection'],'parents':[{'id':p,'relationship':'frozen_report_documented_parent'} for p in r['parents']],'design_parent':r['parents'][0],'retained_best_before_round':r['retained_best_before_round'],'retained_best_after_round':r['retained_best'],'exploration':r['changes'],'changes':r['changes'],'effects':effects,'comparison_baseline':'S0','data_roles':['legal_independent_training_development','v1_exposed_regression','previous_final_exposed_regression'],'negative_examples':[x for x in effects if x['group']!='ALL' and x.get('delta_s_per_source',0)>1e-9],'selection':r['selection'],'lesson':r['lesson'],'next_hypothesis':r.get('next_hypothesis'),'candidate':{'path':str(cp),'absolute_path':str(cp),'sha256':r['sha256'],'commit':commit,'dependencies':summary.get('dependencies',{}),'repository_url':f'https://github.com/xiangguaguadadi-dot/cumcm2026-b/blob/{commit}/experiments/{r["agent"]}/{r["candidate"]}'},'sources':[ctx['source'](cp),ctx['source'](rp/'case_metrics.json'),ctx['source'](rp/'summary.json')],'frozen_report_url':f'https://github.com/xiangguaguadadi-dot/cumcm2026-b/blob/{commit}/experiments/{r["agent"]}/report.md','budget':{'ledger_at_commit':f'https://github.com/xiangguaguadadi-dot/cumcm2026-b/blob/{commit}/experiments/{r["agent"]}/execution_budget.json','compared_exposed_cases':4800,'atlas_new_executions':0},'literature_basis':{'new_batch1_role':'later_context_only; these frozen rounds were independently proposed before batch1','new_literature_causal_adoption':False},'evidence_level':'frozen_git_blob_and_candidate_SHA_matched_all4800_rows_recomputed','unimplemented':False}
 n['literature_basis']=r.get('literature_basis',n['literature_basis'])
 n['next_hypothesis_evidence']=r.get('next_hypothesis_evidence','Frozen report and contemporaneous researcher plan; no performance implied.')
 parent_id=r['parents'][0];parent_rows=stage_rows.get(parent_id)
 if parent_rows is not None:
  n['comparisons_to_design_parent']=ctx['summarize'](raw,parent_rows,'exposed');n['design_parent_regressions']=[x for x in n['comparisons_to_design_parent'] if x['group']!='ALL' and x.get('delta_s_per_source',0)>1e-9]
 stage_rows[n['id']]={x['case_id']:x for x in raw}
 g['nodes'].append(n);byid[n['id']]=n
 for p in r['parents']:g['edges'].append({'source':p,'target':n['id'],'type':'fusion' if len(r['parents'])>1 else 'iteration','evidence':[n['frozen_report_url']],'confidence':'documented','note':'Actual registered parent; no summed gain.'})
 for p in r.get('inspired_by',[]):g['edges'].append({'source':p,'target':n['id'],'type':'inspired_by','evidence':[n['frozen_report_url']],'confidence':'documented','note':'Mechanism adapted, not wholesale parent code fusion.'})
 stage_checks.append({'node':n['id'],'candidate_sha_matches':True,'frozen_git_blob_matches':True,'frozen_result_blobs_match':True,'raw_rows_recomputed':4800,'saved_means_match':True})
for ag in ['R2_open','R3_open']:g['directions'].append({'id':ag,'label':'第三阶段开放研究 '+ag,'stage':3,'round_count':sum(x['agent']==ag for x in reg['rounds'])})
# Root's executed S0 equality audit is evidence distinct from stitched expected parent rows.
control=base/'coordinator/experiments/20260911_stage3/baseline/equivalence/audit.json'
if control.exists():
 ca=ctx['read'](control,'root_actual_S0_rerun_audit');byid['S0']['sources'].append(ctx['source'](control));byid['S0']['verification_note']='Coordinator actually reran4800; equality audit source is attached. Atlas only reads/recomputes the recorded evidence.';byid['S0']['coordinator_actual_rerun_audit']=ca
sources=list(ctx['SOURCES'].values());g['sources']=sources;g['coverage_audit']['stage3_registered_rounds']=len(reg['rounds']);g['coverage_audit']['stage3_frozen_checks']=stage_checks;g['coverage_audit']['stage3_additional_rows_recomputed']=4800*len(reg['rounds']);g['coverage_audit']['all_rounds_including_stage3']=48+len(reg['rounds']);g['coverage_audit']['sources_count']=len(sources)
(OUT/'exploration_graph.json').write_text(json.dumps(g,ensure_ascii=False,indent=2)+'\n')
nd=OUT/'nodes';nd.mkdir(exist_ok=True);index=[]
for n in g['nodes']:
 (nd/f'{n["id"]}.json').write_text(json.dumps(n,ensure_ascii=False,indent=2)+'\n')
 index.append({k:n.get(k) for k in ['id','kind','direction_tags','round','title','status','parents','design_parent','retained_best_before_round','retained_best_after_round','exploration','lesson','next_hypothesis']}|{'primary_effects':[{k:a[k] for k in ['suite','mode','cases','mean_s_per_source','baseline_mean_s_per_source','delta_s_per_source','all_clear_and_normal'] if k in a} for a in n.get('effects',[]) if a['group']=='ALL'],'comparison_baseline':n.get('comparison_baseline'),'details':f'nodes/{n["id"]}.json'})
(OUT/'exploration_index.json').write_text(json.dumps({'schema_version':'1.1','validation':'research/graph_validation.json','historical_rounds':48,'stage3_rounds':len(reg['rounds']),'read_order':'Read this index, then selected nodes/id.json, then source rows as needed. Full graph retains all matrices.','nodes':index},ensure_ascii=False,indent=2)+'\n')
lines=['# 第三阶段冻结节点增量','','只登记冻结并完成4800暴露评测的轮次；对照统一S0，节点详情另列真实设计父的逐批场景对照。R2 R3受首批DRD启发为费用代理，未实现HEC；较早独立想法与之后才收到的论文不反向归因。','','```mermaid','flowchart TB']
for r in reg['rounds']:
 n=byid[r['id']];m=[next(a['mean_s_per_source'] for a in n['effects'] if a['suite']=='combined' and a['group']=='ALL' and a['mode']==q) for q in [3,4]]
 lines.append(f'  {n["id"]}["{n["id"]} {n["title"]}<br/>Q3 {m[0]:.3f} / Q4 {m[1]:.3f}<br/>{n["lesson"].split("；")[0][:40]}"]')
 for p in r['parents']:lines.append(f'  {p} --> {n["id"]}')
 for p in r.get('inspired_by',[]):lines.append(f'  {p} -. "机制启发" .-> {n["id"]}')
lines+=['```','','|节点|合并Q3|合并Q4|真实来源及边界|','|---|---:|---:|---|']
for r in reg['rounds']:
 n=byid[r['id']];m=[next(a['mean_s_per_source'] for a in n['effects'] if a['suite']=='combined' and a['group']=='ALL' and a['mode']==q) for q in [3,4]]
 lines.append(f'|[{n["id"]}](nodes/{n["id"]}.json)|{m[0]:.9f}|{m[1]:.9f}|{n["lesson"]}|')
(OUT/'STAGE3_PROGRESS.md').write_text('\n'.join(lines)+'\n')
for name,text in [('README.md','\n新增[紧凑索引](exploration_index.json)与[nodes逐节点文件](nodes/)、[第三阶段冻结增量](STAGE3_PROGRESS.md)、[新文献支援](RESEARCH_BRIEF.md)。下次Agent先读紧凑索引再按需载入节点。\n'),('AI_README.md','\n优先读取exploration_index.json，每节点details指向nodes/<id>.json；无需先载入完整所有场景矩阵。design_parent表示设计来源，retained_best_after_round表示当时实际保留最佳，两者不能混淆。refresh_atlas.py依登记表重建历史并合入已冻结第三阶段节点；validate_graph.py验证结果。新论文与先前独立想法的关系存research/adoption_timeline.json，不能反向归因。\n'),('DIRECTION_MAP.md','\n第三阶段已冻结新节点见[STAGE3_PROGRESS.md](STAGE3_PROGRESS.md)；AI先读[紧凑索引](exploration_index.json)，再打开对应nodes/<id>.json。\n')]:
 with (OUT/name).open('a') as f:f.write(text)
print(json.dumps({'history_rounds':48,'stage3_rounds':len(reg['rounds']),'total_nodes':len(g['nodes']),'index_nodes':len(index),'sources':len(sources)}))
