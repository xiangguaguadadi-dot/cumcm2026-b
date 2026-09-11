"""Read-only processing of all six historical route text/data/code artifacts."""
import ast, hashlib,json,pathlib,statistics,time
ROOT=pathlib.Path(__file__).resolve().parents[3]; OUT=ROOT/'experiments/R3_open/research'
assign=json.loads((ROOT/'experiments/20260911_agent_campaign/assignments.json').read_text())['assignments']
coverage=[]; summaries=[]; errors=[]; literals=[]

def walk(x):
 if isinstance(x,dict):
  yield x
  for y in x.values():yield from walk(y)
 elif isinstance(x,list):
  for y in x:yield from walk(y)

def read(p,scope):
 raw=p.read_bytes(); s=raw.decode('utf-8',errors='replace'); item=dict(path=str(p),scope=scope,bytes=len(raw),lines=len(s.splitlines()),sha256=hashlib.sha256(raw).hexdigest())
 if p.suffix in ('.json','.jsonl'):
  try:
   data=json.loads(s) if p.suffix=='.json' else [json.loads(l) for l in s.splitlines() if l.strip()]
   nodes=list(walk(data)); rows=[r for r in nodes if 'average_clear_time_s' in r and 'source_count' in r and 'case_id' in r]
   item.update(read_mode='entire JSON recursively parsed; metric rows recomputed when present',metric_rows=len(rows),objects=len(nodes))
   failures=[r for r in nodes if r.get('error') or (('complete' in r) and r['complete'] is False) or ('timeout' in str(r.get('status','')).lower())]
   if failures:summaries.append(dict(path=str(p),failure_records=len(failures),failure_samples=failures[:5]))
   if rows:
    z=[]
    for mode in (3,4):
     for variant in sorted(set(str(r.get('variant','unknown')) for r in rows)):
      a=[r for r in rows if r['mode']==mode and str(r.get('variant','unknown'))==variant]
      if a:z.append(dict(mode=mode,variant=variant,n=len(a),valid=sum(bool(r.get('complete')) and not r.get('error') for r in a),mean=statistics.mean(r['average_clear_time_s'] for r in a if r['average_clear_time_s'] is not None),worst=max((r for r in a if r['average_clear_time_s'] is not None),key=lambda r:r['average_clear_time_s'])['case_id']))
    summaries.append(dict(path=str(p),metrics=z))
  except Exception as e:item.update(read_mode='parse failure',error=repr(e));errors.append(item)
 elif p.suffix=='.py':
  try:
   t=ast.parse(s);item.update(read_mode='entire source AST parsed; changed functions reviewed separately',functions=[n.name for n in ast.walk(t) if isinstance(n,ast.FunctionDef)])
  except SyntaxError as e:item.update(read_mode='parse failure',error=str(e));errors.append(item)
 else:item.update(read_mode='entire text indexed; narrative review tracked separately; tables parsed as evidence not manual trajectory replay')
 coverage.append(item)

for a in assign:
 w=pathlib.Path(a['worktree']); name=a['id']; own=w/'experiments'/name
 files=set(p for p in own.rglob('*') if p.is_file() and p.suffix in ('.json','.jsonl','.md','.py','.log') and '__pycache__' not in str(p))
 files.update(p for p in (w/'results').glob(name+'*/*') if p.is_file() and p.suffix in ('.json','.jsonl','.md','.log'))
 for p in sorted(files):read(p,name)
for p in (ROOT/'experiments/20260911_agent_campaign').rglob('*'):
 if p.is_file() and p.suffix in ('.json','.md','.py','.log'):read(p,'campaign')

for base in ('experiments/B1','experiments/B2','experiments/B3','experiments/20260911_breakthrough','experiments/20260911_stage3'):
 for p in (ROOT/base).rglob('*'):
  if p.is_file() and p.suffix in ('.json','.jsonl','.md','.py','.log'):read(p,base)
read(ROOT/'AGENTS.md','protocol');read(ROOT/'README.md','protocol');read(ROOT/'docs/评测标准_v1.md','protocol');read(ROOT/'experiments/20260911_breakthrough/PROTOCOL.md','protocol')
(OUT/'corpus_summary.json').write_text(json.dumps(summaries,ensure_ascii=False,indent=2))
(ROOT/'experiments/R3_open/reading_coverage.json').write_text(json.dumps(dict(created=time.strftime('%Y-%m-%dT%H:%M:%S%z'),files=coverage,parse_errors=errors,coverage_boundary='所有列示文件全字节处理；JSON逐行解析及聚合不冒充全部逐局人工深读。旧论文原文未全部重读，六份literature.json全量解析并保留继承阅读等级，拟采用核心文献另读关键正文。PDF/大训练权重不复制。'),ensure_ascii=False,indent=2))
print(json.dumps(dict(files=len(coverage),lines=sum(x['lines'] for x in coverage),metric_rows=sum(x.get('metric_rows',0) for x in coverage),parse_errors=len(errors)),ensure_ascii=False))
