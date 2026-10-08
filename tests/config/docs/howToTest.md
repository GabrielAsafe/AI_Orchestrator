O `pytest` é uma biblioteca de Python utilizada para criar e executar testes automatizados. É uma das ferramentas mais utilizadas para garantir que o código funciona como esperado e que alterações futuras não introduzem erros.

No teu projeto de IA distribuída, o `pytest` será especialmente importante para validar o código na máquina de desenvolvimento antes de o executar no Raspberry Pi.

Vou explicar desde o básico, com exemplos práticos.

## 1. Para que serve o pytest?

Imagina que tens uma função Python que soma dois números:

```
def somar(a, b):    return a + b
```

Podes testá-la manualmente:

```
print(somar(2, 3))  # 5
```

Mas, à medida que o projeto cresce, verificar tudo manualmente torna-se impraticável.

Com `pytest`, escreves:

```
def test_somar():    assert somar(2, 3) == 5
```

Quando executas os testes, o `pytest` verifica automaticamente se o resultado é o esperado.

Se for igual, o teste passa. Caso contrário, falha.

## 2. Como instalar e executar

Na tua máquina de desenvolvimento:

```
python -m pip install pytest
```

Para verificar a instalação:

```
python -m pytest --version
```

Para executar todos os testes encontrados no projeto:

```
python -m pytest
```

Recomendo usar `python -m pytest` em vez de apenas `pytest`, porque assim tens maior controlo sobre o interpretador Python utilizado.

## 3. Criar o primeiro teste

Imagina esta estrutura de projeto:

meu_projeto/

calculadora.py

tests/

test_calculadora.py

No ficheiro `calculadora.py`:

```
def somar(a, b):    return a + bdef dividir(a, b):    return a / b
```

No ficheiro `tests/test_calculadora.py`:

```
from calculadora import somar, dividirdef test_somar():    assert somar(2, 3) == 5def test_dividir():    assert dividir(10, 2) == 5
```

Agora, na raiz do projeto, executas:

```
python -m pytest -v
```

O resultado será semelhante a:

```
tests/test_calculadora.py::test_somar PASSED
tests/test_calculadora.py::test_dividir PASSED

2 passed in 0.02s
```

O parâmetro `-v` significa verbose, mostrando o resultado de cada teste.

## 4. O que acontece quando um teste falha?

Suponhamos que escreves:

```
def test_somar():    assert somar(2, 3) == 6
```

O `pytest` irá apresentar algo semelhante a:

```
FAILED test_calculadora.py::test_somar

    assert 5 == 6

1 failed
```

Isto é útil porque o `pytest` mostra exatamente qual a condição que falhou.

## 5. Funcionalidades importantes

| Funcionalidade             | Para que serve                                               |
| -------------------------- | ------------------------------------------------------------ |
| `assert`                   | Verificar resultados                                         |
| `@pytest.mark.parametrize` | Testar vários valores                                        |
| `@pytest.fixture`          | Preparar dados ou recursos reutilizáveis                     |
| `pytest.raises`            | Verificar se uma exceção acontece                            |
| `@pytest.mark.asyncio`     | Testar funções assíncronas, usando o plugin `pytest-asyncio` |
| `monkeypatch`              | Substituir temporariamente funções, atributos ou variáveis   |
| `tmp_path`                 | Criar diretórios temporários para testes                     |

### Exemplo: testar vários valores automaticamente

```
import pytest@pytest.mark.parametrize("a,b,esperado", [    (2, 3, 5),    (10, 20, 30),    (-1, 1, 0),    (0, 0, 0),])def test_somar(a, b, esperado):    assert a + b == esperado
```

Com uma única função, o `pytest` executa quatro casos de teste.

## 6. Como testar código assíncrono com asyncio?

Como estás a explorar `asyncio`, este exemplo será particularmente útil.

Primeiro instala o plugin:

```
python -m pip install pytest-asyncio
```

Imagina que tens uma função assíncrona:

```
import asyncioasync def obter_status():    await asyncio.sleep(0.1)    return "online"
```

Podes testá-la assim:

```
import pytestfrom meu_modulo import obter_status@pytest.mark.asyncioasync def test_obter_status():    resultado = await obter_status()    assert resultado == "online"
```

O `pytest-asyncio` permite que o `pytest` execute testes assíncronos através de um event loop.

## 7. Como isto se aplica ao teu Raspberry Pi?

No teu projeto, vais ter operações como:

- Verificar se um worker Android está disponível.
- Validar respostas HTTP recebidas com `httpx`.
- Guardar e consultar jobs numa base SQLite.
- Verificar decisões do scheduler.
- Tratar erros e timeouts de comunicação.

Por exemplo, uma função que valida o estado de um worker:

```
def worker_disponivel(status):    return status == "online"
```

E os respetivos testes:

```
from worker import worker_disponiveldef test_worker_online():    assert worker_disponivel("online") is Truedef test_worker_offline():    assert worker_disponivel("offline") is Falsedef test_worker_desconhecido():    assert worker_disponivel("unknown") is False
```

Estes são testes unitários: verificam uma pequena parte do sistema de forma isolada, sem necessitar de um Raspberry Pi ou de um telemóvel ligado.

Mais tarde, também poderás ter testes de integração que verificam a comunicação real entre os componentes.

## 8. Comandos que vais utilizar frequentemente

```
# Executar todos os testes
python -m pytest

# Mostrar os nomes dos testes
python -m pytest -v

# Executar um ficheiro específico
python -m pytest tests/test_worker.py

# Executar um teste específico
python -m pytest tests/test_worker.py::test_worker_online

# Executar apenas testes cujo nome contém "worker"
python -m pytest -k worker

# Parar no primeiro erro
python -m pytest -x

# Mostrar resultados de print()
python -m pytest -s
```

## 9. Experimenta: um pequeno exercício

Teste os teus conhecimentos

3 de 3 respondidas

1\. Qual é a função principal de assert num teste?

Instalar dependências

Verificar uma condição esperada

Executar tarefas assíncronas

assert verifica uma condição. Se a condição for falsa, o teste falha.

2\. Como executar apenas um ficheiro de testes?

python -m pytest tests/test_worker.py

python -m pytest --all

python -m pytest --install

Podes indicar diretamente o caminho do ficheiro de testes.

3\. O que precisas para usar @pytest.mark.asyncio neste exemplo?

SQLite

pytest-asyncio

threading

O plugin pytest-asyncio disponibiliza suporte para executar coroutines nos testes.

Resultado: 3/3

Recomeçar

O conceito mais importante: o `pytest` transforma os requisitos do teu software em verificações executáveis. No teu projeto distribuído, isso permite validar a lógica no PC de desenvolvimento e reservar os testes no Raspberry para as funcionalidades que realmente dependem do hardware.

Podemos depois avançar para fixtures, mocks e testes de funções assíncronas, que serão especialmente úteis na implementação do orquestrador.

