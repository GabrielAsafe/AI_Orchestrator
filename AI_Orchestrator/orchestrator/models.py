"""Contratos de domínio de baixo custo, compatíveis com Python 3.9."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import uuid

SCHEMA_VERSION = 1

def new_id(prefix):
    return '%s_%s' % (prefix, uuid.uuid4().hex)

def utcnow():
    return datetime.now(timezone.utc).isoformat()

class JobState(str, Enum):
    CREATED = 'CREATED'
    QUEUED = 'QUEUED'
    DISPATCHING = 'DISPATCHING'
    RUNNING = 'RUNNING'
    VERIFYING = 'VERIFYING'
    WAITING_RETRY = 'WAITING_RETRY'
    SUCCEEDED = 'SUCCEEDED'
    FAILED = 'FAILED'
    CANCELLED = 'CANCELLED'

TERMINAL = {JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED}
TRANSITIONS = {
    JobState.CREATED: {JobState.QUEUED, JobState.CANCELLED, JobState.FAILED},
    JobState.QUEUED: {JobState.DISPATCHING, JobState.CANCELLED, JobState.FAILED},
    JobState.DISPATCHING: {JobState.RUNNING, JobState.WAITING_RETRY, JobState.QUEUED, JobState.CANCELLED, JobState.FAILED},
    JobState.RUNNING: {JobState.VERIFYING, JobState.WAITING_RETRY, JobState.CANCELLED, JobState.FAILED},
    JobState.VERIFYING: {JobState.SUCCEEDED, JobState.WAITING_RETRY, JobState.CANCELLED, JobState.FAILED},
    JobState.WAITING_RETRY: {JobState.QUEUED, JobState.CANCELLED, JobState.FAILED},
    JobState.SUCCEEDED: set(), JobState.FAILED: set(), JobState.CANCELLED: set(),
}

def validate_transition(old, new):
    old, new = JobState(old), JobState(new)
    if new not in TRANSITIONS[old]:
        raise ValueError('Transição ilegal: %s -> %s' % (old.value, new.value))

@dataclass
class WorkerSpec:
    id: str
    endpoint: str
    capabilities: List[str]
    model_name: str = 'unknown'
    context_limit: int = 2048
    max_parallel: int = 1
    performance_tier: int = 1
    enabled: bool = True
    timeout_seconds: int = 90
    token_env: str = ''
    metadata: Dict[str, Any] = field(default_factory=dict)
    def __post_init__(self):
        if not self.id or not self.endpoint.startswith(('http://', 'https://')):
            raise ValueError('Worker id/endpoint inválido')
        if self.max_parallel < 1 or self.context_limit < 1:
            raise ValueError('Capacidade inválida')

@dataclass
class WorkerHealth:
    worker_id: str
    status: str = 'UNKNOWN'
    last_check_at: Optional[str] = None
    latency_ms: Optional[float] = None
    model_loaded: bool = False
    active_jobs: int = 0
    last_error: Optional[str] = None
    consecutive_failures: int = 0

@dataclass
class Requirements:
    required_capabilities: List[str] = field(default_factory=list)
    preferred_worker: Optional[str] = None
    max_context: int = 0
    allow_fallback: bool = True

@dataclass
class JobSpec:
    job_id: str
    job_type: str
    input: Dict[str, Any]
    requirements: Requirements = field(default_factory=Requirements)
    priority: int = 0
    created_at: str = field(default_factory=utcnow)
    max_attempts: int = 2
    idempotency_key: Optional[str] = None
    schema_version: int = SCHEMA_VERSION

@dataclass
class Attempt:
    attempt_id: str
    job_id: str
    worker_id: str
    started_at: str
    finished_at: Optional[str] = None
    error_type: Optional[str] = None
    retryable: bool = False

@dataclass
class ModelRequest:
    prompt: str
    request_id: str = field(default_factory=lambda: new_id('req'))
    max_tokens: int = 256
    temperature: float = 0.2
    timeout: int = 90
    stop: List[str] = field(default_factory=list)
    response_mode: str = 'text'

@dataclass
class ModelResult:
    request_id: str
    worker_id: str
    text: str
    finish_reason: str = 'stop'
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0

@dataclass
class VerificationResult:
    passed: bool
    checks: List[Dict[str, Any]] = field(default_factory=list)
    stdout_summary: str = ''
    stderr_summary: str = ''
    duration: float = 0

@dataclass
class ActionProposal:
    action: str
    resource: str
    parameters: Dict[str, Any]
    reason: str = ''
    expires_at: Optional[str] = None
    confidence: Optional[float] = None
