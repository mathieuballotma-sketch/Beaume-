"""Contrôle des fichiers suivis avant publication ; pas un audit de secrets complet."""
from pathlib import Path
import re
import subprocess


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
    errors = []
    for name in filter(None, paths):
        p = Path(name)
        upper = name.upper()
        if (p.name == 'AGENTS.md' or p.name.startswith('.env')
                or name.startswith(('docs/equipe/', 'organisation/', 'runs/'))
                or p.suffix.lower() in {'.rtf', '.sqlite', '.gguf', '.log'}
                or '.bak' in p.name or any(t in upper for t in ('PASSATION', 'REPRISE', 'PROMPT_BEAUME'))):
            errors.append(name)
        if p.suffix.lower() in {'.md', '.py', '.toml', '.yaml', '.yml', '.json'}:
            text = (root / p).read_text(encoding='utf-8')
            if re.search(re.escape('/' + 'Users' + '/') + r'[^/\s]+/', text):
                errors.append(name + ': chemin personnel')
    if errors:
        print('Publication refusée :\n' + '\n'.join(sorted(set(errors))))
        return 1
    print('Fichiers suivis : aucun document interne ou chemin personnel détecté par ces règles.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
