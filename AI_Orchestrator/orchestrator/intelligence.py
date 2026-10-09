"""Project Intelligence mínimo: ficheiros, imports AST e histórico Git."""
import ast, subprocess, json
from pathlib import Path

def analyze_project(root, max_files=500):
    root = Path(root).resolve(strict=True)
    files, graph = [], {}
    ignored = {'.git','.venv','venv','__pycache__','node_modules'}
    for path in sorted(root.rglob('*.py')):
        if any(part in ignored for part in path.relative_to(root).parts):
            continue
        if len(files) >= max_files:
            break
        relative = str(path.relative_to(root))
        if path.is_symlink() or path.stat().st_size > 256000:
            continue
        files.append(relative)
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
            imports = sorted({alias.name.split('.')[0]
                              for node in ast.walk(tree) if isinstance(node,ast.Import)
                              for alias in node.names} |
                             {node.module.split('.')[0] for node in ast.walk(tree)
                              if isinstance(node,ast.ImportFrom) and node.module})
            graph[relative] = imports
        except (SyntaxError, UnicodeError):
            graph[relative] = ['<parse_error>']
    try:
        git = subprocess.run(['git','-C',str(root),'log','-5','--pretty=format:%h %s'],
                             text=True,capture_output=True,timeout=10,check=False)
        commits = git.stdout.splitlines() if git.returncode == 0 else []
    except (OSError,subprocess.TimeoutExpired):
        commits=[]
    return {'schema_version':1,'files':files,'imports':graph,'recent_commits':commits}

def markdown_report(analysis):
    lines = ['# Project Intelligence — relatório local','',
             'Ficheiros Python analisados: %d' % len(analysis['files']),'',
             '## Imports por ficheiro','']
    for filename,imports in analysis['imports'].items():
        lines.append('- `%s`: %s' % (filename,', '.join(imports) or '(nenhum)'))
    lines.extend(['','## Histórico Git','','\n'.join('- '+c for c in analysis['recent_commits']) or '(sem commits disponíveis)'])
    return '\n'.join(lines)+'\n'
