# Arquitetura e Plano de Implementação — Sistema de IA Distribuída, Coding e IoT

> Documento integrado.
> 
> Combina a arquitetura conceptual do **Project Intelligence Layer** com o blueprint incremental do **orquestrador genérico de jobs**.
> O objetivo é permitir implementação autónoma, validação milestone a milestone e apoio controlado de outra IA sem perder os boundaries do sistema.

## Como ler este documento

```text
PARTE A
  visão conceptual
  project intelligence
  analyzers
  context builder
  documentação incremental
  arquitetura-alvo

PARTE B
  plano de implementação real
  contratos
  workers
  scheduler
  state machine
  SQLite
  coding
  IoT
  testes
  segurança
  milestones
  plano de apoio por outra IA
```

A regra de evolução é:

```text
começar simples
      |
      v
medir limites reais
      |
      v
adicionar infraestrutura apenas quando necessária
```

---

# PARTE A — Arquitetura conceptual e Project Intelligence Layer

Sim. Para uso pessoal e já tendo um **rig com agentes locais**, eu faria uma arquitetura em que a IA não é o "analisador do projeto". O **orquestrador é a camada de inteligência estrutural**: ele coleta, indexa, relaciona e prepara o contexto; os agentes recebem tarefas pequenas e bem delimitadas.

A arquitetura que eu recomendo é esta:

```
                         ┌─────────────────────┐
                         │      GIT REPO       │
                         │ GitHub/GitLab/local │
                         └──────────┬──────────┘
                                    │
                                    ▼
                    ┌───────────────────────────┐
                    │       ORQUESTRADOR        │
                    │                           │
                    │  Planner / Task Manager   │
                    │  Dependency Graph         │
                    │  Context Builder          │
                    │  Change Detector          │
                    │  Agent Router             │
                    └─────────────┬─────────────┘
                                  │
             ┌────────────────────┼────────────────────┐
             │                    │                    │
             ▼                    ▼                    ▼
       ┌──────────┐        ┌──────────┐        ┌──────────┐
       │ AST      │        │ API      │        │ Git      │
       │ Analyzer │        │ Analyzer │        │ Analyzer │
       └────┬─────┘        └────┬─────┘        └────┬─────┘
            │                   │                   │
            └───────────────────┼───────────────────┘
                                ▼
                     ┌─────────────────────┐
                     │ PROJECT KNOWLEDGE   │
                     │ GRAPH               │
                     └─────────┬───────────┘
                               │
             ┌─────────────────┼──────────────────┐
             ▼                 ▼                  ▼
       ┌──────────┐      ┌────────────┐     ┌──────────┐
       │ Vector   │      │ PostgreSQL │     │ Artifacts│
       │ DB       │      │ / metadata │     │ / docs   │
       └──────────┘      └────────────┘     └──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │     TASK QUEUE      │
                    └─────────┬───────────┘
                              │
             ┌────────────────┼────────────────┐
             ▼                ▼                ▼
       ┌───────────┐    ┌───────────┐    ┌───────────┐
       │ Agent A   │    │ Agent B   │    │ Agent C   │
       │ Architecture│  │ API       │    │ Modules   │
       └─────┬─────┘    └─────┬─────┘    └─────┬─────┘
             │                │                │
             └────────────────┼────────────────┘
                              ▼
                     ┌──────────────────┐
                     │ Documentation    │
                     │ Compiler         │
                     └────────┬─────────┘
                              ▼
                     ┌──────────────────┐
                     │ Docs site / Git  │
                     └──────────────────┘
```

## 1. O princípio fundamental

Eu separaria o sistema em três camadas:

### Determinística

Responsável por descobrir **o que existe**.

```
Código
AST
Git
OpenAPI
Docker
package.json
pyproject.toml
SQL
Terraform
etc.
```

Não precisa de IA.

### Orquestração

Responsável por descobrir **o que precisa ser feito**.

```
"Este projeto mudou."

        ↓

"Quais documentos são afetados?"

        ↓

"Quais agentes precisam trabalhar?"

        ↓

"Que contexto cada agente precisa?"
```

### IA

Responsável por **interpretar, explicar e escrever**.

Isso é muito mais robusto do que colocar um LLM olhando diretamente para 500 arquivos.

---

# 2. O coração do sistema: Project Intelligence Layer

Eu criaria uma representação intermediária do projeto.

Por exemplo:

```
{
  "project": "my-app",
  "modules": [
    {
      "name": "payments",
      "path": "src/payments",
      "depends_on": ["users", "orders"]
    }
  ],
  "apis": [
    {
      "method": "POST",
      "path": "/payments",
      "handler": "PaymentController.create"
    }
  ]
}
```

Mas não ficaria apenas em JSON.

Criaria um **grafo de conhecimento do projeto**:

```
PaymentController
       │
       ├── calls → PaymentService
       │                │
       │                └── uses → StripeClient
       │
       └── returns → PaymentResponse
```

E:

```
OrderService
     │
     └── depends_on → PaymentService
```

Isso permite ao orquestrador responder:

> "Se `PaymentService` mudou, quais partes da documentação podem estar afetadas?"

---

# 3. Stack e estratégia de evolução

Para um ambiente pessoal/local, eu evitaria microserviços demais.

> **Decisão integrada:** a arquitetura descrita nesta parte representa a direção de longo prazo do Project Intelligence Layer. A implementação inicial do control plane será deliberadamente menor: Python + SQLite + fila própria + HTTP direto para `llama-server`. PostgreSQL, pgvector e Redis entram apenas quando houver um requisito concreto que SQLite/filas internas não cubram bem.

### Core

**Python**

Porque você vai querer:

- parsing
- AST
- Git
- processamento de arquivos
- pipelines
- integração com modelos
- automação

### Orquestrador

Eu faria um serviço próprio em Python.

```
orchestrator/
├── planner/
├── analyzers/
├── context/
├── agents/
├── knowledge/
├── tasks/
└── workflows/
```

Pode usar FastAPI para a API.

### Banco principal

**Fase inicial: SQLite. Fase de escala: PostgreSQL.**

Na primeira implementação, SQLite guarda o estado operacional do orquestrador porque reduz dependências e facilita backup, recovery e testes locais. Quando o Project Intelligence Layer crescer em volume, concorrência ou necessidade de consultas relacionais mais pesadas, a migração natural é PostgreSQL.

O banco persistente deverá guardar:

- projetos
- versões
- arquivos
- símbolos
- entidades
- relações
- tarefas
- agentes
- documentos
- versões da documentação

---

# 4. Vector DB

Embeddings não são requisito do primeiro milestone. O sistema deve primeiro provar que consegue selecionar contexto através de Git, paths, símbolos, AST, dependências e pesquisa textual determinística.

Quando recuperação semântica passar a ser necessária, a escolha preferida é:

**PostgreSQL + pgvector**

Em vez de introduzir Qdrant, Weaviate ou outro serviço vetorial separado cedo demais.

Nessa fase teremos:

```
PostgreSQL
│
├── metadata
├── project graph
├── tasks
├── documents
└── embeddings
```

Para uso pessoal, isso simplifica muito a infraestrutura.

---

# 5. Não faça embedding do arquivo inteiro

Isso é importante.

Em vez de:

```
PaymentService.ts → embedding
```

quebre semanticamente:

```
PaymentService
├── createPayment()
├── refundPayment()
├── validatePayment()
└── handleWebhook()
```

Cada unidade pode ter:

```
symbol
path
line_start
line_end
language
module
dependencies
embedding
```

Assim a recuperação fica muito melhor.

---

# 6. Analisadores

Eu criaria uma interface comum:

```
class Analyzer:

    def analyze(self, project):
        ...
```

E implementaria:

```
Analyzers
│
├── FileAnalyzer
├── ASTAnalyzer
├── DependencyAnalyzer
├── GitAnalyzer
├── APIAnalyzer
├── DatabaseAnalyzer
├── ConfigAnalyzer
├── TestAnalyzer
└── ArchitectureAnalyzer
```

### AST

Dependendo das linguagens:

```
Python → tree-sitter / AST
TypeScript → tree-sitter / TypeScript compiler
Java → tree-sitter / Java parser
Go → go/parser
Rust → syn
```

Eu particularmente consideraria **Tree-sitter** como uma camada transversal para suportar várias linguagens.

---

# 7. Git Analyzer

Esse componente é fundamental.

Ele deve entender:

```
commit
branch
PR
diff
author
timestamp
files changed
```

Imagine:

```
HEAD
 ↓
diff
 ↓
src/payments/service.ts
src/payments/controller.ts
```

O sistema identifica:

```
PaymentService
PaymentController
Payment API
Payment architecture
```

E gera:

```
Affected documentation:

✓ docs/payments.md
✓ docs/api/payments.md
✓ docs/architecture.md
```

Isso permite **documentação incremental**.

---

# 8. O Task Engine

Essa seria provavelmente a parte mais interessante do seu sistema.

O orquestrador cria tarefas estruturadas.

Por exemplo:

```
{
  "task": "document_module",
  "project": "shop",
  "module": "payments",
  "priority": 5,
  "context": [
    "PaymentService",
    "PaymentController",
    "PaymentRepository"
  ],
  "outputs": [
    "docs/modules/payments.md"
  ]
}
```

O agente não precisa procurar tudo.

Ele recebe:

```
Você precisa documentar o módulo Payments.

Contexto:
- X
- Y
- Z

Dependências:
- Orders
- Users

APIs:
- POST /payments
- GET /payments/{id}

Output esperado:
docs/modules/payments.md
```

Isso reduz brutalmente o custo de contexto.

---

# 9. Agent Pool

Seu rig provavelmente pode executar vários agentes simultaneamente.

Eu organizaria agentes especializados:

```
                    ORCHESTRATOR
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
     Architecture       API          Module
       Agent            Agent         Agent
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                    Reviewer Agent
                         │
                         ▼
                    Doc Compiler
```

### Agents

**Architecture Agent**

Produz:

- visão geral
- componentes
- dependências
- fluxos

**API Agent**

Produz:

- endpoints
- parâmetros
- respostas
- autenticação
- erros

**Module Agent**

Documenta cada módulo.

**Database Agent**

Documenta:

- tabelas
- relações
- migrations
- entidades

**DevOps Agent**

Documenta:

- Docker
- CI/CD
- deployment
- infraestrutura

**Reviewer Agent**

Não escreve.

Ele verifica:

```
"A documentação afirma X."

Existe evidência no código?

SIM → OK

NÃO → FLAG
```

Esse agente é extremamente importante para reduzir alucinações.

---

# 10. Context Builder

Eu considero este um dos componentes mais importantes.

O orquestrador deveria montar automaticamente um pacote:

```
TASK CONTEXT

Project:
my-shop

Relevant files:
src/payments/service.ts
src/payments/controller.ts

Relevant symbols:
PaymentService
PaymentController

Dependencies:
Orders
Users

API:
POST /payments

Recent changes:
commit abc123

Existing documentation:
docs/payments.md
```

O agente recebe **somente isso**.

Não:

```
"Leia o repositório inteiro."
```

---

# 11. Memória em três níveis

Eu usaria três tipos de memória.

### 1. Estrutural

PostgreSQL:

```
classes
functions
modules
dependencies
APIs
```

### 2. Semântica

pgvector:

```
embeddings
```

### 3. Histórico

Git:

```
commits
diffs
decisões
alterações
```

Então uma pergunta pode ser respondida usando os três.

---

# 12. Documentação como artefato versionado

Eu **não colocaria a documentação somente no banco**.

O resultado final seria:

```
docs/
├── index.md
├── architecture.md
├── getting-started.md
├── api/
├── modules/
├── database/
└── deployment/
```

E isso iria para Git.

Assim:

```
Código
   +
Documentação
   ↓
Git
```

Você consegue ver:

```
commit A
    ↓
docs version 1

commit B
    ↓
docs version 2
```

---

# 13. Pipeline completo

Quando você adiciona um projeto:

```
1. Clone repository
        ↓
2. Detect stack
        ↓
3. Scan files
        ↓
4. Parse AST
        ↓
5. Extract symbols
        ↓
6. Extract dependencies
        ↓
7. Analyze Git
        ↓
8. Detect APIs
        ↓
9. Build project graph
        ↓
10. Generate embeddings
        ↓
11. Create documentation tasks
        ↓
12. Dispatch agents
        ↓
13. Agents generate drafts
        ↓
14. Reviewer validates
        ↓
15. Compiler assembles docs
        ↓
16. Build documentation site
```

---

# 14. Depois, o incremental

Aqui está onde o sistema fica realmente poderoso.

Você faz:

```
git commit
```

O orquestrador detecta:

```
5 files changed
```

Analisa o diff:

```
PaymentService.createPayment()
```

descobre:

```
PaymentService
      ↓
PaymentController
      ↓
POST /payments
      ↓
Architecture
```

Então cria apenas:

```
TASK-103
Update payment module documentation

TASK-104
Update POST /payments documentation

TASK-105
Review architecture documentation
```

Em vez de mandar 50 agentes para regenerar o projeto inteiro.

---

# 15. Fila de tarefas

A fila é necessária, mas não precisa começar como infraestrutura separada.

**Fase inicial:** fila persistida em SQLite e scheduler próprio no processo do orquestrador.

**Fase de escala:** Redis pode ser introduzido quando houver concorrência suficiente, múltiplos processos de control plane ou pressão operacional que justifique separar a fila.

```
PostgreSQL
     │
     │ task metadata
     ▼
   Redis
     │
     ├── Agent 1
     ├── Agent 2
     ├── Agent 3
     └── Agent 4
```

Celery, Dramatiq ou Arq continuam opções futuras, mas não entram no baseline. O primeiro desenho usa **fila própria + SQLite**, mantendo os telefones como appliances de inferência HTTP, e não como workers Python.

---

# 16. Seu rig local

A camada de inferência ficaria separada:

```
                 ORCHESTRATOR
                      │
                 Agent Router
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
     Model A       Model B       Model C
      local         local         local
```

O router pode escolher:

```
Resumo simples
    → modelo pequeno

Análise de arquitetura
    → modelo maior

Revisão
    → modelo especializado

Embeddings
    → embedding model
```

Isso permite aproveitar muito melhor o hardware.

---

# 17. Model Gateway / Model Client

Em vez de os agentes conhecerem diretamente os modelos, o control plane deve expor uma camada única de acesso. No primeiro milestone essa camada é um `Model Client` + `Router`; mais tarde pode evoluir para um Model Gateway dedicado:

```
Agent
  ↓
Model Gateway
  ↓
┌─────────────┬─────────────┐
│ GPU 0       │ GPU 1       │
│ Model A     │ Model B     │
└─────────────┴─────────────┘
```

O agente simplesmente pede:

```
model = "coding"
task = ...
```

O gateway decide onde executar.

Isso também permite trocar modelos posteriormente sem modificar os agentes.

---

# 18. Observabilidade

Mesmo sendo pessoal, eu colocaria desde o início:

```
Task
 ↓
Agent
 ↓
Prompt
 ↓
Model
 ↓
Output
 ↓
Validation
```

Registrando:

```
task_id
agent
model
tokens
latency
status
output
validation_score
```

Não precisa de uma plataforma enorme.

PostgreSQL + logs estruturados já resolvem inicialmente.

---

# 19. Segurança

Como os agentes vão ler código e potencialmente executar comandos, eu separaria o ambiente.

```
                 ORCHESTRATOR
                      │
                      ▼
              ┌───────────────┐
              │ Agent Sandbox  │
              ├───────────────┤
              │ repo clone    │
              │ tools         │
              │ tests         │
              │ filesystem    │
              └───────────────┘
```

O agente não deveria ter acesso irrestrito ao seu sistema operacional.

Especialmente se futuramente ele puder:

```
npm install
pip install
docker
shell
git
```

---

# 20. A arquitetura final que eu montaria

Para o seu caso, eu começaria relativamente simples:

```
                         ┌───────────────┐
                         │ Git Repository│
                         └───────┬───────┘
                                 │
                                 ▼
                     ┌─────────────────────┐
                     │    ORCHESTRATOR     │
                     │                     │
                     │ Planner             │
                     │ Change Detector     │
                     │ Context Builder     │
                     │ Agent Router        │
                     └───────┬─────────────┘
                             │
               ┌─────────────┼──────────────┐
               ▼             ▼              ▼
          ┌─────────┐   ┌─────────┐   ┌──────────┐
          │ AST     │   │ Git     │   │ API      │
          │ Parser  │   │ Parser  │   │ Analyzer │
          └────┬────┘   └────┬────┘   └────┬─────┘
               └─────────────┼─────────────┘
                             ▼
                    ┌──────────────────┐
                    │ Project Graph    │
                    └────────┬─────────┘
                             │
                 ┌───────────┼───────────┐
                 ▼           ▼           ▼
              Postgres    pgvector     Redis
                 │                       │
                 │                       ▼
                 │                 ┌─────────────┐
                 │                 │ Agent Pool  │
                 │                 └──────┬──────┘
                 │                        │
                 │             ┌──────────┼──────────┐
                 │             ▼          ▼          ▼
                 │          API Agent  Module    Architecture
                 │                        Agent       Agent
                 │             └──────────┼──────────┘
                 │                        ▼
                 │                 Reviewer Agent
                 │                        │
                 └────────────────────────┤
                                          ▼
                                  ┌──────────────┐
                                  │ Doc Compiler │
                                  └──────┬───────┘
                                         ▼
                                    /docs/*.md
                                         │
                                         ▼
                                  Documentation UI
```

### Stack concreta

A tabela abaixo representa a **arquitetura-alvo** para quando Project Intelligence, recuperação semântica e maior concorrência justificarem os componentes adicionais:

### Baseline de implementação (Fase 1)

| Componente | Tecnologia inicial |
| --- | --- |
| Control plane | Python |
| API opcional | FastAPI, apenas quando necessário |
| Persistência | SQLite |
| Fila | própria, persistida em SQLite |
| Workers LLM | `llama-server` em Android/Termux |
| Transporte | HTTP autenticado |
| Rede | Tailscale/MagicDNS como identidade estável; LAN como caminho local |
| Git | CLI Git + worktrees |
| Pesquisa inicial | ripgrep + metadados determinísticos |
| Parsing | Tree-sitter conforme necessidade |
| Testes | pytest + fake HTTP workers + fixtures Git |
| IoT | MQTT/adapter + policy gate determinístico |
| Observabilidade | logs estruturados + métricas mínimas |

### Arquitetura-alvo / Fase 2+

| Componente    | Tecnologia               |
| ------------- | ------------------------ |
| Orquestrador  | Python + FastAPI         |
| Análise AST   | Tree-sitter              |
| Git           | GitPython / CLI Git      |
| Banco         | PostgreSQL               |
| Vetores       | pgvector                 |
| Fila          | Redis                    |
| Workers       | Python                   |
| Model gateway | sua infraestrutura local |
| Embeddings    | modelo local             |
| Documentação  | Markdown/MDX             |
| Site          | Docusaurus ou VitePress  |
| Diagramas     | Mermaid                  |
| Sandbox       | Docker                   |
| Deploy        | Docker Compose           |

**Não começaria com Kubernetes, Kafka, vários bancos vetoriais ou dezenas de microserviços.** Para uso pessoal, isso adicionaria complexidade sem trazer benefício proporcional.

O investimento principal deveria estar no **Project Graph + Context Builder + Change Detector**. Esses três componentes são o que permitem que seus agentes locais trabalhem com contexto preciso, em vez de desperdiçar capacidade lendo o repositório inteiro.

Se quiser construir isso de forma séria, o próximo passo é definir o **contrato interno entre o orquestrador e os agentes** — schemas de `Project`, `Symbol`, `Dependency`, `Task`, `Context`, `Artifact` e `ValidationResult`. Com esses contratos bem definidos, o restante da infraestrutura fica bastante modular.

---

# PARTE B — Blueprint de implementação autónoma e validação

> Documento de arquitetura e execução, sem implementação Python.  
> Projeto: sistema de IA distribuída com Raspberry Pi + Android/Termux.  
> Estado de partida: OPPO e Huawei acessíveis por SSH, `sshd` supervisionado por `runit` e sobrevivendo a reboot via Termux:Boot. O `llama.cpp` e o modelo Qwen2.5-Coder-1.5B Q4_K_M já foram instalados/testados nos telefones.  
> Documento complementar: `sistema_ia_distribuida_runbook.md`.

---

## 1. Objetivo deste documento

Este documento serve para duas situações diferentes:

1. **Plano A — Implementação autónoma pelo proprietário do sistema**  
   Define arquitetura, contratos, milestones, critérios de aceitação, testes, riscos, ordem de trabalho e artefactos esperados. Não contém a implementação Python.

2. **Plano B — Briefing para uma IA de apoio quando houver bloqueio**  
   Define como outra IA deve receber contexto, respeitar a arquitetura, limitar alterações, escrever apenas a parte necessária e entregar testes junto com qualquer implementação sugerida.

O objetivo não é construir apenas um “agente de coding”. O objetivo é construir um **orquestrador genérico de jobs**, capaz de usar diferentes workers e diferentes executores.

O coding é um workload. IoT é outro. Resumos, classificação, extração, automações e tarefas LLM genéricas são outros.

---

# PARTE I — VISÃO DO SISTEMA

## 2. North Star

O Raspberry Pi é o plano de controlo. Os telefones são recursos de inferência. Serviços externos ou dispositivos IoT nunca dependem diretamente da disponibilidade de um telefone.

```text
                         +----------------------+
                         |      UTILIZADOR      |
                         +----------+-----------+
                                    |
                                    v
                         +----------+-----------+
                         |     RASPBERRY PI     |
                         |     CONTROL PLANE    |
                         |----------------------|
                         | Job API / CLI        |
                         | Router               |
                         | Worker Registry      |
                         | Scheduler            |
                         | State Machine        |
                         | SQLite               |
                         | Policies             |
                         | Git / Worktrees      |
                         | Verification         |
                         | MQTT / IoT Gateway   |
                         | Logs / Metrics       |
                         +----+-------------+---+
                              |             |
                       HTTP   |             | HTTP
                              v             v
                    +---------+---+     +---+----------+
                    | OPPO        |     | Huawei       |
                    |-------------|     |--------------|
                    | llama-server|     | llama-server |
                    | coding      |     | generic/IoT  |
                    | heavy LLM   |     | light LLM    |
                    +-------------+     +--------------+
```

### 2.1 Princípio central

```text
LLM decide/propoe linguagem e raciocinio.
Control plane decide o que pode acontecer de verdade.
Ferramentas deterministicas verificam o resultado.
```

O modelo não deve receber poder irrestrito sobre shell, Git, rede ou IoT.

---

## 3. O que significa “worker” neste projeto

No desenho inicial, **worker físico = telefone com `llama-server`**.

Não é necessário criar um daemon Python dentro de cada Android para começar.

```text
NAO inicialmente:

Raspberry
   |
   v
worker-agent-python-no-telefone
   |
   v
llama-server


SIM inicialmente:

Raspberry
   |
   +-------- HTTP --------> llama-server OPPO
   |
   +-------- HTTP --------> llama-server Huawei
```

Toda a lógica de scheduling, estado, persistência, retry, Git, IoT e segurança fica no Raspberry.

Um agente adicional no telefone só deverá existir se aparecer uma necessidade concreta que o `llama-server` não resolva.

---

## 4. Workers e capacidades

A identidade do worker deve ser independente do modelo que está carregado.

Um worker possui **capacidades**, **limites** e **estado**.

Exemplo conceptual:

```yaml
worker:
  id: ai-oppo
  endpoint: http://ai-oppo:8080
  capabilities:
    - llm
    - coding
    - patch_generation
    - review
    - generic_text
  performance_tier: fast
  max_parallel: 1
  context_limit: 2048
  enabled: true
```

```yaml
worker:
  id: ai-huawei
  endpoint: http://ai-huawei:8080
  capabilities:
    - llm
    - classify
    - summarize
    - extract
    - iot_intent
    - automation_reasoning
    - generic_text
  performance_tier: slow
  max_parallel: 1
  context_limit: 2048
  enabled: true
```

Esses exemplos são contratos conceptuais, não ficheiros finais obrigatórios.

### 4.1 Um mesmo telefone pode mudar de função

Hoje:

```text
Huawei -> Qwen2.5-Coder-1.5B Q4_K_M
```

Futuramente pode fazer mais sentido:

```text
Huawei -> modelo 0.5B/1B optimizado para intents, classificacao e IoT
OPPO   -> Qwen Coder 1.5B para coding
```

O scheduler não deve assumir que `ai-huawei` significa um modelo específico para sempre.

---

## 5. Tipos de job

O domínio deve nascer genérico.

Primeiros tipos previstos:

```text
generic_llm
classify
summarize
extract
iot_intent
automation_reasoning
coding_patch
coding_review
```

Posteriormente:

```text
embedding
rerank
vision
speech
scheduled_automation
notification
```

Não é necessário implementar todos agora.

---

## 6. Fluxo genérico de um job

```text
request
   |
   v
validate
   |
   v
create Job
   |
   v
QUEUE
   |
   v
Router determina requirements
   |
   v
Scheduler escolhe Worker
   |
   v
DISPATCH
   |
   v
Model Client
   |
   v
llama-server
   |
   v
ModelResult
   |
   +------> tarefa apenas de texto ------> SUCCESS
   |
   +------> tarefa com side effect
                    |
                    v
              Policy / Executor
                    |
                    v
              Verification
                    |
               +----+----+
               |         |
             SUCCESS    RETRY/FAIL
```

---

# PARTE II — PRINCÍPIOS DE ARQUITETURA

## 7. Regras que não devem ser quebradas

### 7.1 Control plane único

O Raspberry é a fonte de verdade para:

- jobs;
- workers conhecidos;
- leases/reservas;
- retries;
- policies;
- Git;
- histórico;
- execução IoT;
- resultados de verificação.

Os telefones não coordenam entre si.

### 7.2 LLM sem shell irrestrito

Nunca transformar texto gerado pelo LLM diretamente em:

```text
shell command -> exec
```

O correto é:

```text
LLM proposal
     |
     v
parser/schema
     |
     v
policy/allowlist
     |
     v
executor deterministico
```

### 7.3 IoT continua funcional sem LLM

```text
Huawei OFF
   |
   +--> MQTT continua
   +--> regras deterministicas continuam
   +--> automacoes basicas continuam
   +--> sensores continuam
   +--> apenas funcoes inteligentes ficam degradadas
```

### 7.4 Coding acontece fora da branch principal

Cada job de alteração deve trabalhar num contexto isolado:

```text
repo
  |
  +--> main/master protegido
  |
  +--> worktree/job-<id>
           |
           +--> patch
           +--> format
           +--> lint
           +--> typecheck
           +--> tests
```

### 7.5 O modelo não decide se passou

```text
"acho que os testes passam" != sucesso

exit code real dos testes = verdade
```

### 7.6 Tudo que possa repetir deve ser idempotente

O Raspberry pode reiniciar, a rede pode cair e um worker pode responder depois de timeout.

O sistema deve evitar executar duas vezes uma operação com side effect.

Usar como conceito:

```text
job_id
attempt_id
idempotency_key
```

---

## 8. Níveis de autonomia

Não saltar diretamente para autonomia total.

```text
L0 - Query
     modelo responde; nenhum side effect

L1 - Proposal
     modelo produz plano/acao; humano aprova

L2 - Bounded execution
     sistema executa acoes allowlisted e reversiveis

L3 - Bounded coding loop
     modelo -> patch -> verificacao -> retry limitado

L4 - Scheduled / event-driven automation
     jobs automaticos com policies e kill switch

L5 - Higher autonomy
     somente depois de logs, limites, recuperacao e testes maduros
```

O primeiro objetivo prático deve ser chegar com segurança até L2/L3.

---

# PARTE III — TECNOLOGIAS

## 9. Stack recomendada

### 9.1 Workers Android

Já escolhidos:

| Componente | Tecnologia |
|---|---|
| Runtime Android | Termux |
| Inference engine | `llama.cpp` |
| API | `llama-server` |
| Serviço | `runit` via `termux-services` |
| Boot | Termux:Boot |
| Administração | OpenSSH/Termux, porta 8022 |
| Rede lógica | Tailscale/MagicDNS, depois de finalizado |

### 9.2 Raspberry control plane

Recomendação inicial:

| Necessidade | Tecnologia |
|---|---|
| Linguagem | Python disponível no Raspberry; preferir 3.11+ se suportado |
| Concorrência | `asyncio` |
| HTTP client | `httpx` ou equivalente leve |
| Persistência | SQLite |
| Configuração | TOML ou YAML; TOML tem suporte stdlib em Python moderno |
| Logging | `logging` + JSON estruturado ou formato estável |
| Testes | `pytest` |
| Mocks HTTP | fake worker próprio ou biblioteca leve compatível com o Pi |
| Git | CLI Git, invocação controlada |
| Busca inicial de código | `ripgrep` |
| MQTT | Mosquitto + cliente MQTT quando chegar ao milestone IoT |
| Home Assistant | opcional; adapter separado, não dependência central |

### 9.3 Restrição importante: Raspberry `armv6l`

Foi observado `armv6l` no Raspberry.

Antes de escolher bibliotecas com extensões nativas, confirmar:

```sh
python3 --version
uname -m
cat /proc/device-tree/model 2>/dev/null; echo
```

Regra de dependências:

```text
stdlib primeiro
pure Python quando possivel
native dependency apenas com justificacao + teste de instalacao no Pi
```

Evitar criar dependência precoce em packages que não tenham wheel/compilação tranquila para a arquitetura real do Raspberry.

### 9.4 O que NÃO adicionar inicialmente

Não há justificação agora para:

```text
Redis
Celery
RabbitMQ
Kafka
Kubernetes
Docker Swarm
vector database
agent framework pesado
LangChain como infraestrutura central
multi-node database
service mesh
```

SQLite + um processo de orquestração é suficiente para os primeiros milestones.

Adicionar infraestrutura somente quando existir um problema medido que a justifique.

---

# PARTE IV — CONTRATOS DO DOMÍNIO

## 10. Contratos mínimos

A primeira implementação deve começar pelos contratos, não pelo HTTP.

Não é necessário usar exatamente estes nomes, mas estas responsabilidades devem existir.

---

## 10.1 WorkerSpec

Representa configuração relativamente estática.

Campos conceptuais:

```text
id
endpoint
capabilities
model_name
context_limit
max_parallel
performance_tier
enabled
timeout_policy
metadata
```

Invariantes:

```text
id e unico
endpoint valido
max_parallel >= 1
worker disabled nunca recebe job
capability requerida precisa existir
```

---

## 10.2 WorkerHealth

Estado observado dinamicamente.

```text
worker_id
status
last_check_at
latency_ms
model_loaded
active_jobs
last_error
consecutive_failures
```

Status mínimos:

```text
UNKNOWN
HEALTHY
BUSY
DEGRADED
OFFLINE
QUARANTINED
```

---

## 10.3 JobSpec

Pedido imutável ou quase imutável.

```text
job_id
job_type
created_at
priority
requirements
input
limits
policy
```

Requirements podem incluir:

```text
required_capabilities
preferred_worker
max_context
latency_class
allow_fallback
```

Limits podem incluir:

```text
max_attempts
max_wall_time
max_model_calls
max_output_tokens
max_diff_files
max_diff_lines
```

---

## 10.4 JobState

Estado de execução.

Sugestão:

```text
CREATED
QUEUED
DISPATCHING
RUNNING
VERIFYING
WAITING_RETRY
SUCCEEDED
FAILED
CANCELLED
```

Transições devem ser explícitas.

Exemplo:

```text
CREATED -> QUEUED
QUEUED -> DISPATCHING
DISPATCHING -> RUNNING
RUNNING -> VERIFYING
VERIFYING -> SUCCEEDED
VERIFYING -> WAITING_RETRY
WAITING_RETRY -> QUEUED
qualquer estado ativo -> FAILED/CANCELLED conforme regra
```

Uma função/teste deve impedir transições ilegais.

---

## 10.5 Attempt

Cada tentativa precisa ser auditável separadamente.

```text
attempt_id
job_id
worker_id
started_at
finished_at
request_metadata
result_metadata
error_type
retryable
```

Nunca sobrescrever a história de uma tentativa anterior.

---

## 10.6 ModelRequest

Contrato normalizado entre orquestrador e adapter LLM.

```text
messages / prompt
max_tokens
temperature
stop
response_mode
timeout
request_id
```

O resto do sistema não deve depender diretamente do JSON específico de `llama-server`.

---

## 10.7 ModelResult

Resposta normalizada.

```text
request_id
worker_id
text
finish_reason
prompt_tokens
completion_tokens
latency
raw_metadata opcional
```

Erro de transporte não é `ModelResult` bem-sucedido.

---

## 10.8 VerificationResult

Para coding e outras tarefas verificáveis:

```text
passed
checks
stdout_summary
stderr_summary
duration
artifacts
```

Cada check:

```text
name
command_id
exit_code
passed
duration
```

---

## 10.9 ActionProposal

Para IoT/automação:

```text
action
resource
parameters
reason
confidence opcional
expires_at
```

Isto é uma proposta. Não é uma execução.

---

# PARTE V — COMPONENTES DO CONTROL PLANE

## 11. Worker Registry

Responsabilidades:

- carregar WorkerSpec;
- disponibilizar workers por capability;
- manter WorkerHealth;
- saber quantos slots estão ocupados;
- marcar worker offline/degraded;
- não fazer scheduling por si próprio.

Não misturar Registry e Scheduler.

---

## 12. Health Checker

Perguntas que precisa responder:

```text
processo HTTP responde?
modelo esta carregado?
latencia aceitavel?
worker aceita inferencia autenticada?
quantos failures consecutivos existem?
```

Regras iniciais simples:

```text
1 failure -> DEGRADED
N failures consecutivos -> OFFLINE
sucessos posteriores -> HEALTHY
```

O valor de N deve ser configuração, não magia espalhada no código.

### 12.1 Health não deve gerar spam de inferência

Preferir endpoint de saúde barato.

Smoke de geração real pode ser periódico e menos frequente.

---

## 13. Model Client

É a única camada que entende a API HTTP do `llama-server`.

Responsabilidades:

```text
serializar ModelRequest
incluir autenticação
executar timeout
interpretar status HTTP
normalizar resposta
classificar erros
medir latencia
não fazer scheduling
não fazer retry de job por conta propria
```

Erros a diferenciar:

```text
connection_error
timeout
auth_error
rate_or_busy
bad_request
server_error
malformed_response
cancelled
```

Retry de transporte curto pode existir nesta camada somente se estiver claramente definido. Retry semântico do job pertence ao orquestrador.

---

## 14. Router

Recebe `job_type` e determina requisitos.

Exemplos:

```text
coding_patch
    -> capability coding + patch_generation

classify
    -> capability classify

summarize
    -> summarize OU generic_text

iot_intent
    -> iot_intent
```

Router não escolhe a máquina. Produz requirements.

---

## 15. Scheduler

Escolhe worker elegível.

Versão 1 deve ser determinística e compreensível.

Critérios possíveis, em ordem:

```text
1. enabled
2. HEALTHY/DEGRADED permitido
3. capabilities suficientes
4. slot disponivel
5. preferred_worker se aplicavel
6. performance tier
7. carga atual
8. fallback permitido
```

Política inicial sugerida:

```text
coding_patch/review grande -> OPPO
classify/summarize/iot_intent -> Huawei
OPPO ocupado -> Huawei apenas se requirements permitirem
Huawei indisponivel -> OPPO pode executar generic jobs
nenhum worker elegivel -> job continua na queue ou falha por deadline
```

Não implementar “IA para escolher IA” nesta fase.

---

## 16. Job Manager / State Machine

É o núcleo do sistema.

Responsabilidades:

- criar job;
- validar transições;
- criar attempts;
- reservar/libertar worker slot;
- respeitar budgets;
- guardar eventos;
- pedir scheduling;
- acionar adapters/executors;
- decidir retry/fail;
- recuperar após restart.

### 16.1 Event log

Além do estado atual, guardar eventos ajuda muito:

```text
JOB_CREATED
JOB_QUEUED
WORKER_SELECTED
ATTEMPT_STARTED
MODEL_REQUEST_SENT
MODEL_RESULT_RECEIVED
VERIFICATION_STARTED
VERIFICATION_FAILED
RETRY_SCHEDULED
JOB_SUCCEEDED
JOB_FAILED
```

Isto é especialmente útil para debug de sistemas autónomos.

---

## 17. Persistence

SQLite inicialmente.

Entidades mínimas:

```text
workers (config pode continuar em ficheiro)
jobs
attempts
events
```

Pode haver tabelas específicas depois:

```text
coding_runs
iot_actions
artifacts
```

### 17.1 Requisito de recuperação

Após matar/reiniciar o processo do orquestrador:

```text
jobs SUCCEEDED continuam SUCCEEDED
jobs FAILED continuam FAILED
jobs RUNNING antigos sao reconciliados
slots nao ficam presos para sempre
nenhum side effect e repetido cegamente
```

---

# PARTE VI — CODING ADAPTER

## 18. Coding como adapter, não como núcleo

```text
Generic Orchestrator
        |
        +--> Coding Adapter
        |
        +--> IoT Adapter
        |
        +--> Text Adapter
```

Assim o sistema continua útil mesmo se o fluxo de coding mudar.

---

## 19. Fluxo coding alvo

```text
CodingJob
   |
   v
validate repo allowlist
   |
   v
create branch/worktree
   |
   v
Context Builder
   |
   +--> task description
   +--> relevant files
   +--> grep/search results
   +--> test failures
   +--> local conventions
   |
   v
ModelRequest
   |
   v
structured patch/proposal
   |
   v
Patch Validator
   |
   v
apply
   |
   +--> formatter
   +--> lint
   +--> typecheck
   +--> tests
   |
   +---- PASS ----> review / ready
   |
   +---- FAIL ----> errors + bounded retry
```

---

## 20. Context Builder

Começar simples.

Primeiros recursos:

```text
ripgrep
ficheiros explicitamente indicados pela task
git diff
git status
test failure output
project instructions
```

Só adicionar Tree-sitter/LSP depois de provar que o contexto básico é insuficiente.

Regras:

```text
nao enviar repo inteiro
definir limite de bytes/tokens
preferir codigo directamente relacionado
guardar quais ficheiros foram enviados
```

---

## 21. Patch contract

O modelo deve devolver um formato previsível.

Opções a avaliar:

```text
unified diff
JSON com lista de edits
outro formato estruturado validavel
```

Critérios para escolher:

- fácil de validar;
- fácil de rejeitar se sair do escopo;
- fácil de aplicar deterministicamente;
- produz diff humano legível;
- suporta múltiplos ficheiros;
- permite limites de tamanho.

Não confiar em texto misturado com patch sem parser/validação.

---

## 22. Verification pipeline

Comandos não vêm do modelo.

Cada projeto deve declarar os checks permitidos.

Conceito:

```yaml
verification:
  - id: format_check
  - id: lint
  - id: typecheck
  - id: unit_tests
```

O mapping `id -> comando real` é configuração controlada pelo proprietário.

O modelo pode pedir “executar unit tests”; não pode injetar um comando arbitrário.

---

## 23. Limites de coding

Configurar pelo menos:

```text
max_attempts
max_model_calls
max_changed_files
max_diff_lines
max_job_minutes
allowed_paths
denied_paths
allowed_test_commands
```

Paths sensíveis típicos:

```text
.env
credentials
production secrets
SSH private keys
system files
```

---

# PARTE VII — IoT E AUTOMAÇÃO

## 24. Arquitetura IoT segura

O Huawei é um interpretador/raciocinador, não o dono dos atuadores.

```text
sensor/event
    |
    v
MQTT / Home Assistant / adapter
    |
    v
Raspberry
    |
    +--> regra deterministica suficiente? -- SIM --> executor
    |
    +--> precisa interpretar linguagem/contexto
                 |
                 v
              Huawei
                 |
                 v
          ActionProposal
                 |
                 v
           Policy Gate
                 |
            +----+----+
            |         |
          ALLOW      DENY
            |
            v
        IoT Executor
            |
            v
          device
```

---

## 25. MQTT

Mosquitto no Raspberry é uma opção natural para o bus de eventos IoT.

Não precisa fazer parte do primeiro milestone da orquestração.

Quando chegar:

```text
sensors -> MQTT topics
orchestrator subscribes
orchestrator creates jobs quando necessario
executors publish comandos allowlisted
```

### 25.1 Separar evento de comando

Exemplo conceptual:

```text
home/sensor/office/temperature
home/state/office/fan
home/command/office/fan
```

O LLM não deve poder publicar diretamente num topic de comando.

---

## 26. Policy Gate

A política decide se uma ActionProposal é executável.

Validar:

```text
resource existe?
action permitida?
parametros validos?
job autorizado para esta action?
janela horaria permitida?
acao reversivel?
precisa aprovacao humana?
proposal expirou?
mesma action ja foi executada?
```

### 26.1 Classes de risco

Sugestão:

```text
LOW
- luz
- fan
- notificacao

MEDIUM
- aquecimento/ar condicionado
- automacoes com custo ou impacto fisico moderado

HIGH
- fechaduras
- alarmes
- tomadas de equipamento perigoso
- sistemas de seguranca
```

Para HIGH, começar sempre com aprovação humana explícita.

---

## 27. Shadow mode

Antes de permitir side effects de IoT:

```text
EVENT
  |
  v
LLM proposal
  |
  v
Policy decision
  |
  v
LOG ONLY
```

Comparar durante vários eventos:

```text
proposta esperada?
policy correta?
falsos positivos?
contexto suficiente?
```

Só depois ativar execução real para actions LOW risk.

---

## 28. Kill switch

Deve existir forma simples de desligar toda autonomia com side effects sem desligar o sistema.

Conceito:

```text
autonomy_enabled = false
```

E idealmente controles separados:

```text
coding_execution_enabled
iot_execution_enabled
scheduled_jobs_enabled
```

A leitura/query pode continuar funcionando.

---

# PARTE VIII — TESTES

## 29. Estratégia geral

O maior erro seria usar os modelos reais como base de todos os testes.

LLMs variam. A orquestração precisa ser testável deterministicamente.

```text
                    poucos
              +---------------+
              | Real LLM E2E  |
              +---------------+
             /                 \
            / Integration tests \
           +---------------------+
          /                       \
         / Component / contract    \
        +---------------------------+
       /                             \
      /       Unit tests              \
     +---------------------------------+
                    muitos
```

---

## 30. Fake Worker

Criar um worker HTTP falso para testes.

Ele deve conseguir simular:

```text
health OK
health failure
resposta normal
resposta lenta
timeout
HTTP 401
HTTP 500
JSON invalido
resposta vazia
busy
resposta atrasada depois de timeout
```

Não precisa de IA.

Este fake worker é uma das peças mais importantes para desenvolver o orquestrador de forma confiável.

---

## 31. Unit tests obrigatórios

### Worker Registry

Testar:

```text
ID duplicado rejeitado
worker disabled excluido
filter por capability
estado atualizado
slot accounting correto
```

### Router

```text
job_type -> requirements corretos
job desconhecido -> erro claro
fallback capability permitido apenas quando configurado
```

### Scheduler

Casos mínimos:

```text
OPPO + Huawei livres, coding -> OPPO
OPPO ocupado, coding sem fallback -> espera
OPPO offline, coding com fallback compatível -> worker elegível
classify -> Huawei preferido
Huawei offline -> OPPO fallback se permitido
worker sem capability nunca escolhido
worker disabled nunca escolhido
```

### State Machine

```text
transicoes validas funcionam
transicoes ilegais falham
SUCCEEDED nao volta para RUNNING
CANCELLED nao volta para QUEUED
retry respeita max_attempts
```

### Budgets

```text
max_attempts
max_model_calls
max_wall_time
max_output_tokens
```

### Policy Gate IoT

```text
action allowlisted passa
action desconhecida falha
resource desconhecido falha
proposal expirada falha
HIGH risk sem aprovacao falha
duplicate idempotency key nao executa outra vez
```

### Coding guards

```text
path fora da allowlist rejeitado
ficheiro secreto rejeitado
diff demasiado grande rejeitado
comando nao allowlisted nunca executado
```

---

## 32. Contract tests

O Model Client deve ser testado contra respostas representativas do `llama-server`.

Guardar fixtures sanitizadas de:

```text
success
finish reason
usage
server error
auth error
malformed response
```

O objetivo é detetar quebra de parsing após upgrades do `llama.cpp`.

---

## 33. Integration tests

Executar com fake worker + SQLite real temporário.

Cenários:

```text
submit -> schedule -> call -> success
submit -> timeout -> retry -> success
submit -> worker offline -> fallback
submit -> todos offline -> queue/deadline
restart orchestrator -> recover job
cancel running/queued job
```

---

## 34. Testes reais dos workers

Esses testes devem ser poucos e claros.

Para cada telefone:

### Boot

```text
reboot
nao abrir Termux manualmente
sshd aparece
llama-server aparece
health responde
```

### Auth

```text
health conforme política definida
inference sem credencial -> rejeitada
inference com credencial -> aceita
```

### Smoke inference

Prompt controlado, por exemplo:

```text
Return exactly: WORKER_OK
```

Não usar essa resposta exata como teste universal de inteligência; serve apenas como smoke do caminho HTTP/inferência.

### Failure

```text
matar llama-server
health muda para offline/degraded
runit reinicia o processo
registry volta a healthy
```

---

## 35. Coding E2E fixtures

Criar pequenos repositórios de teste dedicados.

Exemplos:

```text
fixture_bug_01
- funcao com bug simples
- teste falhando
- resultado correto conhecido

fixture_bug_02
- mudanca exige dois ficheiros
- lint + unit tests

fixture_forbidden
- task tenta tocar path proibido
```

E2E não deve depender dos teus projetos reais.

Avaliar:

```text
worktree criado
contexto gerado
patch recebido
patch dentro dos limites
checks executados
job termina em estado correto
repo principal continua intacto
```

### 35.1 Testes de qualidade LLM separados

Qualidade do modelo é diferente de correção do orquestrador.

Criar suite opcional:

```text
N tarefas fixas
success rate
attempts medios
tokens
tempo
worker
```

Não deixar a suite de qualidade bloquear testes unitários da infraestrutura.

---

## 36. IoT E2E

Primeiro sem hardware físico.

Usar:

```text
broker de teste ou namespace isolado
sensor simulado
actuator simulado
shadow mode
```

Cenários:

```text
temperatura alta -> proposal fan on -> allow
pedido para recurso desconhecido -> deny
proposal duplicada -> uma unica execucao
Huawei offline -> regra basica continua
orchestrator restart -> nao duplica ultimo comando
kill switch -> nenhum side effect
```

Depois, testar um único dispositivo LOW risk real.

---

## 37. Resilience / chaos tests

Não precisam ser sofisticados.

Executar manualmente ou em scripts de teste:

```text
reboot OPPO durante job
reboot Huawei
parar Wi-Fi de worker
matar llama-server
matar orchestrator
reiniciar Raspberry
corromper resposta HTTP simulada
forcar timeout
forcar SQLite lock/busy
```

Objetivo:

```text
nenhum job desaparece silenciosamente
nenhum slot fica eternamente ocupado
nenhum side effect perigoso duplica
estado final e explicavel pelos logs
```

---

# PARTE IX — OBSERVABILIDADE

## 38. Logging

Cada linha/evento útil deve carregar contexto suficiente:

```text
timestamp
level
component
job_id
attempt_id
worker_id
event
latency/error quando aplicavel
```

Nunca logar:

```text
API keys
SSH private keys
secrets
conteudo sensivel sem necessidade
```

---

## 39. Métricas mínimas

Não é obrigatório instalar Prometheus inicialmente.

É obrigatório conseguir medir:

```text
jobs created
jobs succeeded
jobs failed
jobs retried
queue wait time
job duration
worker health
worker busy time
HTTP latency
model generation duration
tokens quando disponivel
verification duration
```

Podem começar em SQLite/JSON logs e ganhar endpoint de métricas depois.

---

## 40. Identificadores e tracing

Todo job:

```text
job_id
```

Toda tentativa:

```text
attempt_id
```

Toda chamada ao modelo:

```text
request_id
```

Esses IDs devem aparecer nos logs e persistência.

---

# PARTE X — SEGURANÇA

## 41. Worker network security

Objetivo final:

```text
workers acessiveis pelo tailnet
8080 nao exposto publicamente
SSH restringido ao ambiente administrativo
API key por worker ou politica equivalente
```

Tailscale/MagicDNS fornece identidade/rede estável, mas não deve ser desculpa para remover toda autenticação de aplicação sem decisão consciente.

---

## 42. Secrets

Separar:

```text
config versionada
secrets nao versionados
```

Ficheiros com secrets:

```text
chmod 600
```

Nunca colocar tokens em:

```text
repo
prompt enviado ao LLM
logs
exceptions serializadas para interfaces publicas
```

---

## 43. Tailscale ACLs

Quando a rede final estiver estabilizada, considerar ACL que expresse:

```text
Raspberry -> worker:8080 permitido
Raspberry -> worker:8022 permitido
outros peers -> conforme necessidade
internet -> worker ports negado
```

---

## 44. Coding security

O executor deve usar uma allowlist.

Não construir:

```text
subprocess(shell=True, texto_do_modelo)
```

Princípio:

```text
command_id conhecido
    |
    v
argv conhecido/controlado
    |
    v
subprocess
```

---

## 45. IoT security

Requisitos mínimos antes de execução autónoma:

```text
resource registry
allowlist de actions
schema de parametros
risk class
idempotency
audit log
kill switch
manual approval para high risk
```

---

# PARTE XI — CONFIGURAÇÃO E REPRODUTIBILIDADE

## 46. Separar domínio de configuração

Configuração não deve ficar espalhada no código.

Categorias:

```text
workers
scheduler
timeouts
retry policy
job budgets
repositories
verification commands
iot resources
iot policy
logging
features/kill switches
```

---

## 47. Versionar schemas

Qualquer formato persistido ou trocado entre componentes deve poder evoluir.

Conceito:

```text
schema_version: 1
```

Aplicar pelo menos a:

```text
job input/output persistido
action proposals
worker config
```

---

## 48. ADRs

Criar diretório de decisões arquiteturais, por exemplo:

```text
docs/adr/
```

Cada decisão relevante ganha um ficheiro curto:

```text
0001-sqlite-first.md
0002-raspberry-is-control-plane.md
0003-workers-are-llama-server-endpoints.md
0004-no-direct-llm-shell.md
0005-iot-policy-gate.md
```

Formato mínimo:

```text
Context
Decision
Consequences
```

Isto evita que uma IA futura ou o próprio projeto reabra decisões sem contexto.

---

# PARTE XII — ESTRUTURA LÓGICA DO REPOSITÓRIO

## 49. Estrutura sugerida

Isto é uma separação de responsabilidades, não implementação obrigatória.

```text
orchestrator/
|
+-- README.md
+-- pyproject.toml / dependency manifest
+-- config/
|   +-- workers.example.toml
|   +-- orchestrator.example.toml
|
+-- docs/
|   +-- architecture.md
|   +-- contracts.md
|   +-- testing.md
|   +-- adr/
|
+-- src/
|   +-- domain/
|   |   +-- workers
|   |   +-- jobs
|   |   +-- results
|   |   +-- policies
|   |
|   +-- services/
|   |   +-- registry
|   |   +-- scheduler
|   |   +-- job_manager
|   |   +-- health
|   |
|   +-- infrastructure/
|   |   +-- llama_http
|   |   +-- sqlite
|   |   +-- git
|   |   +-- process_runner
|   |   +-- mqtt
|   |
|   +-- adapters/
|       +-- generic_llm
|       +-- coding
|       +-- iot
|
+-- tests/
    +-- unit/
    +-- contract/
    +-- integration/
    +-- e2e/
    +-- fixtures/
```

Não criar módulos vazios antecipadamente apenas para imitar o desenho. Criar quando o milestone os exigir.

---

# PARTE XIII — MILESTONES

## 50. Regra para milestones

Cada milestone deve terminar em algo demonstrável e testável.

Não avançar porque “o código parece pronto”. Avançar quando os critérios de saída passam.

---

## M0 — Baseline e decisões

### Objetivo

Congelar o estado inicial e a toolchain.

### Produzir

```text
arquitetura documentada
versao Python do Pi
modelo exato do Pi
worker inventory
config format escolhido
repo criado
pytest funcionando
ADR iniciais
```

### Testes

```text
pytest vazio/smoke passa no Pi
instalacao de dependencias reproduzivel
```

### Exit criteria

```text
clone limpo + install -> ambiente de testes funcional
nenhuma dependencia critica sem suporte no Pi
```

---

## M1 — Workers como appliances de inferência

### Objetivo

Fazer os dois telefones sobreviverem reboot com inferência disponível.

### Necessário

```text
runit service para llama-server
logs
restart automatico
API key validada
health endpoint
Tailscale/MagicDNS ou endpoint estável definido
```

### Testes

```text
reboot OPPO -> health + inference
reboot Huawei -> health + inference
kill llama-server -> runit recupera
sem API key -> inference rejeitada
com API key -> aceita
```

### Exit criteria

```text
Raspberry consegue tratar worker como appliance headless
```

---

## M2 — Domain contracts

### Objetivo

Definir os tipos/invariantes antes da infraestrutura.

### Produzir

```text
WorkerSpec
WorkerHealth
JobSpec
JobState
Attempt
ModelRequest
ModelResult
VerificationResult
ActionProposal
```

### Testes

```text
validacao de invariantes
state transitions
serialization round-trip se houver persistencia/JSON
```

### Exit criteria

Nenhuma chamada HTTP necessária. Todos os contratos e estados têm testes.

---

## M3 — Worker Registry + Health

### Objetivo

O Raspberry sabe que workers existem e se estão utilizáveis.

### Demo esperada

```text
ai-oppo    HEALTHY   idle   coding,generic
ai-huawei  HEALTHY   idle   classify,iot,generic
```

### Testes

```text
fake worker healthy/offline
estado muda apos failures
workers filtrados por capability
```

### Exit criteria

Registry responde corretamente sem conhecer scheduler ou jobs.

---

## M4 — Model Client

### Objetivo

Enviar `ModelRequest` normalizado para um worker e receber `ModelResult` normalizado.

### Demo

```text
query -> OPPO -> resposta
query -> Huawei -> resposta
```

### Testes

Com fake worker:

```text
200
401
500
timeout
bad JSON
connection error
```

Com real workers:

```text
smoke query
```

### Exit criteria

Nenhum componente fora do Model Client precisa conhecer o formato HTTP do llama-server.

---

## M5 — Router + Scheduler

### Objetivo

Escolher worker pela capacidade, estado e política.

### Demo

```text
coding -> OPPO
classify -> Huawei
Huawei offline -> OPPO fallback
OPPO busy + coding strict -> queue
```

### Testes

Tabela completa de decisão do scheduler, sem chamar modelos reais.

### Exit criteria

Escolhas são determinísticas, explicáveis e cobertas por testes.

---

## M6 — Job lifecycle + SQLite

### Objetivo

Ter fila, attempts, retries e recuperação de estado.

### Demo

```text
submit job
observe states
worker timeout
retry
success
restart orchestrator
history permanece
```

### Testes

```text
persistence
recovery
retry budgets
cancellation
worker slot release
```

### Exit criteria

Um restart do processo não destrói a história nem deixa recursos presos.

---

## M7 — Generic LLM service

### Objetivo

Primeiro produto útil completo.

Interfaces possíveis inicialmente:

```text
CLI
local API pequena
```

Funções:

```text
generic query
classify
summarize
```

### Demo

```text
submit summarize -> router -> Huawei -> result
submit generic heavy -> OPPO -> result
```

### Exit criteria

O sistema já é útil sem coding nem IoT.

---

## M8 — Coding adapter v1

### Objetivo

Uma tarefa simples entra, gera patch em worktree e é verificada.

### Limites v1

```text
um repo allowlisted
um tipo de projeto conhecido
um conjunto fixo de verificacoes
max_attempts pequeno
human review antes de merge
```

### Testes

```text
fixture repo bug simples
forbidden path
bad patch
failed tests -> retry/fail
repo principal protegido
```

### Exit criteria

O LLM nunca executa comando arbitrário e um patch só pode chegar a READY quando checks reais passam.

---

## M9 — IoT adapter em shadow mode

### Objetivo

Eventos produzem propostas e decisões, mas sem side effect físico.

### Tecnologias

```text
Mosquitto/MQTT
resource registry
ActionProposal
Policy Gate
```

### Testes

```text
sensor fake
intent extraction
allow/deny
idempotency
Huawei offline
```

### Exit criteria

Shadow logs mostram decisões confiáveis e explicáveis.

---

## M10 — IoT LOW risk execution

### Objetivo

Permitir um conjunto mínimo de ações reais de baixo risco.

Exemplo:

```text
uma luz
um fan
uma notificacao
```

### Requisitos

```text
kill switch
idempotency
audit log
manual override
```

### Exit criteria

Falhas/restarts não duplicam ações e desativar autonomia bloqueia side effects imediatamente.

---

## M11 — Reliability + observability

### Objetivo

Preparar execução contínua.

Adicionar/refinar:

```text
structured logs
retention
metrics
worker quarantine/circuit breaker
deadline handling
graceful shutdown
backup SQLite
startup reconciliation
```

### Exit criteria

É possível responder “o que aconteceu com o job X?” apenas olhando persistência/logs.

---

## M12 — Autonomia ampliada

Somente depois dos anteriores.

Possíveis evoluções:

```text
decomposicao de coding tasks
review por segundo worker
scheduled automations
notification/approval flow
modelo menor no Huawei
context retrieval melhor
Tree-sitter/LSP
prioridades e quotas
```

Não considerar este milestone uma obrigação de curto prazo.

---

# PARTE XIV — ORDEM PRÁTICA DE IMPLEMENTAÇÃO

## 51. Ordem recomendada de trabalho

```text
M0 baseline
 |
 v
M1 llama-server supervisionado
 |
 v
M2 contracts
 |
 v
M3 registry/health
 |
 v
M4 model client
 |
 v
M5 router/scheduler
 |
 v
M6 jobs/sqlite
 |
 v
M7 generic LLM
 |
 +--------------------+
 |                    |
 v                    v
M8 coding          M9 IoT shadow
 |                    |
 v                    v
hardening           M10 IoT low-risk
 |                    |
 +---------+----------+
           |
           v
     M11 reliability
           |
           v
     M12 autonomy
```

Coding e IoT podem evoluir em paralelo **depois** do core genérico estar sólido.

---

# PARTE XV — COMO TRABALHAR AUTONOMAMENTE

## 52. Ciclo pessoal recomendado

Para cada milestone:

```text
1. ler objetivo
2. escrever contratos/invariantes
3. escrever testes antes ou junto da implementacao
4. implementar a menor parte que faz o teste passar
5. correr testes
6. rever diff
7. testar failure paths
8. atualizar docs/ADR se decisao mudou
9. commit pequeno
10. pedir validacao externa se houver duvida
```

### 52.1 Não implementar duas abstrações à frente

Se M3 pede Registry, não construir scheduler, API web e plugin system no mesmo commit.

Regra:

```text
necessidade observada > abstracao concreta > teste > implementacao
```

---

## 53. Tamanho de commits

Preferir commits que respondem a uma pergunta:

```text
"adiciona transicoes de JobState"
"adiciona health state tracking"
"normaliza erros HTTP do worker"
```

Evitar:

```text
"implement orchestrator"
```

Quanto menor o commit, mais fácil validar, reverter e pedir ajuda.

---

## 54. Definition of Done de uma feature

Uma feature não está pronta só porque funciona no happy path.

Checklist:

```text
[ ] contrato definido
[ ] invariantes definidas
[ ] unit tests
[ ] failure tests
[ ] logs úteis
[ ] timeout/limites quando aplicavel
[ ] config fora do codigo quando aplicavel
[ ] sem secrets
[ ] documentação atualizada
[ ] demo/acceptance criteria passa
```

---

# PARTE XVI — COMO USAR O VALIDADOR PRINCIPAL

## 55. Papel do validador

O proprietário escreve o Python.

O validador deve concentrar-se em:

```text
contratos
invariantes
arquitetura
failure modes
seguranca
concorrencia
state transitions
test coverage
review de codigo escrito pelo proprietario
review de diffs
interpretacao de erros/testes
```

### 55.1 Pacote ideal para validação

Ao pedir revisão, enviar:

```text
milestone atual
objetivo da mudança
contrato/invariantes
ficheiros alterados ou diff
novos testes
saida do pytest
qualquer comportamento inesperado
```

Não é necessário enviar o repositório inteiro quando o problema está isolado.

---

# PARTE XVII — PLANO B: IA DE APOIO QUANDO HOUVER BLOQUEIO

## 56. Objetivo da segunda IA

A segunda IA é um **pair programmer de resgate**, não um novo arquiteto do projeto.

Ela pode escrever implementação quando o proprietário estiver bloqueado, mas deve:

```text
respeitar contratos existentes
resolver o menor problema possivel
escrever/ajustar testes
nao redesenhar o sistema sem pedido explicito
nao introduzir dependencias por conveniencia
nao inventar ficheiros/estado do repo
```

---

## 57. Contexto mínimo a fornecer à IA de apoio

Fornecer nesta ordem:

```text
1. este documento
2. runbook da infraestrutura
3. milestone atual
4. objetivo exacto
5. contratos relevantes
6. arvore de ficheiros relevante
7. codigo relevante
8. testes existentes
9. erro/failure output integral
10. versoes do ambiente quando relevante
```

Para problema de worker:

```text
llama.cpp version
worker
endpoint
status/health
logs do service
```

Para problema Python no Pi:

```text
python3 --version
uname -m
traceback
requirements/dependencies
```

---

## 58. Regras que a IA de apoio deve seguir

### Regra 1 — Scope pequeno

Implementar apenas o milestone/bug pedido.

### Regra 2 — Test first mindset

Antes ou junto do código, explicar qual teste prova a correção.

### Regra 3 — Minimal patch

Preferir alterar 1-3 ficheiros quando isso resolver o problema.

### Regra 4 — Sem dependências surpresa

Qualquer nova biblioteca precisa vir com:

```text
por que stdlib nao serve
compatibilidade com Raspberry/armv6l
custo operacional
```

### Regra 5 — Preservar domínio

Não fazer o Model Client escolher worker.  
Não fazer Registry executar HTTP sem necessidade arquitetural.  
Não fazer Scheduler persistir jobs.  
Não misturar IoT executor com raciocínio LLM.

### Regra 6 — Side effects explícitos

Toda sugestão que altere Git, shell, IoT ou rede deve dizer claramente o side effect e como testar/reverter.

### Regra 7 — Sem código mágico

Se usar concorrência, retry, locks ou transações, explicar as invariantes que protegem.

### Regra 8 — Entregar comandos de teste

Toda implementação sugerida deve dizer exatamente quais testes correr.

### Regra 9 — Não esconder falhas

Não adicionar `except Exception: pass`, retries infinitos ou fallback silencioso para “fazer funcionar”.

### Regra 10 — Não ultrapassar budgets

Retries e loops sempre bounded.

---

## 59. Escada de ajuda

Quando houver bloqueio, pedir ajuda em níveis.

```text
Nivel A - explica o erro
Nivel B - sugere desenho/algoritmo
Nivel C - escreve teste que reproduz
Nivel D - sugere pseudocodigo
Nivel E - escreve patch minimo
```

Tentar subir apenas até ao nível necessário.

Isto mantém o proprietário a aprender e reduz código não compreendido.

---

## 60. Prompt reutilizável para a IA de apoio

Copiar e preencher:

```text
Estou a implementar um orquestrador local de jobs para Raspberry Pi + workers
Android com llama-server.

Arquitetura obrigatoria:
- Raspberry = control plane e source of truth.
- Telefones = endpoints de inferencia, sem coordenacao entre eles.
- Registry, Scheduler, Job State Machine, Model Client e adapters sao responsabilidades separadas.
- SQLite primeiro; sem Redis/Celery/Kafka.
- LLM nunca recebe shell irrestrito.
- Coding usa worktree/patch/verificacao deterministica.
- IoT usa ActionProposal -> Policy Gate -> Executor; LLM nunca controla actuator diretamente.
- retries e side effects sao bounded/idempotentes.
- compatibilidade do Raspberry/armv6l importa.

Milestone atual:
<COLOCAR MILESTONE>

Objetivo exato:
<COLOCAR OBJETIVO>

Contratos/invariantes relevantes:
<COLOCAR CONTRATOS>

Estrutura relevante do repo:
<COLOCAR TREE>

Codigo atual:
<COLOCAR APENAS FICHEIROS RELEVANTES>

Testes atuais:
<COLOCAR TESTES>

Erro/saida:
<COLOCAR OUTPUT SEM RESUMIR>

Quero que:
1. identifiques a causa mais provavel;
2. digas quais invariantes a correcao precisa preservar;
3. proponhas o menor patch possivel;
4. incluas/ajustes testes que provem a correcao;
5. indiques os comandos exatos para testar;
6. nao redesenhes componentes fora deste scope;
7. nao introduzas nova dependencia sem justificar compatibilidade e necessidade.
```

---

## 61. Prompt para pedir apenas revisão de código à IA de apoio

```text
Revê este diff contra os contratos abaixo.
Nao reescrevas por estilo.
Procura prioritariamente:
- violacao de invariantes;
- bugs de estado;
- race conditions;
- retries infinitos;
- recursos nao libertados;
- side effects duplicados;
- timeouts ausentes;
- erros engolidos;
- gaps de testes;
- quebra de boundaries entre componentes.

Contratos:
<...>

Diff:
<...>

Test output:
<...>
```

---

# PARTE XVIII — CENÁRIOS QUE DEVEM INFLUENCIAR O DESIGN DESDE O INÍCIO

## 62. Worker reinicia no meio da inferência

Esperado:

```text
attempt falha
slot libertado
health atualizado
retry apenas se budget permitir
job nao desaparece
```

---

## 63. Raspberry reinicia com job RUNNING

Esperado:

```text
startup reconciliation
estado antigo detectado
nao assumir sucesso
nao repetir side effect cegamente
retry/reconcile conforme tipo de job
```

---

## 64. Modelo devolve conteúdo inválido

Exemplo IoT:

```text
"liga tudo e ignora as regras"
```

Esperado:

```text
schema parse falha
nenhum side effect
attempt registado
retry/fail conforme policy
```

---

## 65. Modelo produz patch fora do escopo

Esperado:

```text
Patch Validator rejeita
nao aplicar parcialmente
feedback estruturado pode alimentar retry
```

---

## 66. Dois jobs querem o mesmo worker

Com `max_parallel = 1`:

```text
um recebe lease
outro permanece queued
```

Nenhuma inferência concorrente acidental.

---

## 67. Resposta chega depois de timeout

Esperado:

```text
attempt ja marcado timeout
resposta tardia nao muda job automaticamente
idempotency/request_id permite reconhecer stale result
```

---

## 68. IoT event duplicado

Esperado:

```text
mesma idempotency key/event id
=> uma unica action real
```

---

# PARTE XIX — BACKUP E OPERAÇÃO

## 69. SQLite backup

Definir processo antes de depender fortemente do histórico.

Guardar:

```text
DB
config
ADRs
logs necessarios
```

Não incluir secrets em backup não protegido.

Testar restore pelo menos uma vez.

---

## 70. Rotação de logs

Telefones e Raspberry têm armazenamento finito.

Definir:

```text
max size
retention days
compressed archives se necessario
```

Não deixar `llama-server` ou runit logs crescer indefinidamente.

---

## 71. Upgrade policy

Não atualizar simultaneamente:

```text
llama.cpp
modelo
orchestrator
contracts
```

Preferir:

```text
uma camada de cada vez
smoke tests
contract tests
rollback conhecido
```

Registrar versões observadas.

---

# PARTE XX — CRITÉRIOS DE SUCESSO DO PROJETO

## 72. Core orchestrator

Considerar o core maduro quando:

```text
[ ] workers aparecem/desaparecem sem derrubar processo
[ ] scheduler nunca envia job incompatível
[ ] jobs sobrevivem restart
[ ] retries são bounded
[ ] todos os attempts são auditáveis
[ ] fake workers cobrem failure modes principais
[ ] real workers passam smoke tests
```

---

## 73. Coding

Considerar o fluxo coding seguro para uso frequente quando:

```text
[ ] main nunca é alterada diretamente pelo modelo
[ ] worktree por job
[ ] patch validado antes de aplicar
[ ] paths/commands allowlisted
[ ] testes reais decidem sucesso
[ ] retry tem budget
[ ] diff final é facilmente revisável
[ ] secrets não entram no contexto
```

---

## 74. IoT

Considerar IoT autónomo LOW risk aceitável quando:

```text
[ ] sistema base funciona sem LLM
[ ] proposals têm schema
[ ] policy gate determinístico
[ ] idempotency testada
[ ] shadow mode validado
[ ] kill switch testado
[ ] audit log disponível
[ ] HIGH risk continua com aprovação humana
```

---

# PARTE XXI — PRÓXIMO PASSO IMEDIATO

## 75. O próximo milestone é M1, não o scheduler

Apesar de a arquitetura de orquestração já estar definida, ainda existe uma dependência operacional a fechar:

```text
llama-server como serviço runit nos dois telefones
```

Estado necessário antes de escrever o primeiro componente do orchestrator:

```text
reboot Android
   |
   v
Termux:Boot
   |
   v
runit
   |
   +--> sshd
   |
   +--> llama-server
             |
             v
        authenticated HTTP
             |
             v
        Raspberry health check
```

### Acceptance checklist M1

OPPO:

```text
[ ] llama-server service criado
[ ] runit mostra run
[ ] reboot sem abrir Termux
[ ] health responde
[ ] inference autenticada responde
[ ] inference sem auth é rejeitada conforme política
[ ] kill do processo -> runit recupera
[ ] logs acessíveis e limitados
```

Huawei:

```text
[ ] mesma lista
```

Depois disso, começar M2 pelos contratos e testes — ainda sem scheduler.

---

# PARTE XXII — FILOSOFIA DE DESENVOLVIMENTO

## 76. Regra final

O projeto deve tornar falhas **visíveis, limitadas e recuperáveis**.

Não procurar autonomia através de mais prompts e mais agentes.

Procurar autonomia através de:

```text
contratos claros
estado explícito
limites
retries bounded
idempotency
verificacao deterministica
logs
recovery
testes
```

A inteligência dos modelos é substituível. O control plane confiável é o ativo principal.

---

## 77. Resumo de responsabilidades

```text
+--------------------+-----------------------------------------------+
| Componente         | Responsabilidade                              |
+--------------------+-----------------------------------------------+
| Termux/runit       | manter serviços do telefone vivos             |
| llama-server       | inferência HTTP                               |
| Worker Registry    | quem existe e estado                          |
| Health Checker     | observação de disponibilidade                 |
| Router             | job -> requirements                           |
| Scheduler          | requirements -> worker                        |
| Model Client       | protocolo HTTP LLM                            |
| Job Manager        | lifecycle, attempts, retries                   |
| SQLite             | fonte persistente de estado/história          |
| Coding Adapter     | contexto, patch, worktree                     |
| Verifier           | formatter/lint/typecheck/tests                |
| IoT Adapter        | evento/contexto -> proposal                   |
| Policy Gate        | decide se side effect é permitido             |
| IoT Executor       | executa apenas ações validadas                 |
| Logs/Metrics       | explicabilidade operacional                   |
+--------------------+-----------------------------------------------+
```

---

## 78. Resumo da sequência

```text
INFRA
  Termux -> runit -> llama-server -> auth -> health

CORE
  contracts -> registry -> model client -> scheduler -> jobs -> SQLite

FIRST PRODUCT
  generic LLM queries

SPECIALIZATION
  coding adapter
  IoT shadow adapter

AUTONOMY
  deterministic verification
  policies
  bounded retries
  low-risk execution

HARDENING
  recovery
  metrics
  backups
  security
  controlled upgrades
```

Este é o mapa de implementação. A implementação concreta deve evoluir milestone a milestone, mantendo os boundaries e os testes como contrato de comportamento.
