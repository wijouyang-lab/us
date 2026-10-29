#!/usr/bin/env python3
"""Explicit PIT admission decision, separate from capture status."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

ALLOWED_EVIDENCE = {"official_fed_page", "verified_sgml"}


def _dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def admit(record: dict[str, Any], *, decision_at: str | None = None) -> dict[str, Any]:
    reasons = []
    if record.get("is_simulated"):
        reasons.append("simulated_record")
    if record.get("is_historical_backfill"):
        reasons.append("historical_backfill")
    if record.get("parse_status") != "exact":
        reasons.append("parse_status_not_exact")
    if record.get("observation_kind") == "late_observation_of_old_event" or record.get("pit_status") == "late_observation_not_pit":
        reasons.append("late_observation")
    published = _dt(record.get("published_at"))
    first_seen = _dt(record.get("first_seen_at_utc"))
    if published is None:
        reasons.append("published_time_missing")
    if first_seen is None:
        reasons.append("first_seen_missing")
    if published and first_seen:
        if published > first_seen:
            reasons.append("published_after_first_seen")
        elif first_seen - published > timedelta(hours=1):
            reasons.append("observation_lag_exceeds_1h")
    if record.get("source_evidence") not in ALLOWED_EVIDENCE:
        reasons.append("source_evidence_not_verified")
    decision = _dt(decision_at) or _dt(record.get("decision_at_utc"))
    if decision is None:
        reasons.append("decision_time_missing")
    elif first_seen and decision < first_seen:
        reasons.append("decision_before_first_seen")
    research_ready = _dt(record.get("research_ready_at_utc")) or first_seen
    return {
        "admitted": not reasons,
        "reasons": reasons,
        "event_id": record.get("event_id"),
        "published_at": record.get("published_at"),
        "first_seen_at_utc": record.get("first_seen_at_utc"),
        "research_ready_at_utc": research_ready.isoformat().replace("+00:00", "Z") if research_ready else None,
        "decision_at_utc": decision.isoformat().replace("+00:00", "Z") if decision else None,
        "source_evidence": record.get("source_evidence"),
    }
