"""Regression checks for what the publication audit will actually commit."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def publication(tmp_path):
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    (tmp_path / 'scripts').mkdir()
    (tmp_path / 'docs').mkdir()
    shutil.copyfile(ROOT / 'scripts/audit_publication.py', tmp_path / 'scripts/audit_publication.py')
    body = b'print("example")\n'
    (tmp_path / 'main.py').write_bytes(body)
    manifest = {'files': [{'path': 'main.py', 'sha256': hashlib.sha256(body).hexdigest()}],
                'publication_adjustments': []}
    (tmp_path / 'docs/source-manifest.json').write_text(json.dumps(manifest))
    subprocess.run(['git', 'add', '.'], cwd=tmp_path, check=True)
    return tmp_path


def audit(root):
    return subprocess.run([sys.executable, 'scripts/audit_publication.py'], cwd=root,
                          text=True, capture_output=True)


def test_valid_reviewed_index_passes(publication):
    assert audit(publication).returncode == 0


def test_unknown_staged_artifact_is_rejected(publication):
    (publication / 'private-photo.png').write_bytes(b'benign-looking bytes')
    subprocess.run(['git', 'add', 'private-photo.png'], cwd=publication, check=True)
    result = audit(publication)
    assert result.returncode != 0
    assert 'outside-publication-allowlist' in result.stderr


def test_staged_secret_is_rejected_even_when_worktree_is_clean(publication):
    path = publication / 'README.md'
    path.write_text('sk-proj-' + 'A' * 60)
    subprocess.run(['git', 'add', 'README.md'], cwd=publication, check=True)
    path.write_text('clean working copy')
    result = audit(publication)
    assert result.returncode != 0
    assert 'provider-key: README.md' in result.stderr
    assert 'A' * 60 not in result.stderr


def test_staged_source_mismatch_is_rejected(publication):
    (publication / 'main.py').write_text('print("unreviewed change")\n')
    subprocess.run(['git', 'add', 'main.py'], cwd=publication, check=True)
    assert 'source-integrity: main.py' in audit(publication).stderr
