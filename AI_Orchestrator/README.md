# AI Orchestrator — referência pedagógica offline

Implementação **local e limitada** do control plane Raspberry Pi, compatível com Python 3.9. O curso HTML contém as 127 tasks originais, desafios e soluções colapsadas. Este repositório inclui um núcleo funcional para testes e integração gradual. **Não significa que todas as tasks estejam concluídas em hardware real.**

## Quickstart no Raspberry

```bash
cd AI_Orchestrator
python3 -m pip install -r requirements.txt
python3 -m pytest -q
python3 -m orchestrator doctor
```

Terminais SSH distintos:

```bash
# A. Worker HTTP simulado, SEM inferência real
python3 -m orchestrator fake-worker
# B. Submeter + executar uma iteração
python3 -m orchestrator submit summarize 'Olá mundo, texto de exemplo.'
python3 -m orchestrator run-once
python3 -m orchestrator jobs
python3 -m orchestrator metrics
```

Para ver o resultado, usa o `job_id` devolvido por `submit`:

```bash
python3 -m orchestrator result job_XXXX
python3 -m orchestrator explain job_XXXX
```

### Workers Android reais

1. Configura **e valida manualmente** OPPO e Huawei com `llama-server` e autenticação no Termux (M1).
2. Copia `config/workers.real.example.json` para `config/workers.json`, corrige os endpoints/capabilities/contexts.
3. Define `OPPO_LLM_API_KEY` e `HUAWEI_LLM_API_KEY` **fora do Git**.
4. `python3 -m orchestrator health` e `python3 -m orchestrator run`.
5. Mantém portas restritas (loopback + túnel/ACL); não exponhas o llama-server à internet.

### API local

```bash
export ORCH_API_TOKEN='ESCOLHE_TOKEN_FORTE_AQUI'
python3 -m orchestrator serve
# Exemplo curl em outro terminal:
curl -H "Authorization: Bearer $ORCH_API_TOKEN" http://127.0.0.1:8080/jobs
```

A API é somente loopback e requer token; não publica automaticamente o scheduler. Usa `run` em outro terminal.

### Coding e IoT

O coding é **assistido e sujeito a revisão humana**. Para o CLI aceitar um repositório, exporta `ORCH_ALLOWED_REPOS=/caminho/absoluto`. Usa worktrees `lesson/*`; nunca aceita shell arbitrário do LLM. O IoT usa `shadow` ou atuador falso. **Não há executor MQTT físico ativo**. Integração real implica implementação e testes supervisionados de M9–M10.

### Dados persistentes

SQLite em `data/orchestrator.db` por padrão. Faz backups regulares com `python3 -m orchestrator backup data/backup.db`. Valores locais e segredos não são versionados.

### Limites conhecidos

- Dispatch em um processo/iteração, sem lock distribuído entre múltiplos processos `run`.
- Workers reais, autenticação de rede, runit, reboot, Mosquitto e atuadores exigem validação no hardware.
- Sem garantia de cancelamento de uma chamada HTTP já iniciada; o comando `cancel` impede/termina jobs na base, mas a interrupção imediata remota depende do worker.
- Autonomia ampliada, fairness/quota, revisão multi-worker e migrations elaboradas são aulas/desafios, não comportamentos integralmente implementados.
- Não usar para atuadores físicos de segurança, sistemas críticos ou internet pública.
