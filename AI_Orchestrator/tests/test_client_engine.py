import json, threading
from http.server import ThreadingHTTPServer
from orchestrator.fake_worker import FakeHandler
from orchestrator.registry import WorkerRegistry
from orchestrator.models import WorkerSpec
from orchestrator.store import Store
from orchestrator.engine import Engine


def test_fake_worker_lifecycle(tmp_path):
    server=ThreadingHTTPServer(('127.0.0.1',0),FakeHandler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        worker=WorkerSpec('fake','http://127.0.0.1:%d'%server.server_port,['generic_text','summarize'])
        registry=WorkerRegistry([worker]);registry.probe('fake')
        db=Store(tmp_path/'test.sqlite')
        try:
            engine=Engine(db,registry)
            job=engine.submit('summarize','texto de teste')
            outcome=engine.step()
            assert outcome['status']=='succeeded'
            row=db.get(job)
            assert row['state']=='SUCCEEDED'
            assert json.loads(row['result_json'])['output']['text'].startswith('FAKE:')
            assert db.attempt_count(job)==1
        finally:db.close()
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)

def test_queue_when_no_worker(tmp_path):
    db=Store(tmp_path/'db.sqlite')
    try:
        engine=Engine(db,WorkerRegistry([]))
        job=engine.submit('classify','X')
        assert engine.step()['status']=='queued'
        assert db.get(job)['state']=='QUEUED'
    finally:db.close()
