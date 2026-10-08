# tests/tests_config.py

import pytest 
from src.config_loader import load_config


def test_valid_config(tmp_path):
	config = tmp_path / "config.toml"

	config.write_text(
		'schema_version=1\n'
		'[server]\n'
		'port=8080\n'
	)
	result = load_config(config)
