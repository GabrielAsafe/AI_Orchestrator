# ADR-0002 — Raspberry Pi como control plane

- **Status:** Accepted
- **Milestone:** M0

## Context

O projeto usa um Raspberry Pi e telemóveis Android com diferentes capacidades de inferência. É necessário haver uma fonte de verdade única para coordenar jobs, workers, políticas, tentativas e resultados, sem exigir coordenação entre telemóveis.

## Decision

O **Raspberry Pi é o control plane único e fonte de verdade** para jobs, inventário e saúde de workers, leases/reservas, retries, políticas, histórico, Git, verificações e autorizações de execução IoT. Os telemóveis são workers de inferência e **não coordenam entre si**. O PC usado para editar remotamente por SSH não substitui o Raspberry como control plane.

## Consequences

- **Vantagens:** coordenação centralizada, decisões auditáveis e fronteira clara de responsabilidades.
- **Trade-offs:** o Raspberry é um ponto central de falha; persistência, recuperação e observabilidade são essenciais.
- **Implicação:** funcionalidades de controlo permanecem disponíveis independentemente da disponibilidade dos modelos, sempre que tecnicamente possível.
