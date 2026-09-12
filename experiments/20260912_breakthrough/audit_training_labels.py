#!/usr/bin/env python3
"""Independent saved-record audit of the shared first-round full-tail labels.

No trainer, actor, collector, or simulator is imported or executed. Business-call
and physical accounting must also pass audit_training_records.py separately.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

from audit_g1_headroom import decoded, digest, public_boundaries, uniform_indexes
from audit_rl_execution import canonical_log, read_json, require, sha256


def terminal_cost(result, prefix_us=0):
    """Only a proved terminal outcome is eligible; resource stops are not labels."""
    require(result.get('ledger_error') in (None, ''), 'Unsettled outcome ledger')
    require(not result.get('episode', {}).get('error'), 'Engineering/resource error is not a failed label')
    events = result.get('environment_log', [])
    require(bool(events), 'Missing terminal evidence')
    last = events[-1]
    require(result.get('normal_exit') is True and last.get('action') == 'exit'
            and last.get('response', {}).get('accepted') is True
            and last['response'].get('exit_reason') == 'user_exit', 'No proved accepted terminal exit')
    n, cleared, success = result.get('true_terminal_n'), result.get('cleared'), result.get('success')
    require(type(n) is int and 10 <= n <= 16 and type(cleared) is int and 0 <= cleared <= n,
            'Invalid terminal source denominator')
    require(type(success) is bool and success == (cleared == n), 'Terminal success disagrees with full clear')
    total = result.get('modeled_full_virtual_us')
    require(type(total) is int and type(prefix_us) is int and 0 <= prefix_us <= total,
            'Invalid integer full/suffix virtual cost')
    return (total - prefix_us) / (1_000_000_000 * n) + (0 if success else 100)


def verify_sampling(sampling, parent, world):
    require(sampling['world_id'] == world['world_id'] and sampling['world_sha256'] == world['world_sha256']
            and sampling['role'] == world['role'] and sampling['rollin_run_id'] == parent['run_id'],
            'Sampling world/role/origin mismatch')
    require(parent['kind'] == 'full' and parent['success'] is True, 'C7 roll-in incomplete')
    terminal_cost(parent)
    boundaries = public_boundaries(parent, after_intervention=False)
    require(sampling['all_public_source_boundary_count'] == len(boundaries)
            and len(sampling['all_public_boundaries']) == len(boundaries), 'Missing public source boundary')
    for actual, expected in zip(sampling['all_public_boundaries'], boundaries):
        require(all(actual[k] == expected[k] for k in ('source_index', 'choice_id', 'prefix_virtual_us'))
                and actual['teacher_task']['kind'] == 'source'
                and actual['teacher_task']['key'] == expected['channel'], 'Source boundary differs from actual roll-in')
    selected = uniform_indexes(len(boundaries))
    require(sampling['selected_source_indexes'] == selected, 'Sampling is not registered uniform public-index rule')
    require(sampling['zero_states_are_retained'] is True, 'Empty worlds were not retained')
    return selected, boundaries


def verify_handle(handle, world, boundary, source_index):
    unsigned = dict(handle)
    require(digest({k: v for k, v in unsigned.items() if k != 'bundle_integrity_sha256'})
            == unsigned['bundle_integrity_sha256'], 'Handle whole-bundle seal mismatch')
    token, prepared = handle['token'], handle['prepared']
    require(digest({k: v for k, v in token.items() if k != 'integrity_sha256'})
            == token['integrity_sha256'], 'Token integrity seal mismatch')
    require(handle['world_sha256'] == world['world_sha256'] and handle['source_index'] == source_index,
            'Handle world/source mismatch')
    private = decoded(handle['private'])
    require(private['seed'] == world['seed'] and private['noise'] == world['noise']
            and private['_virtual_us'] == token['prefix_virtual_us'], 'Fork seed/noise/prefix differs from registered world')
    verify_world_sources({'private_terminal_sources': private['_sources']}, world)
    require(prepared['choice_id'] == boundary['choice_id']
            and token['prefix_virtual_us'] == boundary['prefix_virtual_us']
            and prepared['pre_state_hash'] == token['semantic_pre_hash'], 'Prepared choice/pre-token/roll-in mismatch')
    inherited = decoded(token['engine_state'])
    require(inherited['used_operation_ids'] == [] and inherited['interventions_remaining'] == 2,
            'Labels were not sampled from unmodified pi0 roll-in')
    require(prepared['expanded'] is True, 'Candidate set was not fully expanded')
    choices = prepared['choices']
    ids, payloads, teacher = choices['candidate_ids'], choices['candidates'], choices['teacher_id']
    require(1 <= len(ids) <= 9 and len(ids) == len(set(ids)) and teacher in ids
            and ids == sorted(ids) and ids == [digest(p) for p in payloads], 'Retained candidate IDs/payloads mismatch')
    return prepared, token, ids, teacher


def verify_label(result, row, reference, token, payload, teacher):
    n = result['true_terminal_n']
    require(n == reference['true_terminal_n'], 'Branch changes world source denominator')
    prefix = token['prefix_virtual_us']
    suffix_cost, full_cost = terminal_cost(result, prefix), terminal_cost(result)
    reference_cost = terminal_cost(reference, prefix)
    for key, expected in (('terminal_normalized_suffix_cost', suffix_cost),
                          ('terminal_normalized_full_cost', full_cost),
                          ('paired_gain_to_A0', reference_cost - suffix_cost)):
        require(type(row.get(key)) in (int, float) and math.isfinite(row[key])
                and abs(row[key] - expected) < 1e-12, 'Wrong normalized label: ' + key)
    require(row['reference_origin_run_id'] == reference['run_id'], 'Label refers to a different A0 run')
    action_id = row['action_id']
    require(action_id == digest(payload), 'Action payload does not match label ID')
    require(result['kind'] == 'suffix' and result['run_id'] == row['run_id'], 'Not the indexed paid suffix')
    require(row['actual_slot_cost'] == int(action_id != teacher), 'Wrong intervention slot charge')
    require(row['terminal_classification'] == ('normal_complete_success' if result['success']
            else 'proven_normal_exit_incomplete_clear_failure'), 'Wrong terminal classification')
    require(row['labels'] == payload.get('labels', []), 'Operation provenance label mismatch')
    episode = result['episode']
    require(episode['prefix_virtual_us'] == prefix and episode['prefix_event_count'] == token['accepted_event_count'],
            'Suffix prefix budget/count mismatch')
    require(canonical_log(result['environment_log'][:token['accepted_event_count']])
            == canonical_log(reference['environment_log'][:token['accepted_event_count']]), 'Suffix actual prefix differs')
    first = episode['macros'][0]
    require(first['action_id'] == action_id and first['choice_id'] == row['choice_id']
            and first['payload'] == payload, 'Actual first macro differs from labeled operation')
    final = decoded(episode['engine_final'])
    require(final['used_operation_ids'] == ([] if action_id == teacher else [action_id])
            and episode['slots_remaining'] == 2 - int(action_id != teacher), 'Continuation is not exactly a + frozen C7')
    return suffix_cost, reference_cost - suffix_cost


def verify_world_sources(result, world):
    original = {str(s['channel']): {k: v for k, v in s.items() if k != 'cleared'} for s in world['sources']}
    final = {str(c): {k: v for k, v in s.items() if k != 'cleared'}
             for c, s in result['private_terminal_sources'].items()}
    require(original == final, 'Actual terminal source geometry differs from registered world')


class Audit:
    def __init__(self, campaign, stage, ledger=None):
        self.campaign, self.stage = Path(campaign).resolve(), Path(stage).resolve()
        self.ledger = Path(ledger or campaign).resolve()
        require(self.stage.is_relative_to(self.campaign / 'results'), 'Stage outside new campaign results')
        self.sources, self.results, self.indexed, self.used = {}, {}, {}, set()

    def load(self, path):
        path = Path(path).resolve()
        require(path.is_relative_to(self.campaign), 'Evidence path outside new campaign')
        self.sources[str(path)] = sha256(path)
        return read_json(path)

    def path(self, relative):
        path = (self.campaign / relative).resolve()
        require(path.is_relative_to(self.stage), 'Indexed path outside label dataset')
        return path

    def run(self):
        status_path = self.ledger / 'execution_status.json'
        status = read_json(status_path)
        self.sources[str(status_path)] = sha256(status_path)
        require(status['current_run'] is None and status['reserved_calls'] == 0, 'Active label execution')
        paid = {r['run_id']: r for r in status['runs'] if r['metadata'].get('stage') == 'labels'}
        manifest = self.load(self.campaign / 'world_manifest.json')
        worlds = [w for w in manifest['worlds'] if w['role'] in ('fit', 'fit_val')]
        require(len(worlds) == 36 and Counter(w['role'] for w in worlds) == {'fit': 24, 'fit_val': 12}
                and len({w['world_sha256'] for w in worlds}) == 36, 'Incomplete or overlapping registered fit/val worlds')
        registration = self.load(self.stage / 'registration.json')
        require(registration['world_ids'] == [w['world_id'] for w in worlds]
                and registration['shared_label_dataset_for_seeds'] == [912101, 912102, 912103]
                and registration['reference_is_A0'] is True, 'Collection registration changed')
        self.pi = digest(registration['continuation_policy'])
        require(registration['continuation_policy_sha256'] == self.pi, 'Continuation identity changed')
        world_by_hash = {w['world_sha256']: w for w in worlds}
        for indexed in self.load(self.stage / 'index.json')['runs']:
            run_id = indexed['run_id']
            require(run_id not in self.results and run_id in paid and indexed['world_sha256'] in world_by_hash,
                    'Duplicate/unregistered/unpaid run')
            result = self.load(self.path(indexed['path']))
            world = world_by_hash[indexed['world_sha256']]
            actual = paid[run_id]
            require(actual['kind'] == indexed['kind'] and actual['metadata']['world_sha256'] == world['world_sha256']
                    and actual['metadata']['mode'] == 4 and actual['success'] is result['success']
                    and actual['unknown_cost'] is False, 'Index differs from settled actual run metadata')
            if indexed['kind'] == 'suffix':
                require(actual['metadata']['policy'] == 'one_retained_operation_then_frozen_c7'
                        and all(indexed[k] == actual['metadata'][k] for k in ('action_id', 'choice_id')),
                        'Journal suffix operation/policy differs')
            else:
                require(indexed['kind'] == 'full' and actual['metadata']['policy'] == 'teacher0', 'Unexpected roll-in policy')
            require(result['run_id'] == run_id and result['kind'] == indexed['kind']
                    and indexed['mode'] == 4 and indexed['actual_policy_id'] == 'c7_pi0'
                    and indexed['continuation_policy_sha256'] == self.pi, 'Index/source policy mismatch')
            require(indexed['success'] is result['success'] and indexed['n'] == result['true_terminal_n'] == len(world['sources'])
                    and indexed['modeled_full_virtual_us'] == result['modeled_full_virtual_us']
                    and all(indexed[k] == world[k] for k in ('world_id', 'role', 'group', 'index')), 'Index changed metrics or world')
            terminal_cost(result)
            verify_world_sources(result, world)
            self.results[run_id], self.indexed[run_id] = result, indexed
        summaries = self.load(self.stage / 'world_results.json')['worlds']
        require([w['world_id'] for w in summaries] == [w['world_id'] for w in worlds], 'Dropped/reordered label worlds')
        counts = Counter()
        world_checks = []
        for world, summary in zip(worlds, summaries):
            require(summary['status'] == 'complete' and all(summary[k] == world[k] for k in
                    ('world_id', 'world_sha256', 'role', 'index', 'group')), 'Incomplete/substituted label world')
            parent_id = summary['c7_rollin_run_id']
            require(parent_id not in self.used, 'Reused roll-in for another world')
            self.used.add(parent_id)
            parent = self.results[parent_id]
            require(self.indexed[parent_id]['family'] == 'c7_rollin'
                    and self.indexed[parent_id]['world_sha256'] == world['world_sha256'], 'Wrong world roll-in')
            directory = self.stage / 'worlds' / f'{world["role"]}_w{world["index"]:03d}'
            selected, boundaries = verify_sampling(self.load(directory / 'sampling.json'), parent, world)
            require(summary['state_count'] == len(selected) == len(summary['states'])
                    and summary['zero_states_retained'] is (len(selected) == 0), 'Sampled-state count/empty world altered')
            candidate_count = failed_count = 0
            for state_index, source_index in enumerate(selected):
                dest = directory / f's{state_index:02d}'
                prepared, token, ids, teacher = verify_handle(self.load(dest / 'handle.json.gz'), world,
                    boundaries[source_index], source_index)
                bundle = self.load(dest / 'labels.json')
                before = self.load(dest / 'registration.json')
                for record in (before, bundle):
                    require(all(record[k] == world[k] for k in ('world_id', 'world_sha256', 'role'))
                            and record['state_index'] == state_index and record['source_index'] == source_index
                            and record['choice_id'] == prepared['choice_id'] and record['candidate_ids'] == ids
                            and record['teacher_id'] == teacher and record['candidate_count'] == len(ids)
                            and record['origin_rollin_run_id'] == parent_id and record['continuation_policy_sha256'] == self.pi
                            and record['prefix_virtual_us'] == token['prefix_virtual_us']
                            and record['prefix_event_count'] == token['accepted_event_count']
                            and record['shared_across_initializations'] is True
                            and record['initialization_seeds'] == [912101, 912102, 912103], 'Bundle registration/identity mismatch')
                require(before['status'] == 'registered_not_complete' and before['outcomes'] == [], 'Pre-registration is not pre-evaluation')
                require(bundle['status'] == 'complete' and bundle['terminal_n'] == len(world['sources'])
                        and [r['action_id'] for r in bundle['outcomes']] == ids, 'Incomplete or reordered candidate bundle')
                state = summary['states'][state_index]
                require(state['state_index'] == state_index and state['source_index'] == source_index
                        and state['candidate_count'] == len(ids) and state['status'] == 'complete'
                        and state['teacher_only'] is (len(ids) == 1)
                        and self.path(state['path']) == dest / 'labels.json'
                        and self.path(state['handle_path']) == dest / 'handle.json.gz', 'World-state index mismatch')
                reference_row = next(r for r in bundle['outcomes'] if r['action_id'] == teacher)
                reference = self.results[reference_row['run_id']]
                require(reference['success'] and reference['true_terminal_n'] == parent['true_terminal_n']
                        and reference['modeled_full_virtual_us'] == parent['modeled_full_virtual_us']
                        and canonical_log(reference['environment_log']) == canonical_log(parent['environment_log']),
                        'A0 complete suffix does not replay the actual full C7 roll-in')
                require(all(self.load(dest / 'a0_replay_check.json').values()), 'Recorded A0 check did not pass')
                for payload, row in zip(prepared['choices']['candidates'], bundle['outcomes']):
                    run_id = row['run_id']
                    require(run_id not in self.used, 'Actual suffix reused for different state/action')
                    self.used.add(run_id)
                    indexed, result = self.indexed[run_id], self.results[run_id]
                    require(all(row[k] == indexed[k] for k in indexed) and indexed['family'] == 'counterfactual_suffix'
                            and indexed['world_sha256'] == world['world_sha256'], 'Bundle row differs from indexed suffix')
                    verify_label(result, row, reference, token, payload, teacher)
                    failed_count += not result['success']
                    counts['nonreference_labels'] += row['action_id'] != teacher
                candidate_count += len(ids)
                counts['teacher_only_states'] += len(ids) == 1
            require(summary['candidate_count'] == candidate_count and summary['failed_branches'] == failed_count
                    and summary['n'] == parent['true_terminal_n'], 'World label counts/denominator mismatch')
            counts.update(worlds=1, states=len(selected), suffixes=candidate_count, real_failed_suffixes=failed_count,
                          zero_state_worlds=int(not selected), source_denominator=parent['true_terminal_n'])
            world_checks.append(dict(world_id=world['world_id'], role=world['role'], states=len(selected),
                candidates=candidate_count, real_failed_suffixes=failed_count, n=parent['true_terminal_n']))
        require(self.used == set(self.results) == set(paid), 'Orphan paid execution or omitted label origin')
        saved_runs = {p.resolve() for p in (self.stage / 'runs').glob('*.json.gz')}
        require(saved_runs == {self.path(r['path']) for r in self.indexed.values()}, 'Missing/extra raw run file')
        summary = self.load(self.stage / 'summary.json')
        require(summary['status'] == 'labels_complete_no_fit_yet' and summary['registered_worlds'] == 36
                and summary['completed_worlds'] == 36 and summary['actual_executions'] == len(self.results)
                and summary['real_failure_branches_retained'] == counts['real_failed_suffixes']
                and summary['current_run'] is None and summary['unknown_cost_calls'] == 0, 'Collection did not settle completely')
        for path, expected in self.sources.items():
            require(sha256(path) == expected, 'Evidence changed during audit: ' + path)
        return dict(schema='bc-rpi-round1-independent-label-audit-v1',
            status='complete_shared_first_round_labels_verified', counts=dict(counts), roles={'fit':24, 'fit_val':12},
            actual_executions_by_auditor=0, actual_neural_fit_runs_by_auditor=0,
            continuation_policy_sha256=self.pi, world_checks=world_checks,
            source_sha256=self.sources, auditor_sha256=sha256(__file__),
            evidence_limits=['Saved full-tail labels, not independent environment replay.',
                             'Must be combined with settled business-record and freeze audits.',
                             'Public feature export and fitted checkpoints require separate validation.'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--campaign', type=Path, required=True)
    p.add_argument('--stage', type=Path, required=True)
    p.add_argument('--ledger', type=Path)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    require(not a.out.exists(), 'Preserve prior audit output')
    result = Audit(a.campaign, a.stage, a.ledger).run()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('status', 'counts')}, indent=2))


if __name__ == '__main__':
    main()
