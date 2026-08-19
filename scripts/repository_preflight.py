#!/usr/bin/env python3
"""Fail-closed repository hygiene checks for V&VN Data Services."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {'.git', '.venv', 'venv', '__pycache__', '.pytest_cache'}
FORBIDDEN_SUFFIXES = {'.pem', '.key', '.pfx', '.p12', '.sqlite', '.sqlite3', '.pdf', '.docx', '.xlsx', '.xls'}
FORBIDDEN_EXACT = {'.env'}
MAX_FILE_BYTES = 5 * 1024 * 1024
SECRET_PATTERNS = {
    'private_key': re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----'),
    'github_token': re.compile(r'(?:github_pat_|ghp_)[A-Za-z0-9_]{20,}'),
    'openai_key': re.compile(r'sk-[A-Za-z0-9_-]{20,}'),
    'azure_storage_key': re.compile(r'AccountKey=(?!<)[^\s;]{20,}'),
}


def files() -> list[Path]:
    out: list[Path] = []
    for path in ROOT.rglob('*'):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if rel.parts[:2] == ('output', 'runtime'):
            continue
        out.append(path)
    return out


def main() -> int:
    errors: list[str] = []
    for path in files():
        rel = path.relative_to(ROOT)
        if path.name in FORBIDDEN_EXACT or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f'forbidden file type/path in repository: {rel}')
        if path.stat().st_size > MAX_FILE_BYTES:
            errors.append(f'file exceeds 5 MiB repository limit: {rel}')
        if path.stat().st_size <= 1024 * 1024:
            try:
                text = path.read_text(encoding='utf-8')
            except (UnicodeDecodeError, OSError):
                text = ''
            for label, pattern in SECRET_PATTERNS.items():
                if pattern.search(text):
                    errors.append(f'possible {label} secret detected in: {rel}')

    tenant_path = ROOT / 'config' / 'tenants.v1.json'
    if tenant_path.exists():
        data = json.loads(tenant_path.read_text(encoding='utf-8'))
        if data.get('tenants'):
            errors.append('config/tenants.v1.json must contain an empty tenants list')

    if errors:
        print(json.dumps({'status': 'BLOCKED', 'errors': errors}, indent=2))
        return 2
    print(json.dumps({'status': 'PASS', 'checked_files': len(files())}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
