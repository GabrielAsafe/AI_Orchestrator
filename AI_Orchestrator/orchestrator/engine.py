"""Orquestração síncrona em passos; compatível com Raspberry Pi 1 ARMv6."""
import json, time
from .models import JobSpec, JobState, Requirements, new_id
from .scheduler import requirements_for, select_worker
from .adapters import make_request, normalize_output
from .client import ModelClient, ModelClientError

class Engine:
    def __init__(self, store, registry, client=None):
        self.store, self.registry, self.client = store, registry, client or ModelClient()

    def submit(self, job_type, text, priority=0, idempotency_key=None, max_attempts=2, preferred_worker=None):
        req = requirements_for(job_type)
        req.preferred_worker = preferred_worker
        job = JobSpec(new_id('job'), job_type, {'text':text}, requirements=req,
                      priority=int(priority),max_attempts=int(max_attempts),idempotency_key=idempotency_key)
        if not 1 <= job.max_attempts <= 10:
            raise ValueError('max_attempts deve ser 1..10')
        if len(text) > 80000:
            raise ValueError('Input demasiado extenso')
        return self.store.submit(job)

    def step(self):
        job = self.store.next_job()
        if not job:
            return {'status':'idle'}
        job_id = job['id']
        requirements = Requirements(**json.loads(job['requirements_json']))
        worker, trace = select_worker(self.registry, requirements)
        self.store.event(job_id, 'SCHEDULER_DECISION', {'trace':trace})
        if worker is None:
            return {'status':'queued','job_id':job_id,'reason':'no_eligible_worker'}
        if not self.registry.reserve(worker.id):
            return {'status':'queued','job_id':job_id,'reason':'slot_full'}
        attempt = None
        try:
            self.store.transition(job_id, JobState.DISPATCHING)
            self.store.event(job_id, 'WORKER_SELECTED', {'worker_id':worker.id})
            attempt = self.store.begin_attempt(job_id, worker.id)
            self.store.transition(job_id, JobState.RUNNING)
            request = make_request(job['job_type'], json.loads(job['input_json']),timeout=worker.timeout_seconds)
            self.store.event(job_id, 'MODEL_REQUEST_SENT', {'request_id':request.request_id})
            result = self.client.complete(worker, request)
            self.store.event(job_id, 'MODEL_RESULT_RECEIVED', {'latency_ms':result.latency_ms})
            self.store.transition(job_id, JobState.VERIFYING)
            normalized = normalize_output(job['job_type'], result.text)
            # Propostas são DADOS: nunca são comandos IoT ou shell nesta camada.
            self.store.transition(job_id, JobState.SUCCEEDED, result={
                'output': normalized, 'worker_id':worker.id,
                'request_id':request.request_id, 'latency_ms':result.latency_ms,
            })
            self.store.finish_attempt(attempt)
            return {'status':'succeeded','job_id':job_id,'worker_id':worker.id}
        except (ModelClientError, ValueError) as exc:
            reason = exc.kind if isinstance(exc, ModelClientError) else 'invalid_model_output'
            retryable = exc.retryable if isinstance(exc, ModelClientError) else False
            if attempt:
                self.store.finish_attempt(attempt,reason,retryable)
            can_retry = retryable and self.store.attempt_count(job_id) < job['max_attempts']
            if can_retry:
                self.store.transition(job_id, JobState.WAITING_RETRY,error=reason)
                self.store.transition(job_id, JobState.QUEUED)
            else:
                self.store.transition(job_id, JobState.FAILED,error=reason)
            return {'status':'retry' if can_retry else 'failed', 'job_id':job_id, 'error':reason}
        finally:
            self.registry.release(worker.id)

    def run(self, idle_seconds=2, stop_flag=None):
        self.store.reconcile()
        while not (stop_flag and stop_flag()):
            outcome = self.step()
            if outcome['status'] in ('idle','queued'):
                time.sleep(idle_seconds)
