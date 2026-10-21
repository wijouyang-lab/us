# -*- coding: utf-8 -*-
"""Regression tests for the shared US market calendar (P1-1)."""

import datetime as dt
from zoneinfo import ZoneInfo

import pytest

import us_market_calendar as cal


ET = ZoneInfo("America/New_York")


def _et(y, m, d, hh=0, mm=0):
    return dt.datetime(y, m, d, hh, mm, tzinfo=ET)


def test_thanksgiving_christmas_and_observed_independence_day_are_closed():
    assert cal.is_trading_day("2026-11-26") is False
    assert cal.is_trading_day("2026-12-25") is False
    assert cal.is_trading_day("2026-07-03") is False


def test_regular_session_days_are_open():
    assert cal.is_trading_day("2026-11-25") is True
    assert cal.is_trading_day("2026-11-27") is True
    assert cal.is_trading_day("2026-12-24") is True


def test_early_close_days_report_1300_et():
    assert cal.session_close_et("2026-11-27") == dt.time(13, 0)
    assert cal.session_close_et("2026-12-24") == dt.time(13, 0)
    assert cal.is_early_close("2026-11-27") is True
    assert cal.is_early_close("2026-12-15") is False


def test_dst_changes_utc_close_time():
    summer = cal.session_close_utc("2026-07-15")
    winter = cal.session_close_utc("2026-12-15")
    assert summer is not None and winter is not None
    assert summer.hour == 20 and summer.minute == 0   # 16:00 EDT
    assert winter.hour == 21 and winter.minute == 0   # 16:00 EST


@pytest.mark.parametrize(
    "when,expected",
    [
        (_et(2026, 7, 15, 8, 0), "PREMARKET"),
        (_et(2026, 7, 15, 9, 29), "PREMARKET"),
        (_et(2026, 7, 15, 9, 30), "REGULAR_SESSION"),
        (_et(2026, 7, 15, 15, 59), "REGULAR_SESSION"),
        (_et(2026, 7, 15, 16, 0), "AFTER_HOURS"),
        (_et(2026, 11, 27, 12, 59), "REGULAR_SESSION"),
        (_et(2026, 11, 27, 13, 0), "AFTER_HOURS"),
        (_et(2026, 11, 26, 9, 0), "MARKET_CLOSED_HOLIDAY"),
        (_et(2026, 7, 4, 9, 0), "MARKET_CLOSED_WEEKEND"),
    ],
)
def test_market_session_state(when, expected):
    assert cal.market_session_state(when) == expected


def test_review_session_date_handles_early_close_and_holiday():
    assert cal.review_session_date(_et(2026, 11, 27, 12, 0)).isoformat() == "2026-11-25"
    assert cal.review_session_date(_et(2026, 11, 27, 13, 1)).isoformat() == "2026-11-27"
    assert cal.review_session_date(_et(2026, 11, 26, 18, 0)).isoformat() == "2026-11-25"
    assert cal.review_session_date(_et(2026, 12, 25, 18, 0)).isoformat() == "2026-12-24"


def test_calendar_unavailable_raises(monkeypatch):
    monkeypatch.setattr(cal, "_CALENDAR", None)

    def boom():
        raise cal.CalendarUnavailable("simulated calendar outage")

    monkeypatch.setattr(cal, "_load_calendar", boom)
    with pytest.raises(cal.CalendarUnavailable):
        cal.is_trading_day("2026-11-25")
    with pytest.raises(cal.CalendarUnavailable):
        cal.market_session_state(_et(2026, 11, 25, 9, 0))
