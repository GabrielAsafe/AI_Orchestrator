# AI Orchestrator Kanban

Kanban local e sem backend para acompanhar a implementação do sistema de IA distribuída.

## Ficheiros

```text
index.html
styles.css
app.js
tasks.json
serve.sh
README.md
```

`tasks.json` é a fonte inicial. Depois do primeiro carregamento, o estado é persistido no `localStorage` do browser.

## Colunas

```text
Backlog
Ready
Developing
Testing
Blocked
Done
```

É possível mover cartões por drag-and-drop, pelas setas no cartão ou alterando o status nos detalhes.

## Executar

No Raspberry/PC:

```sh
cd ai_orchestrator_kanban
./serve.sh
```

Abrir:

```text
http://127.0.0.1:8787
```

Porta alternativa:

```sh
PORT=9000 ./serve.sh
```

Por omissão o servidor só escuta em `127.0.0.1`.

Se executar no Raspberry e quiser abrir no browser de outro computador, a opção mais segura é criar um túnel SSH:

```sh
ssh -L 8787:127.0.0.1:8787 gabi@<raspberry>
```

e abrir `http://127.0.0.1:8787` no computador local.

Também é possível expor temporariamente na LAN:

```sh
BIND=0.0.0.0 ./serve.sh
```

mas isso torna o board acessível a outros hosts que consigam chegar à porta.

## Persistência e troca de dados

- **Exportar JSON**: descarrega o estado atual.
- **Importar JSON**: substitui o estado local pelo JSON escolhido.
- **Recarregar tasks.json**: apaga o estado do browser e volta ao ficheiro original.
- **Promover elegíveis**: move de `Backlog` para `Ready` tarefas cujas dependências já estão `Done`.

Quando quiseres revisão/validação, exporta o JSON e envia-o de volta. O ID da task é suficiente para localizar o contexto, mas o JSON preserva também notas e estados.

## Estrutura de cada task

Campos principais:

```json
{
  "id": "M4-005",
  "milestone": "M4",
  "area": "model-client",
  "kind": "testing",
  "title": "...",
  "description": "...",
  "status": "backlog",
  "priority": "critical",
  "depends_on": ["..."],
  "acceptance_criteria": ["..."],
  "test_plan": ["..."],
  "deliverables": [],
  "tags": [],
  "notes": ""
}
```

As dependências são informativas no board. O programa mostra quais ainda não estão `Done`; não impede manualmente uma movimentação, porque pode haver motivos legítimos para trabalhar em paralelo.
