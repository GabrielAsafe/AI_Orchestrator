import json, pytest
from datetime import datetime,timedelta,timezone
from orchestrator.iot import PolicyGate, FakeActuator, process_proposal, normalize_mqtt_event
from orchestrator.models import ActionProposal
from orchestrator.store import Store
from orchestrator.coding import parse_patch, preview_edits, safe_path, apply_edits, run_check


def test_iot_high_denied():
    assert PolicyGate().evaluate(ActionProposal('unlock','front_door',{}))['decision']=='DENY'

def test_iot_unknown_denied():
    assert PolicyGate().evaluate(ActionProposal('on','ghost',{}))['decision']=='DENY'

def test_iot_expiry_denied():
    old=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
    assert PolicyGate().evaluate(ActionProposal('on','desk_light',{},expires_at=old))['reason']=='expired_or_naive_timestamp'

def test_iot_shadow_no_side_effect(tmp_path):
    db=Store(tmp_path/'iot.db');fake=FakeActuator()
    try:
        prop=ActionProposal('on','desk_light',{})
        outcome=process_proposal(db,prop,PolicyGate(),actuator=fake)
        assert outcome['shadow'] and not outcome['executed']
        assert fake.state=={}
        assert process_proposal(db,prop,PolicyGate())['reason']=='duplicate_action'
    finally:db.close()

def test_iot_fake_needs_explicit_enable(tmp_path):
    db=Store(tmp_path/'iot.db');fake=FakeActuator()
    try:
        prop=ActionProposal('on','desk_light',{})
        assert process_proposal(db,prop,PolicyGate(),mode='fake')['decision']=='DENY'
        assert process_proposal(db,prop,PolicyGate(),mode='fake',autonomy_enabled=True,actuator=fake)['executed']
        assert fake.state['desk_light']=='on'
    finally:db.close()

def test_mqtt_only_sensor_topic():
    assert normalize_mqtt_event('home/sensor/temperature','21')['value']=='21'
    with pytest.raises(ValueError):normalize_mqtt_event('home/command/front_door','unlock')

def test_edits_guard(tmp_path):
    edits=parse_patch('{"schema_version":1,"edits":[{"path":"hello.txt","content":"olá\\n"}]}')
    assert '+olá' in preview_edits(tmp_path,edits)
    with pytest.raises(PermissionError):apply_edits(tmp_path,edits)
    assert apply_edits(tmp_path,edits,approved=True)==1
    assert (tmp_path/'hello.txt').read_text()=='olá\n'
    with pytest.raises(ValueError):safe_path(tmp_path,'../bad.txt')
    with pytest.raises(ValueError):safe_path(tmp_path,'.env')
    with pytest.raises(ValueError):parse_patch('{"schema_version":1,"edits":[]}')

def test_denied_command(tmp_path):
    with pytest.raises(ValueError):run_check(tmp_path,'rm -rf /')
