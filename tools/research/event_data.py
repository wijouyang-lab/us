#!/usr/bin/env python3
"""Canonical event records with explicit publication and PIT confidence."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import pandas as pd

UTC = timezone.utc


@dataclass(frozen=True)
class Event:
    event_id: str
    ticker: str | None
    cik: str | None
    event_type: str
    event_subtype: str
    source: str
    published_at: str | None
    event_date: str | None
    effective_date: str | None
    period_end: str | None
    value: float | None
    previous_value: float | None
    revised_value: float | None
    source_confidence: str
    timestamp_confidence: str
    pit_eligible: bool
    evidence_note: str

    def __post_init__(self):
        if self.published_at is not None:
            dt = datetime.fromisoformat(self.published_at.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                raise ValueError("published_at must be timezone-aware")
            object.__setattr__(self, "published_at", dt.astimezone(UTC).isoformat().replace("+00:00", "Z"))


def make_event(**kw) -> Event:
    return Event(**kw)


def dedupe(events: list[Event]) -> list[Event]:
    seen = {}
    for e in events:
        seen[e.event_id] = e
    return [seen[k] for k in sorted(seen)]


def next_trading_session(published_at: str | None, calendar: list, close_hour: int = 16) -> str | None:
    if published_at is None:
        return None
    dt = pd.Timestamp(published_at)
    if dt.tzinfo is None:
        raise ValueError("published_at must be timezone-aware")
    cal = [pd.Timestamp(x).normalize() for x in calendar]
    day = dt.tz_convert("America/New_York").normalize().tz_localize(None)
    after_close = dt.tz_convert("America/New_York").hour >= close_hour
    later = [x for x in cal if x > day] if after_close or day not in cal else [x for x in cal if x >= day]
    if after_close or day not in cal:
        later = [x for x in cal if x > day]
    return str(later[0].date()) if later else None


def as_dict(e: Event):
    return asdict(e)
