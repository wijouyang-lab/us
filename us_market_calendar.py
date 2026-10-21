# -*- coding: utf-8 -*-
"""US equity market calendar helpers.

Single source of truth for Scan and Review:
  * NYSE trading days (holidays included)
  * regular / early-close session end times in America/New_York
  * DST-aware New York clock via zoneinfo
  * last completed regular session

The calendar itself comes from ``exchange_calendars`` (XNYS).  That package is
used because it is the only dependency already compatible with the project's
pandas 3.x runtime that exposes both NYSE holidays and early-close sessions.
If the calendar cannot be loaded, callers must fail closed instead of treating
the date as a normal trading day.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import pandas as pd


US_TZ = ZoneInfo("America/New_York")
CALENDAR_NAME = "XNYS"


class CalendarUnavailable(RuntimeError):
    """Raised when the exchange calendar cannot be loaded or queried."""


_CALENDAR = None


def _load_calendar():
    try:
        import exchange_calendars as xc
    except Exception as exc:  # pragma: no cover - exercised via monkeypatch
        raise CalendarUnavailable(
            "exchange_calendars is not installed; cannot determine NYSE sessions"
        ) from exc
    try:
        return xc.get_calendar(CALENDAR_NAME)
    except Exception as exc:  # pragma: no cover - exercised via monkeypatch
        raise CalendarUnavailable(
            "cannot load %s calendar: %s" % (CALENDAR_NAME, exc)
        ) from exc


def get_calendar():
    global _CALENDAR
    if _CALENDAR is None:
        _CALENDAR = _load_calendar()
    return _CALENDAR


def _as_us_datetime(value: dt.datetime | None = None) -> dt.datetime:
    if value is None:
        return dt.datetime.now(US_TZ)
    if value.tzinfo is None:
        return value.replace(tzinfo=US_TZ)
    return value.astimezone(US_TZ)


def is_trading_day(value: dt.date | dt.datetime | str) -> bool:
    """Return True when ``value`` is an NYSE regular session date."""
    if isinstance(value, dt.datetime):
        value = value.astimezone(US_TZ).date() if value.tzinfo else value.date()
    elif isinstance(value, str):
        value = dt.date.fromisoformat(value[:10])
    try:
        return bool(get_calendar().is_session(pd.Timestamp(value)))
    except CalendarUnavailable:
        raise
    except Exception as exc:
        raise CalendarUnavailable("cannot test NYSE session %s: %s" % (value, exc)) from exc


def session_close_et(value: dt.date | dt.datetime | str) -> dt.time | None:
    """NYSE close time in New York local time (13:00 on early-close days)."""
    if isinstance(value, dt.datetime):
        value = value.astimezone(US_TZ).date() if value.tzinfo else value.date()
    elif isinstance(value, str):
        value = dt.date.fromisoformat(value[:10])
    if not is_trading_day(value):
        return None
    try:
        close_utc = get_calendar().session_close(pd.Timestamp(value))
        return close_utc.tz_convert(US_TZ).time().replace(tzinfo=None)
    except CalendarUnavailable:
        raise
    except Exception as exc:
        raise CalendarUnavailable("cannot read NYSE close for %s: %s" % (value, exc)) from exc


def session_close_utc(value: dt.date | dt.datetime | str) -> dt.datetime | None:
    """NYSE close as an aware UTC datetime (useful for DST tests)."""
    if isinstance(value, dt.datetime):
        value = value.astimezone(US_TZ).date() if value.tzinfo else value.date()
    elif isinstance(value, str):
        value = dt.date.fromisoformat(value[:10])
    if not is_trading_day(value):
        return None
    try:
        return get_calendar().session_close(pd.Timestamp(value)).tz_convert(dt.timezone.utc)
    except CalendarUnavailable:
        raise
    except Exception as exc:
        raise CalendarUnavailable("cannot read NYSE close for %s: %s" % (value, exc)) from exc


def is_early_close(value: dt.date | dt.datetime | str) -> bool:
    close = session_close_et(value)
    return close is not None and close < dt.time(16, 0)


def market_session_state(asof: dt.datetime | None = None) -> str:
    """Return the same states used by Scan plus an explicit holiday state.

    States:
      MARKET_CLOSED_WEEKEND / MARKET_CLOSED_HOLIDAY /
      PREMARKET_NOT_STARTED / PREMARKET / REGULAR_SESSION / AFTER_HOURS
    """
    now = _as_us_datetime(asof)
    day = now.date()
    if not is_trading_day(day):
        return "MARKET_CLOSED_WEEKEND" if day.weekday() >= 5 else "MARKET_CLOSED_HOLIDAY"
    close = session_close_et(day)
    if close is None:
        # Defensive: is_trading_day() and session_close_et() must agree.
        raise CalendarUnavailable("NYSE session %s has no close time" % day)
    t = now.time()
    if t < dt.time(4, 0):
        return "PREMARKET_NOT_STARTED"
    if t < dt.time(9, 30):
        return "PREMARKET"
    if t < close:
        return "REGULAR_SESSION"
    return "AFTER_HOURS"


def last_completed_regular_session(asof: dt.datetime | None = None) -> dt.date:
    """Most recent NYSE session whose regular close has already passed."""
    now = _as_us_datetime(asof)
    day = now.date()
    cal = get_calendar()
    try:
        if is_trading_day(day):
            close = session_close_et(day)
            if close is not None and now.time() >= close:
                return day
            return cal.previous_session(pd.Timestamp(day)).date()
        return cal.date_to_session(pd.Timestamp(day), direction="previous").date()
    except CalendarUnavailable:
        raise
    except Exception as exc:
        raise CalendarUnavailable(
            "cannot determine last completed NYSE session for %s: %s" % (day, exc)
        ) from exc


def review_session_date(asof: dt.datetime | None = None) -> dt.date:
    """Session date a post-close Review must evaluate (early-close aware)."""
    return last_completed_regular_session(asof)
