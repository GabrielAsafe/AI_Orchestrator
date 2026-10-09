# AI Orchestrator — pacote offline de estudo e referência

Este pacote foi criado a partir do Kanban enviado em 8 de outubro de 2026. Contém:

- **`curso_offline.html`**: abrir no browser com duplo clique. Não necessita de rede; suporta pesquisa, notas, checklist, progresso e código escondido por task. Usa «Exportar progresso» com frequência.
- **`AI_Orchestrator/`**: implementação de referência em Python 3.9, testes, documentos ADR, configurações de exemplo e scripts.
- **`AI_Orchestrator/docs/referencias/kanban_original.json`**: fonte original com as 127 tasks e comentários.

## Utilização sugerida

1. Faz backup do repositório atual no Raspberry. Não substituas automaticamente os teus ficheiros: compara/integra as alterações por Git.
2. Estuda o HTML, começando pela task em que estás (M0-006/M0-007). Implementa autonomamente e abre o código de referência apenas quando precisares.
3. Na pasta Python, `python3 -m pip install -r requirements.txt` e `python3 -m pytest -q tests`.
4. No terminal SSH, `python3 -m orchestrator fake-worker`; noutro terminal, `python3 -m orchestrator submit summarize 'Olá mundo'` seguido de `python3 -m orchestrator run-once`.
5. Consulta `README.md` e `docs/OPERACAO_E_LIMITES.md` antes de conectar workers reais ou IoT.

## Responsabilidade e estados

As **127 tasks são aulas/desafios**, não 127 implementações certificadas. A referência fornece um núcleo executável, testes e exemplos, mas alguns módulos avançados são parciais e várias tasks exigem validação no OPPO, Huawei, Mosquitto e dispositivos físicos. O HTML permite acompanhar essas evidências. A versão original do Kanban incluía estados anteriores: M0-001 a M0-003 foram assinaladas como concluídas por tua confirmação posterior. Não se assume que outras tasks estejam fechadas.

## Segurança

Nunca copies segredos para HTML, Git, logs ou ficheiros `.example`. O servidor de controle apenas suporta loopback com token; MQTT real não está implementado. O coding exige allowlist e aprovação humana; o fake actuator não controla dispositivos reais.
