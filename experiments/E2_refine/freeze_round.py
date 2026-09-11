from pathlib import Path
import json,argparse,hashlib,statistics
P=Path(__file__).resolve().parent;R=P.parents[1]
def load(p):return json.loads(Path(p).read_text())
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
a=argparse.ArgumentParser();a.add_argument('candidate');a.add_argument('round');a=a.parse_args();name=a.candidate
summary=load(P/'results'/f'{name}_exposed/summary.json');assert summary['all_complete']
combined=[r for r in summary['comparisons_to_S1'] if r['suite']=='combined' and r['group']=='ALL']
prev=[r for r in summary['comparisons_to_previous'] if r['suite']=='combined' and r['group']=='ALL']
best=dict(current=name,candidate=f'experiments/E2_refine/snapshots/{name}.py',sha256=summary['candidate_sha256'],deployment_dependencies={},q3_mean_s_per_source=combined[0]['candidate_mean_s_per_source'],q4_mean_s_per_source=combined[1]['candidate_mean_s_per_source'],all_complete=True,result_path=f'experiments/E2_refine/results/{name}_exposed',data_role='4800 exposed local regression',comparisons_to_S1=combined,comparisons_to_previous=prev)
save(P/'best.json',best)
records=[]
for p in sorted((P/'results').glob('*/summary.json')):
 j=load(p)
 if 'comparisons_to_S1' in j and 'new_runs' in j:count=j['new_runs'];role='exposed previous_final after exact-hash v1 reuse'
 elif 'runs' in j:count=j['runs'];role=j['suite']+' exposed regression'
 else:continue
 records.append(dict(path=str(p.relative_to(P)),actual_runs=count,role=role))
for p in sorted((P/'results').glob('*/budget.json')):
 j=load(p);records.append(dict(path=str(p.relative_to(P)),actual_runs=j['actual_runs'],role=j['data_role']))
actual=sum(r['actual_runs'] for r in records);seed=load(P/'used_seeds.json');unique=sum(b['cases'] for b in seed['batches'])
save(P/'execution_budget.json',dict(actual_strategy_executions=actual,distinct_new_development_cases=unique,reused_case_executions=actual-unique,rounds=records,note='Quick is a full subset; v1 reuse and historical caches are not execution. No fresh final holdout.'))
rows=load(P/'results'/f'{name}_exposed/case_metrics.json');base=load(R/'experiments/20260911_stage4/baseline/expected_rows.json');bi={r['case_id']:r for r in base};reg=[]
for r in rows:
 b=bi[r['case_id']];d=r['average_clear_time_s']-b['average_clear_time_s']
 if d>1e-8:reg.append(dict(case_id=r['case_id'],mode=r['mode'],group=r['group'],delta_s_per_source=d))
reg.sort(key=lambda r:r['delta_s_per_source'],reverse=True);save(P/'results'/f'{name}_regressions.json',reg)
path=load(P/'optimization_path.json');path['current']=name
for n,status in [('r2_here','rejected_development_quick'),('r2_one_round','accepted_exposed_best')]:
 if n in [x['id'] for x in path['nodes']]:continue
 prov=load(P/'snapshots'/f'{n}.provenance.json');path['nodes'].append(dict(id=n,status=status,candidate=prov['candidate'],sha256=prov['sha256'],q4_config=prov['q4_config'],parents=['r1_station_only'],evidence=[str(p.relative_to(R)) for p in sorted((P/'results').glob(n+'_*')) if p.is_dir()]));path['edges'].append(dict(from_node='r1_station_only',to=n,relation='source_service_unit_contrast'))
save(P/'optimization_path.json',path)
q4=combined[1];pv=prev[1]
if a.round=='R2':
 with (P/'optimization_path.md').open('a') as f:f.write(f'\n\nR2 tested two source-service units. Same-location certified clear had no development benefit (465.060460 vs R1 465.036237); rejected. One persistent original service-loop round then global replanning gave {q4["candidate_mean_s_per_source"]:.12f} on4800 exposed cases, allcomplete, Q3 unchanged. OwnR1 decrease {abs(pv["delta_s_per_source"]):.12f} s/source. Both distinct controls retained.\n')
 with (P/'report.md').open('a') as f:f.write(f'''\n\n## R2 accepted: bounded source-service round\n\nCurrent best is `{best['candidate']}`, SHA256 `{best['sha256']}`; no deployment dependency. All4800 exposed cases completed; each question cleared30970/30970 sources. Q3 remains{best['q3_mean_s_per_source']:.12f}, Q4{best['q4_mean_s_per_source']:.12f} seconds/source: decrease{abs(q4['delta_s_per_source']):.12f} ({100*q4['reduction_fraction']:.6f}%) from fixedS1, and{abs(pv['delta_s_per_source']):.12f} ({100*pv['reduction_fraction']:.6f}%) from ownR1. Against ownR1: {pv['faster']} faster/{pv['equal']} equal/{pv['slower']} slowerQ4 cases. The largest fixedS1 regression is{reg[0]['delta_s_per_source']:.9f}; all regressions are retained in results/{name}_regressions.json and per-scenario comparisons in the exposed summary.\n\nThe original localize loop becomes a single service round followed by global replanning. Each channel retains its iteration count, so revisiting a channel cannot reset the9-round finite optical fallback. The original within-round measurement/clear/recovery actions, complete discovery route, and exit certificate remain. This changes the planning unit, not the candidate measurement points. One round may contain a paid failed-clear measurement or recovery sequence; it is not falsely counted as one API call.\n\nThe96 new mixedQ4 development cases (seeds45000096..45000191) give R1=465.036236679248, same-location certified clear=465.060459519993 (rejected), one-round=458.391012028693; allcomplete. One-round moves333.764794269518 seconds/source versus R1 340.528650094121, with nonmovement124.626217759175 versus124.507586585127. Thus this round's observed saving is primarily movement. Rules and bothquick120 passed; only the useful one-round candidate ranfull2400+oldfinal2400. Cumulative actual strategy executions={actual}, unique new development cases={unique}; all other cases are exposed or reused. No official or new final holdout.\n\nResearch continues with independent failed-clear geometry and certified optical-cell removal contrasts. Root handles empirical fusion with E1; E2 does not claim untested combination gains.\n''')
(P/'resume.md').write_text(f'''# E2 continuation after {a.round}\n\nOnly write experiments/E2_refine in {R}; branch experiments/20260911-stage4/e2_refine. Use bundledPython3.12. Current frozen best{name}, SHA{best['sha256']}; full+oldfinal4800 allcomplete, Q3={best['q3_mean_s_per_source']}, Q4={best['q4_mean_s_per_source']}. Candidate is a self-contained file. Need commit/push this R2 batch now, then continueR3 failedclear geometry/cell pruning. Old R1de3d660 already rootpushed/merged. R2 full/exposed execution finished; do not rerun. Next seed{seed['next_seed']}; currentbudget{actual} executions/{unique} distinct new cases.\n\nRoot commonC1 priorR2=464.925920209869Q4, root now knowsR2 and will empirically combine with E1 route. E1 studies service-block route entry cost/joint clearing, E3 broader literature/methods. R2 one-round ServiceDirectional(CostDirectional) localize override retains9-round per-channel persistent progress; service_component.py contains exact original loop body extraction. same_hereFalse for winner, separate here variant failed development. Continue until explored hypotheses saturate; no fixed first-round stop/no extra holdout.\n''')
print(json.dumps(best));print(actual,unique)
