"""Offline provenance checks for the explicitly installed design skill.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]


def test_installed_skill_matches_reviewed_upstream_bytes_and_retained_license():
    manifest = json.loads((ROOT/'config/emil_design_eng.v1.json').read_text())
    assert manifest['repository'] == 'https://github.com/emilkowalski/skills'
    assert re.fullmatch(r'[a-f0-9]{40}', manifest['commit'])
    for relative, expected in manifest['files'].items():
        path = ROOT/relative
        assert path.is_file() and not path.is_symlink()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, relative
    skill = ROOT/manifest['distribution']/'SKILL.md'
    data = skill.read_bytes()
    blob = b'blob '+str(len(data)).encode()+b'\0'+data
    assert hashlib.sha1(blob).hexdigest() == manifest['git_blob_sha']
    assert {p.name for p in skill.parent.iterdir()} == {'SKILL.md'}
    assert skill.read_text().startswith('---\nname: emil-design-eng\n')
    license_text = (ROOT/'.agents/licenses/emil-design-eng.txt').read_text()
    assert license_text.startswith('MIT License\n')
    assert 'Copyright (c) 2026 Emil Kowalski' in license_text


def test_installer_lock_keeps_the_same_project_skill_source():
    manifest = json.loads((ROOT/'config/emil_design_eng.v1.json').read_text())
    lock = json.loads((ROOT/'skills-lock.json').read_text())
    installed = lock['skills']['emil-design-eng']
    assert installed['source'] == 'emilkowalski/skills'
    assert installed['sourceType'] == 'github'
    assert installed['skillPath'] == manifest['upstream_path']
    assert re.fullmatch(r'[a-f0-9]{64}', installed['computedHash'])


def test_integration_and_architecture_references_resolve():
    documents = ['docs/agents/emil-design-eng.md',
                 'docs/architecture/annotation-workplace-guided.md']
    for relative in documents:
        document = ROOT/relative
        for target in re.findall(r'\]\(([^)]+)\)', document.read_text()):
            if '://' in target or target.startswith('#'):
                continue
            assert (document.parent/target.split('#',1)[0]).is_file(), (relative,target)
