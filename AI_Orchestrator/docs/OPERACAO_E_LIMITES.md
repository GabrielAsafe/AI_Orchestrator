# Operação, evidências e limitações por milestone

Este documento é complementar às 127 aulas. As tarefas de campo **não podem ser dadas como concluídas** até existirem evidências obtidas nos dispositivos reais. O fake worker demonstra protocolo, não latência/modelo/autenticação de OPPO/Huawei.

## M0 — Baseline

- Python 3.9.2 + ARMv6l no Raspberry Pi Model B Rev 2; guardar `python3 --version`, `uname -m`, `sqlite3 --version`, `git --version`.
- Config TOML `schema_version=1`; segredos em `*_API_KEY` via ambiente; IDs `job_`, `req_`, `att_` com uuid4.
- Testar com `./scripts/run-tests.sh`; os testes devem correr desde a raiz do repo.
- ADRs em `docs/adr/`; rever decisões com o dono.

## M1 — Telefones / Termux

- Não configurar runit, Tailscale nem portas sem acesso aos terminais. É preciso identificar paths GGUF, flags suportadas pela versão concreta do `llama-server`, chaves e IPs de cada telefone.
- Em cada telefone: comprovar partida manual, `/health`, uma geração `/v1/chat/completions`, ausência de key (401/403), key válida (200), `chmod 600`, logs sem segredos, serviço runit, restart automático e reboot.
- Usar túnel SSH ou ACL de rede para não expor inferência publicamente. O exemplo `scripts/termux-runit-example.sh` **não define política de auth**; deve ser completado segundo flags reais do `llama-server` e não ativado assim num endpoint remoto.
- Executar o smoke `WORKER_URL=... WORKER_API_KEY=... ./scripts/worker-smoke.sh`. O secret NÃO aparece no comando se já estiver no ambiente e só os resultados devem ir para logs.
- Guardar evidência por telefone (datas/versão/modelo/latência/restart/reboot).

## M2–M7 — Control plane

- Contratos: `orchestrator/models.py`; Registry `registry.py`; cliente `client.py`; scheduler `scheduler.py`; SQLite `store.py`; orquestração `engine.py`; adapters `adapters.py`; CLI `cli.py`.
- Exemplo ponta a ponta offline com fake worker no README. Trocar por workers reais só após validação M1. Testes reais são necessários para fechar M4-007 e M7-007.
- **Limite**: SQLite suporta aqui um runner por base. Não executar vários runners sobre o mesmo ficheiro de dados; concorrência e lock/claims precisam de robustecimento antes de produção.
- **Limite**: cancelamento de job ativo não interrompe necessariamente request HTTP em curso; reconciliar jobs não significa que se possa repetir side-effects físicos sem risco. `iot_intent` é proposta apenas.

## M8 — Coding

- `orchestrator/coding.py`: patch JSON, validação de path, limite de ficheiros/linhas, diff legível, worktree `lesson/*`, verificações por allowlist.
- Não permitir execução de comandos arbitrários sugeridos pelo modelo. Nunca abrir `.env`, chaves, `.git`, nem código fora do repositório allowlisted.
- O exemplo é **assistido**, depende da confirmação `--approve`; testes de fixture E2E e retries autônomos não estão completos.
- Fluxo de exercício: `ORCH_ALLOWED_REPOS=/caminho/absoluto python3 -m orchestrator coding-preview /caminho/... fixtures/edits.example.json`; para aplicar é obrigatório checkout de branch `lesson/*` e `--approve`.

## M9–M10 — IoT

- Separação MQTT sensor (`home/sensor/*`), state (`home/state/*`), command (`home/command/*`). Só eventos de sensor são normalizados pelo núcleo.
- `iot.py`: unknown/default DENY; HIGH/MEDIUM DENY; LOW em shadow regista decisão sem efeito físico; fake requer habilitação explícita.
- Para Mosquitto, um processo isolado deve tratar credenciais, TLS, retries, idempotência e validar topics; **não há ponte MQTT real** nesta implementação por segurança e falta de hardware.
- Testar LOW-risk real somente em dispositivo benigno, com operador presente, kill switch físico e logs; não usar fechaduras, alarme, tomadas perigosas.

## M11–M12 — Resiliência/evolução

- Backup transacional SQLite: `python3 -m orchestrator backup data/backup.db`; validar restore com cópia isolada, nunca sobrescrever DB ativa.
- Scheduled jobs: `schedule-add` / `schedule-tick`, idempotência por intervalos; um runner trata cron tick. Reboot sem duplicata testado em SQLite, mas não existe calendário complexo.
- AST + análise Git: `python3 -m orchestrator analyze /caminho/repo`; relatório não tem indexação semântica/embeddings.
- Ainda por construir/testar: quotas, fairness, multi-worker review, LSP/Tree-sitter, migrações avançadas, retenção automatizada, chaos matrix completa e condições de migração PostgreSQL/Redis. As respetivas aulas explicam a extensão.

## Regras de documentação

- Só assinalar `Done` após executar os testes e reunir evidências dos critérios.
- Guardar notas e prints sem tokens/passwords/serials identificáveis.
- Segredos: variáveis de ambiente, permissões apropriadas, nunca dentro de HTML, Git, logs nem ficheiros `.example`.
