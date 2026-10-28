#!/usr/bin/env python3
"""Canonical PIT event schema and per-source quality report.

This is an adapter over the existing normalized event records. It does not
fetch, backfill, or alter production behavior.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

DATE_ONLY_PREFIXES = ("date_only",)
FEED_TO_SOURCE = {
    "bls_cpi": "bls_cpi_rss",
    "bls_employment": "bls_employment_situation_rss",
    "fed_all": "federal_reserve_press_rss",
    "fed_speeches": "federal_reserve_speeches_rss",
}


def _aware(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _stamp(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value else None


def _is_date_only(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    raw = value.strip()
    if len(raw) != 10:
        return False
    try:
        datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _valid_url(value: Any) -> bool:
    try:
        parsed = urlparse(str(value or ""))
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def to_canonical(event: Mapping[str, Any]) -> dict[str, Any]:
    """Map a normalized event into the strict research record.

    `event_time` is only copied from an explicit event_time field. Publication
    time is never substituted for event occurrence time.
    """
    source = str(event.get("source") or "").strip().lower()
    source_url = str(event.get("source_url") or "").strip()
    event_id = str(event.get("event_id") or "").strip()
    published_raw = event.get("published_at_utc")
    published = _aware(published_raw)
    first_seen = _aware(event.get("first_seen_at_utc"))
    retrieved = _aware(event.get("retrieved_at_utc"))
    update_seen = _aware(event.get("update_first_seen_at_utc"))
    event_time = _aware(event.get("event_time_utc") or event.get("event_time"))
    available_candidates = [x for x in (published, first_seen, update_seen) if x]
    available = max(available_candidates) if available_candidates else None

    tickers = [str(t).upper() for t in (event.get("tickers") or []) if str(t).strip()]
    entity_id = ",".join(tickers) if tickers else (
        "market" if event.get("market_scope") == "market" else None
    )
    if _is_date_only(published_raw):
        confidence = "date_only"
    elif published is not None and first_seen is not None:
        confidence = "parsed_utc"
    else:
        confidence = "missing"

    reasons = []
    if not event_id:
        reasons.append("missing_event_id")
    if not source:
        reasons.append("missing_source")
    if not _valid_url(source_url):
        reasons.append("missing_or_invalid_source_url")
    if published is None or first_seen is None:
        reasons.append("missing_required_timestamp")
    if confidence == "date_only":
        reasons.append("date_only_not_exact")
    if published and first_seen and first_seen < published:
        reasons.append("first_seen_before_publication")
    if available and first_seen and available < first_seen:
        reasons.append("available_before_first_seen")

    status = "validated" if not reasons and confidence == "parsed_utc" else "rejected"
    revision_id = event.get("event_version_id") or event.get("content_hash")
    return {
        "event_id": event_id or None,
        "event_type": event.get("event_type"),
        "entity_id": entity_id,
        "source": source or None,
        "source_url": source_url or None,
        "event_time": _stamp(event_time),
        "source_published_at": _stamp(published),
        "first_seen_at": _stamp(first_seen),
        "retrieved_at": _stamp(retrieved),
        "available_at": _stamp(available),
        "revision_id": revision_id,
        "payload_hash": event.get("content_hash") or event.get("payload_hash"),
        "supersedes_event_id": event.get("supersedes_event_id"),
        "timestamp_confidence": confidence,
        "validation_status": status,
        "validation_reasons": reasons,
        "raw_published_value": published_raw if isinstance(published_raw, str) else None,
    }


def source_quality_report(events: list[Mapping[str, Any]],
                          metadata: Mapping[str, Any] | None = None,
                          archive_summary: Mapping[str, Any] | None = None) -> dict[str, Any]:
    canonical = [to_canonical(e) for e in events]
    by_source: dict[str, dict[str, Any]] = {}
    for row in canonical:
        source = row["source"] or "unknown"
        s = by_source.setdefault(source, {
            "source": source, "events": 0, "validated": 0, "rejected": 0,
            "parsed_utc": 0, "date_only": 0, "timestamp_missing": 0,
            "missing_url": 0, "revision_ids": set(), "event_ids": set(),
        })
        s["events"] += 1
        s["event_ids"].add(row["event_id"])
        s["revision_ids"].add(row["revision_id"])
        s["validated"] += row["validation_status"] == "validated"
        s["rejected"] += row["validation_status"] == "rejected"
        s["parsed_utc"] += row["timestamp_confidence"] == "parsed_utc"
        s["date_only"] += row["timestamp_confidence"] == "date_only"
        s["timestamp_missing"] += row["timestamp_confidence"] == "missing"
        s["missing_url"] += "missing_or_invalid_source_url" in row["validation_reasons"]
    for source, s in by_source.items():
        s["timestamp_parsed_ratio"] = s["parsed_utc"] / s["events"] if s["events"] else 0.0
        s["revision_count"] = len(s["revision_ids"])
        s["unique_event_count"] = len(s["event_ids"])
        s["revision_rate"] = (s["revision_count"] / s["unique_event_count"]
                              if s["unique_event_count"] else 0.0)
        s["revision_ids"] = sorted(x for x in s["revision_ids"] if x)
        s["event_ids"] = sorted(x for x in s["event_ids"] if x)
    source_rows = []
    for source, s in sorted(by_source.items()):
        source_rows.append(s | {
            "capture_success_ratio": None,
            "capture_failure_reasons": [],
        })
    if metadata:
        for item in (metadata.get("source_reports") or {}).get("official_rss", {}).get("feed_reports", []):
            source_name = str(item.get("source") or FEED_TO_SOURCE.get(item.get("feed_key"), ""))
            for row in source_rows:
                if row["source"] == source_name:
                    row["capture_success_ratio"] = 1.0 if item.get("status") == "ok" else 0.0
                    if item.get("error_type"):
                        row["capture_failure_reasons"].append(item["error_type"])
    return {
        "schema_version": 1,
        "event_count": len(canonical),
        "source_count": len(source_rows),
        "sources": source_rows,
        "archive_summary": dict(archive_summary or {}),
        "research_only": True,
        "not_alpha_evidence": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", required=True)
    parser.add_argument("--metadata")
    parser.add_argument("--archive-summary")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    events = json.loads(Path(args.events).read_text(encoding="utf-8"))
    metadata = json.loads(Path(args.metadata).read_text(encoding="utf-8")) if args.metadata else None
    archive = json.loads(Path(args.archive_summary).read_text(encoding="utf-8")) if args.archive_summary else None
    report = source_quality_report(events, metadata, archive)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
