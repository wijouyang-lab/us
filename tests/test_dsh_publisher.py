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
    m = {"task_id": "t", "branch": "fix/t", "base_branch": "main", "source_commit_sha": "a" * 40, "base_commit_sha": "b" * 40, "status": status, "timed_out": False, "tests_returncode": 0, "files": [{"path": path, "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}], "deletes": []}
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
        with pytest.raises(ValueError, match="UNAUTHORIZED_PATH|SENSITIVE_PATH|WORKSPACE"):
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


def test_publisher_rejects_symlink_target_without_touching_outside(tmp_path):
    from tools.automation.publisher import apply_file
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("ORIGINAL", encoding="utf-8")
    try:
        (root / "docs/research").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink unavailable")
    src = tmp_path / "new.md"
    src.write_text("NEW", encoding="utf-8")
    try:
        apply_file(root, src, "docs/research/new.md")
    except ValueError:
        pass
    else:
        raise AssertionError("symlink parent was followed")
    assert (outside / "secret.txt").read_text(encoding="utf-8") == "ORIGINAL"


def test_manifest_source_required(tmp_path):
    out = _artifact(tmp_path)
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    m["source_commit_sha"] = ""
    (out / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(ValueError, match="SOURCE_COMMIT_MISSING|SOURCE_SHA_INVALID"):
        read_manifest(out)


def test_missing_timed_out_rejected(tmp_path):
    out = _artifact(tmp_path)
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    del m["timed_out"]
    (out / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(ValueError, match="MANIFEST_SCHEMA_INVALID"):
        read_manifest(out)


def test_wrong_tests_returncode_type_rejected(tmp_path):
    out = _artifact(tmp_path)
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    m["tests_returncode"] = True
    (out / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(ValueError, match="TESTS_RETURNCODE_INVALID"):
        read_manifest(out)


def test_all_invalid_timed_out_and_tests_cases(tmp_path):
    cases = [("timed_out", "false"), ("timed_out", True), ("tests_returncode", True), ("tests_returncode", "0"), ("tests_returncode", 1)]
    for key, value in cases:
        out = _artifact(tmp_path / f"{key}-{value}".replace("/", "_"))
        m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        m[key] = value
        (out / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
        with pytest.raises(ValueError):
            read_manifest(out)
    out = _artifact(tmp_path / "missing-tests")
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    del m["tests_returncode"]
    (out / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(ValueError, match="MANIFEST_SCHEMA_INVALID"):
        read_manifest(out)


def test_root_parent_symlink_rejected(tmp_path):
    out = _artifact(tmp_path)
    real = tmp_path / "real"
    real.mkdir()
    import shutil
    shutil.move(str(out), str(real / "art"))
    link_parent = tmp_path / "link-parent"
    try:
        link_parent.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symlink unavailable")
    with pytest.raises(ValueError, match="ROOT_ANCESTOR_SYMLINK|ROOT_NOT_REGULAR_DIR"):
        read_manifest(link_parent / "art")


def test_workspace_symlink_rejected(tmp_path):
    out = _artifact(tmp_path)
    ws = out / "workspace"
    moved = tmp_path / "moved-ws"
    ws.rename(moved)
    try:
        ws.symlink_to(moved, target_is_directory=True)
    except OSError:
        pytest.skip("symlink unavailable")
    with pytest.raises(ValueError, match="WORKSPACE_NOT_REGULAR_DIR"):
        read_manifest(out)


def test_manifest_symlink_rejected(tmp_path):
    out = _artifact(tmp_path)
    target = tmp_path / "target.json"
    (out / "manifest.json").rename(target)
    try:
        (out / "manifest.json").symlink_to(target)
    except OSError:
        pytest.skip("symlink unavailable")
    with pytest.raises(ValueError, match="MANIFEST_NOT_REGULAR_FILE"):
        read_manifest(out)
