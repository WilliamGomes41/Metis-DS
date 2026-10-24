"""A successful unrelated run or modified ZIP must never authorize deployment.

# release-control-evidence: scope/belofte slop releasebewijs
"""
import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from scripts.verified_deploy_artifact import validate_run, verify_package

SHA = 'a'*40
REPO = 'WilliamGomes41/Metis-DS'


def run():
    return dict(id=123, run_attempt=2, status='completed', conclusion='success',
                event='push', head_branch='main', head_sha=SHA,
                path='.github/workflows/ci.yml', repository={'full_name': REPO},
                head_repository={'full_name': REPO})


def package(tmp_path):
    archive = tmp_path / 'metis-console.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('config/deployed_commit.txt', SHA+'\n')
    manifest = dict(schema=1, commit=SHA, repository=REPO, run_id=123, run_attempt=2,
                    sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), package_import_smoke='passed')
    (tmp_path/'manifest.json').write_text(json.dumps(manifest))
    return archive


def test_accepts_exact_successful_main_run_and_package(tmp_path):
    assert validate_run(run(), commit=SHA, repository=REPO, run_id=123) == 2
    archive = package(tmp_path)
    assert verify_package(tmp_path, commit=SHA, repository=REPO, run_id=123, attempt=2) == archive


@pytest.mark.parametrize('field,value', [('conclusion','failure'), ('status','in_progress'),
    ('event','pull_request'), ('head_branch','feature'), ('head_sha','b'*40),
    ('path','.github/workflows/unrelated.yml'), ('id',456), ('run_attempt',0),
    ('repository',{'full_name':'other/repo'}), ('head_repository',{'full_name':'fork/repo'})])
def test_refuses_wrong_or_unfinished_run(field, value):
    data = run()
    data[field] = value
    with pytest.raises(ValueError):
        validate_run(data, commit=SHA, repository=REPO, run_id=123)


@pytest.mark.parametrize('corruption', ['zip', 'commit', 'attempt', 'run', 'repository', 'smoke', 'marker'])
def test_refuses_tampered_or_unrelated_artifact(tmp_path, corruption):
    archive = package(tmp_path)
    manifest_path = tmp_path/'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if corruption == 'zip': archive.write_bytes(archive.read_bytes()+b'changed')
    if corruption == 'commit': manifest['commit'] = 'b'*40
    if corruption == 'attempt': manifest['run_attempt'] = 1
    if corruption == 'run': manifest['run_id'] = 456
    if corruption == 'repository': manifest['repository'] = 'other/repo'
    if corruption == 'smoke': manifest['package_import_smoke'] = 'skipped'
    if corruption == 'marker':
        with zipfile.ZipFile(archive, 'w') as z: z.writestr('config/deployed_commit.txt', 'b'*40)
        manifest['sha256'] = hashlib.sha256(archive.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        verify_package(tmp_path, commit=SHA, repository=REPO, run_id=123, attempt=2)
