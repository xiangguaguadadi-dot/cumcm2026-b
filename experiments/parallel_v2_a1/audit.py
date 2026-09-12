from pathlib import Path
import json,sys,hashlib,statistics,random,collections
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def valid(r):return r['complete'] and r['exit_reason']=='user_exit' and not r['error'] and r['cleared_count']==r['source_count']
label=sys.argv[1];folder=HERE/'results'/f'{label}_exposed';path=folder/'case_metrics.json';rows=json.loads(path.read_text());basepath=ROOT/'experiments/20260912_breakthrough/A1/results/r2_exposed/case_metrics.json';base=json.loads(basepath.read_text());idx={r['case_id']:r for r in base};assert len(rows)==4800==len(idx)==len({r['case_id'] for r in rows});assert set(idx)=={r['case_id'] for r in rows}
out=dict(candidate=label,candidate_sha256=sha(HERE/'snapshots'/f'{label}.py'),rows_sha256=sha(path),baseline_rows_sha256=sha(basepath),all_complete=all(valid(r) for r in rows),modes=[])
for m in (3,4):
 z=[r for r in rows if r['mode']==m];b=[idx[r['case_id']] for r in z];assert all((r['mode'],r['group'],r['source_count'])==(p['mode'],p['group'],p['source_count']) for r,p in zip(z,b));d=[r['average_clear_time_s']-p['average_clear_time_s'] for r,p in zip(z,b)]
 def costs(a):return dict(mean_s_per_source=statistics.mean(r['average_clear_time_s'] for r in a),movement_s_per_source=statistics.mean(r['distance_m']/5/r['source_count'] for r in a),nonmovement_s_per_source=statistics.mean((r['total_virtual_time_s']-r['distance_m']/5)/r['source_count'] for r in a),requests=sum(r['requests'] for r in a),clear_failures=sum(r['clear_failures'] for r in a),max_runtime_s=max(r['program_runtime_s'] for r in a),mean_runtime_s=statistics.mean(r['program_runtime_s'] for r in a))
 cluster=collections.defaultdict(list)
 for r,delta in zip(z,d):cluster[(r['exposure_suite'],r['seed_cluster'])].append(delta)
 strat={suite:[statistics.mean(v) for (s,k),v in cluster.items() if s==suite] for suite in ('v1','previous_final')}
 rng=random.Random(96212991);means=[]
 for _ in range(2000):means.append(statistics.mean(statistics.mean(rng.choices(v,k=len(v))) for v in strat.values()))
 means.sort();groups=[]
 for g in sorted({r['group'] for r in z}):
  part=[r for r in z if r['group']==g];groups.append(dict(group=g,cases=len(part),mean_s_per_source=statistics.mean(r['average_clear_time_s'] for r in part),delta_s_per_source=statistics.mean(r['average_clear_time_s']-idx[r['case_id']]['average_clear_time_s'] for r in part)))
 worst=max(zip(z,d),key=lambda t:t[1]);out['modes'].append(dict(mode=m,cases=len(z),source_count=sum(r['source_count'] for r in z),cleared_count=sum(r['cleared_count'] for r in z),valid=sum(valid(r) for r in z),faster=sum(v<-1e-8 for v in d),same=sum(abs(v)<=1e-8 for v in d),slower=sum(v>1e-8 for v in d),baseline=costs(b),candidate=costs(z),paired_delta_s_per_source=statistics.mean(d),stratified_seed_cluster_bootstrap_95=[means[50],means[1949]],bootstrap_note='Descriptive interval on exposed selected cases; not a fresh validation or an inference guarantee after selection.',worst_regression_case=worst[0]['case_id'],worst_regression_s_per_source=worst[1],groups=groups))
(HERE/'results'/f'{label}_audit.json').write_text(json.dumps(out,indent=2));print(json.dumps([{k:v for k,v in r.items() if k not in ('groups','bootstrap_note')} for r in out['modes']],indent=2))
