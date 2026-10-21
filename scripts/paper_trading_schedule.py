#!/usr/bin/env python3
"""DST-safe gate for the scheduled end-of-day paper-trading run.

Two UTC cron entries cover US daylight-saving and standard time. Exactly one
maps into the 16:00 ET hour on a given date; the other must be skipped.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")


def should_run_eod(now: datetime | None = None) -> bool:
    """Return true only on weekdays during the 16:00–16:59 New York hour."""
    local_now = datetime.now(NEW_YORK) if now is None else now.astimezone(NEW_YORK)
    return local_now.weekday() < 5 and local_now.hour == 16


if __name__ == "__main__":
    now = datetime.now(NEW_YORK)
    allowed = should_run_eod(now)
    print(f"ET now={now.isoformat()} allowed={allowed}")
    print("true" if allowed else "false")
