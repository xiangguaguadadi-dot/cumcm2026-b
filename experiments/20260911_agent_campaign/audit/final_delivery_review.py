"""Independent read-only arithmetic review of final saved rows; no solver/environment imports."""
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
import random
import re
import statistics

HERE=Path(__file__).resolve().parent
CAMPAIGN=HERE.parent
ROOT=CAMPAIGN.parent.parent
FINAL=CAMPAIGN/'final_validation'
observed={}

def text(p):
    raw=p.read_bytes();observed[str(p)]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
    return raw.decode('utf-8-sig')
def read(p):return json.loads(text(p))
def close(a,b):return abs(a-b)<=1e-8
def avg(values):return statistics.mean(values)

registry=read(CAMPAIGN/'candidate_registry.json');manifest=read(FINAL/'manifest.json')
execution=read(FINAL/'execution.json');comparison=read(FINAL/'comparison.json')
cases=read(FINAL/'cases.json');case_index={r['case_id']:r for r in cases}
by_comparison={Path(r['path']).parent.name:r for r in comparison['candidates']}
seeds=manifest['seeds'];labels=['baseline']+[r['label'] for r in registry['candidates']]
baseline=read(FINAL/'baseline/case_metrics.json');base_index={r['case_id']:r for r in baseline}
checks={
    'ten_unique_registered_candidates':len(registry['candidates'])==len(set(labels))-1==10,
    'eleven_expected_directories':set(p.parent.name for p in FINAL.glob('*/case_metrics.json'))==set(labels),
    '2400_unique_case_ids':len(cases)==len(case_index)==2400,
    '100_unique_seed_clusters':len(seeds)==len(set(seeds))==100,
    '24_groups_each_100':len(Counter((r['mode'],r['group']) for r in cases))==24 and set(Counter((r['mode'],r['group']) for r in cases).values())=={100},
    'each_mode_seed_has_12_groups':set(Counter((r['mode'],r['seed']) for r in cases).values())=={12},
    '26400_declared_runs':execution['total_episode_executions']==26400 and execution['processes']==11,
    'new_seeds_disjoint_v1':not set(seeds)&set(range(5000,5100)),
    'registration_precedes_generation':registry['registered_at_utc']<manifest['generation_time_utc']<execution['started_utc'],
    'case_hash_matches':observed[str(FINAL/'cases.json')]['sha256']==manifest['cases_sha256']==execution['cases_sha256'],
    'comparison_has_exact_candidates':set(by_comparison)==set(labels)-{'baseline'},
}
versions=[]
for label in labels:
    folder=FINAL/label;rows=read(folder/'case_metrics.json');summary=read(folder/'summary.json')
    raw_csv=text(folder/'case_metrics.csv')
    csv_rows=list(csv.DictReader(raw_csv.splitlines()))
    complete=all(r['complete'] and r['cleared_count']==r['source_count'] and r['cleared_fraction']==1 and not r['error'] and r['exit_reason']=='user_exit' and r['coverage_certificate'] for r in rows)
    csv_ok=len(csv_rows)==len(rows) and all(all(c[k]==('' if r[k] is None else str(r[k])) for k in c) for c,r in zip(csv_rows,rows))
    pair_ok=len(rows)==len({r['case_id'] for r in rows})==2400 and set(r['case_id'] for r in rows)==set(case_index)
    meta_ok=all(r['source_count']==len(case_index[r['case_id']]['sources']) and r['mode']==case_index[r['case_id']]['mode'] and r['group']==case_index[r['case_id']]['group'] and r['seed_cluster']==case_index[r['case_id']]['seed'] for r in rows)
    formula_ok=all(close(r['average_clear_time_s'],r['total_virtual_time_s']/r['cleared_count']) and r['total_virtual_time_s']<360000 and r['program_runtime_s']<1200 for r in rows)
    version={'label':label,'rows':len(rows),'row_identity_valid':pair_ok,'case_metadata_valid':meta_ok,'all_complete_normal_no_errors_certified':complete,
             'csv_matches_json':csv_ok,'formula_and_time_limits_valid':formula_ok,'summary_runs_valid':summary['runs']==len(rows),
             'wall_seconds':summary['wall_seconds'],'modes':[],'regressing_groups':[]}
    for mode in (3,4):
        part=[r for r in rows if r['mode']==mode];means=avg(r['average_clear_time_s'] for r in part)
        diffs={r['case_id']:base_index[r['case_id']]['average_clear_time_s']-r['average_clear_time_s'] for r in part}
        groups=defaultdict(list)
        for r in part:groups[r['group']].append(r)
        summary_mode=next(m for m in summary['modes'] if m['mode']==mode)
        info={'mode':mode,'cases':len(part),'sources':sum(r['source_count'] for r in part),'complete':sum(r['complete'] for r in part),
              'mean_s_per_source':means,'paired_mean_saved_s_per_source':avg(diffs.values()),
              'wins':sum(v>1e-8 for v in diffs.values()),'ties':sum(abs(v)<=1e-8 for v in diffs.values()),'losses':sum(v<-1e-8 for v in diffs.values()),
              'worst_s_per_source':max(r['average_clear_time_s'] for r in part),'max_virtual_s':max(r['total_virtual_time_s'] for r in part),
              'max_runtime_s':max(r['program_runtime_s'] for r in part),
              'summary_matches_raw':close(means,summary_mode['mean_s_per_source']) and close(max(r['average_clear_time_s'] for r in part),summary_mode['worst_s_per_source']) and summary_mode['sources']==sum(r['source_count'] for r in part),
              'groups':[]}
        if label!='baseline':
            comp=by_comparison[label];cmp=next(m for m in comp['modes'] if m['mode']==mode)
            # Use manifest seed order, independent of comparison's grouping implementation.
            units=[avg(diffs[r['case_id']] for r in part if r['seed_cluster']==s) for s in seeds]
            rng=random.Random(110926)
            bootstrap=[]
            for trial in range(5000):
                drawn=[units[int(rng.random()*100)] for _ in range(100)]
                bootstrap.append(math.fsum(drawn)/100)
            bootstrap.sort();ci=[bootstrap[124],bootstrap[4874]]
            bm=avg(base_index[r['case_id']]['average_clear_time_s'] for r in part)
            movement=avg((base_index[r['case_id']]['distance_m']-r['distance_m'])/5/r['cleared_count'] for r in part)
            other=avg(diffs.values())-movement
            info.update(bootstrap_ci95=ci,seed_clusters=len(units),cluster_mean_equals_case_mean=close(avg(units),avg(diffs.values())),
                        ci_matches_comparison=all(close(x,y) for x,y in zip(ci,cmp['paired_saved_seed_cluster_bootstrap_95ci'])),
                        comparison_mean_matches=close(means,cmp['candidate_mean_s_per_source']) and close(bm,cmp['baseline_mean_s_per_source']) and close(avg(diffs.values()),cmp['paired_mean_saved_s_per_source']),
                        reduction_matches=close(1-means/bm,cmp['reduction_fraction']),
                        movement_saved_s_per_source=movement,other_saved_s_per_source=other,
                        decomposition_matches=close(movement,cmp['time_decomposition']['paired_movement_saved_s_per_source']) and close(other,cmp['time_decomposition']['paired_other_saved_s_per_source']))
        for group,gr in sorted(groups.items()):
            gm=avg(r['average_clear_time_s'] for r in gr);gb=avg(base_index[r['case_id']]['average_clear_time_s'] for r in gr)
            gi={'mode':mode,'group':group,'cases':len(gr),'mean_s_per_source':gm,'baseline_mean_s_per_source':gb,'saved':gb-gm,'regressed':gm>gb+1e-8}
            if label!='baseline':
                cg=next(g for g in by_comparison[label]['groups'] if g['mode']==mode and g['group']==group)
                gi['comparison_matches']=cg['comparison_valid'] and cg['cases']==len(gr) and close(gm,cg['candidate_mean_s_per_source']) and close(gb,cg['baseline_mean_s_per_source']) and close(1-gm/gb,cg['reduction_fraction'])
            info['groups'].append(gi)
            if gi['regressed']:version['regressing_groups'].append(gi)
        version['modes'].append(info)
    versions.append(version)

checks['all_saved_rows_checks']=all(v[k] for v in versions for k in ['row_identity_valid','case_metadata_valid','all_complete_normal_no_errors_certified','csv_matches_json','formula_and_time_limits_valid','summary_runs_valid'])
checks['all_means_match_summaries']=all(m['summary_matches_raw'] for v in versions for m in v['modes'])
checks['all20_CIs_match']=all(m['ci_matches_comparison'] for v in versions if v['label']!='baseline' for m in v['modes'])
checks['all20_mode_comparisons_match']=all(m[k] for v in versions if v['label']!='baseline' for m in v['modes'] for k in ['cluster_mean_equals_case_mean','comparison_mean_matches','reduction_matches','decomposition_matches'])
checks['all240_group_comparisons_match']=all(g['comparison_matches'] for v in versions if v['label']!='baseline' for m in v['modes'] for g in m['groups'])

a6_rows=read(FINAL/'A6_learning_R7/case_metrics.json')
nonruntime=['cleared_count','source_count','cleared_fraction','average_clear_time_s','total_virtual_time_s','complete','exit_reason','error','coverage_certificate','requests','distance_m','clear_failures']
a6_differences=[{'case_id':r['case_id'],'mode':r['mode'],'seed':r['seed_cluster'],'group':r['group'],
                 'changed_fields':{k:{'candidate':r[k],'baseline':base_index[r['case_id']][k]} for k in nonruntime if r[k]!=base_index[r['case_id']][k]}}
                for r in a6_rows if r['mode']==3 and any(r[k]!=base_index[r['case_id']][k] for k in nonruntime)]
checks['a6_exactly_one_q3_metric_difference']=len(a6_differences)==1 and a6_differences[0]['seed']==1433564276 and a6_differences[0]['group']=='fixed_positive_bias'

# Explicitly check rendered numeric rows in the current main report.
report=text(CAMPAIGN/'REPORT.md');report_lines=report.splitlines();report_checks=[]
for v in versions:
    if v['label']=='baseline':continue
    line=next((s for s in report_lines if s.startswith('|'+v['label']) and '2400/2400' in s),None)
    q3,q4=v['modes']
    if line:
        report_checks.append({'label':v['label'],'section':'means','ok':f"{q3['mean_s_per_source']:.5f}" in line and f"{q4['mean_s_per_source']:.5f}" in line and '2400/2400' in line})
    else:report_checks.append({'label':v['label'],'section':'means','ok':False,'reason':'expected mean row not found'})
    ci_line=next((s for s in report_lines if s.startswith('|'+v['label']+'|') and '[' in s),None)
    expected=[f"{m['paired_mean_saved_s_per_source']:.4f} [{m['bootstrap_ci95'][0]:.4f}, {m['bootstrap_ci95'][1]:.4f}]" for m in v['modes']]
    report_checks.append({'label':v['label'],'section':'CI','ok':ci_line is not None and all(s in ci_line for s in expected)})
    group_line=next((s for s in report_lines if s.startswith('- **'+v['label']+'**')),None)
    report_checks.append({'label':v['label'],'section':'regressing_groups','ok':group_line is not None and all(g['group'] in group_line and f"{(-g['saved']):.4f}" in group_line for g in v['regressing_groups']) and (bool(v['regressing_groups']) or '没有场景均值退步' in group_line)})
checks['report_numerical_tables_match']=all(r['ok'] for r in report_checks)
old=read(HERE/'delivery_independent.json')
old_full=sum(r['regression']['full_candidate_executions'] for r in old['routes'].values())+old['A2_budget_supplement']['budget']['candidate_full_runs']
old_quick=sum(r['regression']['quick_candidate_executions'] for r in old['routes'].values())+old['A2_budget_supplement']['budget']['candidate_quick_runs']
budget={'old_rounds':43,'old_full_candidate_runs':old_full,'old_quick_candidate_runs':old_quick,'old_recorded_execution_or_attempt_lower_bound':226868,
        'new_baseline_runs':2400,'new_candidate_runs':24000,'new_total_runs':sum(v['rows'] for v in versions),
        'whole_campaign_recorded_lower_bound':226868+sum(v['rows'] for v in versions),
        'unknown_extra_runs':'A2 interrupted development and unnormalized rule/geometry checks; do not invent exact total.'}
checks['budget_counts_match']=old_full==103200 and old_quick==5160 and budget['new_total_runs']==26400
checks['report_budget_text_matches']=all(s in report for s in ['43轮','103,200','5,160','26,400','28224','4968','50688','15360','5760','2592','未知次数'])

output={'created_utc':datetime.now(timezone.utc).isoformat(),'method':'Saved rows only, no environment or candidate execution; independently reconstructed paired seed bootstrap with integer draws.',
        'checks':checks,'all_machine_checks_passed':all(checks.values()),'versions':versions,'a6_q3_differences':a6_differences,
        'report_numeric_checks':report_checks,'budget':budget,'observed_files':observed}
(HERE/'final_delivery_review.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'checks':checks,'budget':budget,'a6_q3_differences':a6_differences,'report_failures':[r for r in report_checks if not r['ok']],
                  'candidate_wins_ties_losses':{v['label']:{str(m['mode']):[m['wins'],m['ties'],m['losses']] for m in v['modes']} for v in versions}},ensure_ascii=False,indent=2))
