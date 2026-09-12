#!/usr/bin/env python3
"""Independent G1 saved-record audit. Imports no policy, evaluator, or environment."""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import statistics
import zipfile

import audit_rl_execution as records

require = records.require
read = records.read_json
sha256 = records.sha256
canonical_log = records.canonical_log


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def decoded(value):
    """Decode the documented typed JSON without importing implementation code."""
    if type(value) is not dict:
        require(value is None or type(value) in (str, int, bool), 'Unexpected untyped public state')
        return value
    require(set(value) == {'@', 'v'}, 'Invalid typed JSON schema')
    tag, body = value['@'], value['v']
    if tag == 'float':
        return float.fromhex(body)
    if tag == 'dict':
        pairs = [(decoded(k), decoded(v)) for k, v in body]
        result = dict(pairs)
        require(len(result) == len(pairs), 'Duplicate typed mapping keys')
        return result
    require(tag in ('list', 'tuple', 'set'), 'Unknown typed JSON tag')
    items = [decoded(v) for v in body]
    return items if tag == 'list' else tuple(items) if tag == 'tuple' else set(items)


def uniform_indexes(n):
    require(type(n) is int and n >= 0, 'Invalid source-boundary count')
    m = min(4, n)
    return [] if m == 0 else [0] if m == 1 else [k * (n - 1) // (m - 1) for k in range(m)]


def rank(result, plan):
    """Exact integer ranking within one world, equivalent to the fixed +100 loss."""
    n = result['true_terminal_n']
    require(type(n) is int and 10 <= n <= 16, 'Invalid G1 source denominator')
    cost = result['modeled_full_virtual_us'] + (0 if result['success'] else 100_000_000_000 * n)
    return cost, len(plan), tuple((p['choice_id'], p['action_id']) for p in plan)


def check_plan(result, plan):
    require(len(plan) <= 2, 'Too many planned interventions')
    state = decoded(result['episode']['engine_final'])
    require(state['used_operation_ids'] == [p['action_id'] for p in plan], 'Actual intervention history differs from plan')
    require(result['episode']['slots_remaining'] == 2 - len(plan), 'Actual intervention budget differs from plan')
    if result['kind'] == 'full':
        require(result['extra']['applied_plan'] == plan, 'Full replay did not apply the exact plan')


def check_replay(reference, replay, plan):
    require(replay['kind'] == 'full' and replay['success'], 'Selected plan lacks a successful full replay')
    require(reference['true_terminal_n'] == replay['true_terminal_n'], 'Replay changed source denominator')
    require(reference['modeled_full_virtual_us'] == replay['modeled_full_virtual_us'], 'Replay microsecond total differs')
    require(canonical_log(reference['environment_log']) == canonical_log(replay['environment_log']),
            'Replay full request/observation sequence differs')
    check_plan(replay, plan)


def public_boundaries(result, *, after_intervention):
    """Reconstruct all eligible source-entry indexes from the actual macro trace."""
    started_intervention, boundaries = False, []
    for macro in result['episode']['macros']:
        payload = macro['payload']
        kind = payload['kind']
        if kind in ('measure_override', 'clear_override'):
            started_intervention = True
            continue
        if kind != 'teacher_service' or (after_intervention and not started_intervention):
            continue
        start = macro['event_range'][0]
        prefix_us = 0 if start == 0 else round(result['environment_log'][start - 1]['response']['virtual_time_s'] * 1e6)
        boundaries.append(dict(source_index=len(boundaries), choice_id=macro['choice_id'],
                               prefix_virtual_us=prefix_us, channel=payload['channel']))
    return boundaries


def check_sampling(record, parent, phase):
    require(record['trajectory_origin_run_id'] == parent['run_id'], 'Sampling uses the wrong trajectory')
    require(record['stage'] == phase and record['after_intervention_handles_only'] is (phase == 'o2'),
            'Sampling phase/changed-trajectory contract mismatch')
    derived = public_boundaries(parent, after_intervention=phase == 'o2')
    require(record['all_public_source_boundary_count'] == len(derived), 'Source boundary count differs from actual macros')
    actual = record['all_public_boundaries']
    require(len(actual) == len(derived), 'Source boundary list incomplete')
    for left, right in zip(actual, derived):
        require(all(left[k] == right[k] for k in ('source_index', 'choice_id', 'prefix_virtual_us'))
                and left['teacher_task']['kind'] == 'source' and left['teacher_task']['key'] == right['channel'],
                'Sampling source boundary differs from actual public macro history')
    expected = uniform_indexes(len(derived))
    require(record['selected_source_indexes'] == expected, 'Sampling was not the registered public uniform rule')
    return expected, derived


class Audit:
    def __init__(self, implementation, stage):
        self.implementation = Path(implementation).resolve()
        self.stage = Path(stage).resolve()
        require(self.stage.is_relative_to(self.implementation / 'results'), 'G1 stage outside authorized result tree')
        self.sources, self.results, self.index = {}, {}, {}
        self.used_branch_ids = set()

    def load(self, path):
        path = Path(path).resolve()
        require(path.is_relative_to(self.implementation) or path.is_relative_to(self.implementation.parents[1] / 'verification'),
                'Evidence file outside implementation/verification scope')
        self.sources[str(path)] = sha256(path)
        return read(path)

    def path(self, relative):
        path = (self.implementation / relative).resolve()
        require(path.is_relative_to(self.stage), 'G1 indexed artifact points outside its frozen stage')
        return path

    def source_freeze(self):
        freeze = self.load(self.stage / 'source_freeze.json')
        archive_record = self.load(self.stage / 'source_archive.json')
        archive_path = self.stage / 'sources.zip'
        require(sha256(archive_path) == archive_record['sha256'], 'G1 source archive checksum mismatch')
        self.sources[str(archive_path)] = sha256(archive_path)
        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
            require(len(names) == len(set(names)) and set(names) == set(freeze['files']) | {'_SOURCE_ARCHIVE_MANIFEST.json'},
                    'G1 source archive member-set mismatch')
            for name, expected in freeze['files'].items():
                require(digest_bytes(archive.read(name)) == expected, 'G1 archived source bytes mismatch')
                path = (self.implementation.parents[3] / name).resolve()
                require(path.is_relative_to(self.implementation.parents[3]) and sha256(path) == expected,
                        'G1 frozen executed source drift: ' + name)
        return freeze

    def search(self, world, phase, parent, parent_plan):
        directory = self.stage / 'worlds' / f'w{world["index"]:02d}'
        sampling = self.load(directory / (phase + '_sampling.json'))
        chosen = self.load(directory / (phase + '_choice.json'))
        if phase == 'o2' and not parent_plan:
            require(sampling['status'] == 'no_first_intervention_selected'
                    and sampling['selected_source_indexes'] == [] and chosen['bundles'] == []
                    and chosen['plan'] == [] and chosen['selected_reference_run_id'] == parent['run_id']
                    and chosen['selected_modeled_full_virtual_us'] == parent['modeled_full_virtual_us'],
                    'Zero-intervention O1 incorrectly expanded or selected O2')
            return parent, [], 0, 0
        indexes, boundaries = check_sampling(sampling, parent, phase)
        require(sampling['world_sha256'] == world['world_sha256'], 'Sampling world identity mismatch')
        require(len(chosen['bundles']) == len(indexes), 'Missing sampled source bundles')
        possibilities = [(parent, list(parent_plan))]
        branch_count, failed_count = 0, 0
        for state_index, source_index in enumerate(indexes):
            bundle_path = directory / f'{phase}_s{state_index:02d}'
            registration = self.load(bundle_path / 'registration.json')
            bundle = self.load(bundle_path / 'outcomes.json')
            handle = self.load(bundle_path / 'handle.json.gz')
            unsealed = dict(handle)
            seal = unsealed.pop('bundle_integrity_sha256')
            require(digest(unsealed) == seal, 'Saved G1 handle integrity mismatch')
            prepared, token = handle['prepared'], handle['token']
            token_unsealed = dict(token)
            token_seal = token_unsealed.pop('integrity_sha256')
            require(digest(token_unsealed) == token_seal, 'Saved G1 pre-token integrity mismatch')
            inherited = decoded(token['engine_state'])
            require(inherited['used_operation_ids'] == [p['action_id'] for p in parent_plan]
                    and inherited['interventions_remaining'] == 2 - len(parent_plan),
                    'Sampled suffix did not inherit actual parent interventions and remaining slots')
            choice = prepared['choices']
            ids, payloads, teacher = choice['candidate_ids'], choice['candidates'], choice['teacher_id']
            require(ids == sorted(digest(p) for p in payloads) and ids == [digest(p) for p in payloads]
                    and len(ids) == len(set(ids)) and 1 <= len(ids) <= 9 and teacher in ids,
                    'Retained operation IDs/payloads/order are inconsistent')
            require(handle['world_sha256'] == world['world_sha256'] and handle['source_index'] == source_index,
                    'Sampled handle belongs to another world/source index')
            require(prepared['choice_id'] == boundaries[source_index]['choice_id']
                    and token['prefix_virtual_us'] == boundaries[source_index]['prefix_virtual_us'],
                    'Saved handle does not match its actual sampled parent boundary')
            prefix_events = token['accepted_event_count']
            require(prepared['pre_state_hash'] == token['semantic_pre_hash'], 'Prepared choice and pre-token disagree')
            for record in (registration, bundle):
                require(record['world_sha256'] == world['world_sha256'] and record['stage'] == phase
                        and record['state_index'] == state_index and record['source_index'] == source_index
                        and record['trajectory_origin_run_id'] == parent['run_id']
                        and record['choice_id'] == prepared['choice_id']
                        and record['candidate_ids'] == ids and record['candidate_count'] == len(ids)
                        and record['teacher_id'] == teacher and record['continuation_policy_sha256'] == self.pi,
                        'Bundle registration identity/retained-set mismatch')
            require(bundle['status'] == 'complete' and len(bundle['outcomes']) == len(ids), 'Partial action bundle ranked as complete')
            require([r['action_id'] for r in bundle['outcomes']] == ids, 'Missing/duplicate/misordered action outcomes')
            listed = chosen['bundles'][state_index]
            require(self.path(listed['directory']) == bundle_path and listed['candidate_count'] == len(ids)
                    and listed['state_index'] == state_index and listed['source_index'] == source_index
                    and listed['status'] == 'complete', 'Selected search bundle list mismatch')
            for action_id, payload, row in zip(ids, payloads, bundle['outcomes']):
                run_id = row['run_id']
                require(run_id not in self.used_branch_ids, 'Counterfactual execution was reused for distinct actions')
                self.used_branch_ids.add(run_id)
                result, indexed = self.results[run_id], self.index[run_id]
                require(result['kind'] == 'suffix' and indexed['family'] == phase + '_counterfactual'
                        and indexed['world_sha256'] == world['world_sha256']
                        and indexed['action_id'] == action_id and indexed['choice_id'] == prepared['choice_id'],
                        'Bundle outcome points to a different action execution')
                require(all(row[k] == indexed[k] for k in indexed), 'Bundle saved row differs from the stage index')
                require(result['true_terminal_n'] == parent['true_terminal_n'], 'Counterfactual changes terminal N')
                require(result['episode']['prefix_event_count'] == prefix_events
                        and result['episode']['prefix_virtual_us'] == token['prefix_virtual_us'], 'Counterfactual prefix mismatch')
                require(canonical_log(result['environment_log'][:prefix_events])
                        == canonical_log(parent['environment_log'][:prefix_events]), 'Counterfactual uses a different parent history')
                first = result['episode']['macros'][0]
                require(first['choice_id'] == prepared['choice_id'] and first['action_id'] == action_id
                        and first['payload'] == payload, 'First counterfactual macro is not the retained operation')
                expected_plan = list(parent_plan)
                if action_id != teacher:
                    expected_plan.append(dict(choice_id=prepared['choice_id'], action_id=action_id,
                                              source_index=source_index, kind=payload['kind'], labels=payload.get('labels', [])))
                require(row['plan'] == expected_plan, 'Counterfactual plan does not extend the actual parent plan')
                check_plan(result, expected_plan)
                expected_gain = (rank(parent, parent_plan)[0] - rank(result, expected_plan)[0]) / (1_000_000_000 * parent['true_terminal_n'])
                require(abs(row['paired_gain_to_current_reference'] - expected_gain) < 1e-12, 'Counterfactual gain normalization/penalty mismatch')
                if action_id == teacher:
                    require(result['success'] and rank(result, expected_plan) == rank(parent, parent_plan)
                            and canonical_log(result['environment_log']) == canonical_log(parent['environment_log']),
                            'A0 complete continuation differs from its actual parent trajectory')
                possibilities.append((result, expected_plan))
                branch_count += 1
                failed_count += not result['success']
        winner, plan = min(possibilities, key=lambda pair: rank(*pair))
        require(chosen['selected_reference_run_id'] == winner['run_id'] and chosen['plan'] == plan
                and chosen['selected_modeled_full_virtual_us'] == winner['modeled_full_virtual_us'],
                'Finite oracle selection differs from complete enumerated integer-cost minimum')
        return winner, plan, branch_count, failed_count

    def run(self, ledger_directory):
        record_audit = records.audit(self.implementation, self.stage, ledger_directory=ledger_directory)
        self.sources.update(record_audit['source_sha256'])
        freeze = self.source_freeze()
        registration = self.load(self.stage / 'registration.json')
        input_archive = self.load(self.stage / 'input_archive.json')
        input_zip = self.stage / 'inputs.zip'
        require(sha256(input_zip) == input_archive['sha256'], 'G1 input archive checksum mismatch')
        self.sources[str(input_zip)] = sha256(input_zip)
        with zipfile.ZipFile(input_zip) as archive:
            require(set(archive.namelist()) == set(registration['inputs']) | {'_SOURCE_ARCHIVE_MANIFEST.json'},
                    'G1 input archive member-set mismatch')
            for name, expected_hash in registration['inputs'].items():
                path = (self.implementation.parents[3] / name).resolve()
                require(path.is_relative_to(self.implementation.parents[3])
                        and sha256(path) == expected_hash and digest_bytes(archive.read(name)) == expected_hash,
                        'G1 registered input or archived input bytes changed')
                self.sources[str(path)] = expected_hash
        probes = self.load(self.implementation / 'evaluator/probes_v1.json')['worlds']
        expected = [w for w in probes if w['phase'] == 'g1']
        require(len(expected) == 24 and [w['index'] for w in expected] == list(range(24))
                and all(w['mode'] == 4 for w in expected) and len({w['world_sha256'] for w in expected}) == 24,
                'Registered G1 world coverage is not the frozen 24 unique Q4 worlds')
        require(registration['world_ids'] == [w['world_id'] for w in expected]
                and registration['world_content_hashes'] == [w['world_sha256'] for w in expected]
                and registration['world_count'] == 24, 'G1 substituted/reordered registered worlds')
        self.pi = digest(registration['continuation_policy'])
        require(registration['continuation_policy_sha256'] == self.pi
                and registration['continuation_policy']['deploy_implementation_sha256'] == freeze['deploy_implementation_sha256'],
                'Continuation policy identity mismatch')
        journal_path = Path(ledger_directory) / 'execution_calls.jsonl.gz'
        journal = [json.loads(line) for line in gzip.decompress(journal_path.read_bytes()).splitlines() if line.strip()]
        _, campaign_runs = records.audit_journal(journal)
        indexed = self.load(self.stage / 'index.json')
        require(indexed['schema'] == 'bc-rpi-g1-run-index-v1', 'Unknown G1 index schema')
        worlds_by_hash = {w['world_sha256']: w for w in expected}
        for row in indexed['runs']:
            run_id = row['run_id']
            require(run_id not in self.results and run_id in campaign_runs, 'Duplicate or fictitious G1 execution')
            result = self.load(self.path(row['path']))
            start = campaign_runs[run_id]['start']
            world = worlds_by_hash[row['world_sha256']]
            require(row['run_id'] == result['run_id'] and row['kind'] == result['kind'] == start['kind']
                    and row['policy'] == start['metadata']['policy'] and row['world_sha256'] == start['metadata']['world_sha256']
                    and row['mode'] == start['metadata']['mode'] == 4
                    and row['continuation_policy_sha256'] == start['metadata']['continuation_policy_sha256'] == self.pi,
                    'G1 index/result/journal identity mismatch')
            require(row['success'] is result['success'] and row['n'] == result['true_terminal_n'] == len(world['sources'])
                    and row['modeled_full_virtual_us'] == result['modeled_full_virtual_us']
                    and row['seconds_per_source'] == result['seconds_per_source']
                    and row['group'] == world['group'] and row['index'] == world['index'] and row['world_id'] == world['world_id'],
                    'G1 index changed outcome metrics or registered world fields')
            expected_cost = rank(result, [])[0] / (1_000_000_000 * result['true_terminal_n'])
            require(abs(row['normalized_cost_with_failure_penalty'] - expected_cost) < 1e-12, 'Indexed failure penalty/normalization mismatch')
            if result['kind'] == 'suffix':
                require(row['choice_id'] == start['metadata']['choice_id']
                        and row['action_id'] == start['metadata']['action_id'], 'Indexed suffix action differs from actual journal')
            original_sources = {str(s['channel']): {k: v for k, v in s.items() if k != 'cleared'} for s in world['sources']}
            final_sources = {str(c): {k: v for k, v in s.items() if k != 'cleared'} for c, s in result['private_terminal_sources'].items()}
            require(original_sources == final_sources, 'Counterfactual terminal world differs from frozen recipe')
            self.index[run_id], self.results[run_id] = row, result
        stage_runs = {key for key, run in campaign_runs.items() if run['start']['metadata'].get('stage') == self.stage.name}
        require(set(self.results) == stage_runs, 'G1 stage omitted a paid execution outcome')
        world_rows = self.load(self.stage / 'world_results.json')['worlds']
        require(len(world_rows) == 24 and len({r['index'] for r in world_rows}) == 24
                and {r['index'] for r in world_rows} == set(range(24)), 'Incomplete or duplicate registered world status ledger')
        findings = []
        for row in world_rows:
            world = expected[row['index']]
            require(row['world_id'] == world['world_id'] and row['world_sha256'] == world['world_sha256']
                    and row['group'] == world['group'], 'World result identity mismatch')
            if row['status'] != 'complete':
                require(row['status'] in ('incomplete_budget', 'incomplete_engineering', 'not_started_budget', 'not_started_after_failure'),
                        'Unknown incomplete-world status')
                continue
            baseline = self.results[row['c7_run_id']]
            require(baseline['success'] and baseline['kind'] == 'full'
                    and self.index[baseline['run_id']]['family'] == 'c7_rollin', 'Invalid C7 roll-in reference')
            check_plan(baseline, [])
            one, plan1, branches1, fail1 = self.search(world, 'o1', baseline, [])
            replay1 = self.results[row['o1_replay_run_id']]
            check_replay(one, replay1, plan1)
            two, plan2, branches2, fail2 = self.search(world, 'o2', replay1, plan1)
            replay2 = self.results[row['o2_replay_run_id']]
            check_replay(two, replay2, plan2)
            require(all(self.index[r['run_id']]['world_sha256'] == world['world_sha256'] for r in (baseline, replay1, replay2))
                    and self.index[replay1['run_id']]['family'] == 'o1_full_replay'
                    and self.index[replay2['run_id']]['family'] == 'o2_full_replay', 'World references another world or wrong replay family')
            require(row['o1_plan'] == plan1 and row['o2_plan'] == plan2
                    and row['o1_branches'] == branches1 and row['o2_branches'] == branches2
                    and row['failed_branches'] == fail1 + fail2, 'World oracle plan/branch counts mismatch')
            for label, result in (('c7', baseline), ('o1', replay1), ('o2', replay2)):
                require(row[label + '_total_virtual_us'] == result['modeled_full_virtual_us']
                        and row[label + '_seconds_per_source'] == result['seconds_per_source'], 'World metric differs from complete actual replay')
            findings.append(dict(index=world['index'], world_sha256=world['world_sha256'], n=baseline['true_terminal_n'],
                c7=baseline['seconds_per_source'], o1=replay1['seconds_per_source'], o2=replay2['seconds_per_source'],
                o1_interventions=len(plan1), o2_interventions=len(plan2), complete_branches=branches1 + branches2,
                branch_failures=fail1 + fail2))
        summary = self.load(self.stage / 'summary.json')
        all_complete = len(findings) == 24
        if all_complete:
            require(self.used_branch_ids == {run_id for run_id, row in self.index.items() if row['kind'] == 'suffix'}
                    and sum(row['kind'] == 'full' for row in self.index.values()) == 72,
                    'Complete G1 set contains omitted/extra counterfactual or full replay runs')
            means = {key: statistics.mean(r[key] for r in findings) for key in ('c7', 'o1', 'o2')}
            gains = {key: 100 * (1 - means[key] / means['c7']) for key in ('o1', 'o2')}
            expected_status = 'positive_finite_headroom_stop_before_g2' if max(gains.values()) >= 2 else 'below_2pct_stop_current_action_space'
            conclusion = summary['conclusion']
            require(summary['status'] == conclusion['status'] == expected_status, 'G1 whole-set decision differs from exact means')
            require(all(abs(conclusion['whole_set_means'][k + '_seconds_per_source'] - means[k]) < 1e-10 for k in means)
                    and all(abs(conclusion[k + '_relative_improvement_pct'] - gains[k]) < 1e-10 for k in gains),
                    'G1 aggregate means/relative denominator mismatch')
            require(conclusion['total_source_count'] == sum(r['n'] for r in findings), 'G1 source denominator sum mismatch')
        else:
            means, gains = None, None
            require(summary['conclusion']['whole_set_means'] is None
                    and summary['conclusion']['status'] == 'inconclusive_incomplete_registered_world_set',
                    'Partial registered set incorrectly reports headroom/no-headroom')
        counts = record_audit['counts']
        require(summary['actual_calls_this_stage'] == counts['business_calls'] - registration['initial_cumulative_calls']
                and summary['actual_executions_this_stage'] == counts['executions_started'] - registration['initial_cumulative_executions'],
                'G1 stage cost silently excluded actual paid work')
        return dict(schema='bc-rpi-independent-g1-headroom-audit-v1',
            status='complete_24_world_finite_headroom_audited' if all_complete else 'partial_set_records_audited_headroom_undecided',
            scope='Saved exact operation/continuation/replay evidence; independently reconstructed sampling, finite minima and world-equal means. No policy/environment execution.',
            registered_worlds=24, fully_audited_complete_worlds=len(findings), outcomes_checked=len(self.results),
            means_seconds_per_source=means, relative_improvement_pct=gains, worlds=findings,
            cumulative_counts=counts, g1_actual_calls=summary['actual_calls_this_stage'],
            g1_actual_executions=summary['actual_executions_this_stage'],
            not_a_learned_policy=True, o2_not_global_two_intervention_optimum=True,
            no_new_training_authority=True, source_sha256=self.sources,
            auditor_sha256=sha256(__file__), record_auditor_sha256=sha256(records.__file__))


def digest_bytes(value):
    return hashlib.sha256(value).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--implementation', required=True, type=Path)
    p.add_argument('--stage', required=True, type=Path)
    p.add_argument('--ledger-directory', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    args = p.parse_args()
    require(not args.out.exists(), 'Preserve existing G1 audit output')
    result = Audit(args.implementation, args.stage).run(args.ledger_directory)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('status', 'fully_audited_complete_worlds', 'outcomes_checked',
                    'means_seconds_per_source', 'relative_improvement_pct', 'g1_actual_calls')}, indent=2))


if __name__ == '__main__':
    main()
