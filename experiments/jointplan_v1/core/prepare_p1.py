"""Pair pre-frozen public plans with evaluator worlds, with no outcome selection."""
import copy,hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from geometry.engine import snapshot_hash,verify
from geometry.continuous import replay_certificate

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 out=ROOT/'data/p1_batches';out.mkdir(exist_ok=False)
 rawpath=ROOT/'geometry/results/public_prefix_diagnostics_r1/FROZEN_P1_CANDIDATES.json'
 plans=json.loads(rawpath.read_text())['prefixes']
 snaps=json.loads((ROOT/'data/p1_public_snapshots.json').read_text())
 reg=json.loads((ROOT/'data/p1_prefix_registration.json').read_text())
 cases={c['case_id']:c for c in json.loads((ROOT/'data/p0_exposed48.json').read_text())}
 assert len(plans)==len(snaps)==96
 counts=[];datasets=[{} for _ in range(12)];checks=[];same_public={};start=time.perf_counter()
 for world in reg['registry']:
  counts.append(0)
  for pi,ref in enumerate(world['prefixes']):
   index=ref['index'];record,snapshot=plans[index],snaps[index]
   assert record['snapshot_hash']==snapshot_hash(snapshot)==ref['snapshot_hash']
   assert record['candidate_count']==len(record['candidates'])<=6
   physical=[p['plan']['stations'] for p in record['candidates']]
   previous=same_public.setdefault(ref['snapshot_hash'],physical)
   assert previous==physical, 'Same public history generated different candidate geometries'
   for ci,candidate in enumerate(record['candidates']):
    plan=candidate['plan'];checked=verify(snapshot,plan,keep_leaves=True)
    assert checked['status']=='certified'
    seen=set()
    for ch,proof in checked['proofs'].items():
     if proof['quantized_points_hash'] in seen:continue
     seen.add(proof['quantized_points_hash'])
     points=[]
     for row in snapshot['history']:
      if row['action']=='measure' and row['request'].get('channel')==int(ch) and row['response'].get('accepted') is True and row['response'].get('measure_result')=='no_signal':points.append(row['request']['point'])
     points.extend(s['point'] for s in plan['stations'] if int(ch) in s['channels'])
     assert replay_certificate(snapshot['mode'],points,proof)
    slot=pi*6+ci;cid=world['case_id'];assert cid not in datasets[slot]
    datasets[slot][cid]={'jointplan_replay':dict(snapshot_hash=ref['snapshot_hash'],plan=plan,scheduler='parent'),'jointplan_intervention_limit':1,'jointplan_geometry':True,'jointplan_mixed':False}
    checks.append(dict(case_id=cid,prefix_index=pi,candidate_index=ci,block_size=candidate['block_size'],slot=slot,snapshot_hash=ref['snapshot_hash'],plan_sha256=hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':')).encode()).hexdigest(),independent_leaf_replay=True))
    counts[-1]+=1
 for slot,config in enumerate(datasets):
  if not config:continue
  (out/f'slot{slot:02}_cases.json').write_text(json.dumps([cases[c] for c in config],separators=(',',':'))+'\n')
  (out/f'slot{slot:02}_config.json').write_text(json.dumps(config,separators=(',',':'))+'\n')
 result=dict(source_sha256=sha(rawpath),script_sha256=sha(__file__),worlds=48,prefixes=96,candidate_full_runs=sum(counts),worlds_with_candidates=sum(n>0 for n in counts),worlds_without_candidates=sum(n==0 for n in counts),slot_counts=[len(d) for d in datasets],coverage_checks=checks,generation_seconds=time.perf_counter()-start)
 (out/'registration.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='coverage_checks'}))
if __name__=='__main__':main()
