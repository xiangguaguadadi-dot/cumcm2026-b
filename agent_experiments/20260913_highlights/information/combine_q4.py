"""Combine actually executed quick/remainder pairs; retain observer erratum."""
import hashlib,importlib.util,json,math,statistics,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('information_q4',HERE/'q4_experiment.py');M=importlib.util.module_from_spec(sp);sp.loader.exec_module(M)
def readlines(p):return [json.loads(x) for x in p.read_text().splitlines()]
def main():
    out=HERE/'q4_full';out.mkdir(exist_ok=False)
    quick=readlines(HERE/'q4_quick/executed_rows.jsonl');remaining=readlines(HERE/'q4_remaining/executed_rows.jsonl')
    correction=json.loads((HERE/'observer_correction.json').read_text());assert correction['corrected_true_source_exclusions_quick']==0
    rows=[]
    for row in quick+remaining:
        row=dict(row)
        if row['case_id']=='LOCAL-v1-q4-minimum_radius-5003' and row['arm']=='off':
            assert row['true_source_exclusions']==2;row.update(original_observer_false_positives=2,true_source_exclusions=0,observer_erratum='../../observer_correction.json')
        rows.append(row)
    assert len(rows)==4800 and len({(r['case_id'],r['arm']) for r in rows})==4800
    summary=M.summarize(rows)
    events=readlines(HERE/'q4_quick/same_state_events.jsonl')+readlines(HERE/'q4_remaining/same_state_events.jsonl')
    shrinks=[e for e in events if e['area_removed_m2']>1e-6]
    affected={e['case_id'] for e in shrinks}
    summary['same_state']=dict(eligible_updates=len(events),effective_shrinks=len(shrinks),effective_update_fraction=len(shrinks)/len(events),
        affected_cases=len(affected),mean_fractional_shrink_all_updates=statistics.mean(e['fractional_shrink'] for e in events),
        mean_fractional_shrink_effective_updates=statistics.mean(e['fractional_shrink'] for e in shrinks),
        max_fractional_shrink=max(e['fractional_shrink'] for e in events),
        true_source_exclusions=sum(not e['source_inside_after'] for e in events),
        label='Copy-only on/off geometric comparison on the actual off-arm histories; repeated events are not independent cases')
    summary['observer_erratum']=dict(original_quick_false_positives=2,corrected_true_exclusions=0,confirmation_actual_runs=2,reference='../observer_correction.json')
    summary['actual_execution_accounting']=dict(quick=120,remaining=4680,observer_confirmation=2,total=4802,rows_compared=4800,
        note='Quick and remaining sets are disjoint; confirmation duplicates are excluded from performance statistics')
    summary['label']='Current B3 Q4 same-world pair: only convex_no_signal toggled; 2400 historical exposed local cases, not official/blind'
    stored=json.loads((M.ROOT/'最佳方法/实验记录/B_improved/results/B3_exposed/case_metrics.json').read_text())
    indexed={r['case_id']:r for r in stored if r['mode']==4 and r.get('variant')=='candidate'}
    if not indexed:indexed={r['case_id']:r for r in stored if r['mode']==4}
    mismatches=[]
    for row in rows:
        if row['arm']!='on':continue
        old=indexed[row['case_id']]
        if abs(row['total_virtual_time_s']-old['total_virtual_time_s'])>1e-7 or row['cleared_count']!=old['cleared_count']:
            mismatches.append(dict(case_id=row['case_id'],new=row['total_virtual_time_s'],stored=old['total_virtual_time_s']))
    summary['on_arm_stored_B3_reproduction']=dict(compared_cases=2400,mismatches=mismatches)
    M.write(out/'summary.json',summary);M.write(out/'case_metrics.json',rows)
    M.write(out/'source_manifest.json',{str(p.relative_to(HERE)):M.sha(p) for p in [HERE/'q4_quick/executed_rows.jsonl',HERE/'q4_remaining/executed_rows.jsonl',HERE/'observer_correction.json',Path(__file__)]})
    print(json.dumps({k:v for k,v in summary.items() if k!='groups'},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
