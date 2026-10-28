"""Append-only logical archive for point-in-time event versions.

Repeated identical observations are deduplicated without changing their original
first-seen timestamp. Changed source content/timestamps produce a new immutable
logical version. This module performs no network requests and never writes to
production scanner inputs.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping

from tools.research.pit_event_eligibility import _parse_aware_timestamp


def _canonical(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        default=str, allow_nan=False,
    )


def event_version_id(event: Mapping[str, Any]) -> str:
    """Compute a version identity excluding only collector first-seen time."""
    if not str(event.get("event_id") or "").strip():
        raise ValueError("event_id is required to archive an event version")
    version_content = dict(event)
    version_content.pop("first_seen_at_utc", None)
    version_content.pop("event_version_id", None)
    # Human annotations describe an existing immutable source version; they must
    # not change that source-version identity when attached in a derived archive.
    for field in (
        "direction_score", "impact_score", "label_review_status",
        "label_reviewed_at_utc", "label_rationale", "labeler_id",
        "reviewer_id", "label_schema_version",
        "ticker_mapping_review_status", "ticker_mapping_reviewed_tickers",
        "ticker_mapping_reviewed_at_utc", "ticker_mapping_reviewer_id",
        "ticker_mapping_rationale", "ticker_mapping_schema_version",
    ):
        version_content.pop(field, None)
    return sha256(_canonical(version_content).encode("utf-8")).hexdigest()


def _first_seen(event: Mapping[str, Any]) -> datetime:
    parsed = _parse_aware_timestamp(event.get("first_seen_at_utc"))
    if parsed is None:
        raise ValueError("each archived event version requires a timezone-aware first_seen_at_utc")
    return parsed


def _stamp(parsed: datetime) -> str:
    return parsed.isoformat().replace("+00:00", "Z")


def _normalize_archived_version(
    event: Mapping[str, Any], *, verify_existing_id: bool
) -> dict[str, Any]:
    row = dict(event)
    first_seen = _first_seen(row)
    row["first_seen_at_utc"] = _stamp(first_seen)
    expected = event_version_id(row)
    supplied = row.get("event_version_id")
    if verify_existing_id and supplied and supplied != expected:
        raise ValueError(
            f"event_version_id does not match archived content for {row.get('event_id')}"
        )
    row["event_version_id"] = expected
    return row


def merge_event_archive(
    existing_events: Iterable[Mapping[str, Any]],
    incoming_events: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Merge observations, retaining distinct versions and earliest first-seen.

    Fetch failures are collection-health diagnostics, not new source-event
    versions; they are counted but excluded from the logical event archive.
    """
    archive: list[dict[str, Any]] = []
    by_version: dict[str, dict[str, Any]] = {}
    for event in existing_events:
        row = _normalize_archived_version(event, verify_existing_id=True)
        version = row["event_version_id"]
        if version in by_version:
            current = by_version[version]
            if _first_seen(row) < _first_seen(current):
                current["first_seen_at_utc"] = row["first_seen_at_utc"]
        else:
            by_version[version] = row
            archive.append(row)

    incoming_count = 0
    added_count = 0
    duplicate_count = 0
    fetch_error_count = 0
    first_seen_adjustment_count = 0

    for event in incoming_events:
        incoming_count += 1
        if str(event.get("availability_status") or "") == "fetch_error":
            fetch_error_count += 1
            continue
        row = _normalize_archived_version(event, verify_existing_id=False)
        version = row["event_version_id"]
        current = by_version.get(version)
        if current is None:
            by_version[version] = row
            archive.append(row)
            added_count += 1
            continue

        duplicate_count += 1
        if _first_seen(row) < _first_seen(current):
            current["first_seen_at_utc"] = row["first_seen_at_utc"]
            first_seen_adjustment_count += 1

    archive.sort(key=lambda row: (
        row["first_seen_at_utc"],
        str(row.get("event_id") or ""),
        str(row.get("event_version_id") or ""),
    ))
    archive_json = _canonical(archive)
    report = {
        "input_event_count": incoming_count,
        "new_version_count": added_count,
        "duplicate_version_count": duplicate_count,
        "fetch_error_skipped_count": fetch_error_count,
        "first_seen_adjustment_count": first_seen_adjustment_count,
        "archive_event_version_count": len(archive),
        "archive_snapshot_sha256": sha256(archive_json.encode("utf-8")).hexdigest(),
        "research_only": True,
        "production_scanner_modified": False,
    }
    return archive, report


def select_event_versions_asof(
    events: Iterable[Mapping[str, Any]],
    decision_at: str | datetime,
) -> list[dict[str, Any]]:
    """Select the latest observed version of each event known by decision time.

    This is an as-of selector, not a timestamp-eligibility substitute. The
    downstream coverage audit must still reject future publication timestamps,
    missing timestamps, stale versions, and invalid revisions.
    """
    decision = _parse_aware_timestamp(decision_at)
    if decision is None:
        raise ValueError("decision_at must be a timezone-aware timestamp")

    selected: dict[str, tuple[datetime, str, dict[str, Any]]] = {}
    for event in events:
        if str(event.get("availability_status") or "") == "fetch_error":
            continue
        row = _normalize_archived_version(
            event, verify_existing_id=bool(event.get("event_version_id"))
        )
        first_seen = _first_seen(row)
        if first_seen > decision:
            continue
        version_id = row["event_version_id"]
        event_id = str(row.get("event_id") or version_id)
        current = selected.get(event_id)
        candidate_key = (first_seen, version_id)
        if current is None or candidate_key > (current[0], current[1]):
            selected[event_id] = (first_seen, version_id, row)

    output = [value[2] for value in selected.values()]
    output.sort(key=lambda row: (
        str(row.get("event_id") or ""),
        str(row.get("event_version_id") or ""),
    ))
    return output


def _load_json_array(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read JSON file {source}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON file {source}: {exc}") from exc
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError(f"{source} must contain a JSON array of objects")
    return value


def append_archive_file(input_path: str | Path, archive_path: str | Path) -> dict[str, Any]:
    """Atomically update the archive JSON file from one collector snapshot."""
    input_file = Path(input_path)
    archive_file = Path(archive_path)
    if input_file.resolve() == archive_file.resolve():
        raise ValueError("input snapshot and archive must be different files")
    incoming = _load_json_array(input_file)
    existing = _load_json_array(archive_file) if archive_file.exists() else []
    merged, report = merge_event_archive(existing, incoming)
    archive_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = archive_file.with_name(archive_file.name + ".tmp")
    serialized = json.dumps(
        merged, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
    ) + "\n"
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(archive_file)
    report["source_snapshot_sha256"] = sha256(input_file.read_bytes()).hexdigest()
    report["archive_path"] = str(archive_file)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Path to a collector event JSON array")
    parser.add_argument("--archive", required=True, help="Logical event-version archive JSON file")
    args = parser.parse_args(argv)
    try:
        report = append_archive_file(args.input, args.archive)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    sys.stdout.write(json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
