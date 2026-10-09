# ADR complementar — Patch Contract v1

**Escolha inicial:** JSON de lista de ficheiros inteiros (`edits`) em vez de unified diff. Facilita validação de schema e path num Pi antigo; a legibilidade humana vem de `difflib.unified_diff` no preview. Desvantagem: ficheiros completos consomem mais tokens; para grandes alterações estudar unified diff estruturado.

```json
{"schema_version":1,"edits":[{"path":"src/exemplo.py","content":"print('hello')\n"}]}
```

- Máximo configurado no parser: 5 ficheiros, 250 linhas de conteúdo.
- Sem paths absolutos, `..`, symlinks ou ficheiros ocultos sensíveis.
- Apenas worktree `lesson/*` e `--approve` para aplicar; o modelo **nunca** pode executar o comando.
- `allowed_command_id`: `unit_tests`, `syntax_check`. Execução via argv literal, sem shell.
- O parser não garante correção semântica do código; é indispensável pipeline de testes e revisão humana.
