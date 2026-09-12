#!/usr/bin/env python3
"""Independent saved-record audit; never imports a solver or evaluator module."""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import gzip
import hashlib
import json
import math
from pathlib import Path
import zipfile


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nonnegative_integer(value):
    return type(value) is int and value >= 0


def read_json(path):
    path = Path(path)
    if path.suffix == '.gz':
        with gzip.open(path, 'rt', encoding='utf-8') as stream:
            return json.load(stream)
    return json.loads(path.read_text())


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_response(response):
    return {k: v for k, v in response.items()
            if k not in ('real_timestamp_ms', 'remaining_real_duration_s')}


def request_for(call):
    action, args = call['action'], call['args']
    if action in ('enter', 'exit'):
        require(args == [], 'Nonempty argument list for ' + action)
        return {}
    require(action in ('measure', 'clear') and len(args) == 3,
            'Unknown business action or argument schema')
    return {'position': {'x': args[0], 'y': args[1]}, 'channel': args[2]}


def canonical_log(log):
    return [{'action': e['action'], 'request': e['request'],
             'response': canonical_response(e['response'])} for e in log]


def comparable_controller(value, *, latest_q3=False):
    """Retain every field except one explicitly reviewed Q3 CPU diagnostic value."""
    result = deepcopy(value)
    if not latest_q3:
        return result
    require(result.get('@') == 'dict', 'Unknown typed controller representation')
    for name, counters in result['v']:
        if name != 'counters':
            continue
        require(counters.get('@') == 'dict', 'Unknown typed counter representation')
        for pair in counters['v']:
            if pair[0] != 'a1_cover_cpu_s':
                continue
            encoded = pair[1]
            require(type(encoded) is dict and set(encoded) == {'@', 'v'} and encoded['@'] == 'float',
                    'Q3 CPU diagnostic is not the expected encoded float')
            number = float.fromhex(encoded['v'])
            require(math.isfinite(number) and number >= 0, 'Invalid Q3 CPU diagnostic value')
            # Keep field presence and original stored values in the source files.
            pair[1] = {'@reviewed_nonsemantic_machine_counter': 'a1_cover_cpu_s'}
    return result


def audit_physical_costs(log):
    """Recompute v1 microseconds from request geometry and actual result kinds."""
    position, channel, total_us = (0., 0.), 1, 0
    cleared = set()
    entered = False
    exited = False
    for index, event in enumerate(log):
        action, request, response = event['action'], event['request'], event['response']
        require(response.get('accepted') is True, 'Non-accepted event in accepted environment log')
        require(not exited, 'Accepted event after exit')
        if action == 'enter':
            require(index == 0 and not entered and request == {}, 'Repeated or misplaced enter')
            entered, duration = True, 0.
        else:
            require(entered, 'Physical event before enter')
            if action == 'exit':
                require(request == {}, 'Nonempty exit request')
                exited, duration = True, 0.
            else:
                require(action in ('measure', 'clear'), 'Unknown accepted physical action')
                target = (request['position']['x'], request['position']['y'])
                ch = request['channel']
                require(type(ch) in (int, float) and int(ch) == ch and 1 <= ch <= 20,
                        'Invalid accepted physical channel')
                require(all(type(x) in (int, float) and math.isfinite(x) and abs(x) <= 2e6
                            for x in target), 'Invalid accepted physical coordinate')
                movement = math.hypot(target[0] - position[0], target[1] - position[1]) / 5
                if action == 'measure':
                    require(response['measure_result'] in ('direction', 'near', 'no_signal'),
                            'Unknown accepted measurement result')
                    duration = movement + 5 + int(ch != channel)
                    channel = ch
                else:
                    require(response['clear_result'] in ('success', 'no_target_in_range'),
                            'Unknown accepted clear result')
                    success = response['clear_result'] == 'success'
                    require(not success or ch not in cleared, 'One source cleared successfully twice')
                    if success:
                        cleared.add(ch)
                    duration = movement + 3 + 2 * success
                position = target
        total_us += math.floor(duration * 1e6 + 0.5)
        require(round(response['virtual_time_s'] * 1e6) == total_us,
                f'Independent primitive-cost mismatch at accepted event {index}')
    return {'total_virtual_us': total_us, 'cleared_channels': cleared,
            'entered': entered, 'exited': exited}


def audit_journal(rows):
    """Count disjoint physical outcomes, regardless of status counter wording."""
    runs = {}
    current = None
    pending = None
    next_sequence = 0
    counts = Counter()
    for ordinal, row in enumerate(rows, 1):
        event = row['event']
        run_id = row['run_id']
        require(type(run_id) is str and bool(run_id), 'Invalid journal run ID')
        if event == 'run_start':
            require(current is None and pending is None, f'Overlapping run at row {ordinal}')
            require(run_id not in runs, 'Duplicate run ID: ' + run_id)
            require(row['kind'] in ('full', 'suffix', 'fixture'), 'Invalid execution kind')
            current = run_id
            runs[run_id] = {'start': row, 'calls': [], 'finish': None,
                            'counts': Counter()}
            counts['executions_started'] += 1
            counts[row['kind'] + '_runs'] += 1
            continue
        require(current == run_id, f'Event outside its active run at row {ordinal}')
        run = runs[run_id]
        if event == 'call_start':
            require(pending is None, 'Overlapping calls')
            require(nonnegative_integer(row['sequence']) and row['sequence'] == next_sequence,
                    'Call sequence gap, duplication, or invalid integer type')
            request_for(row)
            pending = dict(row)
            run['calls'].append(pending)
            counts['business_calls'] += 1
            run['counts']['business_calls'] += 1
            next_sequence += 1
        elif event in ('call_response', 'call_exception'):
            require(nonnegative_integer(row['sequence']) and pending is not None
                    and row['sequence'] == pending['sequence'],
                    'Unmatched call result')
            pending['result'] = row
            if event == 'call_response':
                require(row['accepted'] is (row['response'].get('accepted') is True),
                        'Accepted flag disagrees with actual response')
                bucket = 'accepted_calls' if row['accepted'] else 'rejected_calls'
                if row['accepted'] and pending['action'] == 'enter':
                    counts['entered'] += 1
            else:
                counts['exception_calls'] += 1
                run['counts']['exception_calls'] += 1
                acceptance = row.get('acceptance', 'unknown')
                require(acceptance in ('known_no_accept', 'unknown'),
                        'Unsupported exception acceptance evidence')
                bucket = 'rejected_calls' if acceptance == 'known_no_accept' else 'unknown_calls'
            counts[bucket] += 1
            run['counts'][bucket] += 1
            pending = None
        elif event == 'run_finish':
            require(pending is None, 'Run settled with a pending call')
            observed = run['counts']
            require(all(nonnegative_integer(row[k]) for k in ('attempted', 'accepted')),
                    'Run counters must be nonnegative nonboolean integers')
            require(type(row['success']) is bool and type(row['unknown_cost']) is bool,
                    'Run result flags must be booleans')
            require(row['attempted'] == observed['business_calls'], 'Run attempted-count mismatch')
            require(row['accepted'] == observed['accepted_calls'], 'Run accepted-count mismatch')
            require(observed['business_calls'] == sum(observed[k] for k in
                    ('accepted_calls', 'rejected_calls', 'unknown_calls')), 'Run outcome partition mismatch')
            require(not observed['unknown_calls'] or (row['unknown_cost'] and not row['success']),
                    'Unknown acceptance reported as a successful settled result')
            run['finish'] = row
            counts['executions_completed'] += 1
            counts['failed_runs'] += not row['success']
            counts['unknown_cost_runs'] += bool(row['unknown_cost'])
            current = None
        else:
            raise ValueError('Unknown journal event: ' + str(event))
    counts['unfinished_runs'] = sum(r['finish'] is None for r in runs.values())
    counts['unresolved_calls'] = sum('result' not in c for r in runs.values() for c in r['calls'])
    require(counts['business_calls'] == sum(counts[k] for k in
            ('accepted_calls', 'rejected_calls', 'unknown_calls', 'unresolved_calls')),
            'Campaign outcome partition mismatch')
    counts['unique_worlds_actually_started'] = len({
        r['start'].get('metadata', {}).get('world_sha256') for r in runs.values()
        if r['start'].get('metadata', {}).get('world_sha256') is not None})
    return counts, runs


def audit_outcome(result, run):
    require(result['schema'] == 'bc-rpi-evaluator-outcome-v1', 'Unsupported outcome schema')
    require(result['run_id'] == run['start']['run_id'], 'Outcome/run identity mismatch')
    require(result['kind'] == run['start']['kind'], 'Outcome execution kind mismatch')
    require(run['finish'] is not None, 'Outcome belongs to an unfinished run')
    require(type(result['success']) is bool and type(result['normal_exit']) is bool,
            'Outcome success/exit flags must be booleans')
    if result['kind'] in ('full', 'suffix'):
        require(result['success'] == run['finish']['success'], 'Outcome/run success disagreement')
    log = result['environment_log']
    episode = result['episode']
    prefix = episode.get('prefix_event_count', 0) if result['kind'] == 'suffix' else 0
    require(type(prefix) is int and 0 <= prefix <= len(log), 'Invalid suffix prefix length')
    accepted = [c for c in run['calls'] if c['result']['event'] == 'call_response'
                and c['result']['accepted']]
    actual = [{'action': c['action'], 'request': request_for(c),
               'response': canonical_response(c['result']['response'])} for c in accepted]
    require(actual == canonical_log(log[prefix:]), 'Outcome log differs from actual accepted requests')
    require(len(actual) == run['counts']['accepted_calls'], 'Accepted log denominator mismatch')
    if result['kind'] == 'suffix':
        require(not any(c['action'] == 'enter' for c in run['calls']), 'Suffix incorrectly re-entered')
        require(episode['prefix_virtual_us'] == run['start']['metadata']['prefix_virtual_us'],
                'Suffix prefix cost differs from run registration')
        prefix_us = 0 if prefix == 0 else round(log[prefix - 1]['response']['virtual_time_s'] * 1e6)
        require(episode['prefix_virtual_us'] == prefix_us,
                'Suffix prefix cost differs from the original accepted event prefix')
    elif result['kind'] == 'full' and 'prefix_event_count' in episode:
        require(episode['prefix_event_count'] == 1 and episode['prefix_virtual_us'] == 0,
                'Full wrapper outcome must have only its zero-cost enter prefix')
        require(bool(log) and log[0]['action'] == 'enter', 'Full wrapper log lacks initial enter')
    sources = result['private_terminal_sources']
    physics = audit_physical_costs(log)
    require(len(sources) == result['true_terminal_n'], 'Terminal source-count mismatch')
    cleared = sum(s['cleared'] is True for s in sources.values())
    require(physics['cleared_channels'] == {int(ch) for ch, s in sources.items() if s['cleared'] is True},
            'Terminal cleared-source flags differ from actual successful clear events')
    require(cleared == result['cleared'] == result['stats']['cleared'], 'Cleared-count mismatch')
    require(result['stats']['n'] == len(sources), 'Stats source denominator mismatch')
    total = result['modeled_full_virtual_us']
    require(type(total) is int and total >= 0, 'Invalid integer-microsecond total')
    require(physics['total_virtual_us'] == total, 'Independent total primitive-cost mismatch')
    require(abs(result['seconds_per_source'] - total / 1e6 / len(sources)) < 1e-9,
            'Per-source arithmetic mismatch')
    require(round(result['stats']['time_s'] * 1e6) == total, 'Stats virtual-time mismatch')
    if log:
        require(round(log[-1]['response']['virtual_time_s'] * 1e6) == total,
                'Final response virtual-time mismatch')
    if 'macros' in episode:
        require(episode['total_virtual_us'] == total, 'Public/private microsecond total mismatch')
        require(episode['prefix_virtual_us'] + sum(m['delta_us'] for m in episode['macros'])
                + episode['tail_virtual_us'] == total, 'Macro/partial/tail cost partition mismatch')
        require(episode['cost_partition_error_us'] == 0, 'Nonzero reported cost partition error')
        require(canonical_log(episode['events']) == canonical_log(log), 'Public/private event sequence mismatch')
        previous = episode['prefix_event_count']
        for macro in episode['macros']:
            start, end = macro['event_range']
            require(nonnegative_integer(start) and nonnegative_integer(end)
                    and start == previous and start <= end <= len(log), 'Macro event overlap, gap, or invalid index type')
            require(nonnegative_integer(macro['delta_us']), 'Macro cost must use integer microseconds')
            before = 0 if start == 0 else round(log[start - 1]['response']['virtual_time_s'] * 1e6)
            after = before if end == start else round(log[end - 1]['response']['virtual_time_s'] * 1e6)
            require(after - before == macro['delta_us'], 'Macro cost differs from its actual event range')
            previous = end
        tail_start_us = 0 if previous == 0 else round(log[previous - 1]['response']['virtual_time_s'] * 1e6)
        require(total - tail_start_us == episode['tail_virtual_us'],
                'Tail cost differs from its actual accepted event suffix')
        if episode.get('fallback_reason') is None:
            require(all(e['action'] == 'exit' for e in log[previous:]),
                    'Unpartitioned physical operation outside macros without declared fallback')
        require(episode['suffix_accepted_events'] == len(log) - episode['prefix_event_count'],
                'Suffix accepted-event denominator mismatch')
        require(nonnegative_integer(episode['slots_remaining']) and episode['slots_remaining'] <= 2,
                'Invalid remaining intervention budget')
    if result['success']:
        require(result['normal_exit'] and cleared == len(sources) and not episode.get('error'),
                'Success hides an incomplete/failed episode')
        require(bool(log) and log[-1]['action'] == 'exit'
                and log[-1]['response'].get('accepted') is True
                and log[-1]['response'].get('exit_reason') == 'user_exit',
                'Success lacks an actual accepted user-exit event')
    return {'run_id': result['run_id'], 'kind': result['kind'],
            'accepted_calls': len(actual), 'prefix_events_not_recounted': prefix,
            'source_count': len(sources), 'cleared': cleared, 'success': result['success']}


def audit_fixture_outcome(result, run):
    """A passed partial/fault fixture is not a successfully completed task."""
    require(result['schema'] == 'bc-rpi-real-interface-fixture-v1', 'Unsupported real fixture schema')
    require(result['run_id'] == run['start']['run_id'], 'Fixture/run identity mismatch')
    require(result['kind'] == run['start']['kind'] == 'fixture', 'Fixture execution kind mismatch')
    require(run['finish'] is not None, 'Fixture run is unfinished')
    require(type(result['success']) is bool and result['success'] == run['finish']['success'],
            'Fixture assertion-success disagreement')
    checks = result['checks']
    require(isinstance(checks, dict) and checks and all(type(v) is bool for v in checks.values()),
            'Malformed fixture assertion flags')
    require(result['success'] == all(checks.values()), 'Fixture success hides a failed assertion')
    metadata = run['start'].get('metadata', {})
    prefix = metadata.get('prefix_event_count', 0)
    log = result['environment_log']
    require(type(prefix) is int and 0 <= prefix <= len(log), 'Invalid fixture prefix length')
    if prefix:
        require(metadata['prefix_virtual_us'] == round(log[prefix - 1]['response']['virtual_time_s'] * 1e6),
                'Fixture prefix cost mismatch')
        require(not any(c['action'] == 'enter' for c in run['calls']), 'Resumed fixture re-entered')
    accepted = [c for c in run['calls'] if c['result']['event'] == 'call_response'
                and c['result']['accepted']]
    actual = [{'action': c['action'], 'request': request_for(c),
               'response': canonical_response(c['result']['response'])} for c in accepted]
    require(actual == canonical_log(log[prefix:]), 'Fixture log differs from actually accepted requests')
    physics = audit_physical_costs(log)
    require(physics['total_virtual_us'] == result['modeled_full_virtual_us'], 'Fixture physical-cost mismatch')
    return {'run_id': result['run_id'], 'kind': 'fixture',
            'accepted_calls': len(actual), 'prefix_events_not_recounted': prefix,
            'assertion_count': len(checks), 'assertions_passed': result['success'],
            'physical_exit_observed': physics['exited'],
            'scope': 'Fixture assertions and cost/log consistency, not full-clear solver performance.'}


def snapshot_ledger(implementation, destination):
    """Archive settled raw source bytes before the live campaign can append G1."""
    implementation, destination = Path(implementation).resolve(), Path(destination).resolve()
    require(not destination.exists(), 'Ledger snapshot destination already exists')
    status_path = implementation / 'execution_status.json'
    journal_path = implementation / 'execution_calls.jsonl'
    status_bytes, journal_bytes = status_path.read_bytes(), journal_path.read_bytes()
    state = json.loads(status_bytes)
    require(state['current_run'] is None and state['reserved_calls'] == 0, 'Cannot snapshot an active run')
    counts, _ = audit_journal([json.loads(line) for line in journal_bytes.splitlines() if line.strip()])
    require(counts['unfinished_runs'] == counts['unresolved_calls'] == 0, 'Cannot snapshot unfinished journal')
    require(state['business_calls'] == counts['business_calls'], 'Snapshot status/journal boundary mismatch')
    require(status_path.read_bytes() == status_bytes and journal_path.read_bytes() == journal_bytes,
            'Live ledger changed while being snapshotted')
    destination.mkdir(parents=True)
    (destination / 'execution_status.json').write_bytes(status_bytes)
    compressed = gzip.compress(journal_bytes, mtime=0)
    (destination / 'execution_calls.jsonl.gz').write_bytes(compressed)
    manifest = {'schema': 'bc-rpi-settled-ledger-snapshot-v1',
                'business_calls': counts['business_calls'],
                'executions_completed': counts['executions_completed'],
                'original_journal_path': str(journal_path),
                'decompressed_journal_sha256': hashlib.sha256(journal_bytes).hexdigest(),
                'compressed_journal_sha256': hashlib.sha256(compressed).hexdigest(),
                'status_sha256': hashlib.sha256(status_bytes).hexdigest(),
                'scope': 'Immutable copy of a settled call-ledger prefix; no policy execution.'}
    (destination / 'snapshot_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return destination


def audit(implementation, stage, *, check_g0=False, ledger_directory=None):
    implementation, stage = Path(implementation).resolve(), Path(stage).resolve()
    ledger = implementation if ledger_directory is None else Path(ledger_directory).resolve()
    journal_path = ledger / 'execution_calls.jsonl'
    if ledger_directory is not None and not journal_path.exists():
        journal_path = ledger / 'execution_calls.jsonl.gz'
    journal_text = gzip.decompress(journal_path.read_bytes()).decode() if journal_path.suffix == '.gz' else journal_path.read_text()
    rows = [json.loads(line) for line in journal_text.splitlines() if line.strip()]
    counts, runs = audit_journal(rows)
    status_path = ledger / 'execution_status.json'
    status = read_json(status_path)
    require(counts['unfinished_runs'] == counts['unresolved_calls'] == 0, 'Execution is still in flight')
    for key in ('business_calls', 'accepted_calls', 'entered', 'full_runs', 'suffix_runs',
                'fixture_runs', 'executions_started', 'executions_completed', 'failed_runs', 'unknown_cost_runs'):
        require(key in status and nonnegative_integer(status[key]) and status[key] == counts[key],
                'Missing, invalid, or mismatched status counter: ' + key)
    if 'rejected_calls' in status:
        require(status['rejected_calls'] == counts['rejected_calls'], 'Rejected-call partition mismatch')
    if 'unknown_cost_calls' in status:
        require(status['unknown_cost_calls'] == counts['unknown_calls'], 'Unknown-call partition mismatch')
    require(status['current_run'] is None and status['reserved_calls'] == 0, 'Pending execution reservation')
    require(status['network_training_runs'] == 0, 'Unexpected model training')
    require(counts['business_calls'] <= status['limits']['business_calls'], 'Call budget exceeded')
    require(counts['executions_started'] <= status['limits']['executions'], 'Execution budget exceeded')
    result_files = sorted((stage / 'runs').glob('*.json.gz'))
    if check_g0 and (stage / 'index.json').exists():
        indexed = read_json(stage / 'index.json')['runs']
        result_files = sorted({(implementation / row['path']).resolve() for row in indexed})
        require(all(p.is_relative_to(implementation / 'results') for p in result_files),
                'Indexed G0 outcome path escapes registered result storage')
    require(result_files, 'No saved stage outcomes')
    findings, result_ids, source_files = [], set(), [journal_path, status_path]
    for path in result_files:
        result = read_json(path)
        run_id = result['run_id']
        require(run_id in runs and run_id not in result_ids, 'Unknown/duplicate saved run outcome')
        check = audit_fixture_outcome if result['schema'] == 'bc-rpi-real-interface-fixture-v1' else audit_outcome
        findings.append(check(result, runs[run_id]))
        result_ids.add(run_id)
        source_files.append(path)
    g0 = None
    if check_g0:
        g0 = audit_g0_pairs(implementation, stage, runs)
        repo = implementation.parents[3]
        freeze_path = stage / 'source_freeze.json'
        if freeze_path.exists():
            freeze = read_json(freeze_path)
            for relative, expected_hash in freeze['files'].items():
                path = (repo / relative).resolve()
                require(path.is_relative_to(repo), 'Frozen source path outside repository')
                require(sha256(path) == expected_hash, 'Frozen G0 source hash mismatch: ' + relative)
            source_files.append(freeze_path)
        else:
            archive_checks, archive_sources = audit_g0_archives(implementation, stage)
            g0['source_archives'] = archive_checks
            source_files += archive_sources
        source_files += [stage / 'index.json', implementation / 'evaluator' / 'probes_v1.json']
    return {'schema': 'bc-rpi-independent-record-audit-v1',
            'status': 'saved_records_consistent_within_checked_scope',
            'scope': 'Entire campaign call journal and the named stage saved outcome files; no policy executions.',
            'not_a_g0_acceptance_by_itself': True,
            'stage': str(stage), 'counts': dict(sorted(counts.items())),
            'g0_pair_audit': g0,
            'outcomes_checked': len(findings), 'outcomes': findings,
            'journal_run_ids_without_outcome_in_this_stage': sorted(set(runs) - result_ids),
            'source_sha256': {str(p): sha256(p) for p in source_files},
            'auditor_sha256': sha256(__file__)}


def audit_g0_archives(implementation, stage):
    """Verify each historical stage's exact archived bytes, not a latest-file substitute."""
    registry_path = stage / 'source_archives.json'
    registry = read_json(registry_path)
    require(registry['archives'], 'Empty G0 source archive registry')
    repo = implementation.parents[3]
    observed_stages, findings, sources = set(), [], [registry_path]
    latest_expected = {}
    for entry in registry['archives']:
        name = entry['stage']
        require(type(name) is str and Path(name).name == name and name not in observed_stages,
                'Invalid or duplicate source archive stage')
        observed_stages.add(name)
        stage_dir = (implementation / 'results' / name).resolve()
        require(stage_dir.is_relative_to(implementation / 'results'), 'Source archive stage escapes results')
        archive_path = stage_dir / 'sources.zip'
        freeze_path = stage_dir / 'source_freeze.json'
        freeze = read_json(freeze_path)
        require(sha256(archive_path) == entry['sha256'], 'Source archive checksum mismatch')
        require(freeze['deploy_implementation_sha256'] == registry['deploy_implementation_sha256'],
                'G0 stages used different deployed implementations')
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.namelist()
            require(len(members) == len(set(members)) == entry['members'] + 1
                    and set(members) == set(freeze['files']) | {'_SOURCE_ARCHIVE_MANIFEST.json'},
                    'Source archive member-set mismatch')
            embedded = json.loads(archive.read('_SOURCE_ARCHIVE_MANIFEST.json'))
            require(embedded['files'] == freeze['files']
                    and embedded['provenance'] == entry['provenance']
                    and embedded['reconstructed_members'] == entry.get('reconstructed_members', []),
                    'Embedded source archive manifest mismatch')
            for relative, expected in freeze['files'].items():
                current = (repo / relative).resolve()
                require(current.is_relative_to(repo), 'Archived source path outside repository')
                require(hashlib.sha256(archive.read(relative)).hexdigest() == expected,
                        'Archived source content hash mismatch: ' + relative)
        latest_expected.update(freeze['files'])
        findings.append({'stage': name, 'source_members_verified': len(freeze['files']),
                         'provenance': entry['provenance'],
                         'reconstructed_members': entry.get('reconstructed_members', [])})
        sources += [archive_path, freeze_path]
    # The registry preserves actual stage execution order. Historical orchestration
    # versions remain verified above; current files must match their final freeze.
    for relative, expected in latest_expected.items():
        require(sha256(repo / relative) == expected, 'Current final frozen source/input drift: ' + relative)
    indexed_stages = set()
    for row in read_json(stage / 'index.json')['runs']:
        resolved = (implementation / row['path']).resolve()
        require(resolved.is_relative_to(implementation / 'results'), 'Archived outcome escapes results')
        parts = resolved.relative_to(implementation / 'results').parts
        require(len(parts) >= 2, 'Archived outcome lacks a stage directory')
        indexed_stages.add(parts[0])
    require(indexed_stages <= observed_stages, 'Indexed outcome lacks a verified stage source archive')
    return findings, sources


def audit_g0_pairs(implementation, stage, campaign_runs):
    """Independently align the registered 48 C7 and 12 latest-Q3 world pairs."""
    implementation, stage = Path(implementation).resolve(), Path(stage).resolve()
    index = read_json(stage / 'index.json')
    require(index['schema'] == 'bc-rpi-g0-run-index-v1', 'Unknown G0 index schema')
    probes = read_json(implementation / 'evaluator' / 'probes_v1.json')['worlds']
    registration = read_json(implementation / 'execution_registration.json')
    require(sha256(implementation / 'evaluator' / 'probes_v1.json') == registration['world_registry_sha256'],
            'Registered probe file hash changed')
    expected_c7 = {w['world_sha256'] for w in probes if w['phase'] == 'g0'}
    expected_q3 = {w['world_sha256'] for w in probes
                   if w['phase'] == 'g0' and w['mode'] == 3 and w['index'] < 12}
    require(len(expected_c7) == 48 and len(expected_q3) == 12, 'Incorrect registered G0 world coverage')
    grouped = {}
    all_ids = set()
    for row in index['runs']:
        require(row['run_id'] not in all_ids, 'Duplicate run ID in stage index')
        all_ids.add(row['run_id'])
        require(row['run_id'] in campaign_runs, 'Indexed run missing from actual journal')
        start = campaign_runs[row['run_id']]['start']
        require(start['metadata']['world_sha256'] == row['world_sha256']
                and start['metadata']['mode'] == row['mode'], 'Index/journal world or mode mismatch')
        path = (implementation / row['path']).resolve()
        require(path.is_relative_to(implementation / 'results'), 'Outcome index escapes registered result storage')
        result = read_json(path)
        require(result['run_id'] == row['run_id'], 'Indexed path points to another run')
        if row['family'] not in ('c7_equivalence', 'latest_q3_passthrough'):
            continue
        require(start['kind'] == result['kind'] == 'full', 'Equivalence pair is not a complete entered execution')
        require(start['metadata']['policy'] == row['policy'], 'Index/journal policy mismatch')
        key = (row['family'], row['world_sha256'])
        block = grouped.setdefault(key, {})
        require(row['policy'] not in block, 'Duplicate policy within a registered world pair')
        block[row['policy']] = result
    findings = []
    family_spec = {
        'c7_equivalence': (expected_c7, ('original_c7', 'teacher0')),
        'latest_q3_passthrough': (expected_q3, ('latest_q3_direct', 'latest_q3_passthrough')),
    }
    for family, (expected, policies) in family_spec.items():
        observed = {world for group, world in grouped if group == family}
        require(observed == expected, 'Missing/extra registered world pairs: ' + family)
        for world in sorted(expected):
            block = grouped[family, world]
            require(set(block) == set(policies), 'Incomplete/extra policy pair: ' + family)
            left, right = (block[p] for p in policies)
            require(left['success'] and right['success'], 'Incomplete episode in equivalence pair')
            require(canonical_log(left['environment_log']) == canonical_log(right['environment_log']),
                    'Independent G0 full request/response parity mismatch')
            require(left['modeled_full_virtual_us'] == right['modeled_full_virtual_us'],
                    'Independent G0 task-cost mismatch')
            require(left['private_terminal_sources'] == right['private_terminal_sources'],
                    'Independent G0 terminal-world mismatch')
            latest_q3 = family == 'latest_q3_passthrough'
            require(comparable_controller(left['episode']['controller_final'], latest_q3=latest_q3)
                    == comparable_controller(right['episode']['controller_final'], latest_q3=latest_q3),
                    'Independent G0 final public-controller mismatch')
            if family == 'c7_equivalence':
                require(not right['episode']['controller_recoveries']
                        and right['episode']['fallback_reason'] is None,
                        'Fallback/controller recovery masks teacher0 equivalence failure')
            findings.append({'family': family, 'world_sha256': world,
                             'left_run': left['run_id'], 'right_run': right['run_id'],
                             'matched_accepted_events_per_run': len(left['environment_log'])})
    return {'status': 'exact_saved_g0_pair_parity', 'paired_c7_worlds': 48,
            'paired_latest_q3_worlds': 12,
            'excluded_response_fields': ['real_timestamp_ms', 'remaining_real_duration_s'],
            'latest_q3_only_excluded_controller_value': 'counters.a1_cover_cpu_s',
            'pairs': findings,
            'scope': 'Registered pair coverage and saved complete traces; fixture safety is a separate review.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--implementation', required=True, type=Path)
    parser.add_argument('--stage', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--g0', action='store_true', help='Also require all registered G0 pairs and frozen source hashes')
    ledger = parser.add_mutually_exclusive_group()
    ledger.add_argument('--ledger-directory', type=Path, help='Use a previously frozen ledger snapshot')
    ledger.add_argument('--snapshot-ledger-to', type=Path, help='Freeze a settled ledger, then audit that immutable copy')
    args = parser.parse_args()
    require(not args.out.exists(), 'Audit output exists; preserve the previous audit')
    ledger_directory = args.ledger_directory
    if args.snapshot_ledger_to is not None:
        ledger_directory = snapshot_ledger(args.implementation, args.snapshot_ledger_to)
    result = audit(args.implementation, args.stage, check_g0=args.g0, ledger_directory=ledger_directory)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('status', 'counts', 'outcomes_checked')}, indent=2))


if __name__ == '__main__':
    main()
