"""Create a human-review queue for recent PIT event labels without generating labels."""
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
    "market_scope", "tickers_json", "sectors_json", "direction_score",
    "impact_score", "label_review_status", "label_reviewed_at_utc",
    "label_rationale", "labeler_id", "reviewer_id", "label_schema_version",
]


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


def build_annotation_queue(
    archive: list[dict[str, Any]],
    *,
    as_of: str,
    max_age_days: float = 30,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cutoff = _timestamp(as_of, "as_of")
    if isinstance(max_age_days, bool) or not isinstance(max_age_days, (int, float)) or max_age_days < 0:
        raise ValueError("max_age_days must be a non-negative number")
    max_age = timedelta(days=float(max_age_days))
    queue: list[dict[str, Any]] = []
    excluded = {"invalid_timestamps": 0, "not_yet_available": 0, "stale": 0, "already_reviewed": 0}
    seen: set[str] = set()
    for event in archive:
        if not isinstance(event, dict):
            excluded["invalid_timestamps"] += 1
            continue
        if event.get("label_review_status") in {"reviewed", "validated"}:
            excluded["already_reviewed"] += 1
            continue
        try:
            published = _timestamp(event.get("published_at_utc"), "published_at_utc")
            first_seen = _timestamp(event.get("first_seen_at_utc"), "first_seen_at_utc")
        except ValueError:
            excluded["invalid_timestamps"] += 1
            continue
        if published > cutoff or first_seen > cutoff or first_seen < published:
            excluded["not_yet_available"] += 1
            continue
        if cutoff - published > max_age:
            excluded["stale"] += 1
            continue
        version = str(event.get("event_version_id") or event.get("event_id") or "")
        if not version or version in seen:
            continue
        seen.add(version)
        queue.append({
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
            "tickers_json": json.dumps(event.get("tickers", []), ensure_ascii=False),
            "sectors_json": json.dumps(event.get("sectors", []), ensure_ascii=False),
            "direction_score": "",
            "impact_score": "",
            "label_review_status": "pending",
            "label_reviewed_at_utc": "",
            "label_rationale": "",
            "labeler_id": "",
            "reviewer_id": "",
            "label_schema_version": "1.0",
        })
    queue.sort(key=lambda row: (row["published_at_utc"], row["event_version_id"]))
    return queue, {
        "status": "queue_created" if queue else "no_events_to_review",
        "as_of_utc": cutoff.isoformat().replace("+00:00", "Z"),
        "max_age_days": float(max_age_days),
        "queue_rows": len(queue),
        "excluded_counts": excluded,
        "labels_generated": False,
        "review_status_set_to_pending": True,
        "research_only": True,
        "limitations": [
            "This file is an annotation work queue, not reviewed data.",
            "Do not change pending to reviewed/validated until a real review is completed.",
            "Use only the archived source version and do not use future returns or later information.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--as-of", required=True, help="Timezone-aware ISO-8601 timestamp")
    parser.add_argument("--max-age-days", type=float, default=30)
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
        queue, report = build_annotation_queue(archive, as_of=args.as_of, max_age_days=args.max_age_days)
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
