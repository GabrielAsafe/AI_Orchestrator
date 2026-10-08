# src/config_loader.py

import tomli


def load_config(path):
    with open(path, "rb") as file:
        config = tomli.load(file)

    if config.get("schema_version") != 1:
        raise ValueError("Versão de configuração inválida")

    server = config.get("server")

    if not isinstance(server, dict):
        raise ValueError("Configuração server em falta")

    port = server.get("port")

    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Porta inválida")

    return config
