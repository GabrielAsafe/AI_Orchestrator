# ADR-0001 — SQLite-first

- **Status:** Accepted
- **Milestone:** M0

## Context

O sistema começa com um único Raspberry Pi como control plane, com recursos limitados e necessidade de recuperar o estado após reinícios. A arquitetura prevê registos de workers, jobs, attempts e events. Uma infraestrutura distribuída de base de dados ou fila adicionaria dependências operacionais antes de existir necessidade demonstrada.

## Decision

Utilizar **SQLite como persistência inicial** e uma **fila própria persistida em SQLite**. O orquestrador mantém o estado dos jobs e eventos no Raspberry Pi. Introduzir Redis ou uma base de dados servidora apenas se houver evidência de limitações de concorrência, múltiplos processos de control plane ou escala.

## Consequences

- **Vantagens:** menos serviços para instalar, operar e recuperar; adequado ao Raspberry e à fase inicial.
- **Trade-offs:** concorrência de escrita limitada e responsabilidade explícita por migrações, transações, backups e recuperação.
- **Implicação:** testar recuperação de jobs em estados transitórios após reinício e impedir repetição cega de efeitos externos.
