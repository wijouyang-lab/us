#!/usr/bin/env python3
"""Persistent, append-only store for forward PIT event snapshots.

Storage is a separate git branch/directory, never main and never production.
Each run keeps its immutable snapshot; the cumulative archive and observation
index are rebuilt by merging all run snapshots.  No database is required.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

from tools.research.pit_event_archive import event_version_id, merge_event_archive

STORE_SCHEMA_VERSION = 1
ARCHIVE = Path("archive/event_archive.json")
OBSERVATIONS = Path("archive/observations.json")
LATEST_MANIFEST = Path("archive/latest_manifest.json")
RUNS = Path("runs")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def _hash_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _hash_value(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _run_manifest(store: Path, run_dir: Path) -> dict[str, Any]:
    path = run_dir / "manifest.json"
    if not path.exists():
        raise ValueError(f"run manifest missing: {run_dir}")
    manifest = _read_json(path)
    if not isinstance(manifest, dict):
        raise ValueError(f"run manifest invalid: {run_dir}")
    if str(manifest.get("run_id") or "") != run_dir.name:
        raise ValueError(f"run manifest id mismatch: {run_dir}")
    hashes = manifest.get("snapshot_sha256") or {}
    for name in ("events.json", "metadata.json", "audit.json"):
        target = run_dir / name
        if not target.exists():
            raise ValueError(f"run snapshot missing {name}: {run_dir}")
        if hashes.get(name) != _hash_file(target):
            raise ValueError(f"run snapshot hash mismatch {name}: {run_dir}")
    return manifest


def _store_manifest(store: Path, archive: list[dict], observations: list[dict]) -> dict[str, Any]:
    runs = []
    for run_dir in sorted(p for p in (store / RUNS).glob("*") if p.is_dir()):
        manifest = _run_manifest(store, run_dir)
        runs.append({
            "run_id": run_dir.name,
            "run_url": manifest.get("run_url", ""),
            "commit_sha": manifest.get("commit_sha", ""),
            "captured_at": manifest.get("captured_at", ""),
            "snapshot_sha256": manifest.get("snapshot_sha256", {}),
            "manifest_sha256": sha256((run_dir / "manifest.json").read_bytes()).hexdigest(),
        })
    return {
        "store_schema_version": STORE_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "run_count": len(runs),
        "latest_run_id": runs[-1]["run_id"] if runs else None,
        "runs": runs,
        "archive_sha256": _hash_value(archive),
        "observations_sha256": _hash_value(observations),
        "event_versions": len(archive),
        "observations": len(observations),
        "research_only": True,
        "production_scanner_modified": False,
    }


def _load_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"corrupt or unreadable JSON: {path}: {exc}") from exc
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError(f"{path} must contain a JSON array of objects")
    return value


def _snapshot_files(snapshot: Path) -> tuple[Path, Path, Path]:
    events = snapshot / "events.json"
    metadata = snapshot / "metadata.json"
    audit = snapshot / "audit.json"
    if not events.exists():
        candidates = sorted(snapshot.glob("*.events.json"))
        if len(candidates) != 1:
            raise ValueError("snapshot must contain exactly one events JSON")
        events = candidates[0]
    if not metadata.exists():
        metadata = events.with_name(events.name.replace(".events.json", ".metadata.json"))
    if not audit.exists():
        audit = events.with_name(events.name.replace(".events.json", ".audit.json"))
    if not events.exists() or not metadata.exists():
        raise ValueError("snapshot requires events and metadata JSON files")
    return events, metadata, audit


def _validate_run_id(run_id: str) -> str:
    clean = str(run_id or "").strip()
    if not clean or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for c in clean):
        raise ValueError("run_id must be a non-empty safe identifier")
    return clean


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON: {path}: {exc}") from exc


def _source_status(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in (metadata.get("source_reports") or {}).get("official_rss", {}).get("feed_reports", []):
        rows.append({
            "feed_key": item.get("feed_key"),
            "status": item.get("status"),
            "event_count": int(item.get("event_count") or 0),
            "error_type": item.get("error_type"),
        })
    return rows


def _counts(prior_archive: list[dict], archive: list[dict], observations: list[dict],
            incoming_events: list[dict], previous_observation_count: int) -> dict[str, Any]:
    prior_versions = {str(e.get("event_version_id")) for e in prior_archive if e.get("event_version_id")}
    prior_events = {str(e.get("event_id")) for e in prior_archive if e.get("event_id")}
    incoming_versions = {
        str(e.get("event_version_id") or event_version_id(e)) for e in incoming_events
    }
    new_versions = incoming_versions - prior_versions
    incoming_events_map = {
        str(e.get("event_version_id") or event_version_id(e)): str(e.get("event_id"))
        for e in incoming_events
    }
    published_by_event: dict[str, set[str]] = {}
    for e in archive:
        if e.get("event_id") and e.get("published_at_utc"):
            published_by_event.setdefault(str(e["event_id"]), set()).add(str(e["published_at_utc"]))
    return {
        "unique_event_ids": len({str(e.get("event_id")) for e in archive if e.get("event_id")}),
        "versions": len({str(e.get("event_version_id")) for e in archive if e.get("event_version_id")}),
        "observations": len(observations),
        "new_observations": len(observations) - previous_observation_count,
        "duplicate_observations": sum(1 for v in incoming_versions if v in prior_versions),
        "new_versions": len(new_versions),
        "new_events": len({
            str(e.get("event_id")) for e in incoming_events
            if str(e.get("event_id")) not in prior_events
        }),
        "revisions": sum(1 for v in new_versions if incoming_events_map.get(v) in prior_events),
        "retractions": sum(
            1 for e in incoming_events
            if e.get("retracted") is True or e.get("retraction") is True or e.get("retracted_at_utc")
        ),
        "timestamp_conflicts": sum(1 for values in published_by_event.values() if len(values) > 1),
    }


def import_snapshot(store: Path, snapshot: Path, *, run_id: str, run_url: str = "",
                    commit_sha: str = "", captured_at: str | None = None,
                    decision_at: str | None = None) -> dict[str, Any]:
    """Merge one immutable run into the store; idempotent for the same run/snapshot."""
    store.mkdir(parents=True, exist_ok=True)
    run_id = _validate_run_id(run_id)
    events_path, metadata_path, audit_path = _snapshot_files(snapshot)
    events = _read_json(events_path)
    metadata = _read_json(metadata_path)
    if not isinstance(events, list) or any(not isinstance(x, dict) for x in events):
        raise ValueError("events snapshot must be a JSON array of objects")
    if not isinstance(metadata, dict):
        raise ValueError("metadata snapshot must be a JSON object")
    audit = _read_json(audit_path) if audit_path.exists() else {}

    existing_archive = _load_list(store / ARCHIVE)
    existing_observations = _load_list(store / OBSERVATIONS)
    previous_observation_count = len(existing_observations)
    if existing_archive and not (store / ARCHIVE).exists():
        raise ValueError("archive file disappeared during import")

    merged, merge_report = merge_event_archive(existing_archive, events)
    # Link each newer version to the previous version of the same event.
    previous: dict[str, str] = {}
    for row in sorted(merged, key=lambda x: (str(x.get("event_id")), str(x.get("first_seen_at_utc")))):
        event_id = str(row.get("event_id") or "")
        version = str(row.get("event_version_id") or "")
        if event_id and version:
            if previous.get(event_id) and not row.get("supersedes_event_version_id"):
                row["supersedes_event_version_id"] = previous[event_id]
            previous[event_id] = version

    run_dir = store / RUNS / run_id
    snapshot_hashes = {}
    for src, name in ((events_path, "events.json"), (metadata_path, "metadata.json"), (audit_path, "audit.json")):
        if not src.exists():
            continue
        snapshot_hashes[name] = sha256(src.read_bytes()).hexdigest()
        run_dir.mkdir(parents=True, exist_ok=True)
        target = run_dir / name
        if target.exists():
            if sha256(target.read_bytes()).hexdigest() != snapshot_hashes[name]:
                raise ValueError(f"run {run_id} already exists with different {name}")
        else:
            shutil.copyfile(src, target)

    observations = list(existing_observations)
    existing_keys = {
        (str(o.get("run_id")), str(o.get("event_version_id")), str(o.get("event_id")))
        for o in observations
    }
    for event in events:
        version = str(event.get("event_version_id") or "")
        if not version:
            version = event_version_id(event)
        event_id = str(event.get("event_id") or "")
        key = (run_id, version, event_id)
        if key in existing_keys:
            continue
        existing_keys.add(key)
        observations.append({
            "run_id": run_id,
            "event_id": event_id,
            "event_version_id": version,
            "source": event.get("source"),
            "event_type": event.get("event_type"),
            "first_seen_at_utc": event.get("first_seen_at_utc"),
            "payload_hash": event.get("content_hash") or event.get("payload_hash"),
        })

    counts = _counts(existing_archive, merged, observations, events, previous_observation_count)
    manifest = {
        "store_schema_version": STORE_SCHEMA_VERSION,
        "run_id": run_id,
        "run_url": run_url,
        "commit_sha": commit_sha,
        "captured_at": captured_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "decision_at": decision_at or metadata.get("decision_at_utc") or "",
        "snapshot_sha256": snapshot_hashes,
        "source_status": _source_status(metadata),
        "merge_report": merge_report,
        "counts": counts,
        "research_only": True,
        "production_scanner_modified": False,
    }
    _dump(run_dir / "manifest.json", manifest)
    _dump(store / ARCHIVE, merged)
    _dump(store / OBSERVATIONS, observations)
    cumulative = _store_manifest(store, merged, observations)
    _dump(store / LATEST_MANIFEST, cumulative)
    return manifest


def rebuild(store: Path) -> dict[str, Any]:
    """Rebuild and verify cumulative archive from all run snapshots."""
    run_dirs = sorted(p for p in (store / RUNS).glob("*") if p.is_dir())
    archive: list[dict] = []
    observations: list[dict] = []
    for run in run_dirs:
        _run_manifest(store, run)
        events_path = run / "events.json"
        if not events_path.exists():
            raise ValueError(f"run snapshot missing events: {run}")
        events = _read_json(events_path)
        archive, _ = merge_event_archive(archive, events)
        for event in events:
            version = str(event.get("event_version_id") or event_version_id(event))
            observations.append({
                "run_id": run.name,
                "event_id": str(event.get("event_id") or ""),
                "event_version_id": version,
                "source": event.get("source"),
                "event_type": event.get("event_type"),
                "first_seen_at_utc": event.get("first_seen_at_utc"),
                "payload_hash": event.get("content_hash") or event.get("payload_hash"),
            })

    actual_archive = _load_list(store / ARCHIVE)
    actual_observations = _load_list(store / OBSERVATIONS)
    if _hash_value(archive) != _hash_value(actual_archive):
        raise ValueError("archive is not reproducible from run snapshots")
    if _hash_value(observations) != _hash_value(actual_observations):
        raise ValueError("observation index is not reproducible from run snapshots")

    latest_path = store / LATEST_MANIFEST
    if not latest_path.exists():
        raise ValueError("latest_manifest.json is missing")
    latest = _read_json(latest_path)
    if not isinstance(latest, dict):
        raise ValueError("latest_manifest.json is invalid")
    if latest.get("run_count") != len(run_dirs):
        raise ValueError("latest_manifest run_count does not match snapshots")
    if latest.get("archive_sha256") != _hash_value(archive):
        raise ValueError("latest_manifest archive hash mismatch")
    if latest.get("observations_sha256") != _hash_value(observations):
        raise ValueError("latest_manifest observations hash mismatch")
    return {
        "runs": len(run_dirs),
        "unique_event_ids": len({e.get("event_id") for e in archive}),
        "versions": len(archive),
        "observations": len(observations),
        "reproducible": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    imp = sub.add_parser("import")
    imp.add_argument("--store", required=True)
    imp.add_argument("--snapshot", required=True)
    imp.add_argument("--run-id", required=True)
    imp.add_argument("--run-url", default="")
    imp.add_argument("--commit-sha", default="")
    imp.add_argument("--captured-at")
    imp.add_argument("--decision-at")
    ver = sub.add_parser("verify")
    ver.add_argument("--store", required=True)
    args = parser.parse_args(argv)
    if args.command == "import":
        result = import_snapshot(Path(args.store), Path(args.snapshot), run_id=args.run_id,
                                 run_url=args.run_url, commit_sha=args.commit_sha,
                                 captured_at=args.captured_at, decision_at=args.decision_at)
    else:
        result = rebuild(Path(args.store))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
