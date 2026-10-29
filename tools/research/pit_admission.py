#!/usr/bin/env python3
"""Explicit PIT admission decision; recalculates from evidence, never trusts flags."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

ALLOWED_SOURCE = {"official_fed_page", "verified_sgml"}
ALLOWED_PUBLISHED = {"official_release_time_in_page", "verified_sgml_header"}
ALLOWED_DECISION = {"strategy_log", "pre_registered_decision_time"}


def _dt(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo is not None else None


def admit(record: dict[str, Any]) -> dict[str, Any]:
    reasons = []
    if record.get("is_simulated") is True:
        reasons.append("simulated_record")
    elif record.get("is_simulated") is not False:
        reasons.append("simulation_flag_missing")
    if record.get("is_historical_backfill"):
        reasons.append("historical_backfill")
    if record.get("parse_status") != "exact":
        reasons.append("parse_status_not_exact")
    if record.get("observation_kind") == "late_observation_of_old_event" or record.get("pit_status") == "late_observation_not_pit":
        reasons.append("late_observation")
    if record.get("source_evidence") not in ALLOWED_SOURCE:
        reasons.append("source_evidence_not_verified")
    if record.get("published_at_evidence") not in ALLOWED_PUBLISHED:
        reasons.append("published_at_evidence_missing")
    published = _dt(record.get("published_at"))
    first_seen = _dt(record.get("first_seen_at_utc"))
    research_ready = _dt(record.get("research_ready_at_utc"))
    if published is None:
        reasons.append("published_time_missing_or_naive")
    if first_seen is None:
        reasons.append("first_seen_missing_or_naive")
    if research_ready is None:
        reasons.append("research_ready_missing_or_naive")
    if published and first_seen:
        if published > first_seen:
            reasons.append("published_after_first_seen")
        elif first_seen - published > timedelta(hours=1):
            reasons.append("observation_lag_exceeds_1h")
    decision = _dt(record.get("decision_at_utc"))
    if decision is None:
        reasons.append("decision_time_missing")
    if record.get("decision_evidence") not in ALLOWED_DECISION:
        reasons.append("decision_evidence_missing")
    if decision and research_ready and decision < research_ready:
        reasons.append("decision_before_research_ready")
    return {
        "admitted": not reasons,
        "reasons": reasons,
        "event_id": record.get("event_id"),
        "published_at": record.get("published_at"),
        "first_seen_at_utc": record.get("first_seen_at_utc"),
        "research_ready_at_utc": record.get("research_ready_at_utc"),
        "decision_at_utc": record.get("decision_at_utc"),
        "source_evidence": record.get("source_evidence"),
        "published_at_evidence": record.get("published_at_evidence"),
        "decision_evidence": record.get("decision_evidence"),
    }
