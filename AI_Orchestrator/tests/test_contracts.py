import pytest
from orchestrator.models import JobState, validate_transition, WorkerSpec, new_id
from orchestrator.scheduler import requirements_for, select_worker
from orchestrator.registry import WorkerRegistry

@pytest.mark.parametrize('state', list(JobState))
def test_terminal_invariant(state):
    if state in (JobState.SUCCEEDED,JobState.FAILED,JobState.CANCELLED):
        with pytest.raises(ValueError):validate_transition(state,JobState.QUEUED)

def test_transition_valid():
    validate_transition(JobState.CREATED,JobState.QUEUED)
    with pytest.raises(ValueError):validate_transition(JobState.CREATED,JobState.RUNNING)

def test_worker_rejects_bad_endpoint():
    with pytest.raises(ValueError):WorkerSpec('id','localhost:123',[])

def test_scheduler_deterministic():
    a=WorkerSpec('a','http://localhost:1',['generic_text'],performance_tier=2)
    b=WorkerSpec('b','http://localhost:2',['generic_text'],performance_tier=1)
    r=WorkerRegistry([a,b]);r.mark_health('a',True);r.mark_health('b',True)
    best,trace=select_worker(r,requirements_for('summarize'))
    assert best.id=='a' and len(trace)==2
    assert r.reserve('a')
    best,_=select_worker(r,requirements_for('summarize'))
    assert best.id=='b'
    r.release('a')

def test_health_threshold():
    r=WorkerRegistry([WorkerSpec('w','http://localhost:3',['generic_text'])])
    for i in range(2):assert r.mark_health('w',False).status=='DEGRADED'
    assert r.mark_health('w',False).status=='OFFLINE'
    assert r.mark_health('w',True).status=='HEALTHY'

def test_id_format():
    assert new_id('job').startswith('job_')
