#!/usr/bin/env python3
"""Multi-snapshot revision audit for forward PIT event captures.

This reads immutable event snapshots and the archive; it never fetches or
rewrites capture files. Duplicate observations are not counted as new events.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def audit(snapshots: Iterable[Path], archive_path: Path) -> dict[str, Any]:
    snapshots = list(snapshots)
    archive = _load(archive_path)
    by_source = defaultdict(lambda: {
        "events": 0, "unique_event_ids": set(), "version_ids": set(),
        "first_seen": [], "last_seen": [], "published_values": defaultdict(set),
        "failures": 0,
    })
    total_observations = 0
    for path in snapshots:
        events = _load(path)
        total_observations += len(events)
        for e in events:
            source = str(e.get("source") or "unknown")
            s = by_source[source]
            s["events"] += 1
            s["unique_event_ids"].add(str(e.get("event_id")))
            s["version_ids"].add(str(e.get("event_version_id") or e.get("content_hash")))
            if e.get("first_seen_at_utc"):
                s["first_seen"].append(str(e["first_seen_at_utc"]))
            if e.get("last_seen_at_utc"):
                s["last_seen"].append(str(e["last_seen_at_utc"]))
            if e.get("published_at_utc"):
                s["published_values"][str(e.get("event_id"))].add(str(e["published_at_utc"]))
    rows = []
    for source, s in sorted(by_source.items()):
        versions = len(s["version_ids"])
        unique = len(s["unique_event_ids"])
        conflicts = sum(1 for values in s["published_values"].values() if len(values) > 1)
        rows.append({
            "source": source,
            "observations": s["events"],
            "unique_event_ids": unique,
            "version_count": versions,
            "duplicate_observations": s["events"] - versions,
            "revision_count": max(0, versions - unique),
            "timestamp_conflict_count": conflicts,
            "first_observed_at": min(s["first_seen"]) if s["first_seen"] else None,
            "last_observed_at": max(s["last_seen"] or s["first_seen"]) if s["first_seen"] else None,
            "failure_count": s["failures"],
        })
    return {
        "schema_version": 1,
        "snapshot_count": len(list(snapshots)),
        "archive_event_versions": len(archive),
        "total_observations": total_observations,
        "unique_event_ids": len({str(e.get("event_id")) for e in archive}),
        "duplicate_observations": total_observations - len(archive),
        "sources": rows,
        "research_only": True,
        "not_alpha_evidence": True,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--capture-dir", required=True)
    p.add_argument("--archive", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args(argv)
    root = Path(args.capture_dir)
    snapshots = sorted(root.glob("*.events.json"))
    report = audit(snapshots, Path(args.archive))
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
