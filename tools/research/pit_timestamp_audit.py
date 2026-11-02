#!/usr/bin/env python3
"""PIT timestamp audit for SEC filings and macro vintages."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
import pandas as pd


def parse_utc(value):
    if value is None or str(value).strip() == "":
        return None
    dt = pd.Timestamp(value)
    if dt.tzinfo is None:
        return None
    return dt.tz_convert("UTC")


def classify_sec(acceptance, first_public_evidence=None, decision_at=None):
    """acceptanceDateTime alone never proves first public availability."""
    acc = parse_utc(acceptance)
    first = parse_utc((first_public_evidence or {}).get("first_public_at"))
    verified = bool(first_public_evidence and first_public_evidence.get("source") and first)
    return {
        "acceptance_at": acc.isoformat().replace("+00:00", "Z") if acc else None,
        "first_public_at": first.isoformat().replace("+00:00", "Z") if first else None,
        "timestamp_confidence": "verified" if verified else "unverified",
        "pit_eligible": bool(verified and decision_at and first and parse_utc(decision_at) >= first),
        "market_usable_at": first.isoformat().replace("+00:00", "Z") if first else None,
    }


def session_rule(published_at, market_close_hour=16, trading_day=True):
    """Return BEFORE_CLOSE / AFTER_CLOSE / NON_TRADING for explicit handling."""
    dt = parse_utc(published_at)
    if dt is None:
        return "UNKNOWN"
    ny = dt.tz_convert("America/New_York")
    if not trading_day:
        return "NON_TRADING"
    return "AFTER_CLOSE" if ny.hour >= market_close_hour else "BEFORE_CLOSE"


@dataclass(frozen=True)
class VintageRecord:
    series_id: str
    observation_date: str
    release_date: str | None
    release_timestamp: str | None
    realtime_start: str | None
    realtime_end: str | None
    first_release_value: float | None
    revised_value: float | None
    source: str
    vintage_verified: bool
    pit_eligible: bool


def split_vintage(series_id, observation_date, vintages):
    """vintages: list of dicts with realtime_start, value, release_timestamp.
    First vintage is first-release; later vintages are revisions; never overwrite."""
    ordered = sorted(vintages, key=lambda x: str(x.get("realtime_start") or ""))
    first = ordered[0] if ordered else {}
    revised = ordered[-1] if len(ordered) > 1 else None
    verified = bool(first.get("realtime_start") and first.get("release_timestamp"))
    return VintageRecord(
        series_id=series_id, observation_date=str(observation_date),
        release_date=str(first.get("release_timestamp"))[:10] if first.get("release_timestamp") else None,
        release_timestamp=first.get("release_timestamp"), realtime_start=first.get("realtime_start"),
        realtime_end=ordered[-1].get("realtime_end") if ordered else None,
        first_release_value=first.get("value"), revised_value=revised.get("value") if revised else None,
        source=str(first.get("source") or "FRED/ALFRED"),
        vintage_verified=verified, pit_eligible=verified)
