"""Read-only artifact audit. Never imports/runs a candidate or a simulator."""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone
import ast
import difflib
import hashlib
import json
import math
import re
import statistics
import subprocess

ROOT = Path('/Users/t/ai project/数学建模2026/代码')
TREES = ROOT.parent / 'agent_experiments/20260911'
OUT = ROOT / 'experiments/20260911_agent_campaign/audit'
ROUTES = ['A1_space', 'A3_coordination', 'A4_directional', 'A5_learning', 'A6_learning']
observed_files = {}

def read(path):
    data = path.read_bytes()
    observed_files[str(path)] = dict(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
    return data.decode()

def js(path): return json.loads(read(path))
def sha(path):
    read(path)
    return observed_files[str(path)]['sha256']
def jl(path): return [json.loads(s) for s in read(path).splitlines() if s.strip()]
def canonical(x): return json.dumps(x, sort_keys=True, separators=(',', ':'))
def mean(x): return statistics.mean(x)
def git(tree, *args):
    return subprocess.check_output(['git', '-C', str(tree), *args])

result = dict(created_utc=datetime.now(timezone.utc).isoformat(), scope=ROUTES,
              candidate_executions_by_this_audit=0, simulator_calls_by_this_audit=0,
              definitions={'executions':'Count raw completed episode records, including repeated cases and input comparators.',
                           'unique_cases':'Within-route identifiers or serialized case contents; never sum as independent statistical samples.',
                           'unknown':'Rule/nominal checks, abandoned or unlogged processes, and research/edit wall clock are outside the episode ledger.'},
              routes={})
frozen_manifest = js(ROOT/'evaluation/manifest_v1.json')
frozen_cases = js(ROOT/'evaluation/cases_v1.json')
frozen_case_index = {r['case_id']: r for r in frozen_cases}
frozen_cache_index = {r['case_id']: r for r in js(ROOT/'evaluation/baseline_metrics_v1.json')['rows']}

for route in ROUTES:
    tree = TREES/route
    exp = tree/'experiments'/route
    best = js(exp/'best.json')
    snap = best.get('snapshot') or best.get('solver_path') or best.get('best_solver_relative') or best['solver_relative_path']
    expected_sha = best.get('solver_sha256') or best['sha256']
    full = best.get('full_result_path') or best.get('full_results_path') or best.get('full_results') or best['full_results_relative']
    commit = best['code_commit']
    committed_path = best.get('code_path_at_commit', snap)
    committed = git(tree, 'show', f'{commit}:{committed_path}')
    info = dict(best_round=best.get('best_round', best.get('round')), snapshot=snap, full_result_path=full,
                solver_sha256=sha(tree/snap), declared_sha256=expected_sha, code_commit=commit,
                code_path_at_commit=committed_path, git_object_sha256=hashlib.sha256(committed).hexdigest(),
                worktree_solver_sha256=sha(tree/'solver.py'),
                manifest_sha256=sha(tree/'evaluation/manifest_v1.json'),
                frozen_files={p:sha(tree/p)==s for p,s in frozen_manifest['sha256'].items()})
    info['identity_checks_passed'] = info['solver_sha256']==expected_sha==info['git_object_sha256']==info['worktree_solver_sha256']
    batches = []
    case_ids = defaultdict(set)
    for summary_path in sorted(tree.rglob('summary.json')):
        if summary_path.parent.name in ('v1_full', 'v1_quick'): continue
        summary = js(summary_path)
        if summary.get('suite') not in ('full','quick') or not (summary_path.parent/'case_metrics.json').exists(): continue
        rows = js(summary_path.parent/'case_metrics.json')
        cand = [r for r in rows if r['variant']=='candidate']
        base = [r for r in rows if r['variant']=='frozen_baseline']
        ids = {r['case_id'] for r in cand}
        case_ids[summary['suite']].update(ids)
        cm = {r['case_id']:r for r in cand}; bm = {r['case_id']:r for r in base}
        complete = all(r['complete'] and r['cleared_count']==r['source_count'] and r['exit_reason']=='user_exit' and not r['error'] and r['coverage_certificate'] for r in cand)
        round_number=int(re.search(r'r(\d+)_(?:full|quick)$',summary_path.parent.name).group(1))
        round_snapshot = (exp/'snapshots'/f'solver_r{round_number}.py' if route=='A1_space' else
                          exp/'candidates'/f'r{round_number}_solver.py' if route=='A4_directional' else
                          exp/'snapshots'/f'r{round_number}_solver.py')
        expected_ids={r['case_id'] for r in frozen_cases if summary['suite']=='full' or r['quick']}
        item = dict(path=str(summary_path.parent.relative_to(tree)), suite=summary['suite'],
                    round=round_number,round_snapshot_matches=sha(round_snapshot)==summary['candidate_sha256'],
                    candidate_sha256=summary['candidate_sha256'], candidate_rows=len(cand),
                    cached_baseline_rows=len(base) if summary['baseline_cached'] else 0,
                    executed_baseline_rows=0 if summary['baseline_cached'] else len(base),
                    paired_unique_ids=len(ids), unique_candidate_ids=len(cand)==len(ids),
                    baseline_id_match=ids==set(bm), all_complete=complete,
                    frozen_case_id_match=ids==expected_ids,
                    source_denominator_matches_frozen=all(r['source_count']==len(frozen_case_index[r['case_id']]['sources']) for r in cand),
                    average_formula_matches=all(abs(r['average_clear_time_s']-r['total_virtual_time_s']/r['cleared_count'])<1e-9 for r in cand),
                    cached_baseline_bytes_match_rows=all(r==frozen_cache_index[r['case_id']] for r in base),
                    summary_runs_matches=len(cand)+(0 if summary['baseline_cached'] else len(base))==summary['runs'],
                    runs_field=summary['runs'], wall_seconds=summary['wall_seconds'],
                    means={str(m):mean(r['average_clear_time_s'] for r in cand if r['mode']==m) for m in (3,4)},
                    best_snapshot_match=summary['candidate_sha256']==expected_sha if str(summary_path.parent.relative_to(tree))==full else None)
        batches.append(item)
    info['regression'] = dict(batches=batches, full_candidate_executions=sum(x['candidate_rows'] for x in batches if x['suite']=='full'),
                             quick_candidate_executions=sum(x['candidate_rows'] for x in batches if x['suite']=='quick'),
                             cached_baseline_rows_stored=sum(x['cached_baseline_rows'] for x in batches),
                             rerun_baseline_executions=sum(x['executed_baseline_rows'] for x in batches),
                             distinct_full_case_ids=len(case_ids['full']), distinct_quick_case_ids=len(case_ids['quick']),
                             quick_is_subset_of_full=case_ids['quick']<=case_ids['full'],
                             distinct_full_candidate_hashes=len({x['candidate_sha256'] for x in batches if x['suite']=='full'}),
                             full_wall_seconds=sum(x['wall_seconds'] for x in batches if x['suite']=='full'),
                             quick_wall_seconds=sum(x['wall_seconds'] for x in batches if x['suite']=='quick'))
    result['routes'][route] = info

# A1: every development/validation JSON contains actual rows; excluded mixture stays separate.
exp=TREES/'A1_space/experiments/A1_space'
batches=[]; unique=set()
for p in sorted(exp.glob('*.json')):
    if not any(t in p.name for t in ('development','validation')):continue
    d=js(p)
    if 'rows' not in d:continue
    rows=d['rows']; invalid='invalid_mixture' in p.name
    ids={(r['mode'],r['scenario'],r['seed']) for r in rows}
    if not invalid:unique.update(ids)
    batches.append(dict(file=str(p.relative_to(exp)), executions=len(rows), unique_ids=len(ids),
                        input_original_baseline=p.name.startswith('baseline'), invalid_mixture=invalid,
                        stage='development' if 'development' in p.name else 'validation',
                        seed_start=d['seed_start'], all_complete=all(r['complete'] and not r['error'] for r in rows), wall_seconds=d['wall_seconds']))
valid=[b for b in batches if not b['invalid_mixture']]
result['routes']['A1_space']['inner_budget']=dict(batches=batches, valid_executions=sum(b['executions'] for b in valid),
    candidate_executions=sum(b['executions'] for b in valid if not b['input_original_baseline']),
    original_baseline_executions=sum(b['executions'] for b in valid if b['input_original_baseline']),
    development_executions=sum(b['executions'] for b in valid if b['stage']=='development'),
    validation_executions=sum(b['executions'] for b in valid if b['stage']=='validation'),
    invalid_mixture_executions=sum(b['executions'] for b in batches if b['invalid_mixture']),
    unique_valid_case_ids=len(unique), unique_basis='mode/scenario/seed, valid generator; repeated IDs are not new samples',
    valid_wall_seconds=sum(b['wall_seconds'] for b in valid), weight_training=False)

# A3: raw development rows contain both a newly executed baseline and candidate.
exp=TREES/'A3_coordination/experiments/A3_coordination'; batches=[];unique=set();outside_unique=set();outside_counts=Counter()
read(exp/'dev_evaluate.py')
for p in sorted((exp/'research').glob('r*_*.json')):
    if not p.stem.endswith(('_train','_dev')):continue
    d=js(p);counts=Counter(r['variant'] for r in d['rows']);unique.update((r['mode'],r['scenario'],r['seed']) for r in d['rows'])
    outside=[r for r in d['rows'] if r['mode']==4 and r['scenario'] in ('boundary','cluster','min_radius')]
    outside_unique.update((r['mode'],r['scenario'],r['seed']) for r in outside)
    outside_counts.update(r['variant'] for r in outside)
    batches.append(dict(file=str(p.relative_to(exp)),split=p.stem.split('_')[-1],executions=len(d['rows']),variants=dict(counts),wall_seconds=d['wall_seconds'],
                        all_complete=all(r['complete'] and not r['error'] for r in d['rows'])))
result['routes']['A3_coordination']['inner_budget']=dict(batches=batches, candidate_executions=sum(b['variants']['candidate'] for b in batches),
    original_baseline_executions=sum(b['variants']['baseline'] for b in batches),
    train_candidate_executions=sum(b['variants']['candidate'] for b in batches if b['split']=='train'),
    dev_candidate_executions=sum(b['variants']['candidate'] for b in batches if b['split']=='dev'),
    unique_case_ids=len(unique),unique_basis='mode/scenario/seed; all three rounds reuse the same 120 identities',weight_training=False)
result['routes']['A3_coordination']['inner_budget']['out_of_problem_mixture']=dict(
    cause='dev_evaluate calls frozen make_case unchanged; Q4 boundary/cluster/min_radius assigns a direction to every source.',
    variant_executions=dict(outside_counts),total_executions=sum(outside_counts.values()),unique_case_ids=len(outside_unique),
    source_evidence='local_env.py lines 23-45 and experiments/A3_coordination/dev_evaluate.py lines 21-23',
    classification='Out-of-problem all-directional stress cases; count actual cost, do not call them valid Q4 mixed-source development evidence.',
    full_regression_affected=False)

# A4: each variant is a policy evaluation; input comparators are explicit and not all the frozen original.
exp=TREES/'A4_directional/experiments/A4_directional';batches=[];unique=set()
for p in sorted((exp/'results').glob('r*_dev*.json')):
    d=js(p);rows=d['rows'];unique.update((r['scene'],r['noise'],r['seed']) for r in rows)
    counts=Counter(r['variant'] for r in rows)
    batches.append(dict(file=str(p.relative_to(exp)),stage='validation' if 'validation' in p.name else 'development',
                        executions=len(rows),variant_counts=dict(counts),wall_seconds=d['wall_seconds'],
                        all_complete=all(r['complete'] and not r['error'] for r in rows)))
result['routes']['A4_directional']['inner_budget']=dict(batches=batches,
    development_executions=sum(b['executions'] for b in batches if b['stage']=='development'),
    validation_executions=sum(b['executions'] for b in batches if b['stage']=='validation'),
    development_variant_evaluations=sum(len(b['variant_counts']) for b in batches if b['stage']=='development'),
    unique_case_ids=len(unique),unique_basis='scene/noise/seed; mode fixed to Q4',
    wall_seconds=sum(b['wall_seconds'] for b in batches),weight_training=False,
    comparator_note='Development includes original/input-policy comparator runs. Variant names r1/r2/r3/r5/r6 mean prior candidates, not original baseline.')

# A5: raw jsonl mixes train and development evaluations. Count actual rows, not planned population size.
exp=TREES/'A5_learning/experiments/A5_learning';batches=[];unique=set();train_unique=set();dev_unique=set()
for p in sorted((exp/'training').glob('*/attempts_m*.jsonl')):
    ds=jl(p);cnt=Counter();nc=Counter();wall=0;local_ids=set()
    for d in ds:
        cnt[d['split']]+=len(d['rows']);nc[d['split']]+=1;wall+=d['wall_s']
        ids={(r['mode'],r['seed']) for r in d['rows']};local_ids.update(ids)
        if p.parent.name!='pilot_timing':
            unique.update(ids)
            (train_unique if d['split']=='train' else dev_unique).update(ids)
    batches.append(dict(file=str(p.relative_to(exp)),round=p.parent.name,executions_by_split=dict(cnt),evaluations_by_split=dict(nc),
                        unique_ids=len(local_ids),all_complete=all(d['complete'] and all(r['complete'] and not r['error'] for r in d['rows']) for d in ds),wall_seconds=wall))
main=[b for b in batches if b['round']!='pilot_timing'];pilot=[b for b in batches if b['round']=='pilot_timing']
abl=js(exp/'ablation_r2_dev.json');abls={name:dict(executions=len(d['rows']),mean=mean(r['seconds_per_source'] for r in d['rows']),all_complete=all(r['complete'] for r in d['rows'])) for name,d in abl['variants'].items()}
result['routes']['A5_learning']['inner_budget']=dict(batches=batches,
    training_executions=sum(b['executions_by_split'].get('train',0) for b in main),
    development_executions=sum(b['executions_by_split'].get('dev',0) for b in main),
    train_dev_policy_evaluations=sum(sum(b['evaluations_by_split'].values()) for b in main),
    pilot_executions=sum(sum(b['executions_by_split'].values()) for b in pilot),
    ablation_executions=sum(d['executions'] for d in abls.values()),ablation=abls,
    unique_train_dev_case_ids=len(unique),unique_train_ids=len(train_unique),unique_dev_ids=len(dev_unique),
    train_dev_id_overlap=len(train_unique&dev_unique),unique_basis='mode/seed; serialized case generation is deterministic; pilot and ablation reuse these IDs',
    train_dev_wall_seconds=sum(b['wall_seconds'] for b in main),weight_training=True)

# A6: full rows for every train vector, shortlist evaluation, saved replay and final ablation.
exp=TREES/'A6_learning/experiments/A6_learning';batches=[];unique=set();train_unique=set();dev_unique=set();validity=[]
for folder in sorted((p for p in (exp/'training').glob('r*') if p.is_dir() and p.name[1:].isdigit()),key=lambda p:int(p.name[1:])):
    budget=js(folder/'budget.json');modes=budget.get('modes_optimized',[3,4]);cases=js(folder/'cases.json')
    rounds=[]
    for m in modes:
        ds=jl(folder/f'q{m}_attempts.jsonl');dev=js(folder/f'q{m}_development.json')
        nt=sum(len(d['training']['rows']) for d in ds);nd=sum(len(d['development']['rows']) for d in dev)
        ids_train={(m,c['seed']) for c in cases[str(m)]['train']};ids_dev={(m,c['seed']) for c in cases[str(m)]['dev']}
        train_unique.update(ids_train);dev_unique.update(ids_dev);unique.update(ids_train|ids_dev)
        for split in ['train','dev']:
            for c in cases[str(m)][split]:
                src=c['sources'];n=len(src);dirs=sum(s['direction'] is not None for s in src)
                ok=(10<=n<=16 and len({s['channel'] for s in src})==n and
                    all(1<=s['channel']<=20 and math.hypot(s['x'],s['y'])<=1800+1e-8 and 1000<=s['radius']<=1500 for s in src) and
                    (dirs==0 if m==3 else 0<dirs<n) and not 5000<=c['seed']<=5099)
                if not ok:validity.append(dict(round=folder.name,mode=m,split=split,seed=c['seed']))
        rounds.append(dict(mode=m,train_vectors=len(ds),train_executions=nt,dev_vectors=len(dev),dev_executions=nd,
                           train_seed_range=[min(x[1] for x in ids_train),max(x[1] for x in ids_train)],
                           dev_seed_range=[min(x[1] for x in ids_dev),max(x[1] for x in ids_dev)],
                           row_seed_ids_match=all({(m,r['seed']) for r in d['training']['rows']}==ids_train for d in ds) and all({(m,r['seed']) for r in d['development']['rows']}==ids_dev for d in dev),
                           all_complete=all(r['complete'] and not r['error'] for d in ds for r in d['training']['rows']) and all(r['complete'] and not r['error'] for d in dev for r in d['development']['rows'])))
    arch=exp/'snapshots'/('baseline_solver.py' if folder.name=='r1' else f'{folder.name}_training_architecture.py')
    batches.append(dict(round=folder.name,modes=rounds,train_executions=sum(x['train_executions'] for x in rounds),
                        dev_executions=sum(x['dev_executions'] for x in rounds),budget_actual=budget['actual_episodes'],
                        budget_matches_rows=budget['actual_episodes']==sum(x['train_executions']+x['dev_executions'] for x in rounds),
                        architecture_sha_matches_budget=sha(arch)==budget['solver_sha256'],wall_seconds=budget['elapsed_seconds']))
replay=exp/'reproduced/r3';rd=jl(replay/'q4_attempts.jsonl');rv=js(replay/'q4_development.json');rb=js(replay/'budget.json')
replay_count=sum(len(d['training']['rows']) for d in rd)+sum(len(d['development']['rows']) for d in rv)
def no_runtime(value):
    if isinstance(value,dict):return {k:no_runtime(v) for k,v in value.items() if k not in ('runtime_s','elapsed_seconds')}
    if isinstance(value,list):return [no_runtime(v) for v in value]
    return value
replay_train_outcomes_match=no_runtime(rd)==no_runtime(jl(exp/'training/r3/q4_attempts.jsonl'))
replay_dev_outcomes_match=no_runtime(rv)==no_runtime(js(exp/'training/r3/q4_development.json'))
abls={}
for p in sorted((exp/'development_ablation').glob('*.json')):
    if p.name in ('budget.json','summary.json'):continue
    d=js(p)
    rows=d.get('rows',d.get('result',{}).get('rows',[]))
    abls[p.stem]=dict(executions=len(rows),mean=mean(r['average_s'] for r in rows),all_complete=all(r['complete'] and not r['error'] for r in rows))
result['routes']['A6_learning']['inner_budget']=dict(batches=batches,
    training_parameter_vectors=sum(x['train_vectors'] for b in batches for x in b['modes']),
    development_policy_evaluations=sum(x['dev_vectors'] for b in batches for x in b['modes']),
    training_executions=sum(b['train_executions'] for b in batches),development_executions=sum(b['dev_executions'] for b in batches),
    unique_train_dev_case_ids=len(unique),unique_train_ids=len(train_unique),unique_dev_ids=len(dev_unique),
    train_dev_id_overlap=len(train_unique&dev_unique),invalid_training_cases=validity,
    replay_executions=replay_count,replay_budget_matches=rb['actual_episodes']==replay_count,
    replay_configs_match=js(replay/'replay_comparison.json'),
    replay_train_outcomes_match=replay_train_outcomes_match,replay_dev_outcomes_match=replay_dev_outcomes_match,
    replay_cases_match=js(replay/'cases.json')==js(exp/'training/r3/cases.json'),
    ablation_executions=sum(x['executions'] for x in abls.values()),ablation=abls,ablation_budget=js(exp/'development_ablation/budget.json'),
    train_dev_wall_seconds=sum(b['wall_seconds'] for b in batches),
    unique_basis='mode/seed on serialized optimized-mode cases; fixed unoptimized Q3 cases created by the script are not counted as executed',weight_training=True)

# Independent best R7 code and raw full inspection, without importing candidate code.
tree=TREES/'A6_learning';snap=tree/result['routes']['A6_learning']['snapshot'];base=tree/'evaluation/baseline_solver.py'
a=read(base);b=read(snap);at=ast.parse(a);bt=ast.parse(b)
def funcs(t):return {n.name:ast.dump(n,include_attributes=False) for n in ast.walk(t) if isinstance(n,ast.FunctionDef)}
af,bf=funcs(at),funcs(bt)
protected=['certified_points','default_points','initial_polygon','clip','add_bearing','enclosing_circle','cover_polygon','_virtual_fallback','_time_guard','scan_station','measure','clear','rescue_bearing','localize','next_station','__init__','_accept']
code=dict(protected_function_ast_equal={k:af[k]==bf[k] for k in protected},
          changed_functions=[k for k in af if k in bf and af[k]!=bf[k]],added_functions=sorted(set(bf)-set(af)),
          exit_certificate_suffix_equal=a[a.index('        unresolved='):]==b[b.index('        unresolved='):],
          imports=sorted({n.name for x in ast.walk(bt) if isinstance(x,ast.Import) for n in x.names}),
          env_attributes=sorted({n.attr for n in ast.walk(bt) if isinstance(n,ast.Attribute) and isinstance(n.value,ast.Attribute) and isinstance(n.value.value,ast.Name) and n.value.value.id=='self' and n.value.attr=='env'}),
          coverage_json_exists={str(p):p.exists() for p in [tree/'coverage_points.json',snap.parent/'coverage_points.json']})
configs=next(ast.literal_eval(n.value) for n in bt.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='OPTIMIZED_CONFIGS' for t in n.targets))
selected=js(exp/'training/r7/selected.json');meta=js(exp/'snapshots/r7_metadata.json')
code['embedded_configs_match_selected']=all(configs[int(m)]==d['config'] for m,d in selected.items())
code['embedded_configs_match_metadata']={m:configs[int(m)]==v for m,v in meta['configs'].items()}
code['zero_second_point_weights']=all(configs[4][k]==0 for k in ('second_range_weight','second_uncertainty_weight','second_route_weight'))
code['learned_feature_names']=[k for k in configs[4] if k.startswith('schedule_')]
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'A6_R7_independent.diff').write_text(''.join(difflib.unified_diff(a.splitlines(True),b.splitlines(True),fromfile=str(base),tofile=str(snap))))
rows=js(tree/'results/A6_learning_r7_full/case_metrics.json');cm={r['case_id']:r for r in rows if r['variant']=='candidate'};bm={r['case_id']:r for r in rows if r['variant']=='frozen_baseline'}
metric_fields=['cleared_count','source_count','cleared_fraction','average_clear_time_s','total_virtual_time_s','complete','exit_reason','error','coverage_certificate','requests','distance_m','clear_failures']
metrics={}
for mode in (3,4):
    rs=[r for r in cm.values() if r['mode']==mode];bs=[bm[r['case_id']] for r in rs]
    regressions=[]
    for group in sorted({r['group'] for r in rs}):
        cr=[r for r in rs if r['group']==group];delta=mean(r['average_clear_time_s']-bm[r['case_id']]['average_clear_time_s'] for r in cr)
        if delta>1e-10:regressions.append(dict(group=group,delta_s_per_source=delta,fraction=delta/mean(bm[r['case_id']]['average_clear_time_s'] for r in cr)))
    metrics[str(mode)]=dict(n=len(rs),complete=sum(r['complete'] for r in rs),error_count=sum(bool(r['error']) for r in rs),
        mean_s_per_source=mean(r['average_clear_time_s'] for r in rs),baseline_mean_s_per_source=mean(r['average_clear_time_s'] for r in bs),
        better_rows=sum(r['average_clear_time_s']<bm[r['case_id']]['average_clear_time_s']-1e-10 for r in rs),
        worse_rows=sum(r['average_clear_time_s']>bm[r['case_id']]['average_clear_time_s']+1e-10 for r in rs),
        equal_rows=sum(abs(r['average_clear_time_s']-bm[r['case_id']]['average_clear_time_s'])<=1e-10 for r in rs),
        identical_nonruntime_metrics=sum(all(r[k]==bm[r['case_id']][k] for k in metric_fields) for r in rs),
        worst_average_s=max(r['average_clear_time_s'] for r in rs),baseline_worst_average_s=max(r['average_clear_time_s'] for r in bs),
        max_total_virtual_s=max(r['total_virtual_time_s'] for r in rs),max_runtime_s=max(r['program_runtime_s'] for r in rs),
        max_requests=max(r['requests'] for r in rs),scenario_regressions=regressions)
code['raw_best_metrics']=metrics
result['A6_R7_code_audit']=code

# Supplement requested after A2 stopped: budget only; do not repeat parent's candidate audit.
exp=TREES/'A2_information/experiments/A2_information';budget=js(exp/'execution_budget.json')
dev=[];diagnostics=[];a2_unique=set();a2_diag_unique=set()
for item in budget['development']:
    d=js(exp/item['file']);rows=d['rows'];cnt=Counter(r['variant'] for r in rows)
    a2_unique.update((r['mode'],r['scenario'],r['noise'],r['seed']) for r in rows)
    dev.append(dict(file=item['file'],rows=len(rows),variant_counts=dict(cnt),
                    row_count_matches=len(rows)==item['runs'],candidate_count_matches=cnt['candidate']==item['candidate_runs'],
                    baseline_count_matches=cnt['baseline']==item['baseline_runs'],baseline_path=d.get('baseline_path'),
                    all_complete=all(r['complete'] and not r['error'] for r in rows)))
for item in budget['diagnostics']:
    rows=jl(exp/item['file']);a2_diag_unique.update((r['mode'],r['scenario'],r['noise'],r['seed']) for r in rows)
    diagnostics.append(dict(file=item['file'],attempts=len(rows),count_matches=len(rows)==item['attempts'],
                            errors=dict(Counter(str(r['error']) for r in rows)),
                            complete_stats_rows=sum(not r['error'] and r['stats']['n']==r['stats']['cleared'] for r in rows)))
result['A2_budget_supplement']=dict(budget_file=str(exp/'execution_budget.json'),budget=budget,
    development_raw=dev,diagnostic_raw=diagnostics,development_executions=sum(d['rows'] for d in dev),
    development_candidate_executions=sum(d['variant_counts']['candidate'] for d in dev),
    development_comparator_executions=sum(d['variant_counts']['baseline'] for d in dev),
    diagnostic_attempts=sum(d['attempts'] for d in diagnostics),unique_development_case_ids=len(a2_unique),
    unique_diagnostic_case_ids=len(a2_diag_unique),combined_unique_case_ids=len(a2_unique|a2_diag_unique),
    full_quick_validation_scope='Taken from finalized execution_budget.json; parent independently verified all A2 full/quick results.',
    unlogged_interrupted_r4_development='Unknown additional count, explicitly disclosed; do not set to zero.')
result['findings']=[dict(id='A3-MIXTURE',severity='evidence-boundary',route='A3_coordination',
    detail='270 recorded inner executions (135 candidate,135 baseline) use all-directional Q4 stress cases outside required mixture; no effect on frozen full validation. Revision to evidence wording needed, not retrospective data deletion.')]
result['observed_files']=observed_files
(OUT/'delivery_independent.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({r:{'best_identity':d['identity_checks_passed'],'full':d['regression']['full_candidate_executions'],'quick':d['regression']['quick_candidate_executions'], 'inner':{k:v for k,v in d['inner_budget'].items() if k not in ('batches','ablation')}} for r,d in result['routes'].items()},ensure_ascii=False,indent=2))
print(json.dumps(code,ensure_ascii=False,indent=2))
