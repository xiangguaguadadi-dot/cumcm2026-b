#!/usr/bin/env python3
"""Read-only audit of a settled training campaign's actual business-call records.

This does not import the trainer, actor, simulator, or their aggregate metrics.
Training updates, label correctness, and model selection need separate checks.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

from audit_rl_execution import (
    audit_fixture_outcome,
    audit_journal,
    audit_outcome,
    nonnegative_integer,
    read_json,
    require,
    sha256,
)


def settle_counts(status, counts):
    for key in (
        'business_calls', 'accepted_calls', 'entered', 'full_runs', 'suffix_runs',
        'fixture_runs', 'executions_started', 'executions_completed', 'failed_runs',
        'unknown_cost_runs',
    ):
        require(key in status and nonnegative_integer(status[key]), 'Invalid status count: ' + key)
        require(status[key] == counts[key], 'Status/journal mismatch: ' + key)
    require(nonnegative_integer(status['rejected_calls']) and status['rejected_calls'] == counts['rejected_calls'],
            'Rejected-call partition differs')
    require(nonnegative_integer(status['unknown_cost_calls']) and status['unknown_cost_calls'] == counts['unknown_calls'],
            'Unknown-call partition differs')
    require(status['current_run'] is None and status['reserved_calls'] == 0, 'Active execution reservation')
    require(counts['unfinished_runs'] == counts['unresolved_calls'] == 0, 'Journal not settled')
    require(counts['business_calls'] <= status['limits']['business_calls'], 'Global call cap exceeded')
    require(counts['executions_started'] <= status['limits']['executions'], 'Global execution cap exceeded')
    # A real fitting run is permitted here. Never reuse the historical G0/G1
    # assertion that network_training_runs must be zero.
    require(nonnegative_integer(status.get('network_training_runs', 0)), 'Invalid training counter')


def audit_reservations(status, rows):
    """Recompute stage use and full-tail admission reserves from actual order."""
    limits = status['limits']
    phase_calls = Counter()
    phase_executions = Counter()
    attempts = executions = run_attempts = 0
    phase = None
    unknown_seen = False
    reserve = limits['run_call_reserve']
    require(type(reserve) is int and reserve == 15846, 'Unexpected full-tail reserve')
    for row in rows:
        event = row['event']
        if event == 'run_start':
            require(not unknown_seen, 'Run started after unknown request acceptance')
            phase = row['metadata']['stage']
            require(phase in limits['phase_calls'], 'Execution in unregistered stage')
            require(attempts + reserve <= limits['business_calls'], 'Started without total tail reserve')
            require(phase_calls[phase] + reserve <= limits['phase_calls'][phase], 'Started without stage tail reserve')
            require(executions < limits['executions'], 'Started beyond execution cap')
            if phase == 'compatibility':
                require(phase_executions[phase] < limits['compatibility_executions'], 'Compatibility count cap exceeded')
            phase_executions[phase] += 1
            executions += 1
            run_attempts = 0
        elif event == 'call_start':
            require(not unknown_seen, 'Call issued after unknown request acceptance')
            attempts += 1
            phase_calls[phase] += 1
            run_attempts += 1
            require(run_attempts <= reserve, 'Per-run continuation request cap exceeded')
        elif event == 'call_exception' and row.get('acceptance', 'unknown') == 'unknown':
            unknown_seen = True
    require(set(status['phase_calls']) == set(limits['phase_calls']), 'Missing/extra stage in status')
    require(set(status['phase_executions']) == set(limits['phase_calls']), 'Missing/extra stage execution count')
    for name in limits['phase_calls']:
        require(nonnegative_integer(status['phase_calls'][name]) and status['phase_calls'][name] == phase_calls[name],
                'Stage call count mismatch: ' + name)
        require(nonnegative_integer(status['phase_executions'][name]) and status['phase_executions'][name] == phase_executions[name],
                'Stage execution count mismatch: ' + name)
        require(phase_calls[name] <= limits['phase_calls'][name], 'Stage call cap exceeded: ' + name)
    return dict(phase_calls=dict(phase_calls), phase_executions=dict(phase_executions), unknown_seen=unknown_seen)


def audit_campaign(campaign, ledger, *, outcome_root=None):
    campaign, ledger = Path(campaign).resolve(), Path(ledger).resolve()
    outcome_root = Path(outcome_root or campaign).resolve()
    require(outcome_root.is_relative_to(campaign), 'Outcome root outside new campaign')
    status_path = ledger / 'execution_status.json'
    journal_path = ledger / 'execution_calls.jsonl'
    if not journal_path.exists():
        journal_path = ledger / 'execution_calls.jsonl.gz'
    status_bytes, journal_bytes = status_path.read_bytes(), journal_path.read_bytes()
    plain = gzip.decompress(journal_bytes) if journal_path.suffix == '.gz' else journal_bytes
    rows = [json.loads(line) for line in plain.splitlines() if line.strip()]
    counts, runs = audit_journal(rows)
    status = json.loads(status_bytes)
    settle_counts(status, counts)
    reservations = audit_reservations(status, rows)
    require(status_path.read_bytes() == status_bytes and journal_path.read_bytes() == journal_bytes,
            'Live ledger changed during read; wait for a settled stage boundary')

    sources = {str(status_path): sha256(status_path), str(journal_path): sha256(journal_path)}
    outcomes, checks = {}, []
    for path in sorted(outcome_root.rglob('*.json.gz')):
        result = read_json(path)
        if not isinstance(result, dict) or result.get('schema') not in (
            'bc-rpi-evaluator-outcome-v1', 'bc-rpi-real-interface-fixture-v1',
        ):
            continue
        run_id = result['run_id']
        require(run_id in runs, 'Saved outcome has no actual journal execution: ' + run_id)
        require(run_id not in outcomes, 'Duplicate actual outcome: ' + run_id)
        check = audit_fixture_outcome if result['schema'] == 'bc-rpi-real-interface-fixture-v1' else audit_outcome
        checks.append(check(result, runs[run_id]))
        outcomes[run_id] = result
        sources[str(path)] = sha256(path)
    require(set(outcomes) == set(runs), 'Paid executions with missing saved outcomes: ' + str(sorted(set(runs) - set(outcomes))))

    stage_counts = {}
    for run_id, run in runs.items():
        metadata = run['start'].get('metadata', {})
        stage = metadata.get('budget_stage', metadata.get('stage', metadata.get('phase', 'unspecified')))
        require(type(stage) is str, 'Invalid stage identity')
        tally = stage_counts.setdefault(stage, Counter())
        tally['executions'] += 1
        tally[run['start']['kind']] += 1
        for key, value in run['counts'].items():
            tally[key] += value
        tally['failed_runs'] += not outcomes[run_id]['success']
    require(sum(t['business_calls'] for t in stage_counts.values()) == counts['business_calls'],
            'Stage calls do not partition total')
    return dict(
        schema='bc-rpi-training-independent-business-record-audit-v1',
        status='all_recorded_business_calls_and_saved_outcomes_reconciled',
        actual_policy_executions_by_this_auditor=0,
        counts=dict(sorted(counts.items())),
        reservation_audit=reservations,
        per_recorded_stage={k: dict(sorted(v.items())) for k, v in sorted(stage_counts.items())},
        outcomes_checked=len(outcomes),
        declared_network_training_runs=status.get('network_training_runs', 0),
        training_counter_verified_against_updates=False,
        decompressed_journal_sha256=hashlib.sha256(plain).hexdigest(),
        outcome_checks=checks,
        source_sha256=sources,
        auditor_sha256=sha256(__file__),
        evidence_limits=[
            'Saved-record physical accounting and success consistency, not an independent replay.',
            'World partition, labels, gradients, calibration and selection are audited separately.',
            'Training counter is declared here, not proof of parameter updates.',
        ],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--ledger', type=Path)
    parser.add_argument('--outcome-root', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    require(not args.out.exists(), 'Preserve prior audit; choose a new output')
    result = audit_campaign(args.campaign, args.ledger or args.campaign, outcome_root=args.outcome_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('status', 'counts', 'outcomes_checked')}, indent=2))


if __name__ == '__main__':
    main()
