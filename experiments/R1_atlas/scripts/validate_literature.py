#!/usr/bin/env python3
import hashlib,json,pathlib
from pypdf import PdfReader
out=pathlib.Path(__file__).resolve().parents[1]
d=json.loads((out/'literature.json').read_text());core=d['core'];ids={x['id'] for x in core};assert len(ids)==len(core)==d['core_count']
assert len({tuple(x['primary_path']) for x in core})==len(core)
checks=[];versions=[]
for p in core:
 assert p['identity_verified'] and p['url'].startswith('https://') and p['pdf_url'].startswith('https://')
 versions.append(p['cache'])
 if p.get('related_version',{}).get('cache'):versions.append(p['related_version']['cache'])
 count=p['cache']['pages'];assert all(1<=x<=count for x in p['actual_reading']['pdf_pages'])
 assert set(p['actual_reading']['visual_checked_pdf_pages'])<=set(p['actual_reading']['pdf_pages'])
 checks.append({'paper':p['id'],'declared_reading_within_pdf':True,'primary_path_unique':True})
assert len(versions)==d['downloaded_version_count']
for c in versions:
 f=pathlib.Path(c['path']);assert hashlib.sha256(f.read_bytes()).hexdigest()==c['sha256'];assert len(PdfReader(f).pages)==c['pages']
for memo in d['sharing_memos']:assert (out/memo).exists()
g=json.loads((out/'exploration_graph.json').read_text())
for n in g['nodes']:
 assert set(n.get('literature_basis',{}).get('paper_ids',[]))<=ids
res={'passed':True,'core_papers':len(core),'downloaded_versions':len(versions),'cached_originals_sha_and_pages_match':True,'paper_reference_ids_valid':True,'checks':checks,'limits':'Identity and actual read ranges were manually checked from official pages and paper body; this script validates counts/references/hashes,not the truth of paper claims.'}
(out/'research/literature_validation.json').write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n');print({k:v for k,v in res.items() if k not in ['checks','limits']})
