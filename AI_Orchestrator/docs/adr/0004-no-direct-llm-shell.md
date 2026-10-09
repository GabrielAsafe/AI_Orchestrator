# ADR-0004 — Sem execução direta de shell por LLM

- **Status:** Accepted
- **Milestone:** M0

## Context

O módulo de coding permitirá que modelos proponham alterações. Saídas de um LLM não são instruções confiáveis para executar diretamente no sistema operativo, Git ou rede. A execução irrestrita aumentaria o risco de operações inesperadas ou destrutivas.

## Decision

**Nunca executar diretamente texto gerado por LLM como comando shell.** O fluxo autorizado é: proposta do modelo → parsing e validação contra schema → política e allowlist → executor determinístico. Alterações de código devem ocorrer em contexto isolado, fora da branch principal, e o resultado deve ser verificado por ferramentas determinísticas; o LLM não decide sozinho se passou.

## Consequences

- **Vantagens:** diminui a superfície de risco e torna operações reproduzíveis e auditáveis.
- **Trade-offs:** acrescenta trabalho de validação, autorização e implementação de executores limitados.
- **Implicação:** chamadas como `subprocess(..., shell=True)` com conteúdo do modelo são proibidas; os testes devem cobrir rejeição de propostas fora do escopo.
