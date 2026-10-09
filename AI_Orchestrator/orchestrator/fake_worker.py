"""Worker HTTP falso; iniciar apenas em 127.0.0.1 para testes locais."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class FakeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/health':
            self.send_error(404); return
        self.reply(200,{'status':'ok'})
    def do_POST(self):
        if self.path != '/v1/chat/completions':
            self.send_error(404); return
        try:
            length = int(self.headers.get('Content-Length','0'))
            if length > 65536:
                self.send_error(413); return
            doc = json.loads(self.rfile.read(length))
            content = doc['messages'][-1]['content']
            text = 'FAKE: ' + content[-150:]
            self.reply(200, {'choices':[{'message':{'role':'assistant','content':text},'finish_reason':'stop'}],
                             'usage':{'prompt_tokens':5,'completion_tokens':10}})
        except (ValueError,KeyError,IndexError):
            self.send_error(400)
    def reply(self,status,data):
        body=json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers();self.wfile.write(body)
    def log_message(self,*args):
        pass

def run(host='127.0.0.1',port=8089):
    server=ThreadingHTTPServer((host,int(port)),FakeHandler)
    print('Fake worker: http://%s:%s' %(host,port),flush=True)
    server.serve_forever()
