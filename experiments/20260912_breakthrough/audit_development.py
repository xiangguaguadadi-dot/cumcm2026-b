#!/usr/bin/env python3
"""Independent saved-row audit for round-one compatibility and development.

Only the Python standard library and the sibling saved-record accounting helper
are imported. No environment, evaluator, actor, tensor runtime, or optimizer is
imported or run. --self-test uses explicitly synthetic in-memory rows only.

Development: 120 worlds, 12 equal strata, five fixed arms. The six paired
comparisons share 10,000 stratified world resamples, seed 912199. Descriptive
95% percentile intervals and latency quantiles use linear interpolation at
(n-1)*p. This is not the calibration quantile rule and not a final-test or
multiple-comparison-adjusted claim. Any incomplete-clear run disqualifies its
whole-arm time comparison; no successful-only subset substitutes for it.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import random
import struct

from audit_rl_execution import audit_journal, audit_outcome, canonical_log, read_json, require, sha256

SEEDS = (912101, 912102, 912103)
ARMS = ('c7', 'q4_r2', *(f'neural_{s}' for s in SEEDS))
COMPAT_ARMS = ('c7', 'neural_912101_teacher_forced')
C7_SHA = 'cf37866829b9c6f376895075e819a732939e6fa8ad6d8d6297a151d7a213dcb3'
R2_SHA = '789096af68fcf470e3973fd93757c556d81d60f3fe3910c5991c537def3f91cc'
BOOTSTRAP_SEED = 912199
BOOTSTRAP_REPLICATES = 10000


def finite(value, message='Expected finite nonnegative duration', *, negative=False):
    require(type(value) in (int, float) and math.isfinite(value)
            and (negative or value >= 0), message)
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def decoded(value):
    if type(value) is not dict:
        require(value is None or type(value) in (bool, int, str), 'Invalid typed public state')
        return value
    require(set(value) == {'@', 'v'}, 'Unknown typed public-state fields')
    tag, item = value['@'], value['v']
    if tag == 'float':
        result = float.fromhex(item)
        require(math.isfinite(result), 'Nonfinite typed state float')
        return result
    if tag == 'dict':
        pairs = [(decoded(k), decoded(v)) for k, v in item]
        require(len(dict(pairs)) == len(pairs), 'Duplicate decoded state key')
        return dict(pairs)
    require(tag in ('tuple', 'list', 'set'), 'Unsupported typed public state')
    items = [decoded(v) for v in item]
    return tuple(items) if tag == 'tuple' else set(items) if tag == 'set' else items


def f32(value):
    finite(value, 'Nonfinite score', negative=True)
    try:
        result = struct.unpack('!f', struct.pack('!f', value))[0]
    except (OverflowError, struct.error) as exc:
        raise ValueError('Float32 overflow') from exc
    require(math.isfinite(result), 'Float32 overflow')
    return result


def selected_from_scores(ids, teacher, scores, margin, forced=False):
    require(type(ids) is list and 1 <= len(ids) <= 9 and ids == sorted(set(ids))
            and teacher in ids and len(scores) == len(ids), 'Invalid retained score alignment')
    require(all(type(v) is str and len(v) == 64 and all(c in '0123456789abcdef' for c in v)
                for v in ids), 'Candidate ID is not a canonical hash')
    require(all(s == f32(s) for s in scores), 'Stored score is not exact float32')
    finite(margin, 'Invalid fixed calibration margin')
    gains = [f32(s-scores[ids.index(teacher)]) for s in scores]
    best = min(range(len(ids)), key=lambda i: (-gains[i], ids[i]))
    chosen = ids[best] if not forced and gains[best] > margin + .0005 else teacher
    return chosen, ids[best], gains[best], gains


def quantile(values, probability):
    require(values and 0 <= probability <= 1, 'Quantile needs a nonempty finite population')
    ordered = sorted(finite(v, negative=True) for v in values)
    rank = (len(ordered)-1)*probability
    lo = math.floor(rank)
    return ordered[lo] + (ordered[min(lo+1, len(ordered)-1)]-ordered[lo])*(rank-lo)


def distribution(values):
    if not values:
        return dict(n=0, mean=None, p50=None, p95=None, p99=None, maximum=None)
    require(all(finite(v) >= 0 for v in values), 'Invalid duration population')
    return dict(n=len(values), mean=math.fsum(values)/len(values),
                p50=quantile(values, .5), p95=quantile(values, .95),
                p99=quantile(values, .99), maximum=max(values))


def check_grid(worlds, rows, arms, expected):
    require(len(worlds) == expected and len({w['world_id'] for w in worlds}) == expected
            and len({w['world_sha256'] for w in worlds}) == expected, 'Wrong world registry')
    expected_pairs = {(w['world_id'], arm) for w in worlds for arm in arms}
    observed = [(r['world_id'], r['actual_policy_id']) for r in rows]
    require(len(observed) == len(set(observed)) and set(observed) == expected_pairs,
            'Missing, duplicated, or unexpected world/arm result')
    require(Counter(w['group'] for w in worlds).values()
            and len(Counter(w['group'] for w in worlds)) == 12
            and set(Counter(w['group'] for w in worlds).values()) == {expected//12},
            'Wrong 12-stratum world denominator')
    require([w['index'] for w in worlds] == list(range(expected)), 'World order differs from fixed index order')


def paired_summary(rows, candidate, control):
    pairs = [(r[candidate], r[control]) for r in rows]
    require(pairs and all(a['world_id'] == b['world_id'] and a['n'] == b['n']
                         and type(a['n']) is int and a['n'] > 0 for a, b in pairs),
            'Paired comparison has mismatched world/source denominator')
    failures = [a['world_id'] for a, b in pairs if not (a['success'] and b['success'])]
    result = dict(candidate=candidate, control=control, paired_worlds=len(pairs),
                  failed_pair_world_ids=failures, valid_full_clear_comparison=not failures)
    if failures:
        return dict(result, mean_paired_delta_seconds_per_source=None,
                    relative_improvement_percent=None, faster=None, same=None, slower=None)
    cmean = math.fsum(a['seconds_per_source'] for a, _ in pairs)/len(pairs)
    bmean = math.fsum(b['seconds_per_source'] for _, b in pairs)/len(pairs)
    require(bmean > 0, 'Zero baseline denominator')
    delta = math.fsum((a['total_us']-b['total_us'])/(1e6*a['n']) for a, b in pairs)/len(pairs)
    return dict(result, candidate_mean_seconds_per_source=cmean, control_mean_seconds_per_source=bmean,
                mean_paired_delta_seconds_per_source=delta,
                relative_improvement_percent=100*(1-cmean/bmean),
                faster=sum(a['total_us'] < b['total_us'] for a, b in pairs),
                same=sum(a['total_us'] == b['total_us'] for a, b in pairs),
                slower=sum(a['total_us'] > b['total_us'] for a, b in pairs))


def stratified_bootstrap(world_rows, comparisons):
    groups = defaultdict(list)
    for row in world_rows:
        groups[row['c7']['group']].append(row)
    require(len(groups) == 12 and all(len(v) == 10 for v in groups.values()),
            'Bootstrap requires exactly 12 strata x 10 worlds')
    eligible = [p for p in comparisons if p['valid_full_clear_comparison']]
    draws = {(p['candidate'], p['control']): ([], []) for p in eligible}
    rng = random.Random(BOOTSTRAP_SEED)
    for _ in range(BOOTSTRAP_REPLICATES):
        sampled = [values[rng.randrange(len(values))] for group in sorted(groups)
                   for values in [groups[group]] for _ in range(len(values))]
        means = {arm: math.fsum(r[arm]['seconds_per_source'] for r in sampled)/120 for arm in ARMS}
        for pair in eligible:
            candidate, control = pair['candidate'], pair['control']
            delta = math.fsum((r[candidate]['total_us']-r[control]['total_us'])/(1e6*r[candidate]['n'])
                              for r in sampled)/120
            change = 100*(1-means[candidate]/means[control])
            draws[(candidate, control)][0].append(delta)
            draws[(candidate, control)][1].append(change)
    result = []
    for pair in comparisons:
        key = (pair['candidate'], pair['control'])
        values = draws.get(key)
        result.append(dict(candidate=key[0], control=key[1], eligible=values is not None,
            paired_delta_95_percentile_ci=None if values is None else [quantile(values[0], p) for p in (.025, .975)],
            relative_improvement_95_percentile_ci=None if values is None else [quantile(values[1], p) for p in (.025, .975)],
            replicate_statistics_sha256=None if values is None else digest(values)))
    return dict(seed=BOOTSTRAP_SEED, replicates=BOOTSTRAP_REPLICATES, unit='paired world within fixed stratum',
                strata=12, worlds_per_stratum=10, resamples_shared_across_all_six_comparisons=True,
                interval='95% percentile; linear interpolation at (replicates-1)*p', comparisons=result,
                evidence='Descriptive development intervals, no final-test or multiplicity-adjusted guarantee')


def audit_decisions(result, model, forced):
    decisions = result['extra']['selector_decisions']
    macros = result['episode']['macros']
    require(len(decisions) == len(macros) and len({d['choice_id'] for d in decisions}) == len(decisions),
            'Missing or duplicated selector decision/macro')
    timings = defaultdict(list)
    scored_count = overrides = 0
    rejection_counts = Counter()
    for decision, macro in zip(decisions, macros):
        require(decision['choice_id'] == macro['choice_id'] and decision['selected_id'] == macro['action_id']
                and macro['invalid_choice_fell_back'] is False and digest(macro['payload']) == macro['action_id'],
                'Chosen ID does not match the actual committed operation')
        require(decision['checkpoint_sha256'] == model['sha256'] and decision['margin'] == model['margin']
                and decision['force_teacher_probe'] is forced and decision['batch_size'] == 1
                and decision['mode'] == 4 and type(decision['model_scored']) is bool,
                'Selector uses another weight, margin, mode, or batch')
        wall = finite(decision['selector_wall_s'])
        complete = finite(decision['complete_prepare_feature_ipc_forward_selection_wall_s'])
        require(complete + 1e-9 >= wall, 'End-to-end timing omits selector work')
        # Engine.expand adds its duration to prepared.prepare_wall_s *inside*
        # the selector.  The stored macro therefore includes expansion twice
        # if naively added to selector_wall_s.  Only the initial prepare is
        # outside the selector; its exact value is complete - selector.
        initial_prepare = complete-wall
        macro_prepare = finite(macro['prepare_wall_s'])
        expansion = macro_prepare-initial_prepare
        require(initial_prepare >= -1e-8 and expansion >= -1e-8
                and expansion <= wall+1e-8, 'Invalid initial-prepare/expansion timing partition')
        timings['all_decisions_end_to_end_s'].append(complete)
        timings['all_decisions_selector_s'].append(wall)
        kind = macro['payload']['kind']
        override = kind in ('measure_override', 'clear_override')
        if override:
            overrides += 1
            require(decision['model_scored'] and not forced and decision['slots_before'] > 0
                    and macro['payload']['channel'] not in macro['forced_teacher_before'],
                    'Override violates teacher-only or intervention-budget guard')
        require(macro['slots_after'] == 2-overrides and overrides <= 2, 'Intervention slots are not charged exactly once')
        if 'slots_before' in decision:
            require(decision['slots_before'] == 2-overrides+int(override), 'Decision intervention denominator changed')
        if decision['model_scored']:
            scored_count += 1
            chosen, best, gain, gains = selected_from_scores(decision['candidate_ids'], decision['teacher_id'],
                                                            decision['scores'], model['margin'], forced)
            require(decision['selected_id'] == chosen and decision['predicted_candidate_id'] == best
                    and decision['predicted_gain'] == gain and decision['gains'] == gains
                    and decision['strict_threshold'] == model['margin']+.0005 and decision['rejection'] is None,
                    'Saved selector differs from independently recomputed float32 gate')
            require((chosen != decision['teacher_id']) == override, 'Action kind contradicts intervention decision')
            roundtrip = finite(decision['inference_roundtrip_wall_s'])
            forward = finite(decision['model_forward_wall_s'])
            tensor = finite(decision['tensor_build_wall_s'])
            feature = finite(decision['candidate_and_feature_wall_s'])
            require(complete + 1e-8 >= wall and wall + 1e-8 >= roundtrip
                    and roundtrip + 1e-8 >= forward+tensor and feature+roundtrip <= wall+1e-8
                    and feature+1e-8 >= expansion, 'Model-only timing exceeds measured end-to-end scope')
            for target, source in (
                ('scored_decisions_end_to_end_s', 'complete_prepare_feature_ipc_forward_selection_wall_s'),
                ('scored_decisions_selector_s', 'selector_wall_s'), ('ipc_roundtrip_s', 'inference_roundtrip_wall_s'),
                ('model_forward_s', 'model_forward_wall_s'), ('model_forward_cpu_s', 'model_forward_cpu_s'),
                ('tensor_build_s', 'tensor_build_wall_s'), ('tensor_build_cpu_s', 'tensor_build_cpu_s'),
                ('candidate_and_features_s', 'candidate_and_feature_wall_s')):
                timings[target].append(finite(decision[source]))
        else:
            require(decision['selected_id'] == decision['teacher_id'] and not override,
                    'Unscored decision changed the teacher action')
            require(type(decision.get('rejection')) is str and decision['rejection'], 'Unscored decision lacks a reason')
            rejection_counts[decision['rejection']] += 1
    final = decoded(result['episode']['engine_final'])
    used = [m['action_id'] for m in macros if m['payload']['kind'] in ('measure_override', 'clear_override')]
    require(final['used_operation_ids'] == used and result['episode']['slots_remaining'] == 2-len(used),
            'Final intervention IDs or slots disagree with actual macros')
    return dict(decisions=len(decisions), scored_decisions=scored_count, overrides=overrides,
                rejections=dict(rejection_counts), timings=dict(timings))


class Evidence:
    def __init__(self):
        self.hashes = {}

    def read(self, path):
        path = Path(path).resolve()
        self.hashes[str(path)] = sha256(path)
        return read_json(path)

    def pin(self, path, expected):
        path = Path(path).resolve()
        require(sha256(path) == expected, 'Changed prior/source evidence: '+str(path))
        self.hashes[str(path)] = expected

    def verify(self):
        for path, expected in self.hashes.items():
            require(sha256(path) == expected, 'Evidence changed during saved-row audit: '+path)


def audit(campaign, stage, ledger, preflight, calibration_audit, phase='development', compatibility_audit=None,
          acceptance_path=None):
    campaign, stage, ledger, preflight = (Path(p).resolve() for p in (campaign, stage, ledger, preflight))
    require(phase in ('compatibility', 'development') and stage.is_relative_to(campaign/'results')
            and preflight.is_relative_to(campaign), 'Wrong audit phase or stage directory')
    repo = campaign.parents[3]
    evidence = Evidence()
    evidence.pin(Path(__file__).resolve(), sha256(__file__))
    helper = Path(__file__).resolve().with_name('audit_rl_execution.py')
    evidence.pin(helper, sha256(helper))
    registered = evidence.read(campaign/'registration.json')
    world_manifest = evidence.read(campaign/'world_manifest.json')
    require(sha256(campaign/'world_manifest.json') == registered['manifest_sha256'], 'Registered worlds changed')
    require(Counter(w['role'] for w in world_manifest['worlds']) == {'fit': 24, 'fit_val': 12, 'calibration': 24, 'development': 120}
            and len({w['world_sha256'] for w in world_manifest['worlds']}) == 180, 'Role counts or world-role isolation changed')
    compat_registry = evidence.read(campaign/'compatibility_registration.json')
    require(sha256(campaign/'compatibility_registration.json') == registered['compatibility_sha256'], 'Old-probe registry changed')
    require(len(compat_registry['worlds']) == 12 and all(w['role'] == 'probe' and w['phase'] == 'g0'
            and w['mode'] == 4 for w in compat_registry['worlds']), 'Compatibility is not the 12 old Q4 probes')
    require(not ({w['world_sha256'] for w in compat_registry['worlds']} &
                 {w['world_sha256'] for w in world_manifest['worlds']}), 'Old compatibility probe entered a new data role')
    worlds = compat_registry['worlds'] if phase == 'compatibility' else [w for w in world_manifest['worlds'] if w['role'] == 'development']
    arms, expected = (COMPAT_ARMS, 12) if phase == 'compatibility' else (ARMS, 120)
    require(all(w['mode'] == 4 for w in worlds), 'Mixed mode in Q4 evaluation')
    registry = evidence.read(stage/'registration.json')
    summary = evidence.read(stage/'summary.json')
    require(acceptance_path is not None, 'Exact coordinator acceptance file is required')
    acceptance = evidence.read(acceptance_path)
    require(sha256(acceptance_path) == registry['acceptance_sha256'] and acceptance['evaluation_accepted'] is True,
            'Evaluation was not bound to the exact coordinator acceptance')
    index = evidence.read(stage/'index.json')['runs']
    saved_worlds = evidence.read(stage/'world_results.json')['worlds']
    check_grid(worlds, index, arms, expected)
    require(registry['world_ids'] == [w['world_id'] for w in worlds] and registry['policy_order'] == list(arms)
            and registry['c7_sha256'] == C7_SHA and registry['q4_r2_sha256'] == R2_SHA,
            'Evaluation registration changed worlds, arm order, or control identity')
    require(registry['no_selection_or_tuning_from_this_stage'] is True and registry['no_deployment_promotion'] is True,
            'Evaluation registration permits undeclared selection or promotion')
    caudit = evidence.read(calibration_audit)
    require(caudit['status'] == '24_world_three_model_calibration_verified' and caudit['world_count'] == 24,
            'An independent complete calibration audit is required')
    for path, expected_sha in caudit['source_sha256'].items():
        evidence.pin(path, expected_sha)
    margin_files = [Path(p) for p, value in caudit['source_sha256'].items()
                    if Path(p).name == 'margins.json' and value == registry['calibration_margins_sha256']]
    require(len(margin_files) == 1, 'Evaluation margins were not independently audited')
    margin_document = evidence.read(margin_files[0])
    require([m['seed'] for m in registry['models']] == list(SEEDS), 'Model initialization set/order changed')
    models = {f'neural_{m["seed"]}': m for m in registry['models']}
    for actual, original, margin in zip(registry['models'], margin_document['models'], margin_document['margins']):
        require(all(actual[k] == v for k, v in original.items()) and actual['margin'] == margin['margin']
                and actual['sha256'] == margin['checkpoint_sha256'], 'Evaluation changes calibrated weights or margin')
        path = (campaign/actual['path']).resolve()
        require(path.is_relative_to(campaign), 'Weight path outside campaign')
        evidence.pin(path, actual['sha256'])
        require(actual['model_source_sha256'] == sha256(campaign/'model.py')
                and actual['feature_implementation_sha256'] == sha256(campaign/'features.py'), 'Model/feature semantics changed after fit')
        definition = actual['policy_definition']
        expected_definition = dict(seed=actual['seed'], checkpoint_sha256=actual['sha256'], margin=actual['margin'],
            strict_extra_gain=.0005, selector_sha256=sha256(campaign/'policy.py'), selection_sha256=sha256(campaign/'selection.py'),
            feature_sha256=sha256(campaign/'features.py'), actor_worker_sha256=sha256(campaign/'actor_worker.py'),
            max_interventions=2, teacher_sha256=C7_SHA)
        require(definition == expected_definition and actual['policy_sha256'] == digest(definition), 'Frozen policy definition changed')
    source = evidence.read(preflight/'source_freeze.json')
    inputs = evidence.read(preflight/'input_freeze.json')
    require(source['schema'] == 'bc-rpi-round1-stage-source-freeze-v1' and source['stage'] == 'evaluation'
            and inputs['schema'] == 'bc-rpi-round1-stage-input-freeze-v1' and inputs['stage'] == 'evaluation'
            and sha256(preflight/'source_freeze.json') == registry['source_freeze_sha256'] == summary['source_freeze_sha256']
            == acceptance['source_freeze_sha256'] and sha256(preflight/'input_freeze.json') == acceptance['input_freeze_sha256']
            and registry['calibration_margins_sha256'] == summary['margins_sha256'] == acceptance['calibration_margins_sha256'],
            'Evaluation source/input stage identity differs')
    for manifest in (source, inputs):
        for relative, expected_sha in manifest['files'].items():
            path = (repo/relative).resolve()
            require(path.is_relative_to(repo), 'Source/input freeze escaped repository')
            evidence.pin(path, expected_sha)
    required_sources = {str((campaign/name).relative_to(repo)) for name in
        ('evaluate_round.py', 'policy.py', 'inference_worker.py', 'actor_worker.py', 'selection.py',
         'features.py', 'model.py', 'torch_runtime.py', 'stage_freeze.py', 'budget.py', 'common.py')}
    require(required_sources <= set(source['files']), 'Actual evaluation module missing from source freeze')
    required_inputs = {str(p.relative_to(repo)) for p in
        [campaign/'world_manifest.json', campaign/'registration.json', campaign/'compatibility_registration.json',
         *(margin_files[0].parent/name for name in ('summary.json', 'margins.json', 'world_results.json', 'registration.json')),
         *(campaign/m['path'] for m in registry['models'])]}
    require(required_inputs <= set(inputs['files']), 'Actual evaluation input absent from freeze')
    if phase == 'development':
        require(compatibility_audit is not None, 'Development requires an independent compatibility audit')
        compat_audit = evidence.read(compatibility_audit)
        compat_complete = (compat_audit['status'] == 'compatibility_saved_rows_verified'
                           and compat_audit['worlds'] == 12 and compat_audit['actual_executions'] == 24)
        compat_complete = compat_complete or (
            compat_audit['status'] == '12_world_24_full_exact_teacher_equivalence_verified'
            and len(compat_audit['world_checks']) == 12
            and all(r['normal_allclear'] is True and r['exact_trace'] is True for r in compat_audit['world_checks']))
        require(compat_complete and compat_audit['source_freeze_sha256'] == registry['source_freeze_sha256']
                and compat_audit['calibration_margins_sha256'] == registry['calibration_margins_sha256'],
                'Compatibility audit is missing or refers to another frozen policy')
        for path, expected_sha in compat_audit['source_sha256'].items():
            evidence.pin(path, expected_sha)
        compatibility_summaries = [Path(p).resolve() for p, value in compat_audit['source_sha256'].items()
            if Path(p).name == 'summary.json' and value == acceptance['compatibility_summary_sha256']
            and Path(p).resolve().is_relative_to(campaign/'results')]
        require(len(compatibility_summaries) == 1, 'Accepted compatibility summary is not independently bound')
        compatibility_dir = compatibility_summaries[0].parent
        compatibility_inputs = {str(p.relative_to(repo)) for p in compatibility_dir.rglob('*') if p.is_file()}
        require(compatibility_inputs <= set(inputs['files']), 'Completed compatibility directory absent from development input freeze')
        compatibility_summary = evidence.read(compatibility_summaries[0])
        require(compatibility_summary['status'] == 'compatibility_complete_exact_teacher_equivalence'
                and compatibility_summary['completed_worlds'] == 12 and compatibility_summary['actual_executions'] == 24,
                'Accepted compatibility summary is not complete')
    journal_path = ledger/'execution_calls.jsonl'
    if not journal_path.exists():
        journal_path = ledger/'execution_calls.jsonl.gz'
    evidence.pin(journal_path, sha256(journal_path))
    opener = gzip.open if journal_path.suffix == '.gz' else open
    with opener(journal_path, 'rt', encoding='utf-8') as stream:
        counts, journal_runs = audit_journal(json.loads(line) for line in stream)
    status = evidence.read(ledger/'execution_status.json')
    require(status['current_run'] is None and status['reserved_calls'] == 0 and not counts['unfinished_runs']
            and not counts['unresolved_calls'] and not counts['unknown_calls'], 'Evaluation ledger is not fully settled')
    require(all(status[key] == counts[key] for key in ('business_calls', 'accepted_calls', 'rejected_calls',
            'executions_started', 'executions_completed')), 'Ledger status counters disagree with journal')
    paid = {key: value for key, value in journal_runs.items() if value['start']['metadata'].get('stage') == phase}
    require(len(paid) == expected*len(arms) and set(paid) == {r['run_id'] for r in index},
            'Missing, extra, or unindexed paid evaluation execution')
    paid_order = [key for key in journal_runs if key in paid]
    require(paid_order == [r['run_id'] for r in index], 'Actual paid execution order differs from saved arm order')
    preceding = []
    for run_id, run in journal_runs.items():
        if run_id in paid:
            break
        preceding.append(run)
    require(registry['before_executions'] == len(preceding)
            and registry['before_calls'] == sum(r['counts']['business_calls'] for r in preceding)
            and status['phase_executions'][phase] == len(paid)
            and status['phase_calls'][phase] == sum(r['counts']['business_calls'] for r in paid.values()),
            'Evaluation stage start/phase accounting differs from actual journal')
    by_world = {w['world_id']: w for w in worlds}
    model_telemetry = defaultdict(lambda: dict(timings=defaultdict(list), rejections=Counter(), decisions=0, scored_decisions=0, overrides=0))
    metrics, indexed = {}, {}
    previous_compat = None
    for offset, row in enumerate(index):
        run_id, world_id, arm = row['run_id'], row['world_id'], row['actual_policy_id']
        require(world_id == worlds[offset//len(arms)]['world_id'] and arm == arms[offset % len(arms)], 'World/arm execution sequence changed')
        world = by_world[world_id]
        path = (campaign/row['path']).resolve()
        require(path.is_relative_to(stage/'runs'), 'Outcome path outside this evaluation stage')
        result = evidence.read(path)
        run = paid[run_id]
        audit_outcome(result, run)
        meta = run['start']['metadata']
        require(result['kind'] == row['kind'] == run['start']['kind'] == 'full'
                and meta['world_sha256'] == world['world_sha256'] and meta['mode'] == row['mode'] == world['mode']
                and all(row[k] == world[k] for k in ('world_id', 'world_sha256', 'index', 'group', 'role')),
                'Actual paid run does not match its registered world')
        true_sources = result['private_terminal_sources']
        require(len(true_sources) == len(world['sources']) == result['true_terminal_n'], 'Source count changed')
        for source_row in world['sources']:
            actual = true_sources[str(source_row['channel'])]
            require(all(actual[k] == v for k, v in source_row.items() if k != 'cleared'), 'Actual world source geometry differs')
        require(not result.get('ledger_error') and not result['episode'].get('error') and result['normal_exit'] is True
                and bool(result['environment_log']) and result['environment_log'][-1]['action'] == 'exit'
                and result['environment_log'][-1]['response'].get('exit_reason') == 'user_exit',
                'Incomplete engineering/resource run is not a terminal performance observation')
        n, cleared, total = result['true_terminal_n'], result['cleared'], result['modeled_full_virtual_us']
        require(type(n) is int and 10 <= n <= 16 and result['success'] is (cleared == n), 'Terminal full-clear flags disagree')
        require(row['success'] is result['success'] and row['n'] == n and row['cleared'] == cleared
                and row['normal_exit'] is result['normal_exit'] and row['modeled_full_virtual_us'] == total
                and abs(row['seconds_per_source']-total/(1e6*n)) < 1e-9, 'Index metrics differ from raw terminal outcome')
        wrapper = finite(result['actual_execution_wall_s'])
        runtime = finite(result['stats']['runtime_s'])
        require(row['actual_execution_wall_s'] == wrapper and wrapper+1e-6 >= runtime,
                'Wrapper wall time is inconsistent with enter-to-finish runtime')
        require(run['finish']['actual_wall_s']+1e-6 >= wrapper, 'Paid-run wall scope is smaller than wrapper execution')
        if arm in ('c7', 'q4_r2'):
            expected_sha = C7_SHA if arm == 'c7' else R2_SHA
            require(row['entry_sha256'] == meta['entry_sha256'] == expected_sha,
                    'Actual direct entry SHA is not the registered C7/R2 control')
            require(meta['policy'] == ('original_c7' if arm == 'c7' else 'latest_q3_direct'),
                    'Unexpected legacy direct-entry execution route')
            if arm == 'q4_r2':
                require(row['legacy_runtime_policy_label_is_not_actual_identity'] is True,
                        'Legacy Q3 label must not be mistaken for actual R2 identity')
        else:
            model = models['neural_912101' if phase == 'compatibility' else arm]
            extra = result['extra']
            require(meta['policy'] == 'round1_neural_'+str(model['seed'])
                    and meta['policy_sha256'] == row['policy_sha256'] == extra['policy_sha256'] == model['policy_sha256']
                    and meta['checkpoint_sha256'] == extra['checkpoint_sha256'] == model['sha256']
                    and meta['force_teacher_probe'] is (phase == 'compatibility')
                    and extra['force_teacher_probe'] is (phase == 'compatibility') and extra['margin'] == model['margin'],
                    'Actual neural execution does not match frozen policy')
            if phase == 'development':
                require(row['checkpoint_sha256'] == model['sha256'] and row['margin'] == model['margin'],
                        'Development index changes frozen checkpoint or margin')
            telemetry = audit_decisions(result, model, phase == 'compatibility')
            aggregate = model_telemetry[arm]
            for key in ('decisions', 'scored_decisions', 'overrides'):
                aggregate[key] += telemetry[key]
            aggregate['rejections'].update(telemetry['rejections'])
            for key, values in telemetry['timings'].items():
                aggregate['timings'][key].extend(values)
        metrics[(world_id, arm)] = dict(world_id=world_id, group=world['group'], arm=arm, run_id=run_id,
            n=n, cleared=cleared, success=result['success'], normal_exit=result['normal_exit'], total_us=total,
            seconds_per_source=total/(1e6*n), seconds_per_cleared=None if cleared == 0 else total/(1e6*cleared),
            cleared_fraction=cleared/n, wrapper_wall_s=wrapper, enter_to_finish_runtime_s=runtime,
            fallback_instrumented='fallback_reason' in result['episode'], fallback_reason=result['episode'].get('fallback_reason'))
        indexed[run_id] = row
        if phase == 'compatibility':
            if arm == 'c7':
                previous_compat = result
            else:
                require(previous_compat['success'] and result['success']
                        and canonical_log(previous_compat['environment_log']) == canonical_log(result['environment_log'])
                        and previous_compat['modeled_full_virtual_us'] == total
                        and previous_compat['true_terminal_n'] == n and telemetry['overrides'] == 0
                        and telemetry['scored_decisions'] > 0, 'Forced-teacher compatibility is not exact or never ran the model')
                check = evidence.read(stage/'checks'/f'w{world["index"]:03d}.json')
                require(check['world_id'] == world_id and check['checks'] and all(v is True for v in check['checks'].values()),
                        'Stored compatibility check differs from independently verified result')
                previous_compat = None
    require(len(saved_worlds) == expected and [r['world_id'] for r in saved_worlds] == [w['world_id'] for w in worlds],
            'World results omit or reorder registered worlds')
    for world, saved in zip(worlds, saved_worlds):
        require(saved['status'] == 'complete' and all(saved[k] == world[k] for k in ('world_id', 'world_sha256', 'index', 'group', 'role'))
                and [r['actual_policy_id'] for r in saved['runs']] == list(arms)
                and all(r == indexed[r['run_id']] for r in saved['runs'])
                and saved['all_policies_normal_allclear'] is all(metrics[(world['world_id'], a)]['success'] for a in arms),
                'Per-world arm bundle differs from saved actual run index')
    expected_status = 'compatibility_complete_exact_teacher_equivalence' if phase == 'compatibility' else 'development_complete_no_tuning_or_promotion'
    require(summary['status'] == expected_status and summary['completed_worlds'] == summary['registered_worlds'] == expected
            and summary['registered_seeds'] == list(SEEDS) and summary['current_run'] is None and summary['unknown_cost_calls'] == 0
            and summary['actual_calls'] == sum(r['counts']['business_calls'] for r in paid.values())
            and summary['actual_executions'] == len(paid)
            and summary['real_failed_runs_retained'] == sum(not r['success'] for r in index)
            and summary['zero_gradient_updates'] is True and summary['no_checkpoint_threshold_selection'] is True
            and summary['no_deployment_promotion'] is True, 'Evaluation summary conceals incomplete runs or changed scope')
    require(summary['registered_world_statuses'] == [dict(world_id=w['world_id'], status='complete') for w in worlds],
            'Summary world statuses differ from complete registered population')
    readiness = evidence.read(stage/'worker_readiness.json')
    expected_seeds = SEEDS[:1] if phase == 'compatibility' else SEEDS
    require([r['seed'] for r in readiness['neural_workers']] == list(expected_seeds), 'Wrong worker initialization set')
    for worker in readiness['neural_workers']:
        model = models['neural_'+str(worker['seed'])]
        expected_identity = dict(ready=True, checkpoint_sha256=model['sha256'], seed=model['seed'], epoch=model['epoch'],
            parameter_count=61121, device='cpu', threads=1, parameter_sha256=model['parameter_sha256'],
            model_source_sha256=model['model_source_sha256'], feature_implementation_sha256=model['feature_implementation_sha256'])
        require(worker['identity'] == expected_identity, 'Worker did not load the exact frozen network')
        finite(worker['startup_wall_s'])
    arm_summaries = []
    for arm in arms:
        rows = [metrics[(w['world_id'], arm)] for w in worlds]
        failed = [r for r in rows if not r['success']]
        arm_summaries.append(dict(arm=arm, worlds=len(rows), full_clear_successes=len(rows)-len(failed),
            failures=len(failed), failed_world_ids=[r['world_id'] for r in failed],
            raw_world_mean_T_over_N_seconds=math.fsum(r['seconds_per_source'] for r in rows)/len(rows),
            mean_eligible_for_speed_comparison=not failed, wrapper_wall_s=distribution([r['wrapper_wall_s'] for r in rows]),
            enter_to_finish_runtime_s=distribution([r['enter_to_finish_runtime_s'] for r in rows]),
            fallback_instrumented_runs=sum(r['fallback_instrumented'] for r in rows),
            reported_fallback_runs=sum(r['fallback_reason'] is not None for r in rows),
            fallback_unavailable_runs=sum(not r['fallback_instrumented'] for r in rows)))
    comparisons = grouped = bootstrap = None
    if phase == 'development':
        paired_rows = [{arm: metrics[(w['world_id'], arm)] for arm in ARMS} for w in worlds]
        comparisons = [paired_summary(paired_rows, candidate, control) for candidate in ARMS[2:] for control in ARMS[:2]]
        grouped = {group: [paired_summary([r for r in paired_rows if r['c7']['group'] == group], candidate, control)
            for candidate in ARMS[2:] for control in ARMS[:2]] for group in sorted({w['group'] for w in worlds})}
        bootstrap = stratified_bootstrap(paired_rows, comparisons)
    timings = {arm: dict(decisions=value['decisions'], scored_decisions=value['scored_decisions'], overrides=value['overrides'],
        rejections=dict(value['rejections']), duration_populations={key: distribution(values) for key, values in value['timings'].items()},
        quantile='Linear interpolation at (n-1)*p; populations pooled over decisions, not averaged episode percentiles')
        for arm, value in model_telemetry.items()}
    evidence.verify()
    return dict(schema='bc-rpi-round1-independent-development-audit-v1',
        status='compatibility_saved_rows_verified' if phase == 'compatibility' else 'development_saved_rows_verified',
        phase=phase, worlds=expected, arms=list(arms), actual_executions=len(paid),
        actual_business_calls=sum(r['counts']['business_calls'] for r in paid.values()),
        stage_directory=str(stage), summary_sha256=sha256(stage/'summary.json'),
        acceptance_sha256=registry['acceptance_sha256'], input_freeze_sha256=sha256(preflight/'input_freeze.json'),
        source_freeze_sha256=registry['source_freeze_sha256'], calibration_margins_sha256=registry['calibration_margins_sha256'],
        arm_summaries=arm_summaries, paired_comparisons=comparisons, by_group_comparisons=grouped, bootstrap=bootstrap,
        selector_telemetry=timings, worker_startup=[dict(seed=r['seed'], wall_s=r['startup_wall_s']) for r in readiness['neural_workers']],
        failure_rows=[r for r in metrics.values() if not r['success']], source_sha256=evidence.hashes,
        auditor_sha256=sha256(__file__), actual_environment_calls_by_auditor=0, actual_optimizer_updates_by_auditor=0,
        evidence_limits=['Saved actual requests, integer-microsecond physics, entry SHA, action gates, complete grid and statistics audited.',
            'Stored neural scores and frozen identities checked, but no independent neural-forward replay is performed by this standard-library auditor.',
            'All-decision and model-scored latency populations are separate; cold model startup is separately reported, not inside episode time.',
            'Direct C7/R2 outcomes do not expose the same fallback_reason instrumentation; unavailable is not counted as zero.',
            'Development only: no sealed final test, official execution, causal attribution, candidate selection, or deployment promotion.'])


def self_test():
    """Pure synthetic invariants; these are not collected worlds or results."""
    require(quantile([0., 10.], .95) == 9.5, 'Linear quantile self-test')
    require(distribution([])['p95'] is None, 'Empty timings must not become zero')
    ids = ['a'*64, 'b'*64]
    gain = f32(1/1024)
    require(selected_from_scores(ids, ids[0], [0., gain], gain-.0005)[0] == ids[0], 'Strict threshold self-test')
    require(selected_from_scores(ids, ids[1], [gain, gain], 0.)[1] == ids[0], 'Canonical tie self-test')
    worlds = [dict(world_id=f'synthetic-{i}', world_sha256=str(i), index=i, group=f'g{i % 12:02d}') for i in range(120)]
    rows = [dict(world_id=w['world_id'], actual_policy_id=a) for w in worlds for a in ARMS]
    check_grid(worlds, rows, ARMS, 120)
    try:
        check_grid(worlds, rows[:-1]+[rows[0]], ARMS, 120)
    except ValueError:
        pass
    else:
        raise AssertionError('Duplicate/missing arm self-test failed')
    paired = [{arm: dict(world_id=w['world_id'], group=w['group'], success=True, n=10,
               total_us=1000000000+(0 if arm in ARMS[:2] else 10000000),
               seconds_per_source=100.+(0 if arm in ARMS[:2] else 1.)) for arm in ARMS} for w in worlds]
    comparisons = [paired_summary(paired, a, b) for a in ARMS[2:] for b in ARMS[:2]]
    require(all(p['mean_paired_delta_seconds_per_source'] == 1. and p['slower'] == 120 for p in comparisons), 'Paired formula self-test')
    boot = stratified_bootstrap(paired, comparisons)
    require(all(r['paired_delta_95_percentile_ci'] == [1., 1.] for r in boot['comparisons']), 'Constant paired bootstrap self-test')
    # Strata have distinct offsets, nonconstant differences, and varying N.
    # An independent scalar resampler gives the expected mean-delta interval.
    # Six identical contrasts must also have identical replicate hashes: this
    # detects separately re-sampling the six otherwise equivalent comparisons.
    for i, row in enumerate(paired):
        n, group = 10+i % 7, i % 12
        difference = group*10+1+i//12
        for arm in ARMS:
            score = 100+group*100+(difference if arm in ARMS[2:] else 0)
            row[arm].update(n=n, total_us=score*n*1000000, seconds_per_source=float(score))
    variable_comparisons = [paired_summary(paired, a, b) for a in ARMS[2:] for b in ARMS[:2]]
    require(all(p['mean_paired_delta_seconds_per_source'] == 60.5 for p in variable_comparisons),
            'Varying-N world mean must not become pooled source ratio')
    variable = stratified_bootstrap(paired, variable_comparisons)
    rng = random.Random(BOOTSTRAP_SEED)
    reference = [sum(group*10+1+rng.randrange(10) for group in range(12) for _ in range(10))/120
                 for _ in range(BOOTSTRAP_REPLICATES)]
    require(all(r['paired_delta_95_percentile_ci'] == [quantile(reference, p) for p in (.025, .975)]
                for r in variable['comparisons'])
            and len({r['replicate_statistics_sha256'] for r in variable['comparisons']}) == 1,
            'Varying-N shared stratified resampling self-test')
    paired[0][ARMS[2]]['success'] = False
    failure = paired_summary(paired, ARMS[2], 'c7')
    require(not failure['valid_full_clear_comparison'] and failure['relative_improvement_percent'] is None,
            'Failed-world exclusion self-test')
    failed_comparisons = [paired_summary(paired, a, b) for a in ARMS[2:] for b in ARMS[:2]]
    failed_boot = stratified_bootstrap(paired, failed_comparisons)
    require(all(not r['eligible'] and r['paired_delta_95_percentile_ci'] is None
                and r['relative_improvement_95_percentile_ci'] is None for r in failed_boot['comparisons'][:2])
            and all(r['eligible'] for r in failed_boot['comparisons'][2:]),
            'Failure must invalidate its complete-arm bootstrap, not silently drop the world')
    try:
        stratified_bootstrap(paired[:-1], failed_comparisons)
    except ValueError:
        pass
    else:
        raise AssertionError('Incomplete bootstrap stratum was accepted')
    paired[0][ARMS[2]]['n'] += 1
    try:
        paired_summary(paired, ARMS[2], 'c7')
    except ValueError:
        pass
    else:
        raise AssertionError('Mismatched world denominator was accepted')
    return dict(status='synthetic_saved_row_self_tests_passed', actual_environment_calls=0,
                actual_optimizer_updates=0, bootstrap_replicates=BOOTSTRAP_REPLICATES)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--phase', choices=('compatibility', 'development'), default='development')
    for name in ('campaign', 'stage', 'ledger', 'preflight', 'calibration-audit', 'compatibility-audit', 'acceptance', 'out'):
        parser.add_argument('--'+name, type=Path)
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), indent=2))
        return
    require(all(getattr(args, name) is not None for name in ('campaign', 'stage', 'ledger', 'preflight', 'calibration_audit', 'acceptance', 'out')),
            'campaign/stage/ledger/preflight/calibration-audit/acceptance/out are required')
    require(not args.out.exists(), 'Preserve prior audit output')
    result = audit(args.campaign, args.stage, args.ledger, args.preflight, args.calibration_audit,
                   args.phase, args.compatibility_audit, args.acceptance)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k: result[k] for k in ('status', 'worlds', 'actual_executions', 'actual_business_calls')}, indent=2))


if __name__ == '__main__':
    main()
