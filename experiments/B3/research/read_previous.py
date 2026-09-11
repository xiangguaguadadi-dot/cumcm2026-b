"""Read-only full-file ingestion and raw-row audit of all six previous routes."""
from pathlib import Path
import json,hashlib,statistics,datetime,ast
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'experiments/B3'
CAM=ROOT/'experiments/20260911_agent_campaign'
coverage=[]
def read(p):
 p=Path(p); raw=p.read_bytes(); s=raw.decode('utf-8')
 entry={'path':str(p),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'lines':len(s.splitlines()),'reading':'full_programmatic_ingestion'}
 try:
  if p.suffix=='.json':
   d=json.loads(s)
  elif p.suffix=='.jsonl':
   d=[json.loads(l) for l in s.splitlines() if l.strip()]
  else:d=s
  if isinstance(d,list):entry['top_level_records']=len(d)
  elif isinstance(d,dict):entry['top_level_keys']=list(d)
  coverage.append(entry);return d
 except Exception as e:
  entry['parse_error']=str(e);coverage.append(entry);return None
assign=read(CAM/'assignments.json')['assignments']
rounds=read(CAM/'all_rounds.json')['rounds']
required=['REPORT.md','LITERATURE_MAP.md','candidate_registry.json','final_validation/comparison.json','audit/delivery_independent.md','audit/final_delivery_review.md']
for name in required:read(CAM/name)
rawsummary=[];libraries=[]
for a in assign:
 work=Path(a['worktree']);exp=work/'experiments'/a['id']
 for p in sorted(exp.rglob('*')):
  if p.is_file() and p.suffix in ('.json','.jsonl','.md','.py','.txt','.log') and 'cache' not in p.parts and not any(x.startswith('.') for x in p.relative_to(exp).parts):
   data=read(p)
   if p.name=='literature.json':libraries.append({'agent':a['id'],'manifest':str(p),'records':data,'B3_reading_level':'完整读取原路线文献记录与报告；不表示B3重读各篇PDF。'})
 for r in (r for r in rounds if r['agent']==a['id']):
  for suite in ('quick','full'):
   folder=Path(r[suite+'_path']);rows=read(folder/'case_metrics.json');summary=read(folder/'summary.json')
   bases={x['case_id']:x for x in rows if x['variant']=='frozen_baseline'}
   cand=[x for x in rows if x['variant']=='candidate']
   assert len(cand)==len(bases)==(2400 if suite=='full' else 120)
   assert len({x['case_id'] for x in cand})==len(cand)
   modes=[]
   for m in (3,4):
    part=[x for x in cand if x['mode']==m];ds=[x['average_clear_time_s']-bases[x['case_id']]['average_clear_time_s'] for x in part]
    groups=[]
    for g in sorted({x['group'] for x in part}):
     group=[x for x in part if x['group']==g];val=statistics.mean(x['average_clear_time_s']-bases[x['case_id']]['average_clear_time_s'] for x in group)
     if val>1e-8:groups.append({'group':g,'delta_s_per_source':val})
    modes.append({'mode':m,'cases':len(part),'complete':sum(x['complete'] and not x.get('error') and x['exit_reason']=='user_exit' and x['cleared_count']==x['source_count'] for x in part),'cleared':sum(x['cleared_count'] for x in part),'sources':sum(x['source_count'] for x in part),'mean_s_per_source':statistics.mean(x['average_clear_time_s'] for x in part),'faster':sum(d<-1e-8 for d in ds),'equal':sum(abs(d)<=1e-8 for d in ds),'slower':sum(d>1e-8 for d in ds),'regressed_groups':groups,'max_case':max(part,key=lambda x:x['average_clear_time_s']),'failure_rows':[x for x in part if not x['complete'] or x.get('error')]})
   rawsummary.append({'agent':a['id'],'round':r['round'],'suite':suite,'sha256':summary['candidate_sha256'],'rows':len(rows),'modes':modes})
# All previous-final rows, including baseline and tradeoffs, decoded in full.
for p in sorted((CAM/'final_validation').rglob('*.json')):read(p)
# All old candidate source parsed including failed candidate rounds; AST identity is only a code reading aid.
source_audit=[]
baseast=ast.parse((ROOT/'evaluation/baseline_solver.py').read_text())
def functions(tree):
 return {n.name:ast.dump(n,include_attributes=False) for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
bf=functions(baseast)
for a in assign:
 exp=Path(a['worktree'])/'experiments'/a['id']
 for folder in ('snapshots','candidates'):
  for p in sorted((exp/folder).glob('*.py')):
   s=p.read_text();tree=ast.parse(s);fs=functions(tree)
   source_audit.append({'path':str(p),'lines':len(s.splitlines()),'functions_added_or_changed':[k for k,v in fs.items() if bf.get(k)!=v],'env_accesses':sorted({n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute) and isinstance(n.value,ast.Attribute) and isinstance(n.value.value,ast.Name) and n.value.value.id=='self' and n.value.attr=='env'})})
for e in coverage:
 if e['path'].endswith('/report.md') or e['path'] in [str(CAM/x) for x in ('REPORT.md','audit/delivery_independent.md','audit/final_delivery_review.md')]:e['reading']='full_text_read_in_chunks_plus_programmatic_ingestion'
result={'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':coverage,'file_count':len(coverage),'total_read_lines':sum(x['lines'] for x in coverage),'raw_review_rows':sum(x['rows'] for x in rawsummary),'not_read':['原路线PDF未全部由B3重读；后续仅重读本轮选用核心来源的明确正文页','缓存下载的HTML/PDF和二进制未遍历；不作为任务统计'],'notes':['所有旧开发JSON/JSONL按文件完整解析；不把读取次数计作执行次数。','源代码全文件AST解析；改变的函数再进行人工代码阅读。']}
(OUT/'reading_coverage.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
(OUT/'research/previous_raw_review.json').write_text(json.dumps(rawsummary,ensure_ascii=False,indent=2))
(OUT/'research/previous_literature_complete.json').write_text(json.dumps(libraries,ensure_ascii=False,indent=2))
(OUT/'research/previous_source_audit.json').write_text(json.dumps(source_audit,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='files'},ensure_ascii=False))
print('source snapshots',len(source_audit),'literature manifest count',len(libraries))
print('all complete?',all(m['complete']==m['cases'] for r in rawsummary for m in r['modes']))
