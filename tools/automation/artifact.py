"""Artifact creation and strict validation for the DSH agent/Publisher split."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from tools.automation.changes import ALLOWED

MANIFEST_KEYS = {"task_id", "branch", "base_branch", "source_commit_sha", "base_commit_sha", "status", "files", "deletes"}


def _safe_path(path: str) -> None:
    p = Path(path)
    if p.is_absolute() or ".." in p.parts or not any(path == a or path.startswith(a + "/") for a in ALLOWED):
        raise ValueError(f"UNAUTHORIZED_PATH:{path}")


def _check_parents(root: Path, rel: str) -> Path:
    _safe_path(rel)
    cur = root
    for part in Path(rel).parts[:-1]:
        cur = cur / part
        if cur.is_symlink():
            raise ValueError(f"PARENT_SYMLINK:{rel}")
        if cur.exists() and not cur.is_dir():
            raise ValueError(f"PARENT_NOT_DIR:{rel}")
    target = root / rel
    if target.is_symlink():
        raise ValueError(f"TARGET_SYMLINK:{rel}")
    return target


def build_artifact(repo: Path, out: Path, manifest: dict, paths: list[str]) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    workspace = out / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    files, deletes = [], []
    for rel in paths:
        target = _check_parents(repo, rel)
        if target.is_symlink():
            raise ValueError(f"SYMLINK_REJECTED:{rel}")
        if not target.exists():
            deletes.append(rel)
            continue
        target_out = _check_parents(workspace, rel)
        target_out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, target_out)
        files.append({"path": rel, "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "bytes": target.stat().st_size})
    manifest = dict(manifest)
    manifest["files"] = files
    manifest["deletes"] = deletes
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def read_manifest(out: Path) -> dict:
    mf = out / "manifest.json"
    if mf.is_symlink() or not mf.is_file():
        raise ValueError("MANIFEST_NOT_REGULAR_FILE")
    m = json.loads(mf.read_text(encoding="utf-8"))
    if not isinstance(m, dict) or set(m) < MANIFEST_KEYS:
        raise ValueError("MANIFEST_SCHEMA_INVALID")
    if m.get("status") != "AGENT_COMPLETE":
        raise ValueError(f"AGENT_NOT_COMPLETE:{m.get('status')}")
    if not m.get("source_commit_sha") or not m.get("base_commit_sha"):
        raise ValueError("SOURCE_COMMIT_MISSING")
    files = m.get("files", [])
    deletes = m.get("deletes", [])
    if not isinstance(files, list) or not isinstance(deletes, list):
        raise ValueError("MANIFEST_SCHEMA_INVALID")
    seen = set()
    for f in files:
        if not isinstance(f, dict) or set(f) != {"path", "sha256", "bytes"}:
            raise ValueError("FILE_ENTRY_SCHEMA_INVALID")
        rel = f["path"]
        _check_parents(out / "workspace", rel)
        if rel in seen:
            raise ValueError(f"DUPLICATE_PATH:{rel}")
        seen.add(rel)
        src = _check_parents(out / "workspace", rel)
        if not src.is_file():
            raise ValueError(f"ARTIFACT_FILE_MISSING:{rel}")
        if src.stat().st_size != f["bytes"] or hashlib.sha256(src.read_bytes()).hexdigest() != f["sha256"]:
            raise ValueError(f"ARTIFACT_HASH_MISMATCH:{rel}")
    for rel in deletes:
        if rel in seen:
            raise ValueError(f"FILE_AND_DELETE_CONFLICT:{rel}")
        _safe_path(rel)
        seen.add(rel)
    return m
