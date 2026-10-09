"""HTTP local-only para leitura e submissão; token ORCH_API_TOKEN obrigatório.

Cada request abre a sua própria conexão SQLite no thread do request: nunca
compartilhar sqlite3.Connection entre threads HTTP.
"""
import json, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from .store import Store
from .engine import Engine

class ServerHandler(BaseHTTPRequestHandler):
    engine = None
    def reply(self,code,data):
        raw=json.dumps(data).encode('utf-8')
        self.send_response(code);self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(raw)))
        self.end_headers(); self.wfile.write(raw)
    def authorized(self):
        import hmac
        token = os.getenv('ORCH_API_TOKEN')
        if not token or not hmac.compare_digest(self.headers.get('Authorization',''), 'Bearer '+token):
            self.reply(401,{'error':'unauthorized'});return False
        return True
    def do_GET(self):
        if not self.authorized():return
        path=urlparse(self.path).path
        if path == '/health':return self.reply(200,{'status':'ok'})
        if path == '/workers':return self.reply(200,self.engine.registry.as_rows())
        with Store(self.engine.store.path) as store:
            if path == '/jobs':return self.reply(200,store.list_jobs())
            if path.startswith('/jobs/'):
                job_id = path.split('/')[2]
                job = store.get(job_id)
                return self.reply(200,job) if job else self.reply(404,{'error':'not_found'})
        self.reply(404,{'error':'not_found'})
    def do_POST(self):
        if not self.authorized():return
        if self.path != '/jobs':return self.reply(404,{'error':'not_found'})
        try:
            length=int(self.headers.get('Content-Length',0))
            if not 0 < length <= 65536:
                return self.reply(413,{'error':'body_size'})
            request=json.loads(self.rfile.read(length))
            with Store(self.engine.store.path) as store:
                engine=Engine(store,self.engine.registry)
                job_id=engine.submit(request['job_type'],request['text'],
                                     idempotency_key=request.get('idempotency_key'))
            self.reply(201,{'job_id':job_id})
        except (ValueError,TypeError,KeyError):
            self.reply(400,{'error':'invalid_request'})
    def log_message(self,*args):pass

def run(engine,host='127.0.0.1',port=8080):
    if host not in ('127.0.0.1','localhost','::1'):
        raise ValueError('Servidor API só aceita loopback; usa túnel SSH')
    if not os.getenv('ORCH_API_TOKEN'):
        raise RuntimeError('Define ORCH_API_TOKEN antes de iniciar a API')
    handler=type('BoundHandler',(ServerHandler,),{'engine':engine})
    srv=ThreadingHTTPServer((host,int(port)),handler)
    print('Control API em %s:%d' % (host,int(port)),flush=True)
    srv.serve_forever()
