"""Worker Registry, slots e health thresholds."""
import json, os, time
from urllib.request import Request, urlopen
from .models import WorkerSpec, WorkerHealth, utcnow

class WorkerRegistry:
    def __init__(self, workers=()):
        self.specs = {}
        self.health = {}
        for worker in workers:
            self.add(worker)

    @classmethod
    def from_json(cls, path):
        with open(path, encoding='utf-8') as stream:
            doc = json.load(stream)
        if doc.get('schema_version') != 1:
            raise ValueError('Workers schema_version deve ser 1')
        return cls(WorkerSpec(**entry) for entry in doc.get('workers', []))

    def add(self, spec):
        if spec.id in self.specs:
            raise ValueError('Worker duplicado: ' + spec.id)
        self.specs[spec.id] = spec
        self.health[spec.id] = WorkerHealth(worker_id=spec.id)

    def reserve(self, worker_id):
        spec, health = self.specs[worker_id], self.health[worker_id]
        if health.active_jobs >= spec.max_parallel:
            return False
        health.active_jobs += 1
        return True

    def release(self, worker_id):
        health = self.health[worker_id]
        health.active_jobs = max(0, health.active_jobs - 1)

    def mark_health(self, worker_id, ok, latency_ms=None, error=None):
        health = self.health[worker_id]
        health.last_check_at = utcnow()
        health.latency_ms = latency_ms
        health.last_error = str(error)[:160] if error else None
        health.model_loaded = bool(ok)
        if ok:
            health.consecutive_failures = 0
            health.status = 'BUSY' if health.active_jobs >= self.specs[worker_id].max_parallel else 'HEALTHY'
        else:
            health.consecutive_failures += 1
            health.status = 'DEGRADED' if health.consecutive_failures < 3 else 'OFFLINE'
        return health

    def probe(self, worker_id, timeout=3):
        spec = self.specs[worker_id]
        start = time.monotonic()
        headers = {}
        if spec.token_env:
            token = os.environ.get(spec.token_env)
            if token:
                headers['Authorization'] = 'Bearer ' + token
        # /health do llama-server, sem gerar tokens
        req = Request(spec.endpoint.rstrip('/') + '/health', headers=headers)
        try:
            with urlopen(req, timeout=timeout) as res:
                ok = 200 <= res.status < 300
            return self.mark_health(worker_id, ok, round((time.monotonic()-start)*1000, 2))
        except Exception as exc:
            return self.mark_health(worker_id, False, error=type(exc).__name__)

    def as_rows(self):
        return [dict(id=s.id, endpoint=s.endpoint, capabilities=s.capabilities,
                     enabled=s.enabled, status=self.health[s.id].status,
                     active_jobs=self.health[s.id].active_jobs,
                     max_parallel=s.max_parallel)
                for s in self.specs.values()]
