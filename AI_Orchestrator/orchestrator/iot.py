"""IoT: policy gate fail-closed, shadow first, fake LOW-risk only."""
import hashlib, json
from datetime import datetime, timezone
from .models import ActionProposal

DEFAULT_RESOURCES = {
    'desk_light': {'risk':'LOW','actions':['on','off'],'enabled':True},
    'desk_fan': {'risk':'LOW','actions':['on','off'],'enabled':True},
    'front_door': {'risk':'HIGH','actions':['unlock','lock'],'enabled':False},
}

class PolicyGate:
    def __init__(self, resources=None):
        self.resources = resources if resources is not None else DEFAULT_RESOURCES

    def evaluate(self, proposal, autonomy_enabled=False, mode='shadow', now=None):
        now = now or datetime.now(timezone.utc)
        resource = self.resources.get(proposal.resource)
        if resource is None:
            return {'decision':'DENY','reason':'unknown_resource'}
        if not resource.get('enabled'):
            return {'decision':'DENY','reason':'disabled_resource'}
        if proposal.action not in resource['actions']:
            return {'decision':'DENY','reason':'action_not_allowed'}
        if proposal.parameters not in ({}, {'value': True}, {'value': False}):
            return {'decision':'DENY','reason':'invalid_parameters'}
        if proposal.expires_at:
            try:
                expiry = datetime.fromisoformat(proposal.expires_at.replace('Z','+00:00'))
                if expiry.tzinfo is None or expiry <= now:
                    return {'decision':'DENY','reason':'expired_or_naive_timestamp'}
            except (TypeError,ValueError):
                return {'decision':'DENY','reason':'invalid_expiry'}
        if resource['risk'] != 'LOW':
            return {'decision':'DENY','reason':'human_approval_required'}
        if mode not in ('shadow','fake'):
            return {'decision':'DENY','reason':'real_executor_unconfigured'}
        if mode == 'fake' and not autonomy_enabled:
            return {'decision':'DENY','reason':'kill_switch'}
        return {'decision':'ALLOW','reason':'shadow_preview' if mode == 'shadow' else 'fake_allowed'}

class FakeActuator:
    def __init__(self):
        self.state = {}
    def perform(self, proposal):
        self.state[proposal.resource] = proposal.action
        return {'resource':proposal.resource,'new_state':proposal.action,'executed':'FAKE'}

def action_key(proposal, key=None):
    if key:
        return key
    body = json.dumps({'resource': proposal.resource,'action':proposal.action,
                       'parameters':proposal.parameters},sort_keys=True)
    return hashlib.sha256(body.encode('utf-8')).hexdigest()

def process_proposal(store, proposal, gate, mode='shadow', autonomy_enabled=False,
                     idempotency_key=None, actuator=None):
    policy = gate.evaluate(proposal, autonomy_enabled=autonomy_enabled, mode=mode)
    if policy['decision'] != 'ALLOW':
        return dict(policy,executed=False)
    # Fail closed: never real MQTT/actuator here. Fake requires explicit flag.
    key = action_key(proposal, idempotency_key)
    if not store.record_iot(key,proposal.resource,proposal.action,mode,policy['decision']):
        return {'decision':'DENY','reason':'duplicate_action','executed':False}
    if mode == 'shadow':
        return dict(policy,executed=False,shadow=True)
    if mode == 'fake' and autonomy_enabled:
        output = (actuator or FakeActuator()).perform(proposal)
        return dict(policy,executed=True,result=output)
    return {'decision':'DENY','reason':'unsafe_mode','executed':False}

def normalize_mqtt_event(topic, payload):
    if not isinstance(topic,str) or not topic.startswith('home/sensor/'):
        raise ValueError('Só são permitidos topics home/sensor/*')
    if not isinstance(payload,(str,bytes)):
        raise ValueError('Payload inválido')
    if isinstance(payload,bytes):
        payload = payload.decode('utf-8')
    if len(payload)>4096:
        raise ValueError('Evento demasiado grande')
    return {'topic':topic,'value':payload,'source':'mqtt'}
