"""Adapters de texto geram prompts, sem executar código ou IoT."""
import json
from .models import ModelRequest

PROMPTS = {
    'generic_text': 'Responde ao pedido com clareza e honestidade.\n\nPedido:\n{input}',
    'summarize': 'Resume fielmente o texto seguinte em português, sem adicionar factos.\n\n{input}',
    'classify': 'Classifica o conteúdo. Responde apenas com o rótulo de uma categoria e nada mais.\n\n{input}',
    'extract': 'Extrai informação e devolve apenas JSON válido (um objeto). Não inventes campos.\n\n{input}',
    'iot_intent': ('Analisa a intenção IoT e devolve APENAS JSON com action, resource, parameters, reason, expires_at. '
                   'Isto é apenas uma proposta; nenhuma ação será executada diretamente.\n\n{input}'),
    'coding_patch': ('Propõe alterações no formato JSON de edits, sem executar comandos. '
                     'É obrigatória revisão humana.\n\n{input}'),
}

def make_request(job_type, input_data, timeout=90):
    if job_type not in PROMPTS:
        raise ValueError('Tipo de job não suportado')
    content = input_data.get('text')
    if not isinstance(content, str) or not content.strip():
        raise ValueError('input.text obrigatório e não vazio')
    if len(content) > 80000:
        raise ValueError('input.text demasiado grande')
    return ModelRequest(prompt=PROMPTS[job_type].format(input=content),timeout=timeout)

def normalize_output(job_type, model_text):
    if job_type in ('extract','iot_intent'):
        try:
            value = json.loads(model_text)
        except (ValueError, TypeError) as exc:
            raise ValueError('Resposta JSON inválida') from exc
        if not isinstance(value, dict):
            raise ValueError('Esperado objeto JSON')
        if job_type == 'iot_intent' and not {'action','resource','parameters'}.issubset(value):
            raise ValueError('ActionProposal incompleta')
        return value
    return {'text': model_text}
