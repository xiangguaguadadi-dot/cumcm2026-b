from pathlib import Path
import json, hashlib, ast, statistics, datetime, csv
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'experiments/B2/research'
readings={}
def read(p,mode='programmatic_full'):
 p=Path(p); b=p.read_bytes();t=b.decode('utf-8-sig');readings[str(p)]={'path':str(p),'bytes':len(b),'lines':len(t.splitlines()),'sha256':hashlib.sha256(b).hexdigest(),'depth':mode};return t
def obj(p):
 t=read(p);o=json.loads(t);return o
campaign=ROOT/'experiments/20260911_agent_campaign'
rounds=obj(campaign/'all_rounds.json')['rounds'];assign=obj(campaign/'assignments.json')['assignments'];registry=obj(campaign/'candidate_registry.json')
for name in ['REPORT.md','LITERATURE_MAP.md','audit/delivery_independent.md','audit/final_delivery_review.md']:
 read(campaign/name,'full_text_read_with_targeted_followup')
obj(campaign/'final_validation/comparison.json')
round_summary=[]
for r in rounds:
 row={'agent':r['agent'],'round':r['round'],'suites':[]}
 for suite in ['quick','full']:
  directory=Path(r[suite+'_path']);rows=obj(directory/'case_metrics.json'); summary=obj(directory/'summary.json')
  a={x['case_id']:x for x in rows if x['variant']=='frozen_baseline'}; b=[x for x in rows if x['variant']=='candidate']
  assert len(a)==len(b)==len({x['case_id'] for x in b})
  modes=[]
  for m in (3,4):
   q=[x for x in b if x['mode']==m];delta=[x['average_clear_time_s']-a[x['case_id']]['average_clear_time_s'] for x in q if x['complete']]
   groups=[]
   for g in sorted({x['group'] for x in q}):
    sub=[x for x in q if x['group']==g];d=[x['average_clear_time_s']-a[x['case_id']]['average_clear_time_s'] for x in sub]
    groups.append(dict(group=g,delta=statistics.mean(d),slower=sum(z>1e-8 for z in d)))
   modes.append(dict(mode=m,cases=len(q),complete=sum(x['complete'] for x in q),mean=statistics.mean(x['average_clear_time_s'] for x in q),faster=sum(x < -1e-8 for x in delta),equal=sum(abs(x)<=1e-8 for x in delta),slower=sum(x>1e-8 for x in delta),worst=max(q,key=lambda x:x['average_clear_time_s']),groups=groups))
  row['suites'].append(dict(suite=suite,modes=modes,wall_seconds=summary['wall_seconds']))
 round_summary.append(row)
source_review=[]; literature=[];inner=[]
for a in assign:
 base=Path(a['worktree'])/'experiments'/a['id']; route={'agent':a['id'],'json_files':0,'jsonl_lines':0,'csv_rows':0,'py_files':0,'nested_metric_rows':0,'failures':[]}
 for p in sorted(base.rglob('*')):
  if not p.is_file() or p.suffix not in {'.json','.jsonl','.py','.md','.csv'}:continue
  if any(x in p.parts for x in ('__pycache__','.cache')):continue
  if p.suffix=='.py':
   t=read(p,'complete_source_parse_and_difference_inventory'); tree=ast.parse(t);route['py_files']+=1
   source_review.append(dict(path=str(p),functions=[n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]))
  elif p.suffix=='.md':read(p,'full_text_read' if p.name=='report.md' else 'programmatic_full_text_index')
  elif p.suffix=='.csv':route['csv_rows']+=len(list(csv.DictReader(read(p).splitlines())))
  else:
   t=read(p)
   if p.suffix=='.jsonl': records=[json.loads(x) for x in t.splitlines() if x.strip()];route['jsonl_lines']+=len(records)
   else:records=json.loads(t);route['json_files']+=1
   if p.name=='literature.json':literature.append(dict(agent=a['id'],source_path=str(p),records=records))
   def visit(o):
    if isinstance(o,dict):
     if type(o.get('complete')) is bool and any(k in o for k in ['seed','case_id']) and any(k in o for k in ['average','average_s','average_clear_time_s','time_s','cleared_count','score','seconds_per_source']):
      route['nested_metric_rows']+=1
      if not o['complete']:route['failures'].append(dict(path=str(p),record=o))
     for v in o.values():visit(v)
    elif isinstance(o,list):
     for v in o:visit(v)
   visit(records)
 inner.append(route)
 # Root solver best needs actual full review/diff, not only parse.
 read(Path(a['worktree'])/'solver.py','complete_source_diff_against_baseline')
for p in [ROOT/'AGENTS.md',ROOT/'README.md',ROOT/'docs/评测标准_v1.md',ROOT/'experiments/20260911_breakthrough/PROTOCOL.md',Path('/Users/t/Documents/Codex/2026-09-10/new-chat/work/problem_extracted.txt')]:read(p,'full_text_read')
coverage={'agent':'B2','time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'All six route report/literature and experiment text/json/jsonl/csv/code files processed; raw metric arrays recomputed, code parsed. Research cached paper text indexed only if under experiment dirs; exact directly read paper excerpts logged separately.','files':list(readings.values()),'full_rounds':len(rounds),'inner_inventory':inner,'unread':'Cached PDFs/images and binary files not reread. Raw JSON programmatic processing is not human line-by-line reading. Prior source full diffs and paper excerpts reviewed separately.'}
(ROOT/'experiments/B2/reading_coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2))
(OUT/'prior_rounds_recomputed.json').write_text(json.dumps(round_summary,ensure_ascii=False,indent=2))
(OUT/'prior_source_inventory.json').write_text(json.dumps(source_review,ensure_ascii=False,indent=2))
(OUT/'prior_literature_complete.json').write_text(json.dumps(literature,ensure_ascii=False,indent=2))
print(json.dumps({'files':len(readings),'lines':sum(x['lines'] for x in readings.values()),'rounds':len(rounds),'inner':inner},ensure_ascii=False)[:6000])
