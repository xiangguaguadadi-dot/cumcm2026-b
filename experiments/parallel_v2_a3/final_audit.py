"""Recompute paired task metrics and distinct execution counts from saved rows."""
import hashlib,json,math,statistics
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def good(r):return r['complete'] and r['exit_reason']=='user_exit' and not r['error'] and r['cleared_count']==r['source_count']>0
cases=read(ROOT/'experiments/20260911_stage4/exposed_cases.json');ids={r['case_id']:r for r in cases}
provenance=read(HERE/'comparison_start_provenance.json')
assert sha(HERE/'comparison_start_rows.json')==provenance['combined_sha256']
base={r['case_id']:r for r in read(HERE/'comparison_start_rows.json')}
assert len(base)==len(ids)==4800 and base.keys()==ids.keys()
audits={}
for name in ['r3_guard','b1_safe','b2_safe','b4_safe']:
    path=HERE/f'results/{name}_exposed/case_metrics.json';rows=read(path);cand={r['case_id']:r for r in rows}
    assert len(rows)==len(cand)==4800 and cand.keys()==ids.keys()
    for variant,mapping in [('candidate',cand),('baseline',base)]:
        for cid,r in mapping.items():
            c=ids[cid];assert good(r)
            assert r['source_count']==len(c['sources']) and r['mode']==c['mode'] and r['group']==c['group']
            assert math.isclose(r['average_clear_time_s'],r['total_virtual_time_s']/r['cleared_count'],abs_tol=1e-9)
    groups=[]
    for mode in [3,4]:
        for suite in ['combined','v1','previous_final']:
            for group in ['ALL',*sorted({r['group'] for r in cases})]:
                keys=[cid for cid,c in ids.items() if c['mode']==mode and (suite=='combined' or c['exposure_suite']==suite) and (group=='ALL' or c['group']==group)]
                aa=[cand[k] for k in keys];bb=[base[k] for k in keys]
                av=[r['average_clear_time_s'] for r in aa];bv=[r['average_clear_time_s'] for r in bb];delta=[a-b for a,b in zip(av,bv)]
                groups.append(dict(mode=mode,suite=suite,group=group,cases=len(keys),source_count=sum(r['source_count'] for r in aa),all_complete=True,
                    candidate_mean=statistics.mean(av),baseline_mean=statistics.mean(bv),delta_mean=statistics.mean(delta),
                    improvement_pct=-100*statistics.mean(delta)/statistics.mean(bv),faster=sum(d<-1e-8 for d in delta),equal=sum(abs(d)<=1e-8 for d in delta),slower=sum(d>1e-8 for d in delta),
                    worst_regression=max(delta),best_improvement=min(delta),max_candidate_s_per_source=max(av),
                    requests=sum(r['requests'] for r in aa),failed_clears=sum(r['clear_failures'] for r in aa)))
    audits[name]=dict(candidate_sha256=sha(HERE/f'snapshots/{name}.py'),rows_sha256=sha(path),compared_ids=4800,all_ids_unique_and_aligned=True,formula_errors=0,groups=groups)
(HERE/'results/final_paired_audit.json').write_text(json.dumps(audits,indent=2))

training=[]
for d in sorted((HERE/'results').glob('*_training')):
    if not (d/'model.json').exists():continue
    episodes=read(d/'episodes.json');samples=read(d/'samples.json');model=read(d/'model.json');reg=read(d/'registry.json')
    assert len(episodes)==len(reg) and all(r['complete'] for r in episodes)
    training.append(dict(round=d.name.split('_')[0],fit_worlds=model['fit_worlds'],calibration_worlds=model['calibration_worlds'],
        completed_rollin_episodes=len(episodes),fit_samples=model['fit_samples'],calibration_samples=model['calibration_samples'],
        counterfactual_branches=sum(len(r['branch_results']) for r in samples),branch_kind='single clear' if d.name=='r2_training' else 'whole-task continuation' if d.name=='r6_training' else 'target-source completion tail',
        actual_requests=sum(r['actual_requests'] for r in episodes),counterfactual_requests=sum(r['counterfactual_requests'] for r in episodes),
        wall_s=model['wall_s'],registry_sha256=sha(d/'registry.json')))
evaluations=[]
for p in sorted((HERE/'results').glob('*/summary.json')):
    d=p.parent;o=read(p)
    if d.name=='b1_safe_quick':
        evaluations.append(dict(output=d.name,stage='runner startup failure',completed_policy_episodes=0,worker_startup_failures=120,reason='Python3.9 cannot import frozen Python>=3.10 environment; all failures retained.'))
        continue
    if d.name.endswith('_development'):
        rows=read(d/'case_metrics.json');count=sum(len(v) for v in rows.values());assert all(good(r) for v in rows.values() for r in v)
        requests=sum(r['requests'] for v in rows.values() for r in v)
        evaluations.append(dict(output=d.name,stage='reused 96-world development',completed_policy_episodes=count,requests=requests,wall_s=o['wall_s']))
    elif d.name.endswith('_exposed'):
        assert o['all_complete'];rows=read(d/'case_metrics.json');new=[r for r in rows if r['exposure_suite']=='previous_final']
        assert len(new)==o['new_runs'];evaluations.append(dict(output=d.name,stage='old exposed second batch; full-v1 rows reused',completed_policy_episodes=o['new_runs'],requests=sum(r['requests'] for r in new),wall_s=o['wall_seconds_new_runs']))
    elif o.get('suite') in ['quick','full']:
        assert o['all_complete'];rows=[r for r in read(d/'case_metrics.json') if r['variant']=='candidate'];assert len(rows)==o['runs']
        evaluations.append(dict(output=d.name,stage=o['suite'],completed_policy_episodes=o['runs'],requests=sum(r['requests'] for r in rows),wall_s=o['wall_seconds']))
manifest=read(HERE/'all_new_worlds_manifest.json')
cost=dict(training=training,evaluations=evaluations,distinct_new_training_worlds=manifest['training_worlds'],distinct_development_worlds=manifest['development_worlds'],
    completed_training_rollins=sum(x['completed_rollin_episodes'] for x in training),counterfactual_branches=sum(x['counterfactual_branches'] for x in training),
    completed_evaluation_episodes=sum(x['completed_policy_episodes'] for x in evaluations),
    training_requests=sum(x['actual_requests']+x['counterfactual_requests'] for x in training),evaluation_requests=sum(x.get('requests',0) for x in evaluations),
    failed_preflight=dict(directory='results/r6_preflight_failed',accepted_training_labels=0,complete_execution_and_request_ledger_available=False,
        note='One teacher rollin and six continuation branches are inferred from rejected G0 control flow and identical first-world selected states; no raw per-action cost ledger was saved. Excluded from exact counted totals.'),
    caveats=['A branch starts from a cloned prefix and is not an independent world or a full enter-to-exit deployment.',
        'Quick cases are part of full; repeated 96-world development is selection exposure, never new holdout.',
        'Exposed summary reuses 2400 v1 rows and executes only 2400 other cases; no double-counting.',
        'Wall times overlap on shared hardware and must not be summed as user waiting time.',
        'Frozen unit and nominal fixtures are separate from source-world deployments.'])
(HERE/'execution_ledger.json').write_text(json.dumps(cost,indent=2))
print(json.dumps({k:v for k,v in cost.items() if not isinstance(v,(dict,list))},indent=2))
for n,a in audits.items():
    print(n,[g for g in a['groups'] if g['mode']==4 and g['suite']=='combined' and g['group']=='ALL'])
