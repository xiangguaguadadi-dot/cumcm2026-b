"""Synthetic compatibility-acceptance wiring tests; no worker/model/environment.

The side-audit *contracts* below are synthetic accepted attestations. These
tests deliberately do not repeat physical-journal or frozen-forward audits.
Only the compatibility auditor is executed, with all evidence reads in memory.
"""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

import audit_round_compatibility as auditor


def typed(value):
    if isinstance(value, dict):
        return {'@': 'dict', 'v': [[k, typed(v)] for k, v in value.items()]}
    if isinstance(value, list):
        return {'@': 'list', 'v': [typed(v) for v in value]}
    return value


class Fixture:
    def __init__(self):
        self.campaign = Path('/synthetic-compatibility/campaign')
        self.stage = self.campaign / 'results/compatibility_v1'
        self.ledger = Path('/synthetic-compatibility/ledger')
        self.records_path = Path('/synthetic-compatibility/records.json')
        self.online_path = Path('/synthetic-compatibility/online.json')
        self.docs = {}
        self.worlds, self.rows, self.index, self.paid = [], [], [], []
        self.results = []
        self.c7_hash, self.checkpoint = 'c' * 64, 'd' * 64
        policy = dict(seed=912101, checkpoint_sha256=self.checkpoint, margin=.125,
                      max_interventions=2, teacher_sha256=self.c7_hash)
        self.model = dict(seed=912101, sha256=self.checkpoint, margin=.125,
                          policy_definition=policy, policy_sha256=auditor.digest(policy))
        for i in range(12):
            world = dict(world_id=f'world-{i:02d}', world_sha256=f'{i+1:064x}',
                         role='probe', index=i, group='synthetic', mode=4,
                         sources=[dict(channel=k, x=i+k, y=0) for k in range(1, 11)])
            self.worlds.append(world)
            entries = []
            for label in ('c7', 'teacher_probe'):
                run_id = f'synthetic-w{i:03d}-{label}'
                relative = f'results/compatibility_v1/runs/{run_id}.json.gz'
                is_neural = label == 'teacher_probe'
                selected_policy = 'neural_912101_teacher_forced' if is_neural else 'c7'
                metadata = dict(stage='compatibility', world_sha256=world['world_sha256'], mode=4,
                    policy='round1_neural_912101' if is_neural else 'original_c7')
                if is_neural:
                    metadata.update(policy_sha256=self.model['policy_sha256'],
                        checkpoint_sha256=self.checkpoint, force_teacher_probe=True)
                else:
                    metadata['entry_sha256'] = self.c7_hash
                self.paid.append(dict(run_id=run_id, kind='full', success=True,
                    unknown_cost=False, attempted=2, accepted=2, metadata=metadata))
                entry = {k: world[k] for k in ('world_id', 'world_sha256', 'role', 'mode', 'index', 'group')}
                entry.update(run_id=run_id, path=relative, actual_policy_id=selected_policy,
                    success=True, n=10, cleared=10, normal_exit=True, kind='full',
                    modeled_full_virtual_us=100_000_000, seconds_per_source=10.,
                    actual_execution_wall_s=.01, fallback_reason=None, error=None)
                entry['policy_sha256' if is_neural else 'entry_sha256'] = (
                    self.model['policy_sha256'] if is_neural else self.c7_hash)
                entries.append(entry)
                self.index.append(entry)
                log = [dict(action='enter', request={}, response=dict(accepted=True, mode=4)),
                       dict(action='exit', request={}, response=dict(accepted=True,
                            exit_reason='user_exit', virtual_time_s=100.))]
                # This is a contract fixture, not a physically simulated episode;
                # an independently accepted records audit is supplied below.
                result = dict(schema='bc-rpi-evaluator-outcome-v1', run_id=run_id,
                    kind='full', success=True, normal_exit=True, true_terminal_n=10,
                    cleared=10, modeled_full_virtual_us=100_000_000, seconds_per_source=10.,
                    actual_execution_wall_s=.01, environment_log=log,
                    private_terminal_sources={str(s['channel']): dict(s, cleared=True)
                                              for s in world['sources']}, extra={},
                    episode=dict(error=None, mode=4 if is_neural else None,
                        normal_exit=True, success=True, slots_remaining=2,
                        engine_final=typed(dict(used_operation_ids=[], interventions_remaining=2))))
                if is_neural:
                    result['extra'] = dict(actual_policy_id='round1_neural_912101',
                        checkpoint_sha256=self.checkpoint, policy_sha256=self.model['policy_sha256'],
                        margin=.125, force_teacher_probe=True, selector_decisions=[dict(
                            choice_id=f'choice-{i}', selected_id='a'*64, teacher_id='a'*64,
                            force_teacher_probe=True, model_scored=True, mode=4,
                            checkpoint_sha256=self.checkpoint, margin=.125)])
                self.results.append(result)
                self.put(self.campaign / relative, result)
            self.rows.append(dict(**{k: world[k] for k in ('world_id', 'world_sha256', 'role', 'index', 'group')},
                                  status='complete', runs=entries))
            self.put(self.stage/'checks'/f'w{i:03d}.json', dict(world_id=world['world_id'], checks={
                name: True for name in ('both_normal_allclear', 'exact_requests_and_observations',
                    'exact_total_virtual_us', 'same_source_denominator', 'zero_interventions',
                    'every_selector_forced_teacher', 'actual_public_neural_forward_seen')}))
        self.status = dict(current_run=None, reserved_calls=0, runs=self.paid,
                           executions_completed=24)
        self.registration = dict(world_ids=[w['world_id'] for w in self.worlds],
            policy_order=['c7', 'neural_912101_teacher_forced'], models=[self.model],
            c7_sha256=self.c7_hash, source_freeze_sha256='e'*64,
            calibration_margins_sha256='f'*64)
        self.put(self.ledger/'execution_status.json', self.status)
        self.put(self.ledger/'execution_calls.jsonl.gz', {'synthetic_journal_contract': True})
        self.put(self.campaign/'compatibility_registration.json', dict(worlds=self.worlds))
        self.put(self.stage/'registration.json', self.registration)
        self.put(self.stage/'index.json', dict(runs=self.index))
        self.put(self.stage/'world_results.json', dict(worlds=self.rows))
        self.put(self.stage/'summary.json', dict(status='compatibility_complete_exact_teacher_equivalence',
            completed_worlds=12, actual_executions=24, actual_calls=48,
            unknown_cost_calls=0, current_run=None))
        self.records = dict(status='all_recorded_business_calls_and_saved_outcomes_reconciled',
            counts=dict(business_calls=48, accepted_calls=48, executions_started=24,
                executions_completed=24, failed_runs=0, unfinished_runs=0, unresolved_calls=0,
                unknown_cost_runs=0), outcomes_checked=24,
            per_recorded_stage={'compatibility': dict(executions=24, full=24,
                business_calls=48, accepted_calls=48, failed_runs=0)},
            outcome_checks=[dict(run_id=r['run_id'], kind='full', accepted_calls=2,
                prefix_events_not_recounted=0, source_count=10, cleared=10, success=True)
                for r in self.results], source_sha256={})
        self.online = dict(status='all_saved_public_online_inputs_and_frozen_forwards_verified',
            counts=dict(neural_episodes=12, successful_forwards=12, selected_interventions=0),
            episode_checks=[dict(run_id=r['run_id'], seed=912101, forwards=1,
                                selected_interventions=0) for r in self.results[1::2]],
            source_sha256={})
        self.put(self.records_path, self.records)
        self.put(self.online_path, self.online)
        self.seal_side_audits()

    def put(self, path, value):
        self.docs[str(Path(path).resolve())] = value

    def read(self, path):
        return deepcopy(self.docs[str(Path(path).resolve())])

    def sha(self, path):
        key = str(Path(path).resolve())
        return auditor.digest(self.docs[key]) if key in self.docs else auditor.digest(key)

    def seal_side_audits(self):
        paths = [self.ledger/'execution_status.json', self.ledger/'execution_calls.jsonl.gz']
        paths += [self.campaign/e['path'] for e in self.index]
        self.records['source_sha256'] = {str(p): self.sha(p) for p in paths}
        paths = [self.stage/'registration.json', self.stage/'index.json']
        paths += [self.campaign/e['path'] for e in self.index[1::2]]
        self.online['source_sha256'] = {str(p): self.sha(p) for p in paths}

    def run(self):
        with patch.object(auditor, 'read_json', side_effect=self.read), \
                patch.object(auditor, 'sha256', side_effect=self.sha):
            return auditor.audit(self.campaign, self.stage, self.ledger,
                                 self.records_path, self.online_path)


class CompatibilityAcceptanceTests(unittest.TestCase):
    def assert_rejected(self, mutate, *, reseal=True):
        fixture = Fixture()
        # A broken positive fixture must not make every rejection vacuously pass.
        fixture.run()
        mutate(fixture)
        if reseal:
            fixture.seal_side_audits()
        with self.assertRaises((ValueError, KeyError)):
            fixture.run()

    def test_complete_contract_fixture_passes_without_executing_dependencies(self):
        result = Fixture().run()
        self.assertEqual(result['status'], '12_world_24_full_exact_teacher_equivalence_verified')
        self.assertEqual(len(result['world_checks']), 12)
        self.assertEqual(result['actual_environment_calls_by_auditor'], 0)
        self.assertEqual(result['actual_optimizer_updates_by_auditor'], 0)

    def test_rejects_failed_side_audit_status(self):
        for side in ('records', 'online'):
            with self.subTest(side=side):
                self.assert_rejected(lambda f: getattr(f, side).__setitem__('status', 'incomplete'))

    def test_rejects_stale_side_audit_source_hash(self):
        for side in ('records', 'online'):
            def mutate(f):
                sources = getattr(f, side)['source_sha256']
                sources[next(iter(sources))] = '0'*64
            with self.subTest(side=side):
                self.assert_rejected(mutate, reseal=False)

    def test_records_audit_must_bind_this_ledger_not_an_unrelated_accepted_stage(self):
        self.assert_rejected(lambda f: f.records['source_sha256'].pop(
            str(f.ledger/'execution_status.json')), reseal=False)

    def test_online_audit_must_cover_each_exact_neural_outcome(self):
        self.assert_rejected(lambda f: f.online['source_sha256'].pop(
            str(f.campaign/f.index[1]['path'])), reseal=False)

    def test_records_audit_must_cover_each_exact_paid_outcome(self):
        self.assert_rejected(lambda f: f.records['source_sha256'].pop(
            str(f.campaign/f.index[0]['path'])), reseal=False)

    def test_online_audit_missing_or_duplicate_neural_episode_rejected(self):
        for kind in ('missing', 'duplicate'):
            def mutate(f):
                checks = f.online['episode_checks']
                checks.pop() if kind == 'missing' else checks.append(deepcopy(checks[-1]))
            with self.subTest(kind=kind):
                self.assert_rejected(mutate)

    def test_duplicate_paid_run_id_not_silently_collapsed_by_dict(self):
        self.assert_rejected(lambda f: f.paid.append(deepcopy(f.paid[-1])))

    def test_paid_failure_or_unknown_cost_rejected(self):
        for key, value in (('success', False), ('unknown_cost', True)):
            with self.subTest(key=key):
                self.assert_rejected(lambda f: f.paid[1].__setitem__(key, value))

    def test_paid_actual_neural_identity_is_bound_not_only_extra_self_report(self):
        for key, value in (('policy_sha256', '0'*64), ('checkpoint_sha256', '0'*64),
                           ('force_teacher_probe', False), ('policy', 'some_other_policy')):
            with self.subTest(key=key):
                self.assert_rejected(lambda f: f.paid[1]['metadata'].__setitem__(key, value))

    def test_paid_actual_c7_identity_is_bound(self):
        for key, value in (('entry_sha256', '0'*64), ('policy', 'another_entry')):
            with self.subTest(key=key):
                self.assert_rejected(lambda f: f.paid[0]['metadata'].__setitem__(key, value))

    def test_index_world_question_and_policy_identity_all_checked(self):
        mutations = (('world_id', 'other'), ('world_sha256', '0'*64), ('role', 'fit'),
                     ('mode', 3), ('index', 99), ('group', 'other'),
                     ('actual_policy_id', 'q4_r2'), ('kind', 'suffix'))
        for key, value in mutations:
            with self.subTest(key=key):
                self.assert_rejected(lambda f: f.index[1].__setitem__(key, value))

    def test_index_metrics_cannot_disagree_with_paid_full_outcome(self):
        mutations = (('success', False), ('normal_exit', False), ('n', 11),
                     ('cleared', 9), ('modeled_full_virtual_us', 99_000_000),
                     ('seconds_per_source', 9.9), ('fallback_reason', 'unexpected'),
                     ('error', 'hidden-error'))
        for key, value in mutations:
            with self.subTest(key=key):
                self.assert_rejected(lambda f: f.index[1].__setitem__(key, value))

    def test_index_entry_and_policy_hashes_cannot_be_relabelled(self):
        self.assert_rejected(lambda f: f.index[0].__setitem__('entry_sha256', '0'*64))
        self.assert_rejected(lambda f: f.index[1].__setitem__('policy_sha256', '0'*64))

    def test_final_engine_and_episode_slots_both_remain_two(self):
        self.assert_rejected(lambda f: f.results[1]['episode'].__setitem__('engine_final',
            typed(dict(used_operation_ids=[], interventions_remaining=1))))
        self.assert_rejected(lambda f: f.results[1]['episode'].__setitem__('slots_remaining', 1))

    def test_duplicate_registered_world_id_rejected_even_with_unique_hashes(self):
        def mutate(f):
            duplicate = f.worlds[0]['world_id']
            f.worlds[-1]['world_id'] = duplicate
            f.rows[-1]['world_id'] = duplicate
            f.registration['world_ids'][-1] = duplicate
            for entry in f.rows[-1]['runs']:
                entry['world_id'] = duplicate
            f.docs[str(f.stage/'checks'/'w011.json')]['world_id'] = duplicate
        self.assert_rejected(mutate)

    def test_neural_episode_requires_q4(self):
        self.assert_rejected(lambda f: f.results[1]['episode'].__setitem__('mode', 3))

    def test_source_denominator_bound_to_registered_source_count(self):
        def mutate(f):
            for result in f.results[:2]:
                result['true_terminal_n'] = result['cleared'] = 11
            for entry in f.index[:2]:
                entry['n'] = entry['cleared'] = 11
                entry['seconds_per_source'] = 100/11
        self.assert_rejected(mutate)

    def test_reference_and_neural_run_order_cannot_be_swapped(self):
        self.assert_rejected(lambda f: f.rows[0]['runs'].reverse())


if __name__ == '__main__':
    unittest.main()
