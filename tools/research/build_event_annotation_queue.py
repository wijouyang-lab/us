"""Build a bounded human-review queue for earliest point-in-time event versions.

The queue never generates labels. It also distinguishes a queried ticker from a
reviewed company mapping; querying a Yahoo RSS endpoint for a symbol is not proof
that every returned headline concerns that company.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

FIELDS = [
    "event_id", "event_version_id", "event_type", "headline", "source",
    "source_url", "published_at_utc", "first_seen_at_utc", "content_hash",
    "market_scope", "tickers_json", "sectors_json", "queried_ticker",
    "ticker_mapping_method", "ticker_mapping_status", "ticker_mapping_confidence",
    "mapping_review_status", "mapped_tickers_json", "mapping_reviewed_at_utc",
    "mapping_reviewer_id", "mapping_rationale", "mapping_schema_version",
    "archive_label_review_status", "archive_direction_score", "archive_impact_score",
    "direction_score", "impact_score", "label_review_status", "label_reviewed_at_utc",
    "label_rationale", "labeler_id", "reviewer_id", "label_schema_version",
]

_TYPE_PRIORITY = {
    "earnings": 0,
    "company_news": 1,
    "macro_release": 2,
    "central_bank": 3,
    "policy": 4,
    "geopolitical": 5,
}


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp")
    return parsed.astimezone(timezone.utc)


def _is_aggregator_company_event(event: dict[str, Any]) -> bool:
    kind = str(event.get("event_type") or "").strip().lower()
    source = str(event.get("source") or "").strip().lower()
    quality = str(event.get("source_quality") or "").strip().lower()
    return kind in {"company_news", "earnings"} and (
        source == "yahoo_finance_rss" or quality == "aggregator"
    )


def _mapping_is_reviewed(event: dict[str, Any]) -> bool:
    return (
        str(event.get("ticker_mapping_review_status") or "").strip().lower() == "human_reviewed"
        and isinstance(event.get("ticker_mapping_reviewed_tickers"), list)
        and bool(event.get("ticker_mapping_reviewed_at_utc"))
        and bool(str(event.get("ticker_mapping_reviewer_id") or "").strip())
        and bool(str(event.get("ticker_mapping_rationale") or "").strip())
        and bool(str(event.get("ticker_mapping_schema_version") or "").strip())
    )


def _mapping_source_fields(event: dict[str, Any]) -> dict[str, str]:
    source = str(event.get("source") or "").strip().lower()
    is_aggregator = (
        source == "yahoo_finance_rss"
        or str(event.get("source_quality") or "").strip().lower() == "aggregator"
    )
    queried_ticker = str(event.get("queried_ticker") or "").strip().upper()
    if not queried_ticker and is_aggregator:
        source_event_id = str(event.get("source_event_id") or "")
        if "|" in source_event_id:
            queried_ticker = source_event_id.split("|", 1)[0].strip().upper()
        if not queried_ticker:
            source_tickers = event.get("tickers")
            if isinstance(source_tickers, list) and source_tickers:
                queried_ticker = str(source_tickers[0]).strip().upper()
    mapping_status = str(event.get("ticker_mapping_status") or "").strip()
    mapping_method = str(event.get("ticker_mapping_method") or "").strip()
    mapping_confidence = str(event.get("ticker_mapping_confidence") or "").strip()
    # Older captures predate query-scope diagnostics; do not upgrade them merely
    # because a ticker appears in the source record.
    if is_aggregator:
        mapping_status = mapping_status or "unverified_query_scope"
        mapping_method = mapping_method or "per_ticker_yahoo_rss_query"
        mapping_confidence = mapping_confidence or "unverified"
    return {
        "queried_ticker": queried_ticker,
        "ticker_mapping_method": mapping_method,
        "ticker_mapping_status": mapping_status,
        "ticker_mapping_confidence": mapping_confidence,
    }


def _queue_row(event: dict[str, Any], *, mapping_required: bool) -> dict[str, Any]:
    source_tickers = event.get("tickers", [])
    if not isinstance(source_tickers, list):
        source_tickers = []
    reviewed_tickers = event.get("ticker_mapping_reviewed_tickers")
    proposed_tickers = (
        reviewed_tickers
        if _mapping_is_reviewed(event) and isinstance(reviewed_tickers, list)
        else source_tickers
    )
    return {
        "event_id": event.get("event_id", ""),
        "event_version_id": event.get("event_version_id", ""),
        "event_type": event.get("event_type", ""),
        "headline": event.get("headline", ""),
        "source": event.get("source", ""),
        "source_url": event.get("source_url", ""),
        "published_at_utc": event.get("published_at_utc", ""),
        "first_seen_at_utc": event.get("first_seen_at_utc", ""),
        "content_hash": event.get("content_hash", ""),
        "market_scope": event.get("market_scope", ""),
        "tickers_json": json.dumps(source_tickers, ensure_ascii=False),
        "sectors_json": json.dumps(event.get("sectors", []), ensure_ascii=False),
        **_mapping_source_fields(event),
        "mapping_review_status": "pending" if mapping_required else "not_required",
        "mapped_tickers_json": json.dumps(proposed_tickers, ensure_ascii=False),
        "mapping_reviewed_at_utc": "",
        "mapping_reviewer_id": "",
        "mapping_rationale": "",
        "mapping_schema_version": "1.0",
        "archive_label_review_status": event.get("label_review_status", ""),
        "archive_direction_score": event.get("direction_score", ""),
        "archive_impact_score": event.get("impact_score", ""),
        # These are a new review form. Existing archive annotations remain visible
        # above but are never implicitly re-submitted by a mapping-only review.
        "direction_score": "",
        "impact_score": "",
        "label_review_status": "pending",
        "label_reviewed_at_utc": "",
        "label_rationale": "",
        "labeler_id": "",
        "reviewer_id": "",
        "label_schema_version": "1.0",
    }


def _round_robin_by_family(candidates: list[dict[str, Any]], max_rows: int) -> list[dict[str, Any]]:
    groups: dict[tuple[int, str, str], list[dict[str, Any]]] = {}
    for row in candidates:
        kind = str(row.get("event_type") or "unknown")
        source = str(row.get("source") or "unknown")
        key = (_TYPE_PRIORITY.get(kind, 99), kind, source)
        groups.setdefault(key, []).append(row)
    ordered_keys = sorted(groups)
    for key in ordered_keys:
        groups[key].sort(
            key=lambda row: (
                str(row.get("published_at_utc") or ""),
                str(row.get("first_seen_at_utc") or ""),
                str(row.get("event_version_id") or ""),
            ),
            reverse=True,
        )
    output: list[dict[str, Any]] = []
    positions = {key: 0 for key in ordered_keys}
    while True:
        added_in_round = False
        for key in ordered_keys:
            if max_rows and len(output) >= max_rows:
                return output
            pos = positions[key]
            if pos < len(groups[key]):
                output.append(groups[key][pos])
                positions[key] = pos + 1
                added_in_round = True
        if not added_in_round:
            return output


def build_annotation_queue(
    archive: list[dict[str, Any]],
    *,
    as_of: str,
    max_age_days: float = 30,
    max_rows: int = 100,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cutoff = _timestamp(as_of, "as_of")
    if isinstance(max_age_days, bool) or not isinstance(max_age_days, (int, float)) or max_age_days < 0:
        raise ValueError("max_age_days must be a non-negative number")
    if isinstance(max_rows, bool) or not isinstance(max_rows, int) or max_rows < 0:
        raise ValueError("max_rows must be a non-negative integer; 0 means unlimited")
    max_age = timedelta(days=float(max_age_days))
    grouped: dict[str, list[tuple[datetime, str, dict[str, Any]]]] = {}
    bad_first_seen: set[str] = set()
    excluded = {
        "invalid_timestamps": 0,
        "not_yet_available": 0,
        "stale": 0,
        "already_reviewed": 0,
        "ambiguous_first_seen": 0,
        "missing_event_id": 0,
        "missing_event_version_id": 0,
    }
    archive_rows = 0
    for source in archive:
        archive_rows += 1
        if not isinstance(source, dict):
            excluded["invalid_timestamps"] += 1
            continue
        event_id = str(source.get("event_id") or "").strip()
        if not event_id:
            excluded["missing_event_id"] += 1
            continue
        try:
            first_seen = _timestamp(source.get("first_seen_at_utc"), "first_seen_at_utc")
        except ValueError:
            bad_first_seen.add(event_id)
            continue
        version_id = str(source.get("event_version_id") or "").strip()
        grouped.setdefault(event_id, []).append((first_seen, version_id, dict(source)))

    candidates: list[dict[str, Any]] = []
    deduplicated_later_versions = 0
    for event_id, versions in grouped.items():
        if event_id in bad_first_seen:
            excluded["invalid_timestamps"] += 1
            continue
        versions.sort(key=lambda item: (item[0], item[1]))
        earliest_time = versions[0][0]
        earliest = [item for item in versions if item[0] == earliest_time]
        earliest_version_ids = {item[1] for item in earliest}
        if len(earliest_version_ids) > 1:
            excluded["ambiguous_first_seen"] += 1
            continue
        first_seen, version_id, event = earliest[0]
        deduplicated_later_versions += max(0, len(versions) - 1)
        if not version_id:
            excluded["missing_event_version_id"] += 1
            continue
        labels_done = str(event.get("label_review_status") or "").strip().lower() in {"reviewed", "validated"}
        mapping_done = _mapping_is_reviewed(event)
        mapping_required = _is_aggregator_company_event(event) and not mapping_done
        if labels_done and not mapping_required:
            excluded["already_reviewed"] += 1
            continue
        try:
            published = _timestamp(event.get("published_at_utc"), "published_at_utc")
        except ValueError:
            excluded["invalid_timestamps"] += 1
            continue
        if published > cutoff or first_seen > cutoff or first_seen < published:
            excluded["not_yet_available"] += 1
            continue
        if cutoff - published > max_age:
            excluded["stale"] += 1
            continue
        candidates.append(_queue_row(event, mapping_required=mapping_required))

    queue = _round_robin_by_family(candidates, max_rows)
    return queue, {
        "status": "queue_created" if queue else "no_events_to_review",
        "as_of_utc": cutoff.isoformat().replace("+00:00", "Z"),
        "max_age_days": float(max_age_days),
        "max_rows": max_rows,
        "archive_rows": archive_rows,
        "unique_event_ids": len(grouped),
        "eligible_candidate_count": len(candidates),
        "queue_rows": len(queue),
        "deferred_rows": max(0, len(candidates) - len(queue)),
        "deduplicated_later_versions": deduplicated_later_versions,
        "queue_selection_policy": (
            "earliest source version per event ID; round-robin by event family/source; "
            "newest published events first within each family/source"
        ),
        "excluded_counts": excluded,
        "labels_generated": False,
        "review_status_set_to_pending": True,
        "research_only": True,
        "limitations": [
            "This file is an annotation work queue, not reviewed data.",
            "Yahoo Finance query ticker is not proof of company relevance; review mapping fields separately.",
            "Do not change pending to reviewed until a real review is completed with provenance.",
            "Use only the archived source version; do not use future returns or later information.",
            "A reviewed mapping completed after an entry decision is retrospective and is not valid evidence of information available at that decision.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--as-of", required=True, help="Timezone-aware ISO-8601 timestamp")
    parser.add_argument("--max-age-days", type=float, default=30)
    parser.add_argument("--max-rows", type=int, default=100, help="Maximum queue rows; 0 means unlimited")
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args(argv)
    outputs = [Path(args.output), Path(args.report)]
    if any(path.exists() for path in outputs):
        parser.error("refusing to overwrite an existing queue or report")
    try:
        archive = json.loads(Path(args.archive).read_text(encoding="utf-8"))
        if not isinstance(archive, list):
            raise ValueError("archive must be a JSON array")
        queue, report = build_annotation_queue(
            archive, as_of=args.as_of, max_age_days=args.max_age_days, max_rows=args.max_rows
        )
        outputs[0].parent.mkdir(parents=True, exist_ok=True)
        outputs[1].parent.mkdir(parents=True, exist_ok=True)
        with outputs[0].open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(queue)
        outputs[1].write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Created {len(queue)} pending annotation rows; no labels were generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
