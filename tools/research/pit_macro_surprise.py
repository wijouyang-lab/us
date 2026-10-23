"""Point-in-time validation for macro actual-versus-consensus surprises.

The helper does not fetch or forecast data. It computes a surprise only when
both values are numeric and the consensus timestamp proves the estimate existed
no later than the verified actual publication time and the decision timestamp.
"""
from __future__ import annotations

from typing import Any, Mapping

from tools.research.pit_event_eligibility import _parse_aware_timestamp


def macro_surprise(
    release: Mapping[str, Any],
    decision_at: str,
) -> dict[str, Any]:
    """Return an auditable surprise result or an explicit ineligibility reason."""
    actual_time = _parse_aware_timestamp(
        release.get("published_at_utc") or release.get("actual_release_at_utc")
    )
    first_seen = _parse_aware_timestamp(release.get("first_seen_at_utc"))
    consensus_time = _parse_aware_timestamp(release.get("consensus_asof_utc"))
    vintage_raw = release.get("vintage_at_utc")
    vintage_time = _parse_aware_timestamp(vintage_raw) if vintage_raw is not None else None
    decision = _parse_aware_timestamp(decision_at)
    if decision is None:
        return {"eligible": False, "reason": "invalid_decision_timestamp", "surprise": None}
    availability = release.get("availability_status")
    if availability is not None and availability != "available":
        return {
            "eligible": False,
            "reason": f"event_unavailable:{availability}",
            "surprise": None,
        }
    if actual_time is None:
        return {"eligible": False, "reason": "actual_release_timestamp_missing", "surprise": None}
    if first_seen is None:
        return {"eligible": False, "reason": "first_seen_timestamp_missing", "surprise": None}
    if actual_time > decision:
        return {"eligible": False, "reason": "actual_release_after_decision", "surprise": None}
    if first_seen > decision:
        return {"eligible": False, "reason": "first_seen_after_decision", "surprise": None}
    if first_seen < actual_time:
        return {"eligible": False, "reason": "first_seen_before_publication", "surprise": None}
    if vintage_raw is not None:
        if vintage_time is None:
            return {"eligible": False, "reason": "vintage_timestamp_invalid", "surprise": None}
        if vintage_time > decision:
            return {"eligible": False, "reason": "vintage_after_decision", "surprise": None}
        if vintage_time > first_seen:
            return {"eligible": False, "reason": "vintage_after_first_seen", "surprise": None}
    if consensus_time is None:
        return {"eligible": False, "reason": "consensus_timestamp_missing", "surprise": None}
    if consensus_time > actual_time:
        return {"eligible": False, "reason": "consensus_after_actual_release", "surprise": None}
    if consensus_time > decision:
        return {"eligible": False, "reason": "consensus_after_decision", "surprise": None}

    try:
        actual = float(release.get("actual_value", release.get("value")))
        consensus = float(release.get("consensus_value"))
    except (TypeError, ValueError):
        return {"eligible": False, "reason": "actual_or_consensus_not_numeric", "surprise": None}
    if not (actual == actual and consensus == consensus):
        return {"eligible": False, "reason": "actual_or_consensus_not_finite", "surprise": None}
    if actual in (float("inf"), float("-inf")) or consensus in (float("inf"), float("-inf")):
        return {"eligible": False, "reason": "actual_or_consensus_not_finite", "surprise": None}

    return {
        "eligible": True,
        "reason": "eligible",
        "actual_value": actual,
        "consensus_value": consensus,
        "surprise": actual - consensus,
        "published_at_utc": actual_time.isoformat().replace("+00:00", "Z"),
        "consensus_asof_utc": consensus_time.isoformat().replace("+00:00", "Z"),
        "vintage_at_utc": vintage_time.isoformat().replace("+00:00", "Z") if vintage_time else None,
    }
