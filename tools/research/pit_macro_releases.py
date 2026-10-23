"""Point-in-time normalizer for official macro release observations.

This parser accepts caller-supplied release metadata only; it does not fetch data.
Scheduled release times and observation periods are not substitutes for actual
publication timestamps. Missing actual timestamps remain ineligible.
"""
from __future__ import annotations

from typing import Any, Mapping

from tools.research.pit_event_records import normalize_event


def normalize_macro_release(
    release: Mapping[str, Any],
    *,
    first_seen_at_utc: str,
    source: str,
    source_quality: str = "official",
) -> dict[str, Any]:
    """Normalize one macro release vintage without filling missing timestamps.

    Required identifiers: series_id and observation_period. actual_release_at_utc
    must represent verified publication time, not a scheduled release time.
    """
    series_id = str(release.get("series_id") or "").strip()
    observation_period = str(release.get("observation_period") or "").strip()
    if not series_id:
        raise ValueError("series_id is required")
    if not observation_period:
        raise ValueError("observation_period is required")

    actual_release = release.get("actual_release_at_utc")
    headline = str(release.get("headline") or series_id).strip()
    record = normalize_event(
        source=source,
        source_event_id=str(release.get("release_id") or f"{series_id}:{observation_period}"),
        event_type="macro_release",
        published_at_utc=actual_release,
        first_seen_at_utc=first_seen_at_utc,
        headline=headline,
        sectors=[],
        source_quality=source_quality,
        raw_payload={
            "series_id": series_id,
            "observation_period": observation_period,
            "value": release.get("value"),
            "units": release.get("units"),
            "release_id": release.get("release_id"),
            "actual_release_at_utc": actual_release,
        },
    )
    record["series_id"] = series_id
    record["observation_period"] = observation_period
    record["value"] = release.get("value")
    record["units"] = release.get("units")
    record["scheduled_release_at_utc"] = release.get("scheduled_release_at_utc")
    record["vintage_at_utc"] = release.get("vintage_at_utc")
    record["consensus_value"] = release.get("consensus_value")
    record["consensus_asof_utc"] = release.get("consensus_asof_utc")
    if not actual_release:
        record["availability_status"] = "timestamp_missing"
    return record
