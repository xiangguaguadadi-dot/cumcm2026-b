#!/usr/bin/env python3
import collections,hashlib,json,pathlib
from node_metadata import RETAINED_BEST
root=pathlib.Path(__file__).resolve().parents[3];out=root/'experiments/R1_atlas';g=json.loads((out/'exploration_graph.json').read_text())
nodes=g['nodes']; ids={x['id'] for x in nodes}; assert len(nodes)==len(ids)
historical=[x for x in nodes if x['kind']=='completed_optimization_round'];assert len(historical)==48
rounds=[x for x in nodes if x['kind'] in ('completed_optimization_round','completed_stage3_round')]
checks=[]
for n in rounds:
 p=pathlib.Path(n['candidate']['absolute_path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==n['candidate']['sha256'],n['id']
 assert len([x for x in n['effects'] if x['suite']=='v1' and x['group']=='ALL'])==2
 for x in n['effects']:
  assert x['all_clear_and_normal'];assert x['complete_cases']==x['cases'];assert x['source_count']==x['cleared_count']
  if 'faster' in x:assert x['faster']+x['equal']+x['slower']==x['cases']
 checks.append({'node':n['id'],'candidate_current_sha_matches':True,'effect_denominators_match':True})
for e in g['edges']:assert e['source'] in ids and e['target'] in ids
byid={n['id']:n for n in nodes}
retention_checks=[]
for direction,retained_rounds in RETAINED_BEST.items():
 first=byid[f'{direction}_R1']
 best_means=[next(x['baseline_mean_s_per_source'] for x in first['effects'] if x['suite']=='v1' and x['group']=='ALL' and x['mode']==q) for q in (3,4)]
 best_id='R0'
 for rn,retained in enumerate(retained_rounds,1):
  nid=f'{direction}_R{rn}';n=byid[nid];expected=f'{direction}_R{retained}' if retained else 'R0'
  means=[next(x['mean_s_per_source'] for x in n['effects'] if x['suite']=='v1' and x['group']=='ALL' and x['mode']==q) for q in (3,4)]
  if all(x<=y+1e-9 for x,y in zip(means,best_means)) and any(x<y-1e-9 for x,y in zip(means,best_means)):
   best_id=nid;best_means=means
  assert expected==best_id,(nid,expected,best_id)
  assert n['retained_best_after_round']==expected
  returns=[e['target'] for e in g['edges'] if e['source']==nid and e['type']=='reverts_to']
  assert returns==([] if expected==nid else [expected]),(nid,returns,expected)
  retention_checks.append({'node':nid,'design_parent':n['design_parent'],'retained_best_after_round':expected,'strict_joint_best_recomputed_from_raw_means':best_id,'decision_reference_matches':True})
assert byid['A2_information_R2']['design_parent']=='A2_information_R1'
assert byid['A2_information_R2']['retained_best_after_round']=='R0'
assert byid['A6_learning_R9']['design_parent']=='A6_learning_R8'
assert byid['A6_learning_R9']['retained_best_after_round']=='A6_learning_R7'
index=json.loads((out/'exploration_index.json').read_text())
assert {n['id'] for n in index['nodes']}==ids
for entry in index['nodes']:
 assert json.loads((out/entry['details']).read_text())==byid[entry['id']]
 assert entry['next_hypothesis']==byid[entry['id']].get('next_hypothesis')
sourceids={s['id'] for s in g['sources']}
for n in nodes:
 assert all(s in sourceids for s in n['sources'])
source_changes=[]
for s in g['sources']:
 p=pathlib.Path(s['absolute_path'])
 if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=s['sha256']:source_changes.append(s['path'])
assert not source_changes,source_changes
adj=collections.defaultdict(list);deg={i:0 for i in ids}
for e in g['edges']:
 if e['type'] in ('iteration','fusion','derived_from'):adj[e['source']].append(e['target']);deg[e['target']]+=1
queue=[i for i,d in deg.items() if not d];seen=[]
while queue:
 i=queue.pop();seen.append(i)
 for j in adj[i]:
  deg[j]-=1
  if not deg[j]:queue.append(j)
assert set(seen)==ids
result={'passed':True,'historical_rounds':48,'all_registered_rounds':len(rounds),'all_node_references_valid':True,'source_files_sha_matched':len(g['sources']),'implementation_dag_acyclic':True,'compact_index_and_node_files_match':True,'retained_decision_references_match':True,'retention_checks':retention_checks,'checks':checks,'new_policy_executions':0}
(out/'research/graph_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ('checks','retention_checks')}))
