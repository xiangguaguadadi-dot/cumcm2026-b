#!/usr/bin/env python3
import collections,hashlib,json,pathlib
root=pathlib.Path(__file__).resolve().parents[3];out=root/'experiments/R1_atlas';g=json.loads((out/'exploration_graph.json').read_text())
nodes=g['nodes']; ids={x['id'] for x in nodes}; assert len(nodes)==len(ids)
rounds=[x for x in nodes if x['kind']=='completed_optimization_round'];assert len(rounds)==48
checks=[]
for n in rounds:
 p=pathlib.Path(n['candidate']['absolute_path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==n['candidate']['sha256'],n['id']
 assert len([x for x in n['effects'] if x['suite']=='v1' and x['group']=='ALL'])==2
 for x in n['effects']:
  assert x['all_clear_and_normal'];assert x['complete_cases']==x['cases'];assert x['source_count']==x['cleared_count']
  if 'faster' in x:assert x['faster']+x['equal']+x['slower']==x['cases']
 checks.append({'node':n['id'],'candidate_current_sha_matches':True,'effect_denominators_match':True})
for e in g['edges']:assert e['source'] in ids and e['target'] in ids
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
result={'passed':True,'rounds':48,'all_node_references_valid':True,'source_files_sha_matched':len(g['sources']),'implementation_dag_acyclic':True,'checks':checks,'new_policy_executions':0}
(out/'research/graph_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='checks'}))
