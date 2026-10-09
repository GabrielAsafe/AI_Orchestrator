import pytest
from orchestrator.config import load_config

def test_defaults(tmp_path):
    d=load_config(tmp_path/'nonexistent.toml')
    assert d['server']['port']==8080

def test_config_env_overrides(tmp_path,monkeypatch):
    file=tmp_path/'settings.toml'
    file.write_text('schema_version=1\n[server]\nport=9000\n')
    monkeypatch.setenv('ORCH_PORT','9001')
    assert load_config(file)['server']['port']==9001

def test_config_bad_port(tmp_path):
    file=tmp_path/'bad.toml'
    file.write_text('schema_version=1\n[server]\nport=-1\n')
    with pytest.raises(ValueError):load_config(file)

def test_config_reject_secret(tmp_path):
    file=tmp_path/'bad.toml'
    file.write_text('schema_version=1\n[server]\napi_key="123"\n')
    with pytest.raises(ValueError):load_config(file)
