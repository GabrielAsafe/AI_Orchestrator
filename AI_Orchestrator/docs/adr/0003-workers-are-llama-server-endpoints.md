# ADR-0003 — Workers como endpoints llama-server HTTP

- **Status:** Accepted
- **Milestone:** M0

## Context

Os modelos são executados em telemóveis Android com Termux e `llama.cpp`. A primeira fase precisa de comunicação simples entre o Raspberry e esses workers, evitando um novo agente Python ou protocolo de coordenação no Android.

## Decision

Cada worker físico expõe um **`llama-server` acessível por HTTP**, com autenticação e regras de rede definidas na implantação. O **Raspberry comunica diretamente com os endpoints** usando um cliente HTTP. A rede lógica poderá utilizar Tailscale/MagicDNS, com LAN como caminho local, conforme o desenho da arquitetura. Não implementar um daemon Python intermédio nos telefones na fase inicial.

## Consequences

- **Vantagens:** menos processos e dependências nos Android; integração direta e separação entre inferência e orquestração.
- **Trade-offs:** é preciso lidar com timeouts, autenticação, indisponibilidade, mudanças de rede e capacidades diferentes entre dispositivos.
- **Implicação:** saúde do worker e testes de inferência são distintos; a existência de um endpoint não prova que um modelo está operacional.
