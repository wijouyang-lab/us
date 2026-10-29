"""Point-in-time eligibility checks for research event records.

Research-only utility. It does not fetch events or alter production scanner behavior.
All timestamps must be timezone-aware; naive timestamps are rejected rather than
implicitly interpreted in the machine's local timezone.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from tools.research.pit_admission import admit


def _parse_aware_timestamp(value: Any) -> datetime | None:
    """Parse an ISO timestamp or datetime; return UTC, or None if invalid/naive."""
    if value is None:
        return None
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            value = datetime.fromisoformat(raw)
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def event_eligibility(
    event: Mapping[str, Any],
    decision_at: datetime | str,
    *,
    max_age: timedelta | None = None,
) -> tuple[bool, str]:
    """Return (eligible, reason) using only timestamps known at decision time."""
    decision = _parse_aware_timestamp(decision_at)
    if decision is None:
        return False, "invalid_decision_timestamp"

    published = _parse_aware_timestamp(event.get("published_at_utc"))
    first_seen = _parse_aware_timestamp(event.get("first_seen_at_utc"))
    if published is None or first_seen is None:
        return False, "missing_or_invalid_required_timestamp"

    if published > decision:
        return False, "published_after_decision"
    if first_seen > decision:
        return False, "first_seen_after_decision"
    if first_seen < published:
        return False, "first_seen_before_publication"

    updated_value = event.get("updated_at_utc")
    if updated_value is not None:
        updated = _parse_aware_timestamp(updated_value)
        update_seen = _parse_aware_timestamp(event.get("update_first_seen_at_utc"))
        if updated is None or update_seen is None:
            return False, "unverifiable_update_timestamp"
        if updated > decision or update_seen > decision:
            return False, "update_after_decision"
        if update_seen < updated:
            return False, "update_seen_before_update"

    if max_age is not None:
        if max_age < timedelta(0):
            raise ValueError("max_age cannot be negative")
        if decision - published > max_age:
            return False, "stale_event"

    strict = admit({
        **dict(event),
        "published_at": event.get("published_at_utc"),
        "decision_at_utc": decision.isoformat().replace("+00:00", "Z"),
    })
    if not strict["admitted"]:
        return False, "pit_admission:" + strict["reasons"][0]

    return True, "eligible"
