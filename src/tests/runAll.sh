# Executar todos os testes
python -m pytest

# Mostrar os nomes dos testes
python -m pytest -v

# Executar um ficheiro específico
#python -m pytest tests/test_worker.py

# Executar um teste específico
#python -m pytest tests/test_worker.py::test_worker_online

# Executar apenas testes cujo nome contém "worker"
#python -m pytest -k worker

# Parar no primeiro erro
python -m pytest -x

# Mostrar resultados de print()
python -m pytest -s
