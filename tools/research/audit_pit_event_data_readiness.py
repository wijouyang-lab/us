"""Audit whether a point-in-time event archive is ready for research evaluation.

This is a read-only, research-only data quality audit. It does not repair or
impute event records, collect data, or generate trading signals.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from tools.research.pit_event_eligibility import _parse_aware_timestamp, event_eligibility


def _load_array(path: str | Path, label: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {label} JSON: {exc}") from exc
    if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
        raise ValueError(f"{label} must be a JSON array of objects")
    return payload


def _valid_label(value: Any, low: float, high: float) -> bool:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(parsed) and low <= parsed <= high


def audit_event_archive(
    archive_path: str | Path,
    *,
    decisions_path: str | Path | None = None,
    audited_at: str | None = None,
) -> dict[str, Any]:
    events = _load_array(archive_path, "archive")
    if audited_at is None:
        audit_time = datetime.now(timezone.utc)
    else:
        audit_time = _parse_aware_timestamp(audited_at)
        if audit_time is None:
            raise ValueError("audited_at must be a timezone-aware ISO-8601 timestamp")

    decisions: list[datetime] = []
    if decisions_path:
        try:
            import pandas as pd
            frame = pd.read_csv(decisions_path, dtype=str)
        except Exception as exc:
            raise ValueError(f"cannot read decisions CSV: {exc}") from exc
        if "decision_at" not in frame.columns or frame.empty:
            raise ValueError("decisions CSV must contain at least one decision_at row")
        for raw in frame["decision_at"]:
            parsed = _parse_aware_timestamp(raw)
            if parsed is None:
                raise ValueError("all decision_at values must be timezone-aware ISO-8601 timestamps")
            decisions.append(parsed)
        decisions = sorted(set(decisions))

    family_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    availability_counts: Counter[str] = Counter()
    rejection_counts: Counter[str] = Counter()
    missing_fields: Counter[str] = Counter()
    timestamp_checks = Counter()
    label_counts = Counter()
    label_review_status_counts: Counter[str] = Counter()
    version_ids: list[str] = []
    eligible_by_decision: dict[str, int] = {d.isoformat().replace("+00:00", "Z"): 0 for d in decisions}

    for event in events:
        family = str(event.get("event_type") or "unknown")
        source = str(event.get("source") or "unknown")
        family_counts[family] += 1
        source_counts[source] += 1
        availability_counts[str(event.get("availability_status") or "missing_status")] += 1

        for field in ("event_id", "event_version_id", "source", "source_event_id",
                      "event_type", "published_at_utc", "first_seen_at_utc",
                      "source_quality", "content_hash", "source_url"):
            if event.get(field) in (None, ""):
                missing_fields[field] += 1

        source_url = event.get("source_url")
        if source_url not in (None, ""):
            try:
                parsed_url = urlsplit(str(source_url).strip())
                valid_source_url = (
                    parsed_url.scheme.lower() == "https"
                    and bool(parsed_url.hostname)
                    and parsed_url.username is None
                    and parsed_url.password is None
                )
            except ValueError:
                valid_source_url = False
            if not valid_source_url:
                timestamp_checks["invalid_source_url"] += 1

        for field in ("published_at_utc", "first_seen_at_utc", "updated_at_utc", "update_first_seen_at_utc"):
            raw = event.get(field)
            parsed = _parse_aware_timestamp(raw) if raw is not None else None
            if raw is not None and parsed is None:
                timestamp_checks[f"invalid_{field}"] += 1
            if field in {"published_at_utc", "first_seen_at_utc"} and parsed is None:
                timestamp_checks[f"missing_{field}"] += 1
        published = _parse_aware_timestamp(event.get("published_at_utc"))
        first_seen = _parse_aware_timestamp(event.get("first_seen_at_utc"))
        if published and first_seen:
            if first_seen < published:
                timestamp_checks["first_seen_before_publication"] += 1
            if published > audit_time:
                timestamp_checks["publication_after_audit_time"] += 1
            if first_seen > audit_time:
                timestamp_checks["first_seen_after_audit_time"] += 1
        if event.get("event_version_id"):
            version_ids.append(str(event["event_version_id"]))

        direction_ok = _valid_label(event.get("direction_score"), -1.0, 1.0)
        impact_ok = _valid_label(event.get("impact_score"), 0.0, 1.0)
        label_counts["direction_valid" if direction_ok else "direction_missing_or_invalid"] += 1
        label_counts["impact_valid" if impact_ok else "impact_missing_or_invalid"] += 1
        label_counts["both_labels_valid" if direction_ok and impact_ok else "not_fully_labeled"] += 1
        review_status = str(event.get("label_review_status") or "missing").strip().lower()
        label_review_status_counts[review_status] += 1
        reviewed_at = _parse_aware_timestamp(event.get("label_reviewed_at_utc"))
        reviewed = (
            direction_ok and impact_ok
            and review_status in {"reviewed", "validated"}
            and reviewed_at is not None
            and reviewed_at <= audit_time
        )
        if reviewed:
            label_counts["reviewed_labels"] += 1
        else:
            label_counts["unverified_label_provenance"] += 1
        if event.get("label_reviewed_at_utc") not in (None, "") and reviewed_at is None:
            timestamp_checks["invalid_label_reviewed_at_utc"] += 1
        elif reviewed_at is not None and reviewed_at > audit_time:
            timestamp_checks["label_review_after_audit_time"] += 1

        for decision in decisions:
            ok, reason = event_eligibility(event, decision)
            if ok:
                eligible_by_decision[decision.isoformat().replace("+00:00", "Z")] += 1
            else:
                rejection_counts[reason] += 1

    duplicate_version_count = len(version_ids) - len(set(version_ids))
    labelled = label_counts["reviewed_labels"]
    if not events:
        status = "fail_no_data"
    elif decisions and not any(eligible_by_decision.values()):
        status = "fail_no_pit_eligible_events"
    elif labelled == 0:
        status = "blocked_no_validated_labels"
    elif (
        timestamp_checks["missing_published_at_utc"]
        or timestamp_checks["missing_first_seen_at_utc"]
        or any(key.startswith("invalid_") for key in timestamp_checks)
        or timestamp_checks["first_seen_before_publication"]
        or timestamp_checks["publication_after_audit_time"]
        or timestamp_checks["first_seen_after_audit_time"]
        or duplicate_version_count
        or missing_fields["source_url"]
    ):
        status = "blocked_data_quality"
    else:
        status = "review_required"

    return {
        "schema_version": "1.0",
        "status": status,
        "archive_path": str(archive_path),
        "audit_time_utc": audit_time.isoformat().replace("+00:00", "Z"),
        "archive_event_version_rows": len(events),
        "unique_event_version_ids": len(set(version_ids)),
        "duplicate_event_version_id_count": duplicate_version_count,
        "event_families": dict(sorted(family_counts.items())),
        "sources": dict(sorted(source_counts.items())),
        "availability_statuses": dict(sorted(availability_counts.items())),
        "missing_required_fields": dict(sorted(missing_fields.items())),
        "timestamp_quality": dict(sorted(timestamp_checks.items())),
        "label_quality": {
            **dict(sorted(label_counts.items())),
            "review_status_counts": dict(sorted(label_review_status_counts.items())),
            "valid_direction_fraction": round(label_counts["direction_valid"] / len(events), 4) if events else 0.0,
            "valid_impact_fraction": round(label_counts["impact_valid"] / len(events), 4) if events else 0.0,
            "fully_labeled_fraction": round(label_counts["both_labels_valid"] / len(events), 4) if events else 0.0,
            "reviewed_label_fraction": round(label_counts["reviewed_labels"] / len(events), 4) if events else 0.0,
        },
        "pit_eligibility": {
            "decision_dates": len(decisions),
            "eligible_events_by_decision": eligible_by_decision,
            "rejection_reason_counts_across_decisions": dict(sorted(rejection_counts.items())),
        },
        "readiness_gates": {
            "archive_nonempty": bool(events),
            "version_ids_unique": duplicate_version_count == 0,
            "required_timestamps_present": not timestamp_checks["missing_published_at_utc"] and not timestamp_checks["missing_first_seen_at_utc"],
            "source_urls_present": missing_fields["source_url"] == 0,
            "source_urls_valid_https": timestamp_checks["invalid_source_url"] == 0,
            "all_timestamps_valid_and_not_future": not any(
                key.startswith("invalid_") or key.endswith("_after_audit_time")
                for key in timestamp_checks
            ),
            "all_first_seen_after_publication": timestamp_checks["first_seen_before_publication"] == 0,
            "validated_labels_present": labelled > 0,
            "label_review_provenance_present": labelled == label_counts["both_labels_valid"],
            "pit_eligible_for_at_least_one_decision": not decisions or any(eligible_by_decision.values()),
            "empirical_alpha_established": False,
            "production_activation_allowed": False,
        },
        "limitations": [
            "Presence and range checks do not prove that event labels were independently reviewed.",
            "A source identifier is not necessarily a retrievable source URL; verify provenance before research use.",
            "Historical first-seen timestamps are trustworthy only when captured prospectively or validated independently.",
            "Eligibility counts do not establish predictive power; use frozen chronological out-of-sample tests.",
            "This audit is read-only, research-only, and does not repair or impute records.",
        ],
        "research_only": True,
        "production_signal_generated": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--decisions", help="Optional CSV containing timezone-aware decision_at rows")
    parser.add_argument("--audited-at", help="Optional fixed timezone-aware audit timestamp for reproducibility")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = audit_event_archive(args.archive, decisions_path=args.decisions, audited_at=args.audited_at)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "archive_event_version_rows": result["archive_event_version_rows"],
        "fully_labeled_fraction": result["label_quality"]["fully_labeled_fraction"],
        "decision_dates": result["pit_eligibility"]["decision_dates"],
        "research_only": True,
        "production_signal_generated": False,
    }, indent=2, sort_keys=True))
    return 0 if result["status"] == "review_required" else 2


if __name__ == "__main__":
    raise SystemExit(main())
