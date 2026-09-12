"""Paired complete-row summaries with explicit failure and tail retention."""
import math,statistics

def compare(base,candidate):
 a={r['case_id']:r for r in base};b={r['case_id']:r for r in candidate};assert len(a)==len(base) and len(b)==len(candidate) and set(a)==set(b)
 results=[]
 for mode in sorted({r['mode'] for r in base}):
  groups=['ALL']+sorted({r['group'] for r in base if r['mode']==mode})
  for group in groups:
   ids=[cid for cid,r in a.items() if r['mode']==mode and (group=='ALL' or r['group']==group)]
   assert all(a[c]['source_count']==b[c]['source_count'] for c in ids)
   ok=all(a[c]['complete'] and b[c]['complete'] for c in ids)
   row=dict(mode=mode,group=group,worlds=len(ids),sources=sum(a[c]['source_count'] for c in ids),baseline_complete=sum(a[c]['complete'] for c in ids),candidate_complete=sum(b[c]['complete'] for c in ids),valid_comparison=ok)
   if ok:
    av=[a[c]['average_clear_time_s'] for c in ids];bv=[b[c]['average_clear_time_s'] for c in ids];d=[y-x for x,y in zip(av,bv)]
    mean_a,mean_b=statistics.mean(av),statistics.mean(bv);worst=max(range(len(ids)),key=lambda i:d[i])
    row.update(baseline_mean=mean_a,candidate_mean=mean_b,delta_seconds_per_source=mean_b-mean_a,reduction_percent=100*(mean_a-mean_b)/mean_a,faster=sum(v<0 for v in d),same=sum(v==0 for v in d),slower=sum(v>0 for v in d),p95=sorted(bv)[math.ceil(.95*len(bv))-1],worst=max(bv),worst_regression_seconds_per_source=d[worst],worst_regression_case=ids[worst],program_runtime_median_s=statistics.median(b[c]['program_runtime_s'] for c in ids),program_runtime_p95_s=sorted(b[c]['program_runtime_s'] for c in ids)[math.ceil(.95*len(ids))-1])
   else:row['failed_case_ids']=[c for c in ids if not a[c]['complete'] or not b[c]['complete']]
   results.append(row)
 return results
