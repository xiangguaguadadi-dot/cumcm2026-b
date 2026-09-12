"""Atomic experiment reservations. Pure accounting; no environment imports."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time


class BudgetStop(RuntimeError):
    pass


class Budget:
    def __init__(self, path, limits=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if limits is not None:
            with self.tx() as db:
                db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT NOT NULL)')
                db.execute('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY,phase TEXT,batch TEXT,case_id TEXT,policy_sha TEXT,state TEXT,reserved INTEGER,attempts INTEGER,accepted INTEGER,rejected INTEGER,unknown INTEGER,known_error INTEGER,created REAL,first_call REAL,finished REAL,result_path TEXT)')
                current = db.execute("SELECT value FROM settings WHERE key='limits'").fetchone()
                text = json.dumps(limits, sort_keys=True)
                if current is None:
                    db.execute("INSERT INTO settings VALUES ('limits',?)", (text,))
                elif current[0] != text:
                    raise ValueError('Budget limits cannot change after initialization')

    @contextmanager
    def tx(self):
        db = sqlite3.connect(self.path, timeout=60, isolation_level=None)
        try:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('PRAGMA synchronous=FULL')
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _limits(db):
        row = db.execute("SELECT value FROM settings WHERE key='limits'").fetchone()
        if row is None:
            raise BudgetStop('Budget must be initialized before use')
        return json.loads(row[0])

    def reserve(self, run_id, phase, batch, case_id, policy_sha):
        with self.tx() as db:
            stopped = db.execute("SELECT value FROM settings WHERE key='halted'").fetchone()
            if stopped is not None:
                raise BudgetStop('Campaign stopped: ' + stopped[0])
            lim = self._limits(db)
            count, live, used, reserved, unknown = db.execute("SELECT COUNT(*),COALESCE(SUM(state='active'),0),COALESCE(SUM(attempts),0),COALESCE(SUM(CASE WHEN state='active' THEN reserved ELSE 0 END),0),COALESCE(SUM(unknown),0) FROM runs").fetchone()
            first = db.execute('SELECT MIN(first_call) FROM runs').fetchone()[0]
            if unknown:
                raise BudgetStop('Unresolved acceptance: audit before starting another run')
            if first is not None and time.time() - first >= lim['wall_seconds']:
                raise BudgetStop('Research wall-clock budget reached')
            if count >= lim['execution_limit'] or live >= lim['workers']:
                raise BudgetStop('Execution or concurrent-worker limit reached')
            cap = lim['per_run_call_cap']
            phase_limit = lim['call_limit'] if phase == 'P3' else lim['call_limit'] - lim['confirmation_reserve']
            if used + reserved + cap > phase_limit:
                raise BudgetStop('Insufficient unreserved calls for another complete run')
            db.execute('INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       (run_id, phase, batch, case_id, policy_sha, 'active', cap, None, None, None, None, None, time.time(), None, None, None))
            return cap

    def halt(self, reason):
        with self.tx() as db:
            if db.execute("SELECT COUNT(*) FROM runs WHERE state='active'").fetchone()[0]:
                raise ValueError('Settle existing runs before sealing the campaign stop')
            db.execute("INSERT INTO settings(key,value) VALUES('halted',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                       (json.dumps(dict(reason=reason,epoch=time.time()),ensure_ascii=False),))

    def first_call(self, run_id):
        with self.tx() as db:
            row = db.execute('SELECT state FROM runs WHERE id=?', (run_id,)).fetchone()
            if row is None or row[0] != 'active':
                raise BudgetStop('Unreserved or completed execution')
            db.execute('UPDATE runs SET first_call=COALESCE(first_call,?) WHERE id=?', (time.time(), run_id))

    def finish(self, run_id, counts, result_path):
        assert set(counts) == {'attempts', 'accepted', 'rejected', 'unknown', 'known_error'}
        assert all(type(v) is int and v >= 0 for v in counts.values())
        assert counts['attempts'] == sum(counts[k] for k in ['accepted', 'rejected', 'unknown', 'known_error'])
        with self.tx() as db:
            row = db.execute('SELECT state,reserved FROM runs WHERE id=?', (run_id,)).fetchone()
            if row is None or row[0] != 'active':
                raise ValueError('Execution cannot be settled twice')
            if counts['attempts'] > row[1]:
                raise ValueError('Execution exceeded its reserved call cap')
            db.execute('UPDATE runs SET state=?,attempts=?,accepted=?,rejected=?,unknown=?,known_error=?,finished=?,result_path=? WHERE id=?',
                       ('completed', counts['attempts'], counts['accepted'], counts['rejected'], counts['unknown'], counts['known_error'], time.time(), str(result_path), run_id))

    def snapshot(self):
        with self.tx() as db:
            limits = self._limits(db)
            cols = 'id,phase,batch,case_id,policy_sha,state,reserved,attempts,accepted,rejected,unknown,known_error,created,first_call,finished,result_path'.split(',')
            rows = [dict(zip(cols, row)) for row in db.execute('SELECT * FROM runs ORDER BY created,id')]
        first = min((r['first_call'] for r in rows if r['first_call'] is not None), default=None)
        totals = {key: sum(r[key] or 0 for r in rows) for key in ['attempts', 'accepted', 'rejected', 'unknown', 'known_error']}
        return dict(limits=limits, executions=len(rows), completed=sum(r['state'] == 'completed' for r in rows),
                    active=sum(r['state'] == 'active' for r in rows), first_business_call_epoch=first,
                    wall_seconds=None if first is None else time.time()-first, settled_calls=totals,
                    reserved_active_calls=sum(r['reserved'] for r in rows if r['state'] == 'active'), runs=rows)
