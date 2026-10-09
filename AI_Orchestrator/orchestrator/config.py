"""TOML + defaults + ambiente. Segredos nunca entram no TOML versionado."""
import os
from pathlib import Path
try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # Python 3.9 / Raspberry Pi
    except ImportError:
        tomllib = None

DEFAULTS = {
    'server': {'host': '127.0.0.1', 'port': 8080},
    'storage': {'db_path': 'data/orchestrator.db'},
    'scheduler': {'max_attempts': 2, 'idle_seconds': 2},
    'iot': {'mode': 'shadow', 'autonomy_enabled': False},
    'logging': {'level': 'INFO'},
}
OVERRIDES = {
    'ORCH_HOST': ('server','host',str),
    'ORCH_PORT': ('server','port',int),
    'ORCH_DB': ('storage','db_path',str),
    'ORCH_IOT_MODE': ('iot','mode',str),
}

def load_config(path='config/orchestrator.toml'):
    import copy
    config = copy.deepcopy(DEFAULTS)
    p = Path(path)
    if p.exists():
        if tomllib is None:
            raise RuntimeError('Instala tomli no Python 3.9: python3 -m pip install tomli')
        with p.open('rb') as stream:
            content = tomllib.load(stream)
        if content.get('schema_version') != 1:
            raise ValueError('schema_version deve ser 1')
        for section, values in content.items():
            if section == 'schema_version':
                continue
            if section not in config or not isinstance(values, dict):
                raise ValueError('Secção inválida: ' + section)
            if any('password' in k.lower() or 'secret' in k.lower() or 'api_key' in k.lower() for k in values):
                raise ValueError('Segredos não devem ficar no TOML')
            config[section].update(values)
    for env, (section, key, typ) in OVERRIDES.items():
        if env in os.environ:
            config[section][key] = typ(os.environ[env])
    port = config['server']['port']
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('server.port fora de 1..65535')
    if config['scheduler']['max_attempts'] < 1:
        raise ValueError('max_attempts deve ser >= 1')
    if config['iot']['mode'] not in ('shadow', 'fake'):
        raise ValueError('Por segurança, somente shadow/fake; execução real exige integração explícita')
    return config
