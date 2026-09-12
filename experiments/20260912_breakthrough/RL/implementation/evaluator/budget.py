"""Persistent actual-call ledger for the one approved G0/G1 campaign."""
from __future__ import annotations
import json
from pathlib import Path
import resource
import time
from datetime import datetime, timezone

IMPL = Path(__file__).resolve().parents[1]
STATUS = IMPL / 'execution_status.json'
JOURNAL = IMPL / 'execution_calls.jsonl'
START_UTC_SECONDS = datetime(2026, 9, 12, 6, 7, 41, tzinfo=timezone.utc).timestamp()


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.pending')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


class BudgetStop(RuntimeError):
    pass


class Budget:
    def __init__(self, *, directory=IMPL):
        self.directory = Path(directory)
        self.status_path = self.directory/'execution_status.json'
        self.journal_path = self.directory/'execution_calls.jsonl'
        if self.status_path.exists():
            self.data = json.loads(self.status_path.read_text())
        else:
            self.data = dict(status='implementing_g0', entered=0, full_runs=0, suffix_runs=0,
                fixture_runs=0, executions_started=0, executions_completed=0,
                business_calls=0, accepted_calls=0, failed_calls=0, failed_runs=0,
                network_training_runs=0, unknown_cost_runs=0, reserved_calls=0,
                current_run=None, runs=[], limits=dict(business_calls=350000,
                    executions=2000, run_call_reserve=15846, campaign_wall_s=21600,
                    raw_bytes=8*1024**3, rss_bytes=16*1024**3))
            self.save()
        if self.data['current_run'] is not None:
            raise BudgetStop('Previous run was not settled; audit before resuming')
        self.data.setdefault('unknown_cost_calls',0)
        self.data.setdefault('rejected_calls',self.data['failed_calls'])
        self.data.setdefault('exception_calls',0)
        self.data.setdefault('stopped_for_unknown_acceptance',False)
        if self.journal_path.exists():
            open_runs=set()
            for line in self.journal_path.read_text().splitlines():
                row=json.loads(line)
                if row['event']=='run_start':open_runs.add(row['run_id'])
                elif row['event']=='run_finish':open_runs.discard(row['run_id'])
            if open_runs:
                raise BudgetStop('Journal contains an unsettled run; status alone is not authoritative')

    def save(self):
        self.data['updated_utc'] = datetime.now(timezone.utc).isoformat()
        self.data['wall_since_registration_s'] = max(0, time.time() - START_UTC_SECONDS)
        atomic_json(self.status_path, self.data)

    def append(self, row):
        row = dict(row, recorded_utc=datetime.now(timezone.utc).isoformat())
        with self.journal_path.open('a') as stream:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')

    def set_phase(self, status):
        self.data['status'] = status
        self.save()

    def start(self, run_id, kind, metadata=None):
        d = self.data
        if d['current_run'] is not None:
            raise BudgetStop('One live run at a time')
        if d['stopped_for_unknown_acceptance']:
            raise BudgetStop('Unknown acceptance requires independent audit; no automatic continuation')
        if any(r['run_id'] == run_id for r in d['runs']):
            raise BudgetStop('Run ID exists; do not silently re-execute')
        if d['business_calls'] + 15846 > d['limits']['business_calls']:
            raise BudgetStop('Insufficient remaining budget for full continuation reserve')
        if d['executions_started'] >= d['limits']['executions']:
            raise BudgetStop('Execution-count budget reached')
        if time.time() - START_UTC_SECONDS >= d['limits']['campaign_wall_s']:
            raise BudgetStop('Campaign wall-time budget reached')
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > d['limits']['rss_bytes']:
            raise BudgetStop('RSS budget reached')
        raw_bytes = sum(p.stat().st_size for p in self.directory.rglob('*') if p.is_file())
        if raw_bytes >= d['limits']['raw_bytes']:
            raise BudgetStop('Raw-data budget reached')
        if kind not in ('full', 'suffix', 'fixture'):
            raise ValueError('Unknown execution kind')
        d['executions_started'] += 1
        d[kind + '_runs'] += 1
        d['reserved_calls'] = 15846
        d['current_run'] = dict(run_id=run_id, kind=kind, attempted=0, accepted=0, failed=0,
            metadata=metadata or {}, started_monotonic=time.monotonic(), pending_call=None,
            unknown_acceptance_calls=[])
        self.append(dict(event='run_start', **d['current_run']))
        self.save()

    def call(self, action, function, args, exception_evidence=None):
        d, r = self.data, self.data['current_run']
        if r is None:
            raise RuntimeError('Unmetered actual API call forbidden')
        if d['stopped_for_unknown_acceptance']:
            raise BudgetStop('A previous call has unknown acceptance; do not retry or fallback')
        if r['attempted'] >= 15846 or d['business_calls'] >= d['limits']['business_calls']:
            raise BudgetStop('Hard business-call bound exceeded')
        sequence = d['business_calls']
        d['business_calls'] += 1
        r['attempted'] += 1
        d['reserved_calls'] -= 1
        r['pending_call'] = sequence
        self.append(dict(event='call_start', run_id=r['run_id'], sequence=sequence,
                         action=action, args=list(args)))
        started = time.monotonic()
        try:
            response = function(*args)
        except BaseException as exc:
            d['exception_calls'] += 1
            evidence = exception_evidence() if exception_evidence is not None else {'acceptance':'unknown'}
            self.append(dict(event='call_exception', run_id=r['run_id'], sequence=sequence,
                             error=type(exc).__name__ + ': ' + str(exc), **evidence))
            if evidence['acceptance']=='unknown':
                r['unknown_acceptance_calls'].append(sequence)
                d['unknown_cost_calls'] += 1
                d['stopped_for_unknown_acceptance'] = True
                d['status'] = 'stopped_unknown_acceptance'
            else:
                d['failed_calls'] += 1
                d['rejected_calls'] += 1
                r['failed'] += 1
            r['pending_call'] = None
            self.save()
            raise
        accepted = response.get('accepted') is True
        if accepted:
            d['accepted_calls'] += 1
            r['accepted'] += 1
            if action == 'enter':
                d['entered'] += 1
        else:
            d['failed_calls'] += 1
            d['rejected_calls'] += 1
            r['failed'] += 1
        self.append(dict(event='call_response', run_id=r['run_id'], sequence=sequence,
                         accepted=accepted, response=response,
                         backend_wall_s=time.monotonic() - started))
        r['pending_call'] = None
        if d['business_calls'] % 25 == 0:
            self.save()
        return response

    def finish(self, success, details=None, unknown_cost=False):
        d, r = self.data, self.data['current_run']
        if r is None or r['pending_call'] is not None:
            raise BudgetStop('Cannot settle an unknown in-flight call')
        unknown_cost = bool(unknown_cost or r['unknown_acceptance_calls'])
        success = bool(success and not unknown_cost)
        row = {k: v for k, v in r.items() if k not in ('started_monotonic', 'pending_call')}
        row.update(success=bool(success), unknown_cost=bool(unknown_cost), details=details or {},
                   actual_wall_s=time.monotonic() - r['started_monotonic'])
        d['runs'].append(row)
        d['executions_completed'] += 1
        d['failed_runs'] += not success
        d['unknown_cost_runs'] += bool(unknown_cost)
        d['reserved_calls'] = 0
        d['current_run'] = None
        if d['business_calls'] != d['accepted_calls']+d['rejected_calls']+d['unknown_cost_calls']:
            raise BudgetStop('Attempt/accepted/rejected/unknown partition differs')
        self.append(dict(event='run_finish', **row))
        self.save()
        return row


class CountedBackend:
    """Expose only four instrumented callables, never the private environment."""
    def __init__(self, environment, budget):
        def invoke(action,args):
            def ledger():
                return (environment._virtual_us,len(environment.log),environment.measures,
                    environment.clear_attempts,environment.successes,environment.position,
                    environment.channel,environment.started)
            before=ledger()
            def evidence():
                after=ledger()
                # Only the trusted local evaluator can prove a deadline/validation
                # rejection by inspecting its immutable-environment ledger.
                return dict(acceptance='known_no_accept' if before==after else 'unknown',
                    local_private_ledger_unchanged=before==after,
                    private_log_count_before=before[1],private_log_count_after=after[1],
                    virtual_us_before=before[0],virtual_us_after=after[0])
            return budget.call(action,getattr(environment,action),args,evidence)
        self.enter = lambda: invoke('enter', ())
        self.measure = lambda x,y,ch: invoke('measure',(x,y,ch))
        self.clear = lambda x,y,ch: invoke('clear',(x,y,ch))
        self.exit = lambda: invoke('exit', ())
