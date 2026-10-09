"""Persistência SQLite: jobs/attempts/events/IoT/schedules, idempotência e recuperação."""
import json, sqlite3
from pathlib import Path
from .models import JobState, validate_transition, utcnow, new_id

class Store:
    def __init__(self, path='data/orchestrator.db'):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys = ON')
        self.db.execute('PRAGMA busy_timeout = 10000')
        self.db.execute('PRAGMA journal_mode = WAL')
        self.init_schema()

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

    def init_schema(self):
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL DEFAULT 1,
            job_type TEXT NOT NULL, state TEXT NOT NULL, input_json TEXT NOT NULL,
            requirements_json TEXT NOT NULL, result_json TEXT,
            priority INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL, max_attempts INTEGER NOT NULL DEFAULT 2,
            error_type TEXT, idempotency_key TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS attempts (
            id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id),
            worker_id TEXT NOT NULL, started_at TEXT NOT NULL,
            finished_at TEXT, error_type TEXT, retryable INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL REFERENCES jobs(id),
            type TEXT NOT NULL, ts TEXT NOT NULL, data_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS iot_actions (
            id TEXT PRIMARY KEY, action_key TEXT NOT NULL UNIQUE, ts TEXT NOT NULL,
            resource TEXT NOT NULL, action TEXT NOT NULL, mode TEXT NOT NULL,
            decision TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS schedules (
            id TEXT PRIMARY KEY, job_type TEXT NOT NULL, input_json TEXT NOT NULL,
            every_seconds INTEGER NOT NULL, next_run_at INTEGER NOT NULL, enabled INTEGER NOT NULL DEFAULT 1
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state,priority,created_at);
        CREATE INDEX IF NOT EXISTS idx_events_job ON events(job_id,id);
        CREATE INDEX IF NOT EXISTS idx_attempts_job ON attempts(job_id,started_at);
        ''')
        self.db.commit()

    def event(self, job_id, kind, data=None):
        # data deve ser sanitizado pelo chamador; nunca passar prompts/segredos
        self.db.execute('INSERT INTO events(job_id,type,ts,data_json) VALUES(?,?,?,?)',
                        (job_id,kind,utcnow(),json.dumps(data or {})))
        self.db.commit()

    def submit(self, job):
        if job.idempotency_key:
            row = self.db.execute('SELECT id FROM jobs WHERE idempotency_key=?', (job.idempotency_key,)).fetchone()
            if row:
                return row['id']
        try:
            with self.db:
                self.db.execute('''INSERT INTO jobs(id,schema_version,job_type,state,input_json,requirements_json,
                    priority,created_at,updated_at,max_attempts,idempotency_key)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                    (job.job_id,job.schema_version,job.job_type,JobState.CREATED.value,
                     json.dumps(job.input),json.dumps(vars(job.requirements)),job.priority,
                     job.created_at,job.created_at,job.max_attempts,job.idempotency_key))
            self.event(job.job_id,'JOB_CREATED')
            self.transition(job.job_id, JobState.QUEUED)
        except sqlite3.IntegrityError:
            if job.idempotency_key:
                row = self.db.execute('SELECT id FROM jobs WHERE idempotency_key=?', (job.idempotency_key,)).fetchone()
                if row:
                    return row['id']
            raise
        return job.job_id

    def get(self, job_id):
        row = self.db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        return dict(row) if row else None

    def next_job(self):
        row = self.db.execute("SELECT * FROM jobs WHERE state='QUEUED' ORDER BY priority DESC, created_at, id LIMIT 1").fetchone()
        return dict(row) if row else None

    def transition(self, job_id, target, result=None, error=None):
        row = self.get(job_id)
        if row is None:
            raise KeyError('Job desconhecido: ' + str(job_id))
        target = JobState(target)
        validate_transition(row['state'], target)
        with self.db:
            self.db.execute('UPDATE jobs SET state=?,updated_at=?,result_json=COALESCE(?,result_json),error_type=? WHERE id=?',
                            (target.value,utcnow(),json.dumps(result) if result is not None else None,error,job_id))
        self.event(job_id, 'JOB_' + target.value, {'error_type': error} if error else {})

    def begin_attempt(self, job_id, worker_id):
        attempt_id = new_id('att')
        with self.db:
            self.db.execute('INSERT INTO attempts(id,job_id,worker_id,started_at) VALUES(?,?,?,?)',
                            (attempt_id,job_id,worker_id,utcnow()))
        self.event(job_id, 'ATTEMPT_STARTED', {'attempt_id': attempt_id, 'worker_id': worker_id})
        return attempt_id

    def finish_attempt(self, attempt_id, error_type=None, retryable=False):
        with self.db:
            self.db.execute('UPDATE attempts SET finished_at=?,error_type=?,retryable=? WHERE id=?',
                            (utcnow(),error_type,int(retryable),attempt_id))

    def attempt_count(self, job_id):
        return self.db.execute('SELECT count(*) FROM attempts WHERE job_id=?', (job_id,)).fetchone()[0]

    def history(self, job_id):
        return [dict(row) for row in self.db.execute('SELECT * FROM events WHERE job_id=? ORDER BY id', (job_id,))]

    def attempts(self, job_id):
        return [dict(row) for row in self.db.execute('SELECT * FROM attempts WHERE job_id=? ORDER BY started_at', (job_id,))]

    def list_jobs(self, limit=30):
        return [dict(row) for row in self.db.execute('SELECT id,job_type,state,priority,created_at,error_type FROM jobs ORDER BY created_at DESC LIMIT ?', (limit,))]

    def cancel(self, job_id):
        row = self.get(job_id)
        if row and row['state'] not in ('SUCCEEDED','FAILED','CANCELLED'):
            self.transition(job_id, JobState.CANCELLED)
            return True
        return False

    def reconcile(self):
        # Evita inventar se um side effect externo ocorreu: requer retry explícito.
        rows = list(self.db.execute("SELECT id,state FROM jobs WHERE state IN ('DISPATCHING','RUNNING','VERIFYING','WAITING_RETRY')"))
        for row in rows:
            if row['state'] != 'WAITING_RETRY':
                self.transition(row['id'], JobState.WAITING_RETRY, error='process_restarted')
            self.transition(row['id'], JobState.QUEUED)
        return len(rows)

    def metrics(self):
        return {row['state']:row['n'] for row in self.db.execute('SELECT state,count(*) n FROM jobs GROUP BY state')}

    def backup(self, output):
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        dest = sqlite3.connect(output)
        try:
            self.db.backup(dest)
        finally:
            dest.close()

    def record_iot(self, action_key, resource, action, mode, decision):
        try:
            with self.db:
                self.db.execute('INSERT INTO iot_actions(id,action_key,ts,resource,action,mode,decision) VALUES(?,?,?,?,?,?,?)',
                                (new_id('iot'),action_key,utcnow(),resource,action,mode,decision))
            return True
        except sqlite3.IntegrityError:
            return False

    def add_schedule(self, schedule_id, job_type, input_data, every_seconds, next_run_at):
        if every_seconds < 60:
            raise ValueError('Intervalo mínimo: 60 segundos')
        with self.db:
            self.db.execute('INSERT INTO schedules(id,job_type,input_json,every_seconds,next_run_at) VALUES(?,?,?,?,?)',
                            (schedule_id,job_type,json.dumps(input_data),every_seconds,int(next_run_at)))

    def due_schedules(self, now):
        return [dict(r) for r in self.db.execute('SELECT * FROM schedules WHERE enabled=1 AND next_run_at<=? ORDER BY next_run_at', (int(now),))]

    def advance_schedule(self, schedule_id, from_ts, next_run_at):
        with self.db:
            cur = self.db.execute('UPDATE schedules SET next_run_at=? WHERE id=? AND next_run_at=?',
                                  (int(next_run_at),schedule_id,int(from_ts)))
        return cur.rowcount == 1
