"""Point-in-time event features for research, with explicit coverage semantics.

No network calls and no production ranking integration. A missing or unmapped
event family is reported as missing coverage, never converted to a neutral zero.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Iterable, Mapping

from tools.research.pit_event_eligibility import _parse_aware_timestamp, event_eligibility


def build_event_features(
    events: Iterable[Mapping[str, Any]],
    *,
    ticker: str,
    decision_at: str,
    sector: str | None = None,
    max_age_by_type: Mapping[str, timedelta] | None = None,
) -> dict[str, Any]:
    """Build auditable event-family counts for one ticker and decision timestamp.

    Company-specific events require an explicit ticker match. Sector events
    require an explicit sector match. Market-wide event families are included
    only when the source record explicitly sets market_scope to market.
    """
    decision = _parse_aware_timestamp(decision_at)
    if decision is None:
        raise ValueError("decision_at must be a timezone-aware ISO-8601 timestamp")
    ticker_value = str(ticker or "").strip().upper().replace("$", "")
    if not ticker_value:
        raise ValueError("ticker is required")
    sector_value = str(sector or "").strip().lower()
    rows = [dict(row) for row in events]

    family_totals: dict[str, int] = {}
    family_eligible: dict[str, int] = {}
    family_missing: dict[str, int] = {}
    family_latest_age: dict[str, float] = {}
    eligible_ids: dict[str, list[str]] = {}
    rejection_reasons: dict[str, int] = {}

    for row in rows:
        family = str(row.get("event_type") or "unknown")
        relevant = (
            ticker_value in {
                str(value).strip().upper().replace("$", "")
                for value in (row.get("tickers") or [])
            }
            or (bool(sector_value) and sector_value in {
                str(value).strip().lower()
                for value in (row.get("sectors") or [])
            })
            or str(row.get("market_scope") or "").strip().lower() == "market"
        )
        if not relevant:
            continue
        family_totals[family] = family_totals.get(family, 0) + 1

        status = str(row.get("availability_status") or "status_missing")
        if status != "available":
            reason = f"availability_{status}"
            family_missing[family] = family_missing.get(family, 0) + 1
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
            continue

        eligible, reason = event_eligibility(
            row,
            decision_at,
            max_age=(max_age_by_type or {}).get(family),
        )
        if not eligible:
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
            if reason in {
                "missing_or_invalid_required_timestamp",
                "unverifiable_update_timestamp",
                "first_seen_before_publication",
            }:
                family_missing[family] = family_missing.get(family, 0) + 1
            continue

        published = _parse_aware_timestamp(row.get("published_at_utc"))
        age_seconds = (decision - published).total_seconds() if published else None
        family_eligible[family] = family_eligible.get(family, 0) + 1
        if age_seconds is not None:
            family_latest_age[family] = min(
                family_latest_age.get(family, age_seconds), age_seconds
            )
        event_id = str(row.get("event_version_id") or row.get("event_id") or "")
        if event_id:
            eligible_ids.setdefault(family, []).append(event_id)

    families = sorted(set(family_totals) | set(family_eligible) | set(family_missing))
    family_features: dict[str, Any] = {}
    for family in families:
        eligible_count = family_eligible.get(family, 0)
        family_features[family] = {
            "coverage_status": "available" if eligible_count else "missing",
            "observed_event_count": family_totals.get(family, 0),
            "eligible_event_count": eligible_count,
            "missing_event_count": family_missing.get(family, 0),
            "latest_event_age_seconds": family_latest_age.get(family),
            "eligible_event_ids": sorted(set(eligible_ids.get(family, []))),
        }

    return {
        "ticker": ticker_value,
        "sector": sector_value or None,
        "decision_at_utc": decision.isoformat().replace("+00:00", "Z"),
        "feature_asof_utc": decision.isoformat().replace("+00:00", "Z"),
        "event_family_count": len(families),
        "event_families": family_features,
        "eligible_event_ids": sorted({
            event_id for values in eligible_ids.values() for event_id in values
        }),
        "rejection_reason_counts": dict(sorted(rejection_reasons.items())),
        "coverage_status": (
            "available" if any(family_eligible.values()) else "missing"
        ),
        "research_only": True,
    }
