import json, threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import pytest
from http.server import ThreadingHTTPServer
from orchestrator.server import ServerHandler
from orchestrator.registry import WorkerRegistry
from orchestrator.store import Store
from orchestrator.engine import Engine


def test_api_needs_token(tmp_path,monkeypatch):
    monkeypatch.setenv('ORCH_API_TOKEN','test-secret')
    store=Store(tmp_path/'api.sqlite')
    handler=type('TestHandler',(ServerHandler,),{'engine':Engine(store,WorkerRegistry())})
    server=ThreadingHTTPServer(('127.0.0.1',0),handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    address='http://127.0.0.1:%s/jobs'%server.server_port
    try:
        with pytest.raises(HTTPError) as exc:
            urlopen(address,timeout=3)
        assert exc.value.code==401
        with urlopen(Request(address,headers={'Authorization':'Bearer test-secret'}),timeout=3) as res:
            assert json.load(res)==[]
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2);store.close()
