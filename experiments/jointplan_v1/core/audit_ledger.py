"""Read-only reconciliation of every settled run against its retained journal."""
import collections,gzip,hashlib,json,sqlite3,sys
from pathlib import Path
C=Path(__file__).resolve().parents[1];sys.path.insert(0,str(Path(__file__).resolve().parent))
from budget import Budget
from runner import dump

def main():
 s=Budget(C/'execution.sqlite').snapshot();assert s['active']==0 and s['executions']==s['completed']
 total=collections.Counter();phase={};batches={};kind=collections.Counter();files=[]
 for run in s['runs']:
  path=Path(run['result_path']);data=json.loads(gzip.decompress(path.read_bytes()) if path.name.endswith('.gz') else path.read_text())
  assert data['calls']=={k:run[k] for k in ('attempts','accepted','rejected','known_error','unknown')}
  folder=path.parent;rid=run['id'];jp=folder/(rid+'.journal.jsonl.gz')
  records=[json.loads(x) for x in gzip.decompress(jp.read_bytes()).decode().splitlines()]
  assert len(records)%2==0
  counts=collections.Counter(attempts=0,accepted=0,rejected=0,known_error=0,unknown=0)
  for i in range(0,len(records),2):
   a,b=records[i:i+2];assert a['event']=='attempt' and b['event']=='outcome' and a['seq']==b['seq']==i//2
   counts['attempts']+=1;counts[b['category']]+=1
  assert dict(counts)==data['calls'] and counts['unknown']==0 and counts['attempts']<=run['reserved']==5000
  total.update(counts);phase.setdefault(run['phase'],collections.Counter()).update(dict(executions=1,**counts))
  batches.setdefault(run['batch'],collections.Counter()).update(dict(executions=1,**counts))
  if data.get('kind')=='frozen_rule_fixture':kind['rule_fixtures']+=1
  else:
   assert data['row']['complete'];kind['complete_strategy_runs']+=1
  files.append(dict(path=str(path.relative_to(C)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),journal=str(jp.relative_to(C)),journal_sha256=hashlib.sha256(jp.read_bytes()).hexdigest()))
 assert dict(total)==s['settled_calls']
 # Recheck exact concurrency reservations from event endpoints; settled run caps
 # cover both active workers even when a run has not made its first call yet.
 events=sorted([(r['created'],1) for r in s['runs']]+[(r['finished'],-1) for r in s['runs']])
 live=peak=0
 for t,d in events:live+=d;peak=max(peak,live);assert 0<=live<=2
 assert live==0
 last=max(r['finished'] for r in s['runs']);first=s['first_business_call_epoch']
 out=dict(passed=True,executions=s['executions'],kinds=dict(kind),counts=dict(total),phases={k:dict(v) for k,v in phase.items()},batches={k:dict(v) for k,v in batches.items()},peak_reserved_workers=peak,first_call_epoch=first,last_settlement_epoch=last,first_call_to_last_settlement_seconds=last-first,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),files=files)
 dump(C/'results/FINAL_LEDGER_AUDIT.json',out)
 target=C/'results/execution_final.sqlite';assert not target.exists()
 with sqlite3.connect(C/'execution.sqlite') as a,sqlite3.connect(target) as b:a.backup(b)
 raw=target.read_bytes();gp=target.with_suffix('.sqlite.gz');gp.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(gp.read_bytes())==raw;target.unlink()
 dump(C/'results/FINAL_LEDGER_SNAPSHOT.json',dict(snapshot_sha256=hashlib.sha256(gp.read_bytes()).hexdigest(),raw_sqlite_sha256=hashlib.sha256(raw).hexdigest(),snapshot_file=gp.name,execution_status=s))
 print(json.dumps({k:v for k,v in out.items() if k not in ('files','batches')}))
if __name__=='__main__':main()
