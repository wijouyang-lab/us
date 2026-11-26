"""Artifact creation and strict validation for the DSH agent/Publisher split."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

from tools.automation.changes import ALLOWED
from tools.automation.validate import validate_base, validate_branch, validate_task_id

REQUIRED = {"task_id", "branch", "base_branch", "source_commit_sha", "base_commit_sha", "status", "files", "deletes", "timed_out", "tests_returncode"}
OPTIONAL = {"final", "timed_out", "tests_returncode", "tests_tail", "error", "diagnostic_summary"}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _root(path: Path) -> Path:
    cur = path.absolute()
    for anc in [cur] + list(cur.parents):
        if anc == anc.parent:
            break
        if anc.is_symlink():
            raise ValueError(f"ROOT_ANCESTOR_SYMLINK:{anc}")
    if cur.is_symlink() or not cur.is_dir():
        raise ValueError(f"ROOT_NOT_REGULAR_DIR:{path}")
    return cur.resolve()


def _safe_path(path: str) -> None:
    p = Path(path)
    if not isinstance(path, str) or p.is_absolute() or ".." in p.parts or not any(path == a or path.startswith(a + "/") for a in ALLOWED):
        raise ValueError(f"UNAUTHORIZED_PATH:{path}")


def _check_parents(root: Path, rel: str) -> Path:
    _safe_path(rel)
    base = _root(root)
    cur = base
    for part in Path(rel).parts[:-1]:
        cur = cur / part
        if cur.is_symlink():
            raise ValueError(f"PARENT_SYMLINK:{rel}")
        if cur.exists() and not cur.is_dir():
            raise ValueError(f"PARENT_NOT_DIR:{rel}")
    target = base / rel
    if target.is_symlink():
        raise ValueError(f"TARGET_SYMLINK:{rel}")
    if target.exists() and base not in target.resolve().parents:
        raise ValueError(f"PATH_ESCAPE:{rel}")
    return target


def _check_workspace(out: Path) -> Path:
    root = _root(out)
    ws = root / "workspace"
    if ws.is_symlink() or not ws.is_dir():
        raise ValueError("WORKSPACE_NOT_REGULAR_DIR")
    if root not in ws.resolve().parents:
        raise ValueError("WORKSPACE_ESCAPE")
    return ws


def build_artifact(repo: Path, out: Path, manifest: dict, paths: list[str]) -> dict:
    # Validate ancestors before creating anything.
    for anc in [out.absolute()] + list(out.absolute().parents):
        if anc == anc.parent:
            break
        if anc.is_symlink():
            raise ValueError(f"ROOT_ANCESTOR_SYMLINK:{anc}")
    out.mkdir(parents=True, exist_ok=True)
    _root(out)
    (out / "workspace").mkdir(parents=True, exist_ok=True)
    ws = _check_workspace(out)
    files, deletes = [], []
    for rel in paths:
        target = _check_parents(repo, rel)
        if target.is_symlink():
            raise ValueError(f"SYMLINK_REJECTED:{rel}")
        if not target.exists():
            deletes.append(rel)
            continue
        target_out = _check_parents(ws, rel)
        target_out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, target_out)
        files.append({"path": rel, "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "bytes": target.stat().st_size})
    manifest = dict(manifest)
    manifest["files"] = files
    manifest["deletes"] = deletes
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def read_manifest(out: Path) -> dict:
    root = _root(out)
    mf = root / "manifest.json"
    if mf.is_symlink() or not mf.is_file():
        raise ValueError("MANIFEST_NOT_REGULAR_FILE")
    m = json.loads(mf.read_text(encoding="utf-8"))
    if not isinstance(m, dict) or not REQUIRED.issubset(m):
        raise ValueError("MANIFEST_SCHEMA_INVALID")
    if set(m) - REQUIRED - OPTIONAL:
        raise ValueError("MANIFEST_UNKNOWN_FIELD")
    for k in ("task_id", "branch", "base_branch"):
        if not isinstance(m[k], str):
            raise ValueError("MANIFEST_FIELD_TYPE")
    validate_task_id(m["task_id"])
    validate_base(m["base_branch"])
    validate_branch(m["branch"], m["base_branch"])
    for k in ("source_commit_sha", "base_commit_sha"):
        if not isinstance(m[k], str) or not SHA_RE.fullmatch(m[k]):
            raise ValueError("SOURCE_SHA_INVALID")
    if m["status"] != "AGENT_COMPLETE":
        raise ValueError(f"AGENT_NOT_COMPLETE:{m['status']}")
    if type(m["timed_out"]) is not bool or m["timed_out"] is not False:
        raise ValueError("TIMED_OUT_INVALID")
    if type(m["tests_returncode"]) is not int or isinstance(m["tests_returncode"], bool) or m["tests_returncode"] != 0:
        raise ValueError("TESTS_RETURNCODE_INVALID")
    if not isinstance(m["files"], list) or not isinstance(m["deletes"], list):
        raise ValueError("MANIFEST_SCHEMA_INVALID")
    ws = _check_workspace(root)
    seen = set()
    for f in m["files"]:
        if not isinstance(f, dict) or set(f) != {"path", "sha256", "bytes"}:
            raise ValueError("FILE_ENTRY_SCHEMA_INVALID")
        if not isinstance(f["path"], str) or not isinstance(f["bytes"], int) or isinstance(f["bytes"], bool) or f["bytes"] < 0:
            raise ValueError("FILE_ENTRY_SCHEMA_INVALID")
        if not isinstance(f["sha256"], str) or not HEX64.fullmatch(f["sha256"]):
            raise ValueError("FILE_HASH_INVALID")
        rel = f["path"]
        _check_parents(ws, rel)
        if rel in seen:
            raise ValueError(f"DUPLICATE_PATH:{rel}")
        seen.add(rel)
        src = _check_parents(ws, rel)
        if not src.is_file():
            raise ValueError(f"ARTIFACT_FILE_MISSING:{rel}")
        if src.stat().st_size != f["bytes"] or hashlib.sha256(src.read_bytes()).hexdigest() != f["sha256"]:
            raise ValueError(f"ARTIFACT_HASH_MISMATCH:{rel}")
    for rel in m["deletes"]:
        if not isinstance(rel, str):
            raise ValueError("DELETE_PATH_INVALID")
        if rel in seen:
            raise ValueError(f"FILE_AND_DELETE_CONFLICT:{rel}")
        _safe_path(rel)
        seen.add(rel)
    return m


def artifact_digest(out: Path) -> str:
    root = _root(out)
    return hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest()
