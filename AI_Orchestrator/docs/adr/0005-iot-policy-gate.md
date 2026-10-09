# ADR-0005 — Policy Gate determinístico para IoT

- **Status:** Accepted
- **Milestone:** M0

## Context

O sistema poderá interpretar eventos de sensores e sugerir ações IoT. Como estas ações podem produzir efeitos físicos, a decisão de executá-las não pode depender apenas da saída de um modelo de linguagem. As automações básicas também devem continuar a funcionar sem LLM.

## Decision

Para propostas de ações IoT provenientes de LLM, exigir o fluxo **evento → adapter → proposta estruturada (ActionProposal) → Policy Gate determinístico → executor autorizado**. O Policy Gate verifica recurso, ação, parâmetros, autorização, risco, validade e duplicação, entre outras regras aplicáveis. O LLM não publica comandos MQTT diretamente nem controla atuadores. Começar em **shadow mode** (registar decisões, sem efeitos físicos); só depois permitir ações **LOW-risk** aprovadas pelas políticas. Ações HIGH-risk exigem aprovação humana explícita. Prever um kill switch para autonomia com efeitos externos.

## Consequences

- **Vantagens:** decisões auditáveis, possibilidade de simular políticas e isolamento entre raciocínio probabilístico e efeitos físicos.
- **Trade-offs:** necessidade de catálogo de ações, classificação de risco, validações e gestão de autorização.
- **Implicação:** testar deny-by-default, duplicados, expiração, ações fora da allowlist e funcionamento do sistema sem LLM antes de permitir execução real.
