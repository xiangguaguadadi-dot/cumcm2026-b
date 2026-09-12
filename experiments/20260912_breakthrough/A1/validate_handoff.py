"""Static hash, tree, rule-log, row-budget, and local Markdown-link audit."""
import hashlib
import json
import re
from pathlib import Path

HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
literature=read(HERE/'literature.json')
assert len(literature['core'])==literature['core_count']==3
assert len(literature['expanded'])==literature['expanded_count']==1
core_ids={x['id'] for x in literature['core']}
assert len(core_ids)==3
def leaves(node):
    if isinstance(node,list):return node
    return [x for sub in node.values() for x in leaves(sub)]
tree_ids=leaves(literature['primary_tree'])
assert set(tree_ids)==core_ids and len(tree_ids)==len(core_ids)
hashes=[]
for path in sorted(HERE.glob('r*_registration.json')):
    item=read(path)
    checks={role:sha(Path(item[role]))==item[role+'_sha256'] for role in ('candidate','parent','component')}
    assert checks['candidate'] and checks['parent'],path
    if not checks['component']:
        assert item['round'] in ('r6','r6a')
    hashes.append(dict(registration=path.name,checks=checks,
        component_explanation=None if checks['component'] else 'Live cover_component.py later corrected; this registration pins the preserved immutable pre-correction snapshot and old component hash, not the new file'))
rules=[]
for path in sorted((HERE/'results').glob('*_rules/execution.json')):
    records=read(path)
    assert all(r['returncode']==0 for r in records),path
    rules.append(str(path.relative_to(HERE)))
ledger=read(HERE/'iteration_ledger.json')
assert not any(r['status']=='in_progress' for r in ledger['rows'])
assert ledger['totals']['unique_exposed_case_ids']==4800
assert ledger['totals']['evaluation_failures']==59
manifest=read(HERE/'BEST_manifest.json')
assert manifest['best_sha256']==sha(HERE/'BEST.py')
assert manifest['component_sha256']==sha(HERE/'BEST_Q3_COMPONENT.py')
assert manifest['rows_sha256']==sha(HERE/manifest['rows'])
assert manifest['ledger_sha256']==sha(HERE/'iteration_ledger.json')
links=[]
for name in ('REPORT.md','RESEARCH.md'):
    for label,destination in re.findall(r'\[([^\]]+)\]\(([^)]+)\)',(HERE/name).read_text()):
        if '://' in destination or destination.startswith('#'):
            continue
        target=(HERE/destination.split('#')[0]).resolve()
        assert target.exists(),(name,label,destination)
        links.append(dict(document=name,destination=destination))
sources=[]
for paper in literature['core']:
    cache=Path(paper['cache_path'])
    if not cache.is_absolute():cache=HERE/cache
    assert sha(cache)==paper['cache_sha256'],paper['id']
    sources.append(dict(id=paper['id'],cache_sha_verified=True))
result=dict(all_checks=True,core_count=3,expanded_count=1,one_tree_leaf_per_core=True,
    immutable_candidate_and_parent_hashes=hashes,rule_runs=rules,local_links=links,primary_source_hashes=sources,
    evidence_boundary='Static and saved-row validation; external URLs could not be refreshed through web tool, and this is not another solver evaluation')
(HERE/'HANDOFF_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in result.items() if k not in ('immutable_candidate_and_parent_hashes','rule_runs','local_links')},ensure_ascii=False,indent=2))
