"""Coverage and leakage audit for normalized point-in-time event records."""
from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import Any, Iterable, Mapping

from tools.research.pit_event_eligibility import event_eligibility


_TEMPORAL_FAILURES = {
    "invalid_decision_timestamp",
    "published_after_decision",
    "first_seen_after_decision",
    "first_seen_before_publication",
    "update_after_decision",
    "update_seen_before_update",
}


def audit_event_coverage(
    events: Iterable[Mapping[str, Any]],
    decision_at: str,
    *,
    max_age_by_type: Mapping[str, timedelta] | None = None,
    expected_sources: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Summarize eligibility, expected-source coverage, missingness, and leakage.

    expected_sources is an optional list of source identifiers expected in this
    capture. It is a strict presence check, not a claim that a source's feed is
    historically complete. An empty batch always fails closed with fail_no_data.
    """
    rows = list(events)
    family_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    eligible_counts: Counter[str] = Counter()
    version_ids: list[str] = []
    eligible_total = 0

    for event in rows:
        family = str(event.get("event_type") or "unknown")
        family_counts[family] += 1
        status = str(event.get("availability_status") or "status_missing")
        status_counts[status] += 1
        version_id = str(event.get("event_version_id") or event.get("event_id") or "")
        if version_id:
            version_ids.append(version_id)

        if status != "available":
            eligible, reason = False, f"availability_{status}"
        else:
            max_age = (max_age_by_type or {}).get(family)
            eligible, reason = event_eligibility(event, decision_at, max_age=max_age)
        reason_counts[reason] += 1
        if eligible:
            eligible_total += 1
            eligible_counts[family] += 1

    duplicate_count = len(version_ids) - len(set(version_ids))
    data_failure_reasons = {
        "missing_or_invalid_required_timestamp",
        "unverifiable_update_timestamp",
        "update_seen_before_update",
    }
    has_missing = (
        any(reason.startswith("availability_") for reason in reason_counts)
        or any(reason in data_failure_reasons for reason in reason_counts)
    )
    has_temporal = any(reason in _TEMPORAL_FAILURES for reason in reason_counts)
    has_stale = "stale_event" in reason_counts

    seen_sources = sorted({
        str(event.get("source") or "").strip().lower()
        for event in rows
        if str(event.get("source") or "").strip()
    })
    expected = sorted({
        str(source).strip().lower()
        for source in (expected_sources or [])
        if str(source).strip()
    })
    missing_sources = sorted(set(expected) - set(seen_sources))

    flags: list[str] = []
    if not rows:
        flags.append("fail_no_data")
    if missing_sources:
        flags.append("fail_source_coverage")
    if has_temporal:
        flags.append("fail_temporal_integrity")
    if has_stale:
        flags.append("fail_stale_events")
    if has_missing:
        flags.append("fail_missing_data")
    if duplicate_count:
        flags.append("fail_duplicates")
    audit_status = flags[0] if flags else "pass"

    total = len(rows)
    return {
        "decision_at_utc": decision_at,
        "total_events": total,
        "eligible_events": eligible_total,
        "ineligible_events": total - eligible_total,
        "eligible_rate": eligible_total / total if total else 0.0,
        "duplicate_event_id_count": duplicate_count,
        "duplicate_event_version_id_count": duplicate_count,
        "event_type_counts": dict(sorted(family_counts.items())),
        "eligible_by_event_type": dict(sorted(eligible_counts.items())),
        "availability_status_counts": dict(sorted(status_counts.items())),
        "eligibility_reason_counts": dict(sorted(reason_counts.items())),
        "expected_sources": expected,
        "observed_sources": seen_sources,
        "missing_sources": missing_sources,
        "audit_flags": flags,
        "audit_status": audit_status,
    }
