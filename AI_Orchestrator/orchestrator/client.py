"""Única camada que conhece a API llama-server. HTTP stdlib."""
import json, os, time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import socket
from .models import ModelResult

class ModelClientError(Exception):
    def __init__(self, kind, retryable=False):
        super().__init__(kind)
        self.kind, self.retryable = kind, retryable

class ModelClient:
    def complete(self, worker, request):
        # OpenAI-compatible chat completion / llama-server
        payload = {
            'model': worker.model_name,
            'messages': [{'role': 'user', 'content': request.prompt}],
            'max_tokens': request.max_tokens,
            'temperature': request.temperature,
            'stream': False,
        }
        if request.stop:
            payload['stop'] = request.stop
        headers = {'Content-Type': 'application/json', 'X-Request-ID': request.request_id}
        if worker.token_env:
            token = os.getenv(worker.token_env)
            if not token:
                raise ModelClientError('auth_missing')
            headers['Authorization'] = 'Bearer ' + token
        url = worker.endpoint.rstrip('/') + '/v1/chat/completions'
        req = Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
        start = time.monotonic()
        try:
            with urlopen(req, timeout=request.timeout) as response:
                body = response.read(1024 * 1024)
        except HTTPError as exc:
            if exc.code in (401, 403):
                raise ModelClientError('auth_error') from exc
            if exc.code in (429, 503):
                raise ModelClientError('rate_or_busy', True) from exc
            if exc.code >= 500:
                raise ModelClientError('server_error', True) from exc
            raise ModelClientError('bad_request') from exc
        except (URLError, socket.timeout, TimeoutError, OSError) as exc:
            kind = 'timeout' if isinstance(exc, (socket.timeout, TimeoutError)) else 'connection_error'
            raise ModelClientError(kind, True) from exc
        try:
            doc = json.loads(body)
            message = doc['choices'][0]['message']['content']
            if not isinstance(message, str):
                raise TypeError('content inválido')
            usage = doc.get('usage', {})
            return ModelResult(request.request_id, worker.id, message,
                               doc['choices'][0].get('finish_reason') or 'unknown',
                               usage.get('prompt_tokens', 0), usage.get('completion_tokens', 0),
                               round((time.monotonic()-start)*1000, 2))
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ModelClientError('malformed_response') from exc
