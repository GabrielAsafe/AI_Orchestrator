"""Coding humano-supervisionado: JSON edits, worktree e checks allowlisted.

Nunca executar comandos sugeridos pelo modelo e nunca modificar branches principais.
"""
import json, subprocess, difflib, re, os
from pathlib import Path
from .models import VerificationResult

DENIED = {'.env','.git','id_rsa','id_ed25519','credentials.json','secrets.json','authorized_keys'}
ALLOWED_COMMANDS = {
    'unit_tests': ['python3','-m','pytest','-q'],
    'syntax_check': ['python3','-m','compileall','-q','.'],
}

def repo_allowed(repo, allowlist):
    path = Path(repo).resolve(strict=True)
    paths = [Path(p).resolve(strict=True) for p in allowlist]
    return any(path == item for item in paths)

def safe_path(root, relative):
    if not isinstance(relative,str) or not relative or relative.startswith(('/', '\\')):
        raise ValueError('Caminho absoluto/vazio proibido')
    if '\\' in relative or '\x00' in relative or any(p in ('..','') for p in Path(relative).parts):
        raise ValueError('Traversal/segmento inválido')
    parts = Path(relative).parts
    if any(x in DENIED or x.startswith('.') or x.endswith(('.pem','.key')) for x in parts):
        raise ValueError('Ficheiro sensível proibido')
    root = Path(root).resolve(strict=True)
    candidate = root.joinpath(*parts).resolve(strict=False)
    if candidate != root and root not in candidate.parents:
        raise ValueError('Fora do repositório')
    # Rejeitar symlinks em qualquer segmento existente.
    cursor = root
    for segment in parts:
        cursor = cursor / segment
        if cursor.is_symlink():
            raise ValueError('Symlinks proibidos')
    return candidate

def parse_patch(text, max_files=5, max_lines=250):
    """Contract: {"schema_version":1,"edits":[{"path":"...","content":"..."}]}.
    Cada edit contém o ficheiro completo, e a revisão humana vê um unified diff.
    """
    data = json.loads(text)
    if not isinstance(data,dict) or data.get('schema_version') != 1:
        raise ValueError('Patch schema_version inválida')
    edits = data.get('edits')
    if not isinstance(edits,list) or not 1 <= len(edits) <= max_files:
        raise ValueError('Número de ficheiros inválido')
    seen, lines = set(), 0
    for edit in edits:
        if not isinstance(edit,dict) or set(edit) != {'path','content'}:
            raise ValueError('Edit inválido')
        if not isinstance(edit['path'],str) or not isinstance(edit['content'],str):
            raise ValueError('path/content devem ser strings')
        if edit['path'] in seen:
            raise ValueError('Ficheiro duplicado')
        seen.add(edit['path'])
        lines += len(edit['content'].splitlines())
    if lines > max_lines:
        raise ValueError('Budget de linhas ultrapassado')
    return edits

def preview_edits(root, edits):
    diffs = []
    for edit in edits:
        target = safe_path(root,edit['path'])
        before = target.read_text(encoding='utf-8') if target.exists() else ''
        after = edit['content']
        diffs.extend(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                                          fromfile='a/'+edit['path'],tofile='b/'+edit['path']))
    return ''.join(diffs)

def apply_edits(root, edits, approved=False):
    if not approved:
        raise PermissionError('Revisão humana obrigatória (--approve)')
    targets = [(safe_path(root,e['path']),e['content']) for e in edits]
    for target,content in targets:
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(content,encoding='utf-8')
    return len(targets)

def run_check(root, command_id, timeout=30):
    if command_id not in ALLOWED_COMMANDS:
        raise ValueError('Verificação não permitida: ' + command_id)
    if not 1 <= timeout <= 120:
        raise ValueError('Timeout fora do limite')
    # Apenas argv fixo controlado pelo proprietário. shell=False.
    import time
    start = time.monotonic()
    try:
        result = subprocess.run(ALLOWED_COMMANDS[command_id],cwd=str(root),capture_output=True,
                                text=True,timeout=timeout,check=False)
        return {'name':command_id,'command_id':command_id,'exit_code':result.returncode,
                'passed':result.returncode==0,'duration':round(time.monotonic()-start,2),
                'stdout':result.stdout[-1500:],'stderr':result.stderr[-1500:]}
    except subprocess.TimeoutExpired:
        return {'name':command_id,'command_id':command_id,'exit_code':-1,'passed':False,
                'duration':round(time.monotonic()-start,2),'stdout':'','stderr':'timeout'}

def verify(root, checks=('syntax_check',)):
    entries = [run_check(root,key) for key in checks]
    return VerificationResult(passed=all(e['passed'] for e in entries), checks=entries)

def create_worktree(repo, output_path, branch):
    if not re.fullmatch(r'lesson/[a-zA-Z0-9_-]{1,48}',branch):
        raise ValueError('Branch deve ter formato lesson/nome')
    path=Path(output_path).resolve()
    if path.exists():
        raise FileExistsError(str(path))
    subprocess.run(['git','-C',str(Path(repo).resolve()),'worktree','add','-b',branch,str(path)],check=True,
                   timeout=30,capture_output=True)
    return str(path)
