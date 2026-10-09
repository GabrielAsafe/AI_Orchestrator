# Architecture Decision Records (ADRs)

Decisões arquiteturais aceites para a baseline M0 do AI_Orchestrator.

| ADR | Decisão | Estado |
| --- | --- | --- |
| [0001](0001-sqlite-first.md) | SQLite-first | Accepted |
| [0002](0002-raspberry-is-control-plane.md) | Raspberry Pi como control plane | Accepted |
| [0003](0003-workers-are-llama-server-endpoints.md) | Workers HTTP `llama-server` | Accepted |
| [0004](0004-no-direct-llm-shell.md) | Sem shell direto por LLM | Accepted |
| [0005](0005-iot-policy-gate.md) | Policy Gate IoT | Accepted |

Cada ADR contém `Context`, `Decision` e `Consequences`.

Quando uma decisão mudar, criar um novo ADR ou atualizar o estado do anterior com referência à substituição, preservando o histórico da decisão.

**Referência:** `docs/arquitetura_e_plano_orquestracao_integrado.md`, secção 48 (ADRs) e secções de arquitetura correspondentes.
