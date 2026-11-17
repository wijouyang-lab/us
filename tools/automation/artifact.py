"""Artifact creation and strict validation for the DSH agent/Publisher split."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from tools.automation.changes import ALLOWED


def _safe_path(path: str) -> None:
    p = Path(path)
    if p.is_absolute() or ".." in p.parts or not any(path == a or path.startswith(a + "/") for a in ALLOWED):
        raise ValueError(f"UNAUTHORIZED_PATH:{path}")


def build_artifact(repo: Path, out: Path, manifest: dict, paths: list[str]) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    workspace = out / "workspace"
    files = []
    deletes = []
    for rel in paths:
        _safe_path(rel)
        src = repo / rel
        if not src.exists():
            deletes.append(rel)
            continue
        if src.is_symlink():
            raise ValueError(f"SYMLINK_REJECTED:{rel}")
        target = workspace / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        files.append({"path": rel, "sha256": hashlib.sha256(src.read_bytes()).hexdigest(), "bytes": src.stat().st_size})
    manifest = dict(manifest)
    manifest["files"] = files
    manifest["deletes"] = deletes
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def read_manifest(out: Path) -> dict:
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    if m.get("status") != "AGENT_COMPLETE":
        raise ValueError(f"AGENT_NOT_COMPLETE:{m.get('status')}")
    for rel in [x["path"] for x in m.get("files", [])] + list(m.get("deletes", [])):
        _safe_path(rel)
        if rel.startswith(".git") or "token" in rel.lower() or "credentials" in rel.lower():
            raise ValueError(f"SENSITIVE_PATH:{rel}")
        src = out / "workspace" / rel
        if src.is_symlink():
            raise ValueError(f"SYMLINK_REJECTED:{rel}")
        if src.exists() and out.resolve() not in src.resolve().parents:
            raise ValueError(f"PATH_ESCAPE:{rel}")
    return m
