"""Frozen-source, budgeted LOCAL runs. All policies see only four API methods."""
from __future__ import annotations
import argparse
import concurrent.futures
import gzip
import hashlib
import importlib.util
import json
import math
import multiprocessing
import os
from pathlib import Path
import platform
import sys
import time
import traceback
import uuid
import zipfile

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
REPO = CAMPAIGN.parents[1]
sys.path.insert(0, str(HERE))
from budget import Budget, BudgetStop


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False,
                      default=lambda x: sorted(x) if isinstance(x,set) else _unsupported(x))


def _unsupported(value):
    raise TypeError('Not serializable: '+type(value).__name__)


def journal_safe(value):
    if isinstance(value,float) and not math.isfinite(value):
        return {'nonfinite_float':repr(value)}
    if isinstance(value,(list,tuple)):
        return [journal_safe(v) for v in value]
    if isinstance(value,dict):
        return {k:journal_safe(v) for k,v in value.items()}
    return value


def dump(path, value):
    path = Path(path)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    os.replace(temp, path)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def verify_manifest():
    mpath = REPO / 'evaluation/manifest_v1.json'
    data = json.loads(mpath.read_text())
    for name, sha in data['sha256'].items():
        if digest(REPO / name) != sha:
            raise RuntimeError('Frozen evaluation mismatch: ' + name)
    return digest(mpath)


class CallLimit(BaseException):
    pass


class Recorder:
    def __init__(self, env, file, budget, run_id, cap):
        self.env, self.file, self.budget, self.run_id, self.cap = env, file, budget, run_id, cap
        self.counts = dict(attempts=0, accepted=0, rejected=0, known_error=0, unknown=0)
        self.poisoned = False

    def write(self, record):
        self.file.write(canonical(journal_safe(record)) + '\n')
        self.file.flush()

    def call(self, action, *args, **kwargs):
        if self.poisoned:
            raise CallLimit('Unknown acceptance blocks further requests')
        if self.counts['attempts'] >= self.cap:
            raise CallLimit('Per-execution research request cap')
        if not self.counts['attempts']:
            self.budget.first_call(self.run_id)
        seq = self.counts['attempts']
        self.write(dict(event='attempt', seq=seq, action=action, args=args, kwargs=kwargs))
        self.counts['attempts'] += 1
        before = (self.env.measures, self.env.clear_attempts, self.env.successes, self.env._virtual_us, len(self.env.log), self.env.started, self.env.finished)
        try:
            response = getattr(self.env, action)(*args, **kwargs)
        except BaseException as exc:
            after = (self.env.measures, self.env.clear_attempts, self.env.successes, self.env._virtual_us, len(self.env.log), self.env.started, self.env.finished)
            # Closed guard may finish without accepting a request. Any measurement,
            # clear, virtual-time, enter or accepted-log mutation makes it unknown.
            stable = before[:6] == after[:6]
            category = 'known_error' if isinstance(exc, (ValueError, ConnectionError)) and stable else 'unknown'
            self.counts[category] += 1
            self.poisoned = category == 'unknown'
            self.write(dict(event='outcome', seq=seq, category=category, error=type(exc).__name__ + ': ' + str(exc)))
            raise
        category = 'accepted' if response.get('accepted') is True else 'rejected' if response.get('accepted') is False else 'unknown'
        self.counts[category] += 1
        self.poisoned = category == 'unknown'
        self.write(dict(event='outcome', seq=seq, category=category, response=response))
        return response

    def api(self):
        class FourMethods:
            pass
        obj = FourMethods()
        for name in ('enter', 'measure', 'clear', 'exit'):
            setattr(obj, name, lambda *a, _name=name, **k: self.call(_name, *a, **k))
        return obj


def journal_counts(path):
    attempts, outcomes = {}, {}
    malformed = 0
    if Path(path).exists():
        for line in Path(path).read_text().splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if r['event'] == 'attempt':
                if r['seq'] in attempts:
                    raise ValueError('Duplicate attempt sequence')
                attempts[r['seq']] = r
            else:
                if r['seq'] in outcomes or r['seq'] not in attempts:
                    raise ValueError('Duplicate or orphan outcome')
                outcomes[r['seq']] = r
    counts = dict(attempts=len(attempts), accepted=0, rejected=0, unknown=0, known_error=0)
    for seq in attempts:
        counts[outcomes.get(seq, {}).get('category', 'unknown')] += 1
    # Conservatively block all new work if a crash left a malformed record.
    # This may overcount an unexecuted attempt; it never conceals a paid call.
    counts['attempts'] += malformed
    counts['unknown'] += malformed
    return counts


def execute_child(task, conn):
    """The child only writes its unique journal/result. Parent owns settlement."""
    sys.path.insert(0, str(REPO))
    out = Path(task['output'])
    journal = out / (task['run_id'] + '.journal.jsonl')
    env = recorder = solver = None
    result = {}
    start = time.monotonic()
    cpu_start = time.process_time()
    error = None
    try:
        for name, sha in task['frozen_files'].items():
            if digest(name) != sha:
                raise RuntimeError('Changed source before execution: ' + name)
        from local_env import LocalEnv, Source
        case = task['case']
        env = LocalEnv([Source(**s) for s in case['sources']], case['seed'], case['noise'], keep_log=True)
        with journal.open('x', encoding='utf-8') as log:
            recorder = Recorder(env, log, Budget(task['budget_path']), task['run_id'], task['cap'])
            policy = load_module('jointplan_policy_' + task['run_id'].replace('-', '_'), task['candidate'])
            config = dict(policy.OPTIMIZED_CONFIGS[case['mode']])
            config.update(task.get('policy_config',{}))
            solver = policy.Solver(recorder.api(), mode=case['mode'], **config)
            result = solver.run() or {}
            log.flush()
            os.fsync(log.fileno())
    except BaseException as exc:
        error = type(exc).__name__ + ': ' + str(exc)
        result = result if isinstance(result, dict) else {}
    elapsed, cpu = time.monotonic() - start, time.process_time() - cpu_start
    if env is not None:
        if env.started and not env.finished:
            env._finish('strategy_exception' if error else 'missing_exit')
        stats = env.stats()
        row = dict(case_id=task['case']['case_id'], mode=task['case']['mode'], group=task['case']['group'],
                   exposure_suite=task['case'].get('exposure_suite'), seed_cluster=task['case']['seed'], variant=task['label'],
                   source_count=stats['n'], cleared_count=stats['cleared'], cleared_fraction=stats['fraction'],
                   average_clear_time_s=stats['average_s'], total_virtual_time_s=stats['time_s'],
                   distance_m=stats['distance_m'], measures=stats['measures'], switches=stats['switches'],
                   clear_attempts=stats['clear_attempts'], clear_failures=stats['clear_failures'],
                   complete=stats['cleared']==stats['n'] and env.exit_reason=='user_exit' and error is None,
                   exit_reason=env.exit_reason, error=error, program_runtime_s=env.runtime_s,
                   worker_runtime_s=elapsed, worker_cpu_s=cpu,
                   requests=stats['measures']+stats['clear_attempts']+int(env.started)+int(env.exit_reason=='user_exit'),
                   coverage_certificate=result.get('coverage_complete',False))
    else:
        row = dict(case_id=task['case']['case_id'], mode=task['case']['mode'], group=task['case']['group'],
                   variant=task['label'], source_count=len(task['case']['sources']), cleared_count=None,
                   complete=False, error=error, worker_runtime_s=elapsed, worker_cpu_s=cpu)
    row.update(run_id=task['run_id'], policy_sha256=task['frozen_files'][task['candidate']],
               world_sha256=hashlib.sha256(canonical(task['case']).encode()).hexdigest())
    counts = journal_counts(journal)
    audit_payload = dict(row=row, calls=counts, solver_result=result,
                         environment_log=[] if env is None else env.log,
                         source_identity=task['frozen_files'])
    if solver is not None:
        audit_payload['semantic_state'] = {k: getattr(solver,k) for k in
            ('position','channel','virtual_time','cleared','scanned','points','counters') if hasattr(solver,k)}
        if isinstance(audit_payload['semantic_state'].get('cleared'),set):
            audit_payload['semantic_state']['cleared'] = sorted(audit_payload['semantic_state']['cleared'])
        # Optional diagnostic export is public-history-only by contract and reviewed separately.
        method = getattr(solver, 'jointplan_diagnostics', None)
        if callable(method):
            try:
                audit_payload['policy_diagnostics'] = method()
            except Exception as exc:
                audit_payload['diagnostics_error'] = type(exc).__name__ + ': ' + str(exc)
    gz = out / (task['run_id'] + '.json.gz')
    raw = canonical(audit_payload).encode()
    with gz.open('xb') as f:
        f.write(gzip.compress(raw, mtime=0))
    dump(out / (task['run_id'] + '.row.json'), row)
    conn.send(dict(row=row, calls=counts, result_path=str(gz)))
    conn.close()


def run_task(task):
    budget = Budget(task['budget_path'])
    task['run_id'] = uuid.uuid4().hex
    task['cap'] = budget.reserve(task['run_id'], task['phase'], task['batch'], task['case']['case_id'], task['frozen_files'][task['candidate']])
    out = Path(task['output'])
    dump(out / (task['run_id'] + '.registration.json'), {k:v for k,v in task.items() if k!='case'})
    ctx = multiprocessing.get_context('spawn')
    receiver, sender = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=execute_child, args=(task, sender))
    proc.start()
    sender.close()
    deadline = time.monotonic() + 1205
    payload = None
    while time.monotonic() < deadline:
        if receiver.poll(0.2):
            try:
                payload = receiver.recv()
            except EOFError:
                pass
            break
        if not proc.is_alive():
            break
    if payload is None:
        if proc.is_alive():
            proc.terminate()
        proc.join(3)
        if proc.is_alive():
            proc.kill()
            proc.join()
        row_path = out / (task['run_id'] + '.row.json')
        # A complete row may be written immediately before a pipe/process failure.
        if row_path.exists():
            row = json.loads(row_path.read_text())
            row['complete'] = False
            row['error'] = 'worker_interrupted_after_result'
        else:
            row = dict(run_id=task['run_id'], case_id=task['case']['case_id'], mode=task['case']['mode'],
                       group=task['case']['group'], variant=task['label'], source_count=len(task['case']['sources']),
                       cleared_count=None, complete=False, error='worker_timeout_or_crash',
                       policy_sha256=task['frozen_files'][task['candidate']])
        counts = journal_counts(out / (task['run_id'] + '.journal.jsonl'))
        dump(row_path, row)
        payload = dict(row=row, calls=counts, result_path=str(row_path))
    else:
        proc.join(3)
        if proc.is_alive():
            proc.terminate()
            proc.join()
    receiver.close()
    budget.finish(task['run_id'], payload['calls'], payload['result_path'])
    journal = out / (task['run_id'] + '.journal.jsonl')
    if journal.exists():
        compressed = journal.with_suffix(journal.suffix + '.gz')
        raw = journal.read_bytes()
        with compressed.open('xb') as f:
            f.write(gzip.compress(raw, mtime=0))
        assert gzip.decompress(compressed.read_bytes()) == raw
        # Byte-identical compressed journal replaces only this run's redundant hot file.
        journal.unlink()
    return payload['row']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--cases', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--phase', choices=['P0','P1','P2','P3'], required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('--dependency', type=Path, action='append', default=[])
    parser.add_argument('--config', type=Path, help='Public policy options shared by all worlds')
    parser.add_argument('--config-by-case', type=Path, help='P1 evaluator-only map; only selected public options reach the actor')
    parser.add_argument('--workers', type=int, choices=[1,2], default=2)
    args = parser.parse_args()
    verify_manifest()
    candidate, cases_path, output = args.candidate.resolve(), args.cases.resolve(), args.out.resolve()
    output.mkdir(parents=True, exist_ok=False)
    runs = output / 'runs'; runs.mkdir()
    cases = json.loads(cases_path.read_text())
    assert len({c['case_id'] for c in cases}) == len(cases) > 0
    config=json.loads(args.config.read_text()) if args.config else {}
    bycase=json.loads(args.config_by_case.read_text()) if args.config_by_case else {}
    if bycase:
        assert args.phase=='P1' and set(bycase)=={c['case_id'] for c in cases}
    files = [candidate, cases_path, Path(__file__), HERE/'budget.py', REPO/'local_env.py', REPO/'evaluation/manifest_v1.json', *args.dependency]
    files += [p for p in (args.config,args.config_by_case) if p is not None]
    files = [p.resolve() for p in files]
    frozen = {str(p):digest(p) for p in files}
    with zipfile.ZipFile(output/'frozen_inputs.zip','x',compression=zipfile.ZIP_DEFLATED) as archive:
        for path, sha in frozen.items():
            content = Path(path).read_bytes()
            if hashlib.sha256(content).hexdigest() != sha:
                raise RuntimeError('Source changed while archiving: '+path)
            archive.writestr(str(Path(path).relative_to(REPO)),content)
    registration = dict(candidate=str(candidate), cases=str(cases_path), source_files=frozen,
                        phase=args.phase, label=args.label, cases_count=len(cases), workers=args.workers,
                        started_epoch=time.time(), python=sys.version, platform=platform.platform(),
                        data_role='new_confirmation' if args.phase=='P3' else 'exposed_or_development')
    registration['frozen_archive_sha256'] = digest(output/'frozen_inputs.zip')
    dump(output/'registration.json', registration)
    rows, failure = [], None
    common = dict(candidate=str(candidate), output=str(runs), frozen_files=frozen, phase=args.phase,
                  batch=str(output.relative_to(CAMPAIGN)), label=args.label, budget_path=str(CAMPAIGN/'execution.sqlite'))
    try:
        # At most two outstanding tasks, including during a stop; no unbounded queue.
        iterator = iter(cases)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            pending = set()
            exhausted = False
            while pending or not exhausted:
                while not exhausted and failure is None and len(pending)<args.workers:
                    case = next(iterator, None)
                    if case is None:
                        exhausted=True;break
                    pending.add(pool.submit(run_task, dict(common,case=case,policy_config=bycase.get(case['case_id'],config))))
                if not pending:
                    break
                done,pending=concurrent.futures.wait(pending,return_when=concurrent.futures.FIRST_COMPLETED)
                for fut in done:
                    try:
                        rows.append(fut.result())
                    except Exception as exc:
                        failure=type(exc).__name__+': '+str(exc);exhausted=True
                dump(output/'case_metrics.json', rows)
                dump(output/'progress.json', dict(completed=len(rows),requested=len(cases),error=failure))
                if len(rows)%24<args.workers or failure:
                    print(canonical(dict(batch=output.name,completed=len(rows),requested=len(cases),error=failure)),flush=True)
    finally:
        changed=[path for path,h in frozen.items() if digest(path)!=h]
        if changed:
            failure='Sources changed during execution: '+str(changed)
        verify_manifest()
        dump(output/'case_metrics.json',rows)
        summary=dict(**registration, actual_runs=len(rows), complete_runs=sum(r['complete'] for r in rows),
                     all_complete=len(rows)==len(cases) and all(r['complete'] for r in rows) and failure is None,
                     batch_error=failure, source_changed=changed, wall_seconds=time.time()-registration['started_epoch'])
        dump(output/'summary.json',summary)
        snap=Budget(CAMPAIGN/'execution.sqlite').snapshot();dump(CAMPAIGN/'execution_status.json',snap)
    print(canonical({k:summary[k] for k in ['actual_runs','complete_runs','all_complete','batch_error','wall_seconds']}),flush=True)
    if failure:
        raise SystemExit(1)


if __name__=='__main__':
    main()
