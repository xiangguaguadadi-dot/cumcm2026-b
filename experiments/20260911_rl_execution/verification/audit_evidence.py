#!/usr/bin/env python3
"""Read-only, standard-library audit of the registered RL evidence.

No simulator/policy import, world construction, checkpoint deserialization,
training, recovery, deletion, or ledger repair occurs here. Missing future
results are pending unless a completed stage claims to contain them.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import time

VERSION = 'rl-evidence-audit-v1'
POINTS = [128, 256, 512, 1024]
TOL = 2e-5
NO_EXPECTATION = object()
SNAPSHOT_KEYS = {'candidate_features', 'candidate_ids', 'candidates',
    'channel_features', 'decision_id', 'generator_version', 'global_features',
    'observable_state', 'schema_version', 'state_version', 'teacher_index', 'valid_mask'}
PRIVILEGED_KEYS = {'n', 'true_n', 'source_count', 'total_sources', 'sources',
    'source_truth', 'true_sources', 'ground_truth', 'world_id', 'recipe', 'seed',
    'terminal_labels', 'stats', 'reward', 'rewards', 'previous_reward',
    'normalized_reward', 'normalized_return', 'return_target', 'mc_return'}
SEMANTIC_RESPONSE_OMISSIONS = {'real_timestamp_ms', 'remaining_real_duration_s'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def close(a, b, tol=TOL):
    return finite(a) and finite(b) and abs(a - b) <= tol + 1e-10 * max(abs(a), abs(b))


def forbidden_paths(value, prefix=''):
    if isinstance(value, dict):
        for key, item in value.items():
            path = prefix + '/' + str(key)
            if str(key).lower() in PRIVILEGED_KEYS:
                yield path
            yield from forbidden_paths(item, path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from forbidden_paths(item, prefix + '/' + str(index))


def semantic_event(event):
    return dict(action=event['action'], request=event['request'],
        response={key: value for key, value in event['response'].items()
            if key not in SEMANTIC_RESPONSE_OMISSIONS})


class Audit:
    def __init__(self, root, archives=False, require_complete=False):
        self.root = Path(root).resolve()
        self.archives = archives
        self.require_complete = require_complete
        self.findings = []
        self.counts = Counter()
        self.fail_counts = Counter()
        self.tracked = {}
        self.hashes = {}
        self.registered = {}
        self.stages = {}
        self.storage_refs = {}
        self.archive_seen = set()
        self.archive_checks = Counter()
        self.unknown_costs = []
        self.known_orphans = []
        self.model_records = {}
        self.trajectory_inventory = {}
        self.executed_world_ids = set()
        self.selection_traces = defaultdict(dict)
        self.started = time.monotonic()

    def rel(self, path):
        try:
            return str(Path(path).resolve().relative_to(self.root))
        except ValueError:
            return str(path)

    def finding(self, level, code, location, detail):
        self.fail_counts[(level, code)] += 1
        # Preserve totals and bound duplicate detail size for a corrupt archive.
        if self.fail_counts[(level, code)] <= 30:
            self.findings.append(dict(level=level, code=code,
                location=str(location), detail=detail))

    def check(self, condition, code, location, detail):
        self.counts[code] += 1
        if not condition:
            self.finding('error', code, location, detail)
        return bool(condition)

    def pending(self, code, location, detail):
        self.finding('pending', code, location, detail)

    def resolve(self, value, base=None):
        path = Path(value)
        path = path if path.is_absolute() else (base or self.root) / path
        path = path.resolve()
        if not path.is_relative_to(self.root):
            raise ValueError('Evidence path escapes execution root: ' + str(path))
        return path

    def read_bytes(self, path):
        path = Path(path)
        before = path.stat()
        data = path.read_bytes()
        after = path.stat()
        stamp = (before.st_size, before.st_mtime_ns, before.st_ino)
        if stamp != (after.st_size, after.st_mtime_ns, after.st_ino):
            self.pending('input_changed_during_read', self.rel(path), 'Retry after writers finish.')
        self.tracked.setdefault(path, stamp)
        return data

    def json(self, path, required=False):
        path = Path(path)
        if not path.exists():
            method = self.finding if required else self.pending
            if required:
                method('error', 'missing_required_file', self.rel(path), 'Required evidence is missing.')
            else:
                method('missing_future_file', self.rel(path), 'Not produced yet.')
            return None
        try:
            return json.loads(self.read_bytes(path), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
        except (OSError, ValueError) as exc:
            self.finding('error', 'invalid_json', self.rel(path), str(exc))
            return None

    def rows(self, path):
        path = Path(path)
        if not path.exists():
            return []
        try:
            data = self.read_bytes(path)
        except OSError as exc:
            self.finding('error', 'ledger_read', self.rel(path), str(exc))
            return []
        rows = []
        lines = data.splitlines()
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                row = json.loads(line, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
                if not isinstance(row, dict):
                    raise ValueError('Row must be an object')
                rows.append(row)
            except ValueError as exc:
                if i == len(lines) - 1 and not data.endswith(b'\n'):
                    self.pending('partial_last_ledger_line', self.rel(path), 'Writer may be appending: ' + str(exc))
                else:
                    self.finding('error', 'invalid_ledger_line', f'{self.rel(path)}:{i+1}', str(exc))
        return rows

    def hash_file(self, path, expected=NO_EXPECTATION):
        path = Path(path)
        if not self.check(path.is_file(), 'referenced_file_exists', self.rel(path), 'Missing referenced file.'):
            return None
        before = path.stat()
        h = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                h.update(block)
        self.tracked.setdefault(path, (before.st_size, before.st_mtime_ns, before.st_ino))
        value = h.hexdigest()
        self.hashes[self.rel(path)] = value
        if expected is not NO_EXPECTATION:
            self.check(isinstance(expected, str) and bool(re.fullmatch('[0-9a-f]{64}', expected)),
                'expected_sha256_schema', self.rel(path), expected)
            self.check(value == expected, 'file_sha256', self.rel(path), {'expected': expected, 'actual': value})
        return value

    def inventory(self, path, storage=None, actual=None):
        """Digest provenance stays explicit in the portable evidence inventory."""
        path = self.resolve(path)
        storage = storage or {}
        record = dict(path=self.rel(path), local_only_trajectory=True,
            exists=path.is_file(), bytes=path.stat().st_size if path.is_file() else None,
            sha256=storage.get('sha256'), content_sha256=storage.get('content_sha256'),
            raw_json_bytes=storage.get('raw_json_bytes'),
            digest_status='saved_index_not_recomputed' if storage.get('sha256') else 'not_read_metadata_only')
        if actual:
            record.update(actual)
            record['digest_status'] = 'recomputed_from_file_bytes'
        self.trajectory_inventory[self.rel(path)] = record

    def register(self, recipes, scope, count=None):
        if not isinstance(recipes, list):
            self.check(False, 'recipe_list', scope, 'Recipes must be a list.')
            return []
        if count is not None:
            self.check(len(recipes) == count, 'registered_world_count', scope,
                {'expected': count, 'actual': len(recipes)})
        ids = []
        for i, recipe in enumerate(recipes):
            where = f'{scope}[{i}]'
            try:
                wid = recipe['world_id']
                version = wid.split(':')[0]
                expected = f"{version}:{recipe['split']}:q{recipe['mode']}:{recipe['index']:05d}"
                self.check(wid == expected and recipe['mode'] in (3, 4), 'recipe_identity', where, recipe)
                self.check(type(recipe['seed']) is int, 'recipe_seed_type', where, recipe.get('seed'))
                self.check(wid not in self.registered, 'world_registration_unique', where, wid)
                self.registered[wid] = recipe
                ids.append(wid)
            except (KeyError, TypeError, ValueError) as exc:
                self.check(False, 'recipe_schema', where, str(exc))
        return ids

    def registries(self):
        initial = self.json(self.root / 'data/initial_registry.json', required=True) or {}
        plan = self.json(self.root / 'data/g2_plan.json', required=True) or {}
        initial_worlds = initial.get('worlds', [])
        self.register(initial_worlds, 'initial_registry', 64)
        self.register(plan.get('demonstrations', []), 'g2/demonstrations', 512)
        seeds = plan.get('initialization_seeds', [])
        self.check(len(seeds) == len(set(seeds)) == 3, 'initializations', 'g2_plan', seeds)
        for seed in seeds:
            self.register(plan.get('training', {}).get(str(seed), []), f'g2/train/{seed}', 1024)
        self.register(plan.get('selection', []), 'g2/selection', 192)
        self.check(Counter(r.get('mode') for r in plan.get('selection', [])) == {3: 96, 4: 96},
            'selection_question_denominators', 'g2_plan', 'Exactly 96 registered worlds per question.')
        protocol = plan.get('selection_protocol', {})
        self.check(protocol.get('worlds') == 192 and protocol.get('worlds_per_question') == 96
            and protocol.get('checkpoints_per_algorithm_init') == 4, 'selection_registered_budget', 'g2_plan', protocol)
        all_seeds = [r.get('seed') for r in self.registered.values()]
        self.check(len(all_seeds) == len(set(all_seeds)), 'registered_seed_disjointness', 'all_registries',
            'G0/G1/demo/train/selection recipe seeds must be distinct across registered worlds.')
        self.check(initial.get('final_worlds_generated') == 0 and plan.get('final_test_worlds_generated') == 0,
            'no_final_test_declared', 'registries', 'This run must remain development/selection evidence.')
        for algorithm in ('ppo', 'q'):
            cfg = plan.get(algorithm, {})
            self.check(cfg.get('max_new_episodes_per_init') == 1024 and cfg.get('max_business_calls_per_init') == 1000000,
                'registered_training_caps', algorithm, cfg)
            self.check(cfg.get('checkpoint_episodes') == POINTS, 'registered_checkpoint_positions', algorithm, cfg)
        self.check(plan.get('complete_episode_call_reserve') == 15846, 'registered_completion_reserve', 'g2_plan', plan.get('complete_episode_call_reserve'))
        self.check({'shared.py', 'core/engine.py', 'core/schema.py', 'data/worlds.py'} <= set(plan.get('code_sha256', {})),
            'registered_runtime_hash_coverage', 'g2_plan', sorted(plan.get('code_sha256', {})))
        physics = self.json(self.root / 'data/runtime_dependency_freeze.json', required=True) or {}
        amendment = physics.get('plan_orchestration_amendment')
        allowed_historical_orchestration_changes = {'runners/common.py', 'runners/collect_demo.py'}
        for name, expected in plan.get('code_sha256', {}).items():
            try:
                current = self.hash_file(self.resolve(name))
                if current != expected and name in allowed_historical_orchestration_changes and amendment:
                    self.finding('note', 'disclosed_historical_orchestration_amendment', name,
                        {'original_plan_sha256': expected, 'current_sha256': current,
                        'declaration': amendment,
                        'current_binding': 'Actual common/runner runtime is checked against every initialization manifest; original plan remains unchanged.'})
                else:
                    self.check(current == expected, 'plan_algorithm_or_runtime_sha256', name,
                        {'expected': expected, 'actual': current})
            except (OSError, ValueError) as exc:
                self.check(False, 'registered_code_path', name, str(exc))
        repo = self.root.parents[1]
        self.check({'local_env.py', 'evaluation/manifest_v1.json'} <= set(physics.get('files', {})),
            'physical_dependency_hash_coverage', 'runtime_dependency_freeze', sorted(physics.get('files', {})))
        for file, expected in physics.get('files', {}).items():
            path = (repo / file).resolve()
            self.check(path.is_relative_to(repo), 'dependency_path_within_repo', file, str(path))
            if path.is_relative_to(repo):
                self.hash_file(path, expected)
        gate_paths = {'core_g0': 'core/g0_results_v1/summary.json',
            'core_reordered_g0': 'core/g0_audit_v1/summary.json',
            'resource_g1': 'results/g1_pipeline_v1/summary.json'}
        for gate, expected in plan.get('gates', {}).items():
            if gate in gate_paths:
                self.hash_file(self.root / gate_paths[gate], expected)
        self.plan = plan
        self.initial = initial
        self.stages['registration'] = dict(unique_registered_worlds=len(self.registered),
            selection_unique_worlds=len(plan.get('selection', [])), initialization_seeds=seeds,
            old_seed_overlap='Registry declarations read; historical corpora are not re-instantiated or independently re-mined.')

    def stats(self, stats, success, where):
        n, cleared, total = stats.get('n'), stats.get('cleared'), stats.get('time_s')
        self.check(type(n) is int and n > 0 and type(cleared) is int and 0 <= cleared <= n,
            'terminal_denominators', where, {'n': n, 'cleared': cleared})
        self.check(finite(total) and total >= 0, 'terminal_time', where, total)
        if type(n) is int and n > 0 and type(cleared) is int:
            self.check(close(stats.get('fraction'), cleared / n), 'terminal_fraction', where, stats.get('fraction'))
        if type(cleared) is int and cleared > 0 and finite(total):
            self.check(close(stats.get('average_s'), total / cleared), 'terminal_average', where, stats.get('average_s'))
        elif cleared == 0:
            self.check(stats.get('average_s') is None, 'zero_clear_average_null', where, stats.get('average_s'))
        if success:
            self.check(cleared == n, 'success_means_all_cleared', where, {'n': n, 'cleared': cleared})

    def snapshot(self, snapshot, previous_delta, decision, where):
        self.archive_checks['snapshots'] += 1
        self.check(set(snapshot) == SNAPSHOT_KEYS, 'online_snapshot_keys', where,
            {'extra': sorted(set(snapshot) - SNAPSHOT_KEYS), 'missing': sorted(SNAPSHOT_KEYS - set(snapshot))})
        leaks = list(forbidden_paths(snapshot))
        self.check(not leaks, 'no_privileged_online_keys', where, leaks[:20])
        candidates = snapshot.get('candidates', [])
        ids = snapshot.get('candidate_ids', [])
        mask = snapshot.get('valid_mask', [])
        features = snapshot.get('candidate_features', [])
        glob = snapshot.get('global_features', [])
        channels = snapshot.get('channel_features', [])
        count = len(candidates)
        if not self.check(1 <= count <= 64 and len(ids) == len(mask) == len(features) == count
                and len(glob) == 16 and len(channels) == 20 and all(len(x) == 12 for x in channels)
                and all(len(x) == 16 for x in features), 'feature_shapes', where, {'candidates': count}):
            return
        self.check(all(finite(x) for row in [glob, *channels, *features] for x in row), 'finite_online_features', where, 'All numerical features must be finite.')
        self.check(ids == sorted(set(ids)), 'candidate_ids_sorted_unique', where, ids)
        self.check(all(type(x) is bool for x in mask) and any(mask), 'candidate_mask', where, mask)
        index = decision.get('index')
        valid_index = type(index) is int and 0 <= index < count
        self.check(valid_index and mask[index] and decision.get('candidate_id') == ids[index],
            'chosen_candidate_identity', where, index)
        self.check(type(snapshot.get('teacher_index')) is int and 0 <= snapshot['teacher_index'] < count,
            'teacher_index_valid', where, snapshot.get('teacher_index'))
        state = snapshot.get('observable_state', {})
        self.check(snapshot.get('state_version') == digest(canonical(state)), 'observable_state_hash', where, snapshot.get('state_version'))
        for i, payload in enumerate(candidates):
            self.archive_checks['candidate_payloads'] += 1
            self.check(ids[i] == digest(canonical(payload))[:24], 'candidate_payload_hash', where + f'/candidate/{i}', ids[i])
            self.check(payload.get('state_version') == snapshot.get('state_version'), 'candidate_state_binding', where, ids[i])
        # Specifically rule out the normalized T/N reward as previous input.
        self.check(close(glob[15], previous_delta / 10000., 1e-10), 'previous_macro_physical_seconds', where,
            {'saved': glob[15], 'expected': previous_delta / 10000.})
        try:
            cleared = set(state['cleared'])
            known = cleared | {int(ch) for ch, obs in state['observations'].items() if obs}
            expected = {0: float(state['mode'] == 3), 1: float(state['mode'] == 4),
                2: state['position'][0] / 4000., 3: state['position'][1] / 4000., 4: state['channel'] / 20.,
                5: state['virtual_time'] / 360000., 7: len(cleared) / 20., 8: len(known) / 20.,
                9: (20 - len(known)) / 20., 10: len(state['todo']) / 49., 13: snapshot['decision_id'] / 10000.}
            self.check(all(close(glob[i], v, 1e-9) for i, v in expected.items()), 'observable_global_features', where,
                'Rebuilt observable counts, physical time, position, and decision index.')
            for i, payload in enumerate(candidates):
                source, station = payload['kind'] == 'source', payload['kind'] == 'station'
                target, ch, succ = payload['target'], payload['channel'], payload['route_successor']
                dist = math.dist(state['position'], target)
                cost = dist / 5. + (5 + int(ch != state['channel']) if source else 6 * (20 - len(known)) if station else 53000.)
                expected_features = {0: float(source), 1: float(station), 2: float(payload['kind'] == 'fallback'),
                    3: (ch or 0) / 20., 4: (payload['index'] if station else 0) / 49.,
                    5: target[0] / 4000., 6: target[1] / 4000., 7: dist / (8000 * math.sqrt(2)),
                    8: cost / 10000., 10: len(state['observations'][str(ch)]) / 64. if source else 0.,
                    11: (20 - len(known)) / 20., 12: succ[0] / 4000. if succ else 0.,
                    13: succ[1] / 4000. if succ else 0., 14: float(succ is not None)}
                self.check(all(close(features[i][j], v, 1e-9) for j, v in expected_features.items()),
                    'observable_candidate_features', where + f'/candidate/{i}', 'Observable candidate feature reconstruction.')
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            self.check(False, 'observable_feature_schema', where, str(exc))

    def raw_episode(self, raw, stats, success, attempted, where, teacher=False):
        if raw is None:
            self.finding('warning', 'unrecoverable_raw_failure', where, 'Executed failure retained; raw trajectory unavailable.')
            self.check(not success, 'missing_raw_cannot_succeed', where, success)
            return
        if 'events' not in raw:
            # Historical/original C7 has a different raw schema.
            if 'virtual_time_s' in raw:
                self.check(close(raw['virtual_time_s'], stats.get('time_s')), 'original_c7_terminal_time', where, raw['virtual_time_s'])
            self.archive_checks['original_c7_without_core_events'] += 1
            return
        self.check(raw.get('success') == success and raw.get('terminal') == ('success' if success else 'failure'),
            'core_terminal_labels', where, {'core': raw.get('terminal'), 'evaluator_success': success})
        events = raw.get('events', [])
        self.event_physics(events, stats, where)
        decisions = raw.get('decisions', [])
        accepted = raw.get('business_primitive_count')
        self.check(accepted == len(events) and type(attempted) is int and accepted <= attempted,
            'accepted_attempted_counts', where, {'events': len(events), 'core': accepted, 'attempted': attempted})
        deltas = [e.get('delta_time_s') for e in events]
        self.check(all(finite(x) and x >= -TOL for x in deltas), 'event_costs_finite_nonnegative', where, 'Bad event cost.')
        if all(finite(x) for x in deltas):
            self.check(close(sum(deltas), stats.get('time_s')) and close(raw.get('total_time_s'), stats.get('time_s')),
                'event_terminal_cost', where, {'sum_events': sum(deltas), 'terminal': stats.get('time_s')})
        self.check([e.get('index') for e in events] == list(range(len(events))), 'event_index_order', where, 'Event index must be contiguous.')
        last_end = 0
        previous_delta = 0.
        for i, decision in enumerate(decisions):
            scope = where + f'/decision/{i}'
            snapshot = decision.get('snapshot', {})
            self.snapshot(snapshot, previous_delta, decision, scope)
            start, end = decision.get('event_range', [-1, -1])
            self.check(type(start) is int and type(end) is int and 0 <= start <= end <= len(events) and start >= last_end,
                'macro_event_range', scope, [start, end])
            if type(start) is int and type(end) is int and 0 <= start <= end <= len(events):
                self.check(close(decision.get('delta_time_s'), sum(deltas[start:end])), 'macro_event_cost', scope, decision.get('delta_time_s'))
                last_end = end
            if teacher:
                self.check(decision.get('index') == snapshot.get('teacher_index'), 'demonstration_teacher_action', scope, decision.get('index'))
            previous_delta = decision.get('delta_time_s', 0.)
        partition = raw.get('prefix_time_s', 0.) + raw.get('tail_time_s', 0.) + sum(d.get('delta_time_s', 0.) for d in decisions)
        self.check(close(partition, stats.get('time_s')) and close(raw.get('cost_partition_error_s'), 0.),
            'prefix_macro_tail_partition', where, {'partition': partition, 'terminal': stats.get('time_s')})
        if success:
            self.check(raw.get('normal_exit') is True and raw.get('observed_completion_certified') is True,
                'success_exit_certificate', where, 'Success requires observed certificate and normal exit.')
        if teacher:
            self.check(raw.get('fallback_reason') is None and not raw.get('controller_recoveries'),
                'demonstration_pure_teacher', where, 'Shared demonstrations may not include fallback/recovery.')

    def event_physics(self, events, stats, where):
        """Recompute paid movement/switch/action costs from saved interface data."""
        position, channel = (0., 0.), 1
        previous_time = 0.
        cleared = set()
        action_counts = Counter()
        for i, event in enumerate(events):
            scope = where + f'/event/{i}'
            action, request, response = event.get('action'), event.get('request', {}), event.get('response', {})
            self.check(action in ('enter', 'measure', 'clear', 'exit') and response.get('accepted') is True,
                'accepted_event_action', scope, action)
            action_counts[action] += 1
            expected = 0.
            if action in ('measure', 'clear'):
                target = (request['position']['x'], request['position']['y'])
                ch = request['channel']
                self.check(all(finite(v) and abs(v) <= 2000000 for v in target)
                    and type(ch) is int and 1 <= ch <= 20, 'paid_event_request_domain', scope, request)
                distance = math.dist(position, target)
                if action == 'measure':
                    expected = distance / 5. + 5. + int(ch != channel)
                    channel = ch
                else:
                    is_success = response.get('clear_result') == 'success'
                    expected = distance / 5. + 3. + 2. * is_success
                    if is_success:
                        self.check(ch not in cleared, 'distinct_successful_clear', scope, ch)
                        cleared.add(ch)
                position = target
            saved_time = response.get('virtual_time_s')
            # Quantization is at most 0.5 us per primitive. Comparing increments
            # avoids an accumulating tolerance that could hide a wrong cost.
            if finite(saved_time):
                self.check(close(saved_time - previous_time, expected, 1.1e-6), 'paid_event_physical_cost', scope,
                    {'response_increment': saved_time - previous_time, 'recomputed': expected})
                if 'delta_time_s' in event:
                    self.check(close(event['delta_time_s'], saved_time - previous_time, 1e-8),
                        'event_delta_matches_response', scope, event['delta_time_s'])
                previous_time = saved_time
            else:
                self.check(False, 'response_virtual_time', scope, saved_time)
        self.archive_checks['paid_events_recomputed'] += len(events)
        self.check(close(previous_time, stats.get('time_s')) and len(cleared) == stats.get('cleared'),
            'event_physics_terminal', where, {'time_s': previous_time, 'distinct_cleared': len(cleared)})
        for action, stat in [('measure', 'measures'), ('clear', 'clear_attempts')]:
            if stat in stats:
                self.check(action_counts[action] == stats[stat], 'event_stat_count', where + '/' + stat,
                    {'events': action_counts[action], 'stats': stats[stat]})

    def envelope(self, entry, row, where, teacher=False):
        wid = entry.get('world_id')
        self.check(wid in self.registered and entry.get('recipe') == self.registered.get(wid),
            'archive_registered_recipe', where, {'world_id': wid, 'recipe': entry.get('recipe')})
        if row:
            self.check(wid == row.get('world_id') and entry.get('label', entry.get('selector')) == row.get('label'),
                'archive_row_identity', where, {'world_id': wid, 'label': entry.get('label', entry.get('selector'))})
            if row.get('label') in self.model_records:
                self.check(entry.get('frozen_model') == self.model_records[row['label']],
                    'archive_frozen_model_binding', where, entry.get('frozen_model'))
        if 'terminal_labels' in entry:
            labels = entry['terminal_labels']
            stats = labels.get('stats', {})
            success = labels.get('success')
            self.check(labels.get('true_n') == stats.get('n'), 'true_n_terminal_only_consistency', where, labels.get('true_n'))
            self.check(type(success) is bool, 'terminal_success_boolean', where, success)
            if success:
                self.check(labels.get('exit_reason') == 'user_exit' and not labels.get('error') and not labels.get('validation_errors'),
                    'successful_terminal_integrity', where, labels)
            calls = entry.get('actual_calls', {})
            self.check(set(calls) == {'enter', 'measure', 'clear', 'exit'} and all(type(n) is int and n >= 0 for n in calls.values()),
                'call_counter_schema', where, calls)
            self.check(sum(calls.values()) == entry.get('business_primitives'), 'actual_call_sum', where, calls)
            raw = entry.get('raw')
            baseline_log = entry.get('baseline_primitive_log')
            if row and row.get('label') == 'original_c7' and row['label'] in self.model_records:
                self.check(isinstance(baseline_log, list), 'original_c7_selection_primitive_log', where,
                    'Original baseline must retain the accepted request/response trace.')
            if isinstance(baseline_log, list):
                self.event_physics(baseline_log, stats, where + '/baseline_primitive_log')
                accepted_calls = Counter(e.get('action') for e in baseline_log)
                self.check(all(accepted_calls[action] <= calls.get(action, 0) for action in accepted_calls),
                    'baseline_accepted_vs_attempted_calls', where, dict(accepted_calls))
                self.archive_checks['original_c7_primitive_logs_read'] += 1
            if row and row.get('label') in ('original_c7', 'teacher_wrapper') and row['label'] in self.model_records:
                events = baseline_log if row['label'] == 'original_c7' else (raw or {}).get('events')
                if isinstance(events, list):
                    normalized = [semantic_event(event) for event in events]
                    self.selection_traces[wid][row['label']] = dict(path=where,
                        trace_sha256=digest(canonical(normalized)), events=len(events),
                        event_sha256=[digest(canonical(event)) for event in normalized],
                        time_s=stats.get('time_s'), average_s=stats.get('average_s'),
                        cleared=stats.get('cleared'), true_n=stats.get('n'), success=success)
            if row:
                fields = {'n': stats.get('n'), 'cleared': stats.get('cleared'), 'fraction': stats.get('fraction'),
                    'virtual_time_s': stats.get('time_s'), 'average_s': stats.get('average_s'), 'success': success,
                    'actual_calls': calls, 'business_primitives': entry.get('business_primitives'),
                    'execution_wall_s': entry.get('execution_wall_s'), 'peak_process_mib': entry.get('peak_process_mib'),
                    'decisions': len((raw or {}).get('decisions', [])), 'error': labels.get('error') or (raw or {}).get('error')}
                for key, value in fields.items():
                    self.check(row.get(key) == value, 'archive_row_field', where + '/' + key,
                        {'row': row.get(key), 'archive': value})
        else:
            stats = entry.get('stats', {})
            success = entry.get('valid_complete')
            raw = entry.get('result')
            log = entry.get('primitive_log', [])
            self.check(len(log) == entry.get('business_primitives'), 'g0_log_call_count', where, len(log))
            if raw is None or 'events' not in raw:
                self.event_physics(log, stats, where + '/primitive_log')
            if 'semantic_trace_sha256' in entry:
                trace = [semantic_event(e) for e in log]
                self.check(digest(canonical(trace)) == entry['semantic_trace_sha256'], 'g0_semantic_trace_recomputed',
                    where, entry['semantic_trace_sha256'])
            if success:
                self.check(entry.get('environment_exit_reason') == 'user_exit' and not entry.get('error'),
                    'g0_success_exit', where, entry.get('environment_exit_reason'))
        self.stats(stats, success, where)
        self.raw_episode(raw, stats, success, entry.get('business_primitives'), where, teacher=teacher)

    def archive(self, path, storage, row=None, teacher=False):
        path = self.resolve(path)
        key = self.rel(path)
        if key in self.archive_seen:
            return None
        self.archive_seen.add(key)
        try:
            compressed = self.read_bytes(path)
            actual_hash = digest(compressed)
            self.hashes[key] = actual_hash
            if storage.get('sha256'):
                self.check(actual_hash == storage['sha256'], 'archive_compressed_sha256', key, actual_hash)
            decoded = gzip.decompress(compressed) if path.suffix == '.gz' else compressed
            self.inventory(path, storage, dict(sha256=actual_hash, content_sha256=digest(decoded),
                raw_json_bytes=len(decoded), bytes=len(compressed)))
            if storage.get('content_sha256'):
                self.check(digest(decoded) == storage['content_sha256'], 'archive_content_sha256', key, digest(decoded))
            for field, actual in [('gzip_bytes', len(compressed)), ('raw_json_bytes', len(decoded))]:
                if field in storage:
                    self.check(storage[field] == actual, 'archive_byte_count', key + '/' + field, actual)
            entry = json.loads(decoded, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
            self.envelope(entry, row, key, teacher=teacher)
            self.archive_checks['archives_read'] += 1
            self.archive_checks['compressed_or_json_bytes'] += len(compressed)
            self.archive_checks['decoded_bytes'] += len(decoded)
            return entry
        except (OSError, ValueError, TypeError, KeyError, IndexError, OverflowError) as exc:
            self.check(False, 'archive_read_or_schema', key, type(exc).__name__ + ': ' + str(exc))
            return None

    def ledger(self, name, directory, expected_ids, *, label=None, completed=False, teacher=False, caps=None):
        directory = Path(directory)
        rows = self.rows(directory / 'rows.jsonl')
        ids = [r.get('world_id') for r in rows]
        self.executed_world_ids.update(x for x in ids if x in self.registered)
        self.check(len(ids) == len(set(ids)), 'ledger_world_unique', name, 'One row per world per model/algorithm.')
        self.check(ids == expected_ids[:len(ids)], 'ledger_registered_order', name,
            {'rows': len(ids), 'expected_worlds': len(expected_ids)})
        if completed:
            self.check(len(ids) == len(expected_ids), 'completed_ledger_count', name,
                {'rows': len(ids), 'expected': len(expected_ids)})
        elif len(ids) < len(expected_ids):
            self.pending('stage_incomplete', name, {'rows': len(ids), 'expected_or_cap': len(expected_ids)})
        total_calls = 0
        for index, row in enumerate(rows):
            where = f'{name}/row/{index}'
            wid = row.get('world_id')
            recipe = self.registered.get(wid, {})
            self.check(wid in self.registered and row.get('mode') == recipe.get('mode') and row.get('group') == recipe.get('group'),
                'row_registration', where, wid)
            if label is not None:
                self.check(row.get('label') == label, 'row_label', where, row.get('label'))
            self.stats(dict(n=row.get('n'), cleared=row.get('cleared'), time_s=row.get('virtual_time_s'),
                average_s=row.get('average_s'), fraction=row.get('fraction')), row.get('success'), where)
            calls = row.get('business_primitives')
            self.check(type(calls) is int and calls >= 0, 'row_business_calls', where, calls)
            if type(calls) is int:
                total_calls += calls
            actual = row.get('actual_calls', {})
            self.check(all(type(n) is int and n >= 0 for n in actual.values()) and sum(actual.values()) == calls,
                'row_call_sum', where, actual)
            if row.get('validation_errors'):
                self.finding('error', 'retained_integrity_failure', where, row['validation_errors'])
            if teacher:
                self.check(row.get('teacher_matches') == row.get('decisions') and not row.get('fallback_reason')
                    and not row.get('controller_recoveries') and row.get('success') is True,
                    'shared_demo_pure_complete', where, 'Every demonstration must be an actual pure teacher success.')
            storage = row.get('storage', {})
            try:
                path = self.resolve(storage['path'])
                self.check(path.is_relative_to(directory.resolve()), 'archive_owned_by_ledger', where, self.rel(path))
                self.check(path.is_file(), 'indexed_archive_exists', where, self.rel(path))
                self.check(bool(re.fullmatch('[0-9a-f]{64}', storage.get('sha256', '')))
                    and bool(re.fullmatch('[0-9a-f]{64}', storage.get('content_sha256', ''))),
                    'archive_hash_index_schema', where, storage)
                key = self.rel(path)
                self.inventory(path, storage)
                self.check(key not in self.storage_refs, 'archive_single_execution_reference', where, key)
                self.storage_refs[key] = row
                if path.is_file() and 'gzip_bytes' in storage:
                    self.check(path.stat().st_size == storage['gzip_bytes'], 'archive_indexed_size', where, path.stat().st_size)
                if self.archives and path.is_file():
                    self.archive(path, storage, row, teacher=teacher)
            except (ValueError, KeyError, TypeError) as exc:
                self.check(False, 'row_storage_schema', where, str(exc))
        summary = dict(unique_worlds=len(set(ids)), episode_executions=len(rows), business_primitives=total_calls,
            successes=sum(r.get('success') is True for r in rows), failures=sum(r.get('success') is not True for r in rows),
            execution_wall_s=sum(r.get('execution_wall_s', 0.) for r in rows),
            storage_timing_unavailable_count=sum(bool(r.get('storage', {}).get('storage_timing_unavailable')) for r in rows))
        if caps:
            self.check(len(rows) <= caps[0] and total_calls <= caps[1], 'training_budget', name, summary)
        self.stages[name] = summary
        return rows, summary

    def summary_matches(self, saved, actual, where):
        for key in ('unique_worlds', 'episode_executions', 'business_primitives', 'successes', 'execution_wall_s', 'storage_timing_unavailable_count'):
            if key in saved:
                self.check(close(saved[key], actual[key]), 'summary_recomputed', where + '/' + key,
                    {'saved': saved[key], 'computed': actual[key]})
        if 'failures' in saved:
            self.check(isinstance(saved['failures'], list) and len(saved['failures']) == actual['failures'],
                'summary_failure_count', where, {'saved': len(saved['failures']), 'computed': actual['failures']})

    def g0(self, subdir, split):
        directory = self.root / 'core' / subdir
        summary = self.json(directory / 'summary.json', required=True) or {}
        manifest = self.json(directory / 'manifest.json', required=True) or {}
        rows = self.json(directory / 'rows.json', required=True) or []
        expected = [r['world_id'] for r in self.initial.get('worlds', []) if r.get('split') == split]
        labels = manifest.get('labels', [])
        self.hash_file(self.root / 'data/initial_registry.json', manifest.get('registry_sha256'))
        for name, expected_hash in manifest.get('core_hashes', {}).items():
            self.hash_file(self.root / 'core' / name, expected_hash)
        actual_ids = {r.get('world_id') for r in rows}
        self.executed_world_ids.update(x for x in actual_ids if x in self.registered)
        self.check(actual_ids == set(expected), 'g0_worlds', subdir, {'actual': len(actual_ids), 'expected': len(expected)})
        calls = 0
        if split == 'g0_core':
            self.check(len(rows) == 20, 'g0_core_row_count', subdir, len(rows))
            for i, row in enumerate(rows):
                calls += sum(row.get('business_primitives', {}).values())
                self.check(row.get('all_three_complete') and row.get('teacher_exact_event_equality'), 'g0_teacher_equivalence', f'{subdir}/{i}', row.get('errors'))
                hashes = {}
                for label in labels:
                    path = directory / f'{i:02d}_{label}.json'
                    self.check(path.exists(), 'legacy_g0_raw_retained', self.rel(path), 'Original large JSON must be retained.')
                    self.inventory(path)
                    if self.archives and path.exists():
                        entry = self.archive(path, {})
                        if entry:
                            self.check(entry['world_id'] == row['world_id'] and entry['label'] == label,
                                'g0_legacy_row_identity', self.rel(path), entry.get('world_id'))
                            hashes[label] = entry.get('semantic_trace_sha256')
                if hashes:
                    self.check(hashes.get('original_c7') == hashes.get('teacher_wrapper'), 'g0_archived_teacher_equivalence', str(i), hashes)
            self.finding('note', 'legacy_g0_hash_boundary', subdir,
                'Raw JSON is retained and current digests are reported in --archives; original manifest has no frozen digest for each raw file.')
            executions = len(rows) * len(labels)
        else:
            indexed = {r['file']: r for r in manifest.get('compressed_records', [])}
            pair_counts = Counter((r.get('world_id'), r.get('selector')) for r in rows)
            self.check(set(pair_counts) == {(wid, label) for wid in expected for label in labels}
                and all(n == 1 for n in pair_counts.values()), 'g0_audit_execution_pairs', subdir, len(pair_counts))
            for i, row in enumerate(rows):
                calls += row.get('business_primitives', 0)
                self.check(row.get('valid_complete') and row.get('cleared') == row.get('source_count'), 'g0_audit_complete', f'{subdir}/{i}', row)
                file = row.get('evidence_file')
                record = indexed.get(file, {})
                self.check(bool(record), 'g0_archive_indexed', subdir, file)
                if record:
                    self.inventory(directory / file, dict(sha256=record['gzip_sha256'],
                        content_sha256=record['raw_json_sha256'], raw_json_bytes=record['raw_bytes']))
                if self.archives and record:
                    converted = dict(sha256=record['gzip_sha256'], content_sha256=record['raw_json_sha256'],
                        raw_json_bytes=record['raw_bytes'], gzip_bytes=record['gzip_bytes'])
                    entry = self.archive(directory / file, converted)
                    if entry:
                        self.check(entry['world_id'] == row['world_id'] and entry['selector'] == row['selector']
                            and entry['business_primitives'] == row['business_primitives'], 'g0_audit_archive_row', file, 'Identity/calls mismatch.')
            executions = len(rows)
        self.check(summary.get('business_primitives') == calls and summary.get('episode_executions') == executions
            and summary.get('unique_worlds_executed') == len(actual_ids), 'g0_summary_recomputed', subdir, {'calls': calls, 'executions': executions})
        self.stages[subdir] = dict(unique_worlds=len(actual_ids), episode_executions=executions, business_primitives=calls)

    def g1(self):
        directory = self.root / 'results/g1_pipeline_v1'
        summary = self.json(directory / 'summary.json', required=True) or {}
        manifest = self.json(directory / 'manifest.json', required=True) or {}
        expected = [r['world_id'] for r in self.initial.get('worlds', []) if r.get('split') == 'g1_resource']
        self.check(manifest.get('worlds') == [self.registered[x] for x in expected], 'g1_manifest_recipes', 'g1', 'Manifest must match initial registry.')
        train = set(manifest.get('bc_train_worlds', [])); holdout = set(manifest.get('bc_diagnostic_holdout', []))
        self.check(len(train) == len(holdout) == 12 and not train & holdout and train | holdout == set(expected),
            'g1_diagnostic_partition', 'g1', '12 training and 12 disjoint exposed diagnostic worlds.')
        rows = self.rows(directory / 'rows.jsonl')
        self.executed_world_ids.update(r['world_id'] for r in rows if r.get('world_id') in self.registered)
        aggregate = dict(unique_worlds=len({r['world_id'] for r in rows}), episode_executions=len(rows),
            business_primitives=sum(r['business_primitives'] for r in rows), successes=sum(r['success'] for r in rows),
            failures=sum(not r['success'] for r in rows), execution_wall_s=sum(r['execution_wall_s'] for r in rows),
            storage_timing_unavailable_count=sum(bool(r.get('storage', {}).get('storage_timing_unavailable')) for r in rows))
        pairs = Counter((r['world_id'], r['label']) for r in rows)
        wanted = {(wid, label) for wid in expected for label in ('teacher', 'bc', 'greedy')} | {(expected[0], 'ppo_update_probe')} if expected else set()
        self.check(set(pairs) == wanted and all(n == 1 for n in pairs.values()), 'g1_registered_executions', 'g1', {'executions': len(rows), 'unique_worlds': aggregate['unique_worlds']})
        self.check(len(rows) == 73 and aggregate['business_primitives'] <= 100000, 'g1_budget', 'g1', aggregate)
        for row in rows:
            storage = row.get('storage', {})
            try:
                path = self.resolve(storage['path'])
                self.check(path.is_file(), 'g1_archive_retained', self.rel(path), 'Missing raw record.')
                self.inventory(path, storage)
                self.storage_refs[self.rel(path)] = row
                if self.archives:
                    self.archive(path, storage, row)
            except (KeyError, ValueError) as exc:
                self.check(False, 'g1_storage_schema', 'g1', str(exc))
        self.summary_matches(summary, aggregate, 'g1')
        self.stages['g1'] = aggregate

    def demo(self):
        directory = self.root / 'results/g2_shared_demo'
        saved = self.json(directory / 'summary.json')
        ids = [r['world_id'] for r in self.plan.get('demonstrations', [])]
        rows, actual = self.ledger('shared_demonstrations', directory, ids, label='g2_shared_c7_teacher', completed=bool(saved), teacher=True)
        if saved:
            self.summary_matches(saved, actual, 'shared_demonstrations')
            self.check(saved.get('all_pure_teacher') is True and saved.get('corpus_collections') == 1,
                'one_shared_corpus', 'shared_demonstrations', {'collections': saved.get('corpus_collections')})
            self.hash_file(self.root / 'data/g2_plan.json', saved.get('plan_sha256'))
        self.demo_rows = rows
        self.demo_paths = {r['storage']['path'] for r in rows if 'storage' in r}

    def checkpoints(self, base, algorithm, seed, completed, is_complete):
        path = base / 'checkpoints.json'
        records = self.json(path) if path.exists() else []
        records = records or []
        episodes = [r.get('episodes') for r in records]
        self.check(len(records) <= 4 and len(episodes) == len(set(episodes)) and all(e in POINTS for e in episodes),
            'checkpoint_positions_and_cap', self.rel(base), episodes)
        for record in records:
            where = self.rel(base) + '/checkpoint/' + str(record.get('episodes'))
            self.check(record.get('algorithm') == algorithm and record.get('seed') == seed,
                'checkpoint_identity', where, record)
            self.check(record.get('episodes', 10**9) <= completed, 'checkpoint_training_position', where, completed)
            try:
                checkpoint = self.resolve(record['path'])
                self.check(checkpoint.is_relative_to((base / 'checkpoints').resolve()), 'checkpoint_owned_by_initialization', where, self.rel(checkpoint))
                self.hash_file(checkpoint, record.get('sha256'))
            except (KeyError, ValueError, OSError) as exc:
                self.check(False, 'checkpoint_file', where, str(exc))
        reached = [e for e in POINTS if e <= completed]
        if is_complete:
            self.check(set(reached) == set(episodes), 'all_reached_checkpoints_saved', self.rel(base), {'reached': reached, 'saved': episodes})
        self.stages.setdefault(f'train/{seed}/{algorithm}', {})['checkpoint_status'] = {
            str(point): ('saved' if point in episodes else 'missing_after_reached' if point <= completed else 'not_reached') for point in POINTS}
        return records

    def training(self, seed):
        base = self.root / f'results/g2/init_{seed}'
        manifest = self.json(base / 'manifest.json')
        if manifest:
            self.check(manifest.get('seed') == seed and manifest.get('shared_corpus') is True and manifest.get('selection_worlds_read') == 0,
                'initialization_scope', self.rel(base), manifest.get('selection_worlds_read'))
            self.check({'shared.py', 'runners/train_initialization.py', 'runners/common.py'} <= set(manifest.get('runtime_sha256', {})),
                'training_runtime_hash_coverage', self.rel(base), sorted(manifest.get('runtime_sha256', {})))
            for key, target in [('plan_sha256', 'data/g2_plan.json'),
                ('demonstration_summary_sha256', 'results/g2_shared_demo/summary.json'),
                ('demonstration_rows_sha256', 'results/g2_shared_demo/rows.jsonl')]:
                self.hash_file(self.root / target, manifest.get(key))
            for path, expected in manifest.get('runtime_sha256', {}).items():
                try:
                    self.hash_file(self.resolve(path), expected)
                except (ValueError, OSError) as exc:
                    self.check(False, 'runtime_manifest_file', path, str(exc))
        bc = self.json(base / 'bc/summary.json')
        if bc:
            self.check(bc.get('seed') == seed and bc.get('shared_demonstrations') == 512 and bc.get('new_episodes') == 0
                and bc.get('passes') == 8 and bc.get('optimizer_steps') == 512, 'bc_shared_corpus_and_updates', self.rel(base), bc)
            self.hash_file(base / 'bc' / bc.get('checkpoint', 'final.pt'), bc.get('sha256'))
        expected = [r['world_id'] for r in self.plan.get('training', {}).get(str(seed), [])]
        for algorithm in ('ppo', 'q'):
            out = base / algorithm
            saved = self.json(out / 'summary.json')
            # Episode budget can end before 1024 at the reserved primitive cap.
            expected_completed = expected[:saved.get('completed_training_episodes', 0)] if saved else expected
            name = f'train/{seed}/{algorithm}'
            rows, actual = self.ledger(name, out, expected_completed, label=f'{algorithm}_init{seed}',
                completed=bool(saved), caps=(1024, 1000000))
            if saved:
                self.summary_matches(saved, actual, name)
                self.check(saved.get('seed') == seed and saved.get('algorithm') == algorithm
                    and saved.get('completed_training_episodes') == len(rows), 'training_summary_identity', name, saved.get('completed_training_episodes'))
                self.hash_file(out / 'resume.pt', saved.get('final_state_sha256'))
                reason = saved.get('stop_reason')
                if reason == 'episode_cap':
                    self.check(len(rows) == 1024, 'episode_cap_stop', name, len(rows))
                elif reason == 'primitive_cap_with_complete_episode_reserve':
                    self.check(actual['business_primitives'] + 15846 > 1000000, 'primitive_cap_stop', name, actual['business_primitives'])
                else:
                    self.check(False, 'registered_stop_reason', name, reason)
            records = self.checkpoints(out, algorithm, seed, len(rows), bool(saved))
            self.stages[name]['checkpoints'] = records
            if saved:
                self.check(saved.get('checkpoint_positions') == [r['episodes'] for r in records], 'summary_checkpoint_positions', name, saved.get('checkpoint_positions'))
            updates = self.rows(out / 'updates.jsonl')
            commits = [r.get('commit_id') for r in updates]
            self.check(len(commits) == len(set(commits)), 'unique_committed_update_log', name, len(commits))
            if algorithm == 'q':
                own = {r['storage']['path']: i + 1 for i, r in enumerate(rows) if 'storage' in r}
                for update in updates:
                    sampled = update.get('sampled_episode_paths', [])
                    count = update.get('completed_new_episodes', 0)
                    allowed = self.demo_paths | {path for path, position in own.items() if position <= count}
                    self.check(len(sampled) == 8 and len(set(sampled)) == 8 and set(sampled) <= allowed,
                        'q_replay_only_demo_and_own_past', name + '/' + str(update.get('commit_id')), sampled)
                mc = self.json(out / 'mc_summary.json')
                if mc:
                    self.check(mc.get('shared_demo_episodes') == 512 and mc.get('passes') == 4 and mc.get('optimizer_steps') == 256,
                        'q_mc_shared_demo_passes', name, mc)
        if not (base / 'complete.json').exists():
            self.pending('initialization_not_complete', self.rel(base), 'Training may still be running.')
        else:
            complete = self.json(base / 'complete.json', required=True) or {}
            self.check(complete.get('seed') == seed and complete.get('local_only') is True and complete.get('selection_performed') is False,
                'initialization_complete_scope', self.rel(base), complete)
            self.check(all((base / algorithm / 'summary.json').is_file() for algorithm in ('bc', 'ppo', 'q')),
                'initialization_complete_summaries', self.rel(base), 'A complete initialization must have all three summaries.')

    def expected_models(self):
        models = {name: dict(model_id=name, algorithm=name, seed=None, checkpoint=None)
            for name in ('original_c7', 'teacher_wrapper', 'same_candidates_greedy')}
        for seed in self.plan.get('initialization_seeds', []):
            bcpath = self.root / f'results/g2/init_{seed}/bc/final.pt'
            bcsummary = self.root / f'results/g2/init_{seed}/bc/summary.json'
            bc = self.json(bcsummary) if bcsummary.exists() else {}
            model_id = f'bc_init{seed}'
            models[model_id] = dict(model_id=model_id, algorithm='bc', seed=seed,
                checkpoint=dict(path=self.rel(bcpath), sha256=(bc or {}).get('sha256'), episodes=0))
            for algorithm in ('ppo', 'q'):
                for record in self.stages.get(f'train/{seed}/{algorithm}', {}).get('checkpoints', []):
                    model_id = f"{algorithm}_init{seed}_ep{record['episodes']:04d}"
                    models[model_id] = dict(model_id=model_id, algorithm=algorithm, seed=seed, checkpoint=record)
        return models

    def selection(self):
        base = self.root / 'results/g2_selection'
        models = self.expected_models()
        self.model_records = models
        expected_ids = [r['world_id'] for r in self.plan.get('selection', [])]
        observed_ids = set()
        executions = 0
        calls = 0
        freeze_path = self.root / 'data/selection_freeze.json'
        if not freeze_path.exists():
            self.pending('selection_not_frozen', self.rel(freeze_path),
                {'expected_unique_worlds': 192, 'currently_available_models': sorted(models)})
            self.check(not base.exists() or not any(base.rglob('rows.jsonl')), 'selection_requires_freeze',
                self.rel(base), 'Selection rows require the registered immutable freeze.')
            self.stages['selection'] = dict(unique_worlds=0, episode_executions=0, registered_unique_worlds=192,
                independent_world_denominator=0, completed_models=0, business_primitives=0)
            return
        freeze = self.json(freeze_path, required=True) or {}
        self.check(all((self.root / f'results/g2/init_{seed}/complete.json').is_file()
            for seed in self.plan.get('initialization_seeds', [])), 'selection_after_all_training_complete',
            'selection_freeze', 'All three training initializations must be complete before selection freeze.')
        frozen_records = freeze.get('baselines', []) + freeze.get('models', [])
        declared = {r.get('model_id'): r for r in frozen_records}
        self.check(len(declared) == len(frozen_records) and declared == models,
            'selection_registered_models', 'selection_freeze',
            {'expected': sorted(models), 'declared': sorted(str(x) for x in declared)})
        self.check(freeze.get('selection_worlds') == self.plan.get('selection'), 'selection_freeze_recipes',
            'selection_freeze', 'Selection recipes must match the registered 192 worlds exactly.')
        self.check(freeze.get('final_test_worlds') == 0 and freeze.get('default_solver_replacement') is False,
            'selection_evidence_boundary', 'selection_freeze', 'No final worlds or automatic default replacement.')
        self.hash_file(self.root / 'data/g2_plan.json', freeze.get('plan_sha256'))
        freeze_sha = self.hash_file(freeze_path)
        physics_path = self.root / 'data/runtime_dependency_freeze.json'
        self.hash_file(physics_path, freeze.get('physics_freeze_sha256'))
        physics = self.json(physics_path, required=True) or {}
        repo = self.root.parents[1]
        for file, expected_hash in list(freeze.get('runtime_sha256', {}).items()) + list(physics.get('files', {}).items()):
            path = (repo / file).resolve()
            self.check(path.is_relative_to(repo), 'dependency_path_within_repo', file, str(path))
            if path.is_relative_to(repo):
                self.hash_file(path, expected_hash)
        self.check(set(freeze.get('training_summaries', {})) == {f'{algorithm}_init{seed}'
            for seed in self.plan.get('initialization_seeds', []) for algorithm in ('ppo', 'q')},
            'frozen_training_summary_coverage', 'selection_freeze', sorted(freeze.get('training_summaries', {})))
        for name, frozen in freeze.get('training_summaries', {}).items():
            match = re.fullmatch(r'(ppo|q)_init(\d+)', name)
            if not self.check(bool(match), 'frozen_training_summary_identity', name, name):
                continue
            out = self.root / f'results/g2/init_{match[2]}/{match[1]}'
            self.hash_file(out / 'summary.json', frozen.get('sha256'))
            self.hash_file(out / 'rows.jsonl', frozen.get('rows_sha256'))
            current = self.json(out / 'summary.json', required=True)
            self.check(current == frozen.get('summary'), 'frozen_training_summary_content', name, 'Summary changed after freeze.')
            recorded = [r['episodes'] for r in self.stages.get(f'train/{match[2]}/{match[1]}', {}).get('checkpoints', [])]
            self.check(frozen.get('missing_planned_checkpoints') == sorted(set(POINTS) - set(recorded)),
                'frozen_missing_checkpoint_disclosure', name, frozen.get('missing_planned_checkpoints'))
        actual_dirs = set()
        for folder in ('models', 'baselines'):
            root = base / folder
            if root.exists():
                actual_dirs.update(p.name for p in root.iterdir() if p.is_dir())
                wanted_here = {name for name, record in models.items()
                    if (record['algorithm'] in ('q', 'ppo')) == (folder == 'models')}
                self.check({p.name for p in root.iterdir() if p.is_dir()} <= wanted_here,
                    'selection_model_directory_scope', folder, sorted({p.name for p in root.iterdir() if p.is_dir()} - wanted_here))
        self.check(actual_dirs <= set(models), 'no_unregistered_selection_model', 'g2_selection', sorted(actual_dirs - set(models)))
        complete_models = 0
        for model_id, expected_model in models.items():
            folder = 'models' if expected_model['algorithm'] in ('q', 'ppo') else 'baselines'
            directory = base / folder / model_id
            saved = self.json(directory / 'summary.json') if directory.exists() else None
            if not directory.exists():
                self.pending('selection_model_not_started', model_id, expected_model)
                continue
            model_manifest = self.json(directory / 'manifest.json')
            expected_manifest = dict(**expected_model, selection_freeze_sha256=freeze_sha,
                world_count=192, deployment=True, training_exploration=False, feature_range_extended=False)
            if model_manifest:
                self.check(model_manifest == expected_manifest, 'selection_model_manifest', model_id,
                    {'expected': expected_manifest, 'actual': model_manifest})
            rows, actual = self.ledger('selection/' + model_id, directory, expected_ids,
                label=model_id, completed=bool(saved))
            observed_ids.update(r['world_id'] for r in rows)
            executions += len(rows)
            calls += actual['business_primitives']
            if saved:
                self.summary_matches(saved, actual, 'selection/' + model_id)
                self.check(all(saved.get(k) == v for k, v in expected_model.items()),
                    'selection_summary_model_identity', model_id, 'Summary model must match freeze.')
                self.check(saved.get('selection_only') is True and saved.get('official_validation') is False
                    and saved.get('final_blind_validation') is False, 'selection_summary_evidence_scope', model_id, 'Selection evidence only.')
                complete_models += len(rows) == 192
        self.stages['selection'] = dict(unique_worlds=len(observed_ids), episode_executions=executions,
            business_primitives=calls, registered_unique_worlds=192, independent_world_denominator=len(observed_ids),
            per_question_unique_worlds={str(mode): sum(self.registered[x]['mode'] == mode for x in observed_ids) for mode in (3, 4)},
            completed_models=complete_models, currently_available_models=len(models),
            inference_unit='World ID. Repeated initialization/model runs are paired repeated measurements, never additional independent worlds.',
            evidence_class='Checkpoint selection, exposed after analysis; not blind final or official validation.')

    def selection_teacher_equivalence(self):
        expected_ids = [r['world_id'] for r in self.plan.get('selection', [])]
        if not self.archives:
            self.stages['selection_teacher_equivalence'] = dict(status='not_checked_metadata_only',
                registered_pairs=len(expected_ids), note='Use --archives to compare actual request/response traces.')
            return
        rows = []
        missing = []
        for wid in expected_ids:
            traces = self.selection_traces.get(wid, {})
            if not all(label in traces for label in ('original_c7', 'teacher_wrapper')):
                missing.append(wid)
                continue
            original, wrapper = traces['original_c7'], traces['teacher_wrapper']
            same_trace = original['trace_sha256'] == wrapper['trace_sha256'] and original['events'] == wrapper['events']
            same_time = original['time_s'] == wrapper['time_s']
            same_labels = all(original[key] == wrapper[key] for key in ('true_n', 'cleared', 'success'))
            original_row = self.storage_refs.get(original['path'], {})
            wrapper_row = self.storage_refs.get(wrapper['path'], {})
            same_attempts = original_row.get('actual_calls') == wrapper_row.get('actual_calls')
            pair = dict(world_id=wid, mode=self.registered[wid]['mode'],
                semantic_trace_equal=same_trace, virtual_time_equal=same_time,
                terminal_labels_equal=same_labels, attempted_call_counts_equal=same_attempts,
                original=dict(path=original['path'], trace_sha256=original['trace_sha256'],
                    accepted_events=original['events'], virtual_time_s=original['time_s'], average_s=original['average_s'],
                    actual_calls=original_row.get('actual_calls')),
                teacher_wrapper=dict(path=wrapper['path'], trace_sha256=wrapper['trace_sha256'],
                    accepted_events=wrapper['events'], virtual_time_s=wrapper['time_s'], average_s=wrapper['average_s'],
                    actual_calls=wrapper_row.get('actual_calls')),
                virtual_time_difference_s=wrapper['time_s'] - original['time_s'])
            if not same_trace:
                orig_hashes, wrap_hashes = original['event_sha256'], wrapper['event_sha256']
                first = next((i for i in range(min(len(orig_hashes), len(wrap_hashes)))
                    if orig_hashes[i] != wrap_hashes[i]), min(len(orig_hashes), len(wrap_hashes)))
                pair['first_different_event_index'] = first
                pair['first_different_events'] = {}
                for label, record in [('original_c7', original), ('teacher_wrapper', wrapper)]:
                    data = self.read_bytes(self.resolve(record['path']))
                    entry = json.loads(gzip.decompress(data))
                    events = entry.get('baseline_primitive_log', []) if label == 'original_c7' else (entry.get('raw') or {}).get('events', [])
                    pair['first_different_events'][label] = semantic_event(events[first]) if first < len(events) else None
            if not (same_trace and same_time and same_labels and same_attempts):
                self.finding('warning', 'selection_teacher_semantic_difference', wid, pair)
            rows.append(pair)
        if missing:
            self.pending('selection_teacher_pairs_incomplete', 'selection_teacher_equivalence',
                {'paired_archives_checked': len(rows), 'registered_pairs': len(expected_ids), 'missing_pairs': len(missing)})
        all_equal = all(r['semantic_trace_equal'] and r['virtual_time_equal'] and
            r['terminal_labels_equal'] and r['attempted_call_counts_equal'] for r in rows)
        self.stages['selection_teacher_equivalence'] = dict(
            status='different' if not all_equal else 'partial_equal' if missing else 'all_equal',
            registered_pairs=len(expected_ids), paired_archives_checked=len(rows),
            unique_paired_worlds=len({r['world_id'] for r in rows}),
            semantic_equal_pairs=sum(r['semantic_trace_equal'] for r in rows),
            virtual_time_equal_pairs=sum(r['virtual_time_equal'] for r in rows),
            terminal_label_equal_pairs=sum(r['terminal_labels_equal'] for r in rows),
            attempted_call_equal_pairs=sum(r['attempted_call_counts_equal'] for r in rows),
            compared_fields=['action', 'request', 'response'],
            omitted_response_fields=sorted(SEMANTIC_RESPONSE_OMISSIONS),
            wall_time_compared=False, request_trajectory_scope='Accepted interface requests; attempted call counts checked separately.',
            missing_world_ids=missing, rows=rows,
            note='A behavioral difference is reported, not silently normalized away; it is distinct from corrupted evidence. No world was re-executed.')

    def unresolved_costs(self):
        directories = [self.root / 'results/g2_shared_demo', self.root / 'results/g2', self.root / 'results/g2_selection']
        for directory in directories:
            if not directory.exists():
                continue
            for path in directory.rglob('*.json.gz'):
                if self.rel(path) in self.storage_refs:
                    continue
                self.inventory(path)
                record = dict(path=self.rel(path), status='archive_without_index', calls=None)
                if self.archives:
                    entry = self.archive(path, {})
                    if entry:
                        record.update(world_id=entry.get('world_id'), calls=entry.get('business_primitives'))
                        self.known_orphans.append(record)
                if record['calls'] is None:
                    self.unknown_costs.append(record)
                self.pending('orphan_archive_needs_reconciliation', self.rel(path), record)
            for path in directory.rglob('*.started.json'):
                record = self.json(path)
                if not record:
                    continue
                archive = Path(str(path)[:-len('.started.json')] + '.gz')
                row = self.storage_refs.get(self.rel(archive))
                if record.get('status') == 'completed_and_saved':
                    if row:
                        self.check(record.get('actual_calls') == row.get('business_primitives') and
                            ('trajectory_sha256' not in record or record['trajectory_sha256'] == row.get('storage', {}).get('sha256')),
                            'completed_started_marker', self.rel(path), record)
                    else:
                        self.pending('completed_marker_without_observed_row', self.rel(path),
                            'Complete archive/index may have appeared after the ledger snapshot; reconcile before final audit.')
                elif record.get('status') in ('execution_started', 'started'):
                    if row:
                        self.finding('note', 'stale_started_marker_known_cost', self.rel(path),
                            {'calls': row.get('business_primitives'), 'archive': self.rel(archive)})
                    elif not archive.exists():
                        unknown = dict(path=self.rel(path), world_id=record.get('world_id'),
                            status='execution_started_without_complete_archive', calls=None,
                            reserved_calls_upper_bound=record.get('reserved_calls', record.get('reserved_call_bound')),
                            note='May still be running. Reservation is not measured cost; do not report zero or auto-rerun.')
                        self.unknown_costs.append(unknown)
                        self.pending('unresolved_environment_attempt', self.rel(path), unknown)
            for path in directory.rglob('pending_update.json'):
                record = self.json(path)
                if record:
                    unknown = dict(path=self.rel(path), status='pending_compute', commit_id=record.get('commit_id'),
                        actual_optimizer_steps=None, optimizer_steps_upper_bound=record.get('optimizer_steps_upper_bound'),
                        compute_wall_s=None, environment_reexecution=False)
                    self.unknown_costs.append(unknown)
                    self.pending('unresolved_compute_attempt', self.rel(path), unknown)
            for path in directory.rglob('interrupted_compute.jsonl'):
                for record in self.rows(path):
                    unknown = dict(path=self.rel(path), status='recorded_interrupted_compute', **record)
                    self.unknown_costs.append(unknown)
                    self.finding('warning', 'interrupted_compute_cost_unknown', self.rel(path), unknown)
        # Known complete orphan files count toward real environment budget even
        # before a runner reconciles its row ledger.
        by_algorithm = defaultdict(lambda: {'episodes': 0, 'calls': 0})
        for record in self.known_orphans:
            match = re.match(r'results/g2/init_(\d+)/(ppo|q)/episodes/', record['path'])
            if match and type(record.get('calls')) is int:
                stage = f'train/{match[1]}/{match[2]}'
                by_algorithm[stage]['episodes'] += 1
                by_algorithm[stage]['calls'] += record['calls']
        for stage, extra in by_algorithm.items():
            current = self.stages.get(stage, {})
            self.check(current.get('episode_executions', 0) + extra['episodes'] <= 1024
                and current.get('business_primitives', 0) + extra['calls'] <= 1000000,
                'training_budget_including_orphans', stage, extra)

    def finish(self):
        for path, before in self.tracked.items():
            try:
                now = path.stat()
                after = (now.st_size, now.st_mtime_ns, now.st_ino)
            except OSError:
                after = None
            if before != after:
                self.pending('input_changed_during_audit', self.rel(path), 'This is a live snapshot; retry after writers finish.')
        errors = sum(n for (level, _), n in self.fail_counts.items() if level == 'error')
        pending = sum(n for (level, _), n in self.fail_counts.items() if level == 'pending')
        unknown = len(self.unknown_costs)
        status = 'inconsistent' if errors else 'consistent_partial' if pending or unknown else 'consistent_complete'
        cost_stage_names = ['g0_results_v1', 'g0_audit_v1', 'g1', 'shared_demonstrations', 'selection']
        cost_stage_names += [name for name in self.stages if name.startswith('train/')]
        known_costs = dict(included_disjoint_stages=cost_stage_names,
            indexed_episode_executions=sum(self.stages.get(name, {}).get('episode_executions', 0) for name in cost_stage_names),
            indexed_business_primitives=sum(self.stages.get(name, {}).get('business_primitives', 0) for name in cost_stage_names),
            unique_executed_world_ids=len(self.executed_world_ids),
            note='Selection per-model stages are not added again. Orphan archives and unresolved attempts are listed separately; no zero imputation.')
        return dict(audit_version=VERSION, created_utc=datetime.now(timezone.utc).isoformat(),
            execution_root=str(self.root), mode='archives' if self.archives else 'metadata_only',
            status=status, errors=errors, pending_findings=pending, unknown_cost_records=unknown,
            elapsed_wall_s=time.monotonic() - self.started, checks=dict(sorted(self.counts.items())),
            finding_counts={level + '/' + code: n for (level, code), n in sorted(self.fail_counts.items())},
            findings=self.findings, stages=self.stages, archive_checks=dict(self.archive_checks),
            observed_file_sha256=self.hashes, unknown_costs=self.unknown_costs, known_unindexed_archive_costs=self.known_orphans,
            local_only_trajectory=[self.trajectory_inventory[k] for k in sorted(self.trajectory_inventory)],
            known_cost_totals=known_costs,
            boundaries=[
                'Read-only evidence audit: zero world/policy executions and zero checkpoint deserializations.',
                'Metadata mode does not read/decompress episode bodies or establish online feature non-leakage.',
                'Archive mode checks saved snapshot keys, feature shapes, observable feature reconstruction and physical previous-macro seconds; this is not a formal information-flow proof.',
                'Checkpoint bytes are hashed against the registered indices; hidden tensor/trainer state requires the separate diagnostics.',
                'Original C7 retains its own summary schema. Its baseline_primitive_log supplies accepted request/response data for physical cost checks; no macro decisions are invented.',
                'Hashes detect changes relative to saved indices, not independent authenticity of self-generated data.',
                'Known costs are separate from pending/interrupted attempts. Missing actual cost is not zero.',
                'Training repetitions and initialization repetitions are executions, not independent world samples.',
                'No new blind or official validation is claimed. Historical G0 raw JSON is retained unchanged.'])

    def run(self):
        for name, operation in [('registries', self.registries),
            ('g0_core', lambda: self.g0('g0_results_v1', 'g0_core')),
            ('g0_audit', lambda: self.g0('g0_audit_v1', 'g0_audit')),
            ('g1', self.g1), ('demo', self.demo)]:
            try:
                operation()
            except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
                self.check(False, 'stage_schema_or_read', name, type(exc).__name__ + ': ' + str(exc))
        for seed in getattr(self, 'plan', {}).get('initialization_seeds', []):
            try:
                self.training(seed)
            except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
                self.check(False, 'stage_schema_or_read', f'init/{seed}', type(exc).__name__ + ': ' + str(exc))
        for name, operation in [('selection', self.selection), ('selection_teacher_equivalence', self.selection_teacher_equivalence), ('unresolved_costs', self.unresolved_costs)]:
            try:
                operation()
            except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
                self.check(False, 'stage_schema_or_read', name, type(exc).__name__ + ': ' + str(exc))
        return self.finish()


def markdown(report):
    lines = ['# RL evidence consistency audit', '',
        f"Status: **{report['status']}**; mode: `{report['mode']}`.", '',
        f"Errors: {report['errors']}; pending findings: {report['pending_findings']}; unknown-cost records: {report['unknown_cost_records']}.", '',
        '| Stage | Unique worlds | Executions | Known business calls |', '|---|---:|---:|---:|']
    for name, stage in report['stages'].items():
        if 'episode_executions' in stage:
            lines.append(f"| {name} | {stage.get('unique_worlds', '')} | {stage['episode_executions']} | {stage.get('business_primitives', '')} |")
    lines += ['', 'Repeated initializations are paired observations of the same selection world. The registered selection population is 192 worlds (96 per question), regardless of the number of models.', '',
        '## Teacher wrapper versus original C7', '']
    equivalence = report['stages'].get('selection_teacher_equivalence', {})
    lines.append(f"Trace comparison: **{equivalence.get('status', 'not checked')}**. "
        f"Checked {equivalence.get('paired_archives_checked', 0)} paired worlds; "
        f"equal semantic traces: {equivalence.get('semantic_equal_pairs', 0)}; "
        f"equal virtual costs: {equivalence.get('virtual_time_equal_pairs', 0)}.")
    lines += ['', 'Only `real_timestamp_ms` and `remaining_real_duration_s` are omitted from response equality. Wall time is not compared. Differences and their first mismatching request are retained in the JSON report.', '',
        '## Findings', '']
    relevant = [f for f in report['findings'] if f['level'] in ('error', 'warning', 'pending')]
    for finding in relevant[:35]:
        lines.append(f"- **{finding['level']} / {finding['code']}** — `{finding['location']}`: {json.dumps(finding['detail'], ensure_ascii=False)}")
    if len(relevant) > 35:
        lines.append(f'- {len(relevant) - 35} additional details are in the JSON report.')
    if not relevant:
        lines.append('No consistency failures or unfinished records found in the selected audit scope.')
    lines += ['', '## Evidence boundary', ''] + ['- ' + text for text in report['boundaries']]
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1], help='20260911_rl_execution root')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--metadata-only', action='store_true', help='Default: lightweight indices, manifests, file existence/sizes and checkpoint/code hashes.')
    mode.add_argument('--archives', action='store_true', help='Read every saved episode and verify compressed/content digests, labels, costs and observable-only snapshots.')
    parser.add_argument('--require-complete', action='store_true', help='Exit 2 if consistent but training/selection or actual-cost records remain incomplete.')
    parser.add_argument('--out', type=Path, help='New output directory for audit.json and REPORT.md; refuses to overwrite.')
    args = parser.parse_args()
    if args.out and args.out.exists():
        parser.error('--out must not already exist; previous audits are retained.')
    report = Audit(args.root, archives=args.archives, require_complete=args.require_complete).run()
    if args.out:
        args.out.mkdir(parents=True, exist_ok=False)
        (args.out / 'audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        (args.out / 'REPORT.md').write_text(markdown(report))
        (args.out / 'local_only_trajectory_manifest.json').write_text(json.dumps(dict(
            audit_version=VERSION, mode=report['mode'],
            files=report['local_only_trajectory'],
            note='Original trajectory files remain local and unchanged; digest_status distinguishes recomputed hashes from saved index values.'),
            ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    print(json.dumps({k: report[k] for k in ('status', 'mode', 'errors', 'pending_findings', 'unknown_cost_records', 'elapsed_wall_s')}, ensure_ascii=False), file=sys.stderr)
    return 1 if report['errors'] else 2 if args.require_complete and report['status'] != 'consistent_complete' else 0


if __name__ == '__main__':
    sys.exit(main())
