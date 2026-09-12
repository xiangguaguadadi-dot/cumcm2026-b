"""Register unchanged historical full/quick/other-exposed inputs and cached anchor."""
import hashlib,json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parents[1]/'data/regression'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 OUT.mkdir(exist_ok=True);assert not any(OUT.iterdir())
 v1=ROOT/'evaluation/cases_v1.json';allpath=ROOT/'experiments/20260911_stage3/exposed_cases.json';old=ROOT/'experiments/parallel_v2_coordinator/fusion_r5_exposed'
 full=json.loads(v1.read_text());allcases=json.loads(allpath.read_text());rows=json.loads((old/'case_metrics.json').read_text());summary=json.loads((old/'summary.json').read_text())
 assert len(full)==2400 and len(allcases)==len(rows)==4800
 assert sha(allpath)==summary['cases_sha256']
 assert sha(ROOT/'experiments/parallel_v2_coordinator/fusion_r5.py')==summary['candidate_sha256']
 fullids={c['case_id'] for c in full};other=[c for c in allcases if c['case_id'] not in fullids];assert len(other)==2400
 cases={c['case_id']:c for c in allcases};assert len(cases)==len(rows)==len({r['case_id'] for r in rows})
 for r in rows:
  c=cases[r['case_id']];n=len(c['sources'])
  assert r['complete'] and r['cleared_count']==n and r['source_count']==n and r['error'] is None
  assert r['average_clear_time_s']==r['total_virtual_time_s']/n
  clears=r['clear_failures']+n;measures=r['requests']-clears-2
  remainder=r['total_virtual_time_s']-(r['distance_m']/5+5*measures+3*clears+2*n)
  switches=round(remainder);assert 0<=switches<=measures
  tolerance=(measures+clears)*.500001e-6
  assert abs(remainder-switches)<=tolerance+1e-7
 for name,data in [('full2400',full),('quick120',[c for c in full if c['quick']]),('other_exposed2400',other),('anchor4800',rows)]:
  (OUT/(name+'.json')).write_text(json.dumps(data,separators=(',',':'))+'\n')
 result=dict(parent_sha256=summary['candidate_sha256'],inputs={str(p.relative_to(ROOT)):sha(p) for p in (v1,allpath,old/'case_metrics.json',old/'summary.json')},worlds=4800,modes={str(q):dict(worlds=len(rr:=[r for r in rows if r['mode']==q]),sources=sum(r['source_count'] for r in rr),mean_seconds_per_source=statistics.mean(r['average_clear_time_s'] for r in rr)) for q in (3,4)},virtual_cache_only=True,current_machine_runtime_not_reused=True)
 (OUT/'registration.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
