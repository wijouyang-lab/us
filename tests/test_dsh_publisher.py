import hashlib
import json
from pathlib import Path

import pytest

from tools.automation.artifact import read_manifest

ROOT = Path(__file__).resolve().parents[1]


def _artifact(tmp_path, path="docs/research/a.md", status="AGENT_COMPLETE", body=b"x"):
    out = tmp_path / "agent-artifact"
    f = out / "workspace" / path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(body)
    m = {"task_id": "t", "branch": "fix/t", "base_branch": "main", "status": status, "files": [{"path": path, "sha256": hashlib.sha256(body).hexdigest()}], "deletes": []}
    out.mkdir(exist_ok=True)
    (out / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    return out


def test_artifact_accepts_valid_file(tmp_path):
    assert read_manifest(_artifact(tmp_path))["task_id"] == "t"


def test_artifact_rejects_incomplete_status(tmp_path):
    with pytest.raises(ValueError, match="AGENT_NOT_COMPLETE"):
        read_manifest(_artifact(tmp_path, status="AGENT_FAILED"))


def test_artifact_rejects_traversal_and_symlink_and_git(tmp_path):
    for bad in ("../outside.md", "main.py", ".git/config"):
        with pytest.raises(ValueError, match="UNAUTHORIZED_PATH|SENSITIVE_PATH"):
            read_manifest(_artifact(tmp_path, path=bad))
    out = _artifact(tmp_path, path="docs/research/link.md")
    f = out / "workspace/docs/research/link.md"
    f.unlink()
    try:
        f.symlink_to("/etc/passwd")
    except (OSError, NotImplementedError):
        pytest.skip("symlink unavailable")
    with pytest.raises(ValueError, match="SENSITIVE_PATH|UNAUTHORIZED_PATH|INVALID|SYMLINK"):
        read_manifest(out)


def test_publisher_has_temporary_auth_only():
    text = (ROOT / "tools/automation/publisher.py").read_text(encoding="utf-8")
    assert "credential.helper=!gh auth git-credential" in text
    assert "git config" not in text
