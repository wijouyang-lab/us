#!/usr/bin/env python3
"""FS-2 versioned snapshot publisher.

Immutable version files + one atomically replaced manifest pointer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REQUIRED = {"ticker", "composite_tier", "tradability_status", "style_tags"}
TIERS = {"TIER_1", "TIER_2", "WATCH", "BLOCKED"}
STATUSES = {"ELIGIBLE_FOR_RESEARCH", "WATCH", "BLOCKED", "INSUFFICIENT_DATA"}
ROWS = 5600
KEEP = 30
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def validate(data: dict) -> int:
    if data.get("research_only") is not True:
        raise ValueError("research_only missing")
    rows = data.get("rows")
    if not isinstance(rows, list) or len(rows) != ROWS:
        raise ValueError(f"row count {len(rows) if rows else 0}")
    tickers = [r.get("ticker") for r in rows]
    if any(not isinstance(t, str) or not t for t in tickers):
        raise ValueError("bad ticker")
    if len(set(tickers)) != len(tickers):
        raise ValueError("duplicate ticker")
    for r in rows:
        if not REQUIRED.issubset(r):
            raise ValueError(f"missing fields {r.get('ticker')}")
        if r["composite_tier"] not in TIERS:
            raise ValueError("bad tier")
        if r["tradability_status"] not in STATUSES:
            raise ValueError("bad status")
    for k in ("version", "prices_as_of", "fundamentals_as_of"):
        if not data.get(k):
            raise ValueError(f"missing {k}")
    return len(rows)


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def version_name(version: str) -> str:
    if not isinstance(version, str) or not VERSION_RE.match(version):
        raise ValueError("unsafe version")
    if ".." in version or "/" in version or "\\" in version or Path(version).is_absolute():
        raise ValueError("unsafe version")
    return version


def version_file(versions: Path, version: str) -> Path:
    version = version_name(version)
    stem = version[4:] if version.startswith("fs2.") else version
    p = (versions / f"fs2_v{stem}.json").resolve()
    if p.parent != versions.resolve():
        raise ValueError("version escapes versions dir")
    return p


def info(path: Path, manifest_dir: Path, data: dict) -> dict:
    return {
        "path": path.relative_to(manifest_dir).as_posix(),
        "version": data["version"],
        "sha256": sha_bytes(path.read_bytes()),
        "row_count": len(data["rows"]),
        "generated_at": data.get("generated_at", ""),
        "prices_as_of": data.get("prices_as_of", ""),
        "fundamentals_as_of": data.get("fundamentals_as_of", ""),
    }


def fsync_dir(path: Path) -> bool:
    """Persist the directory entry where supported; return False on Windows."""
    try:
        fd = os.open(str(path), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return True
    except OSError:
        return False


def atomic_write(path: Path, payload: bytes) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
        return fsync_dir(path.parent)
    except BaseException:
        if os.path.exists(tmp):
            try: os.unlink(tmp)
            except OSError: pass
        raise


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_manifest(path: Path) -> dict:
    m = load_json(path)
    if m.get("schema_version") != 2 or not isinstance(m.get("current"), dict):
        raise ValueError("manifest schema invalid")
    return m


def verify_entry(entry: dict, manifest_dir: Path) -> dict:
    if not isinstance(entry, dict) or not entry.get("path"):
        raise ValueError("bad manifest entry")
    p = (manifest_dir / entry["path"]).resolve()
    if manifest_dir.resolve() not in p.parents:
        raise ValueError("entry escapes manifest dir")
    if not p.exists():
        raise ValueError(f"missing {p}")
    raw = p.read_bytes()
    if sha_bytes(raw) != entry.get("sha256"):
        raise ValueError(f"SHA mismatch {p}")
    d = load_json(p)
    validate(d)
    if len(d["rows"]) != entry.get("row_count") or entry["row_count"] != ROWS:
        raise ValueError(f"row count {p}")
    if d.get("version") != entry.get("version"):
        raise ValueError("version mismatch")
    return d


def verify_manifest(manifest_path: Path) -> dict:
    m = read_manifest(manifest_path)
    verify_entry(m["current"], manifest_path.parent)
    if m.get("previous"):
        verify_entry(m["previous"], manifest_path.parent)
    return m


def prune_versions(versions: Path, refs: set[str], pinned: set[str], keep: int) -> list[str]:
    files = sorted(versions.glob("fs2_v*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in files[keep:]:
        if p.name in refs or p.name in pinned:
            continue
        try: p.unlink()
        except OSError: pass
    return sorted(p.name for p in versions.glob("fs2_v*.json"))


def build_manifest(manifest_path: Path, cur: dict, prev: dict | None, retained: list[str], pinned: list[str], durability: dict) -> dict:
    return {
        "schema_version": 2,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "current": cur,
        "previous": prev,
        "retained": retained,
        "pinned": pinned,
        "durability": durability,
    }


def publish(args) -> dict:
    manifest, versions = args.manifest, args.versions
    versions.mkdir(parents=True, exist_ok=True)
    data = load_json(args.source); validate(data)
    version = args.version or data["version"]
    vp = version_file(versions, version)
    payload = json.dumps({**data, "version": version}, separators=(",", ":"), ensure_ascii=False).encode()
    if vp.exists():
        if sha_bytes(vp.read_bytes()) != sha_bytes(payload):
            raise ValueError("version already exists with different content")
    else:
        atomic_write(vp, payload)
    got = load_json(vp); validate(got)
    if sha_bytes(vp.read_bytes()) != sha_bytes(payload):
        raise ValueError("version readback SHA mismatch")
    new_info = info(vp, manifest.parent, got)
    old = read_manifest(manifest) if manifest.exists() else None
    prev = old["current"] if old else None
    pinned = sorted(set(old.get("pinned", []))) if old else []
    refs = {vp.name}
    if prev: refs.add(Path(prev["path"]).name)
    if old and old.get("previous"): refs.add(Path(old["previous"]["path"]).name)
    retained = prune_versions(versions, refs, {Path(x).name for x in pinned}, args.keep)
    m = build_manifest(manifest, new_info, prev, retained, pinned, {"file_fsync": True, "dir_fsync": os.name != "nt"})
    atomic_write(manifest, json.dumps(m, indent=2).encode())
    verify_manifest(manifest)
    print(json.dumps(m, indent=2))
    return m


def cmd_validate(args):
    m = verify_manifest(args.manifest)
    print(json.dumps({"valid": True, "current": m["current"]["version"], "sha256": m["current"]["sha256"]}, indent=2))


def cmd_rollback(args):
    m = read_manifest(args.manifest)
    target = version_file(args.versions, args.version)
    if not target.exists(): raise ValueError("version not found")
    d = load_json(target); validate(d)
    entry = info(target, args.manifest.parent, d)
    if entry["version"] != args.version: raise ValueError("version mismatch")
    refs = {target.name}
    if m.get("previous"): refs.add(Path(m["previous"]["path"]).name)
    retained = prune_versions(args.versions, refs, {Path(x).name for x in m.get("pinned", [])}, args.keep)
    new = build_manifest(args.manifest, entry, m["current"], retained, m.get("pinned", []), {"file_fsync": True, "dir_fsync": os.name != "nt"})
    atomic_write(args.manifest, json.dumps(new, indent=2).encode())
    verify_manifest(args.manifest)
    print(json.dumps(new, indent=2))


def cmd_list(args):
    m = read_manifest(args.manifest)
    print(json.dumps({"current": m["current"], "previous": m.get("previous"), "retained": m.get("retained", [])}, indent=2))


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("publish")
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--versions", type=Path, required=True)
    p.add_argument("--version", default=None)
    p.add_argument("--keep", type=int, default=KEEP)
    p.set_defaults(fn=publish)
    for name, fn in (("validate", cmd_validate), ("verify", cmd_validate), ("list-versions", cmd_list)):
        q = sub.add_parser(name); q.add_argument("--manifest", type=Path, required=True); q.set_defaults(fn=fn)
    r = sub.add_parser("rollback")
    r.add_argument("--manifest", type=Path, required=True)
    r.add_argument("--versions", type=Path, required=True)
    r.add_argument("--version", required=True)
    r.add_argument("--keep", type=int, default=KEEP)
    r.set_defaults(fn=cmd_rollback)
    a = ap.parse_args(); a.fn(a)


if __name__ == "__main__":
    main()
