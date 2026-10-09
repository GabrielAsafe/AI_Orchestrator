import json, pytest
from orchestrator.store import Store
from orchestrator.models import JobSpec, new_id
from orchestrator.scheduler import requirements_for

@pytest.fixture
def store(tmp_path):
    db=Store(tmp_path/'db.sqlite')
    yield db
    db.close()

def test_persist_job_and_events(store):
    j=JobSpec(new_id('job'),'summarize',{'text':'abc'},requirements_for('summarize'))
    assert store.submit(j)==j.job_id
    assert store.get(j.job_id)['state']=='QUEUED'
    assert len(store.history(j.job_id))>=2
    assert store.cancel(j.job_id)
    assert not store.cancel(j.job_id)

def test_duplicate_key_returns_original(store):
    j=JobSpec(new_id('job'),'summarize',{'text':'abc'},requirements_for('summarize'),idempotency_key='same')
    first=store.submit(j)
    j.job_id=new_id('job')
    assert store.submit(j)==first
    assert len(store.list_jobs())==1

def test_backup(store,tmp_path):
    backup=tmp_path/'backup.db'
    store.backup(backup)
    copy=Store(backup)
    assert copy.metrics()=={}
    copy.close()

def test_reconcile_running(store):
    j=JobSpec(new_id('job'),'summarize',{'text':'x'},requirements_for('summarize'))
    store.submit(j)
    store.transition(j.job_id,'DISPATCHING');store.transition(j.job_id,'RUNNING')
    assert store.reconcile()==1
    assert store.get(j.job_id)['state']=='QUEUED'

def test_schedule_minute(store):
    with pytest.raises(ValueError):store.add_schedule('a','summarize',{'text':'hi'},30,100)
    store.add_schedule('a','summarize',{'text':'hi'},60,100)
    assert len(store.due_schedules(100))==1
    assert store.advance_schedule('a',100,160)
    assert not store.advance_schedule('a',100,220)
