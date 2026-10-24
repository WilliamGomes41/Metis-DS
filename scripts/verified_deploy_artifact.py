#!/usr/bin/env python3
"""Bind a deploy ZIP to successful main CI, an exact commit and a SHA-256."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.request
import zipfile


def validate_identity(commit, repository, run_id, attempt):
    if (not re.fullmatch(r'[0-9a-f]{40}', commit)
            or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository)
            or type(run_id) is not int or run_id < 1
            or type(attempt) is not int or attempt < 1):
        raise ValueError('invalid commit, repository or CI run identity')


def artifact_name(commit, attempt):
    return f'metis-console-{commit}-attempt-{attempt}'


def validate_run(run, *, commit, repository, run_id):
    attempt = run.get('run_attempt')
    validate_identity(commit, repository, run_id, attempt)
    expected = dict(id=run_id, status='completed', conclusion='success', event='push',
                    head_branch='main', head_sha=commit, path='.github/workflows/ci.yml')
    if (any(run.get(key) != value for key, value in expected.items())
            or run.get('repository', {}).get('full_name') != repository
            or run.get('head_repository', {}).get('full_name') != repository):
        raise ValueError('deployment requires successful ci.yml main-push for the exact commit/repository')
    return attempt


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def marker(archive):
    with zipfile.ZipFile(archive) as package:
        if package.namelist().count('config/deployed_commit.txt') != 1:
            raise ValueError('missing or ambiguous packaged commit')
        return package.read('config/deployed_commit.txt').decode().strip()


def verify_package(directory, *, commit, repository, run_id, attempt):
    validate_identity(commit, repository, run_id, attempt)
    directory = Path(directory)
    manifest = json.loads((directory/'manifest.json').read_text())
    archive = directory/'metis-console.zip'
    expected = dict(schema=1, commit=commit, repository=repository, run_id=run_id,
                    run_attempt=attempt, package_import_smoke='passed')
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise ValueError('package identity or import smoke does not match verified CI')
    if manifest.get('sha256') != sha256(archive) or marker(archive) != commit:
        raise ValueError('package hash or embedded commit mismatch')
    return archive


def seal_package(directory, *, commit, repository, run_id, attempt):
    validate_identity(commit, repository, run_id, attempt)
    if sys.version_info[:2] != (3, 12):
        raise ValueError('Azure package smoke requires Python 3.12')
    directory = Path(directory)
    archive = directory/'metis-console.zip'
    if marker(archive) != commit:
        raise ValueError('package commit mismatch')
    with tempfile.TemporaryDirectory(prefix='metis-package-smoke-') as raw:
        extracted = Path(raw)
        with zipfile.ZipFile(archive) as package:
            for entry in package.infolist():
                path = Path(entry.filename)
                if path.is_absolute() or '..' in path.parts:
                    raise ValueError('unsafe package path')
            package.extractall(extracted)
        # -I -S excludes checkout, user paths and system site-packages. Imported
        # native wheels and the entrypoint must work using only the shipped tree.
        program = '''import importlib, pathlib, sys
root = pathlib.Path(sys.argv[1]).resolve()
sys.path[:0] = [str(root / '.python_packages'), str(root)]
for name in ('fastapi', 'uvicorn', 'psycopg', 'cryptography.hazmat.bindings._rust',
             'pydantic_core', 'pymupdf', 'azure.identity', 'azure.storage.blob',
             'azure.monitor.opentelemetry.exporter', 'src.console_asgi'):
    module = importlib.import_module(name)
    assert pathlib.Path(module.__file__).resolve().is_relative_to(root), name
print('packaged application and native dependency imports passed')
'''
        subprocess.run([sys.executable, '-I', '-S', '-c', program, str(extracted)],
                       cwd=extracted, check=True, timeout=120)
    manifest = dict(schema=1, commit=commit, repository=repository, run_id=run_id,
                    run_attempt=attempt, sha256=sha256(archive), package_import_smoke='passed')
    (directory/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    verify_package(directory, commit=commit, repository=repository, run_id=run_id, attempt=attempt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['run', 'seal', 'verify'])
    parser.add_argument('--commit', required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--run-id', type=int, required=True)
    parser.add_argument('--attempt', type=int)
    parser.add_argument('--directory', type=Path)
    args = parser.parse_args()
    identity = dict(commit=args.commit, repository=args.repository, run_id=args.run_id)
    if args.command == 'run':
        validate_identity(**identity, attempt=1)
        request = urllib.request.Request(
            f'https://api.github.com/repos/{args.repository}/actions/runs/{args.run_id}',
            headers={'Authorization': 'Bearer '+os.environ['GH_TOKEN'],
                     'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'})
        with urllib.request.urlopen(request, timeout=30) as response:
            run = json.load(response)
        attempt = validate_run(run, **identity)
        outputs = f'attempt={attempt}\nartifact_name={artifact_name(args.commit, attempt)}\n'
        with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
            stream.write(outputs)
        print(f'verified main CI run {args.run_id}, attempt {attempt}, commit {args.commit}')
    elif args.command == 'seal':
        seal_package(args.directory, **identity, attempt=args.attempt)
    else:
        verify_package(args.directory, **identity, attempt=args.attempt)
        print('package identity, SHA-256 and embedded commit verified')


if __name__ == '__main__':
    main()
