#!/usr/bin/env python3
"""Check publishable files, Python syntax and common credential formats offline."""
from __future__ import annotations
import ast
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r'\b(?:sk-(?:or-v1-)?[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,}|hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,})\b')
BANNED_SUFFIXES = {'.safetensors', '.wav', '.mp3', '.zip', '.whl', '.pyc', '.pem', '.key'}
PRIVATE_KEY_MARKER = '-----BEGIN ' + 'PRIVATE KEY-----'


def main() -> None:
    result = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
                            cwd=ROOT, check=True, stdout=subprocess.PIPE)
    names = sorted(set(result.stdout.decode('utf-8').split('\0')) - {''})
    failures = []
    for name in names:
        p = ROOT / name
        if not p.is_file():
            failures.append(f'{name}: missing file')
            continue
        if (p.suffix.lower() in BANNED_SUFFIXES or 'cookies' in p.name.lower()
                or name.startswith(('Month1/', 'Month2/', 'Month3/', '.repo_work/'))
                or name in ('.env', 'configs/local.env')):
            failures.append(f'{name}: private/generated artifact in publishable files')
        if p.stat().st_size > 5 * 1024 * 1024:
            failures.append(f'{name}: larger than 5 MiB')
            continue
        try:
            text = p.read_text(encoding='utf-8-sig')
        except UnicodeError:
            failures.append(f'{name}: unexpected binary file')
            continue
        if TOKEN.search(text) or PRIVATE_KEY_MARKER in text:
            failures.append(f'{name}: potential credential (value hidden)')
        if p.suffix == '.py':
            try:
                ast.parse(text, filename=name)
            except SyntaxError as exc:
                failures.append(f'{name}:{exc.lineno}: {exc.msg}')
    if failures:
        print('\n'.join(failures), file=sys.stderr)
        raise SystemExit(1)
    print(f'PASS: {len(names)} publishable text files; syntax, size and credential checks passed.')


if __name__ == '__main__':
    main()
