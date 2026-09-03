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

INFRA_MANIFEST = ROOT / 'config' / 'infrastructure_manifest.v1.json'
STACK_BASELINE = ROOT / 'docs' / 'STACK_SETUP_BASELINE.md'
INFRA_REQUIRED_FIELDS = {
    'capability_id',
    'capability',
    'environment',
    'requirement_status',
    'implementation_status',
    'current_implementation',
    'target_implementation',
    'provider',
    'data_classification',
    'region',
    'persistence',
    'identity_secret_boundary',
    'cost_model',
    'expected_cost_range',
    'budget_owner',
    'operational_owner',
    'decision_deadline_gate',
    'evidence',
}
VALID_REQUIREMENT_STATUSES = {'required', 'optional', 'future', 'not_applicable'}
VALID_IMPLEMENTATION_STATUSES = {
    'implemented',
    'selected_not_provisioned',
    'decision_open',
    'blocked',
    'not_needed',
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


def validate_infrastructure_manifest(errors: list[str]) -> None:
    if not STACK_BASELINE.exists():
        errors.append('docs/STACK_SETUP_BASELINE.md is required')
    if not INFRA_MANIFEST.exists():
        errors.append('config/infrastructure_manifest.v1.json is required')
        return

    try:
        manifest = json.loads(INFRA_MANIFEST.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError) as exc:
        errors.append(f'infrastructure manifest is not valid readable JSON: {exc}')
        return

    environments = manifest.get('environments')
    dependencies = manifest.get('dependencies')
    if not isinstance(environments, list) or not environments:
        errors.append('infrastructure manifest must declare at least one environment')
        environments = []
    if not isinstance(dependencies, list) or not dependencies:
        errors.append('infrastructure manifest must declare at least one dependency')
        return

    known_environments = {str(x) for x in environments}
    seen_ids: set[str] = set()
    for idx, item in enumerate(dependencies):
        prefix = f'infrastructure dependency[{idx}]'
        if not isinstance(item, dict):
            errors.append(f'{prefix} must be an object')
            continue

        missing = sorted(INFRA_REQUIRED_FIELDS - item.keys())
        if missing:
            errors.append(f'{prefix} missing fields: {", ".join(missing)}')
            continue

        capability_id = str(item.get('capability_id') or '').strip()
        if not capability_id:
            errors.append(f'{prefix} capability_id must not be empty')
        elif capability_id in seen_ids:
            errors.append(f'duplicate infrastructure capability_id: {capability_id}')
        else:
            seen_ids.add(capability_id)

        environment = str(item.get('environment') or '')
        if environment not in known_environments:
            errors.append(f'{prefix} references undeclared environment: {environment}')

        requirement_status = str(item.get('requirement_status') or '')
        if requirement_status not in VALID_REQUIREMENT_STATUSES:
            errors.append(f'{prefix} invalid requirement_status: {requirement_status}')

        implementation_status = str(item.get('implementation_status') or '')
        if implementation_status not in VALID_IMPLEMENTATION_STATUSES:
            errors.append(f'{prefix} invalid implementation_status: {implementation_status}')

        if requirement_status == 'required' and implementation_status == 'not_needed':
            errors.append(f'{prefix} required capability cannot be marked not_needed')

        for field in ('capability', 'current_implementation', 'target_implementation', 'provider',
                      'data_classification', 'identity_secret_boundary', 'cost_model',
                      'expected_cost_range', 'decision_deadline_gate'):
            if not str(item.get(field) or '').strip():
                errors.append(f'{prefix} {field} must not be empty')

        evidence = item.get('evidence')
        if not isinstance(evidence, list) or not evidence or not all(str(x).strip() for x in evidence):
            errors.append(f'{prefix} evidence must contain at least one non-empty reference')


G2_RUNTIME_PINS = (
    'azure-identity==1.25.3',
    'azure-storage-blob==12.30.1',
)


def _requirement_files_declare_pin(paths: list[Path], pin: str) -> bool:
    seen: set[Path] = set()
    queue = list(paths)
    include_re = re.compile(r'^(?:-r|--requirement)\s+(\S+)')
    while queue:
        path = queue.pop()
        resolved = path.resolve()
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        text = resolved.read_text(encoding='utf-8')
        if pin in text:
            return True
        for raw in text.splitlines():
            line = raw.split('#', 1)[0].strip()
            match = include_re.match(line)
            if match:
                queue.append(resolved.parent / match.group(1))
    return False


def validate_g2_runtime_pins(errors: list[str]) -> None:
    pyproject = (ROOT / 'pyproject.toml').read_text(encoding='utf-8')
    lock = ROOT / 'requirements.lock'
    requirements = ROOT / 'requirements.txt'
    console = ROOT / 'requirements-console.txt'
    retrieval = ROOT / 'requirements-retrieval.txt'
    dev_lock = (ROOT / 'requirements-dev.lock').read_text(encoding='utf-8')
    for pin in G2_RUNTIME_PINS:
        if pin not in pyproject:
            errors.append(f'pyproject.toml missing required G2 runtime pin: {pin}')
        if not _requirement_files_declare_pin([lock], pin):
            errors.append(f'requirements.lock missing required G2 runtime pin: {pin}')
        if not _requirement_files_declare_pin([requirements], pin):
            errors.append(f'requirements.txt missing required G2 runtime pin: {pin}')
        if pin not in console.read_text(encoding='utf-8'):
            errors.append(f'requirements-console.txt missing required G2 runtime pin: {pin}')
    if '-r requirements.lock' not in dev_lock:
        errors.append('requirements-dev.lock must include -r requirements.lock so G2 SDK pins stay in sync')
    if '-r requirements-retrieval.txt' not in dev_lock:
        errors.append('requirements-dev.lock must include -r requirements-retrieval.txt so CI can test retrieval extras')
    if not console.is_file():
        errors.append('requirements-console.txt is required for the thin console pack')
    if not retrieval.is_file():
        errors.append('requirements-retrieval.txt is required for the Product API / retrieval extra')
    forbidden = ('numpy', 'sklearn', 'scipy', 'scikit-learn')
    console_text = console.read_text(encoding='utf-8').lower() if console.is_file() else ''
    for name in forbidden:
        if re.search(rf'(?m)^{re.escape(name)}\b', console_text):
            errors.append(f'requirements-console.txt MUST NOT declare {name}')
    retrieval_text = retrieval.read_text(encoding='utf-8').lower() if retrieval.is_file() else ''
    for name in ('scikit-learn', 'numpy', 'scipy'):
        if not re.search(rf'(?m)^{re.escape(name)}\b', retrieval_text):
            errors.append(f'requirements-retrieval.txt must keep the heavier extra pin: {name}')


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

    validate_infrastructure_manifest(errors)
    validate_g2_runtime_pins(errors)

    if errors:
        print(json.dumps({'status': 'BLOCKED', 'errors': errors}, indent=2))
        return 2
    print(json.dumps({'status': 'PASS', 'checked_files': len(files())}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
