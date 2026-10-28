# -*- coding: utf-8 -*-
"""Tests for post-event price readiness; no network or strategy."""

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import event_post_bar_readiness as mod  # noqa: E402


def event(**overrides):
    row = {
        "event_id": "e1", "event_type": "policy", "source": "fed_test",
        "source_url": "https://www.federalreserve.gov/x",
        "published_at_utc": "2026-10-05T12:30:00Z",
        "first_seen_at_utc": "2026-10-05T12:31:00Z",
        "event_time_utc": "2026-10-05T12:30:00Z",
        "market_scope": "market", "tickers": ["AAA"],
    }
    row.update(overrides)
    return row


def prices(days=8, ticker="AAA", close=100.0):
    rows = []
    for i in range(days):
        d = date(2026, 10, 5) + timedelta(days=i)
        rows.append({"Date": d.isoformat(), "Ticker": ticker, "Open": close,
                     "High": close + 10, "Low": close - 10, "Close": close + i, "Volume": 1000})
    return pd.DataFrame(rows)


def test_ready_requires_bars_and_verified_price_basis():
    out = mod.evaluate([event()], prices(), as_of="2026-10-20T00:00:00Z",
                       adjusted_price_available=True, corporate_actions_verified=True)
    assert out["ready"] == 1
    assert out["events"][0]["returns"]["return_1d"] is not None
    assert out["events"][0]["returns"]["return_5d"] is not None


def test_future_bars_are_pending_not_missing_data_error():
    out = mod.evaluate([event()], prices(days=3), as_of="2026-10-20T00:00:00Z")
    assert out["pending_future_bar"] == 1
    assert out["excluded"] == 0
    assert "pending_future_5d_bar" in out["events"][0]["reasons"]


def test_unverified_adjustment_is_pending():
    out = mod.evaluate([event()], prices(), as_of="2026-10-20T00:00:00Z",
                       adjusted_price_available=False, corporate_actions_verified=True)
    assert out["pending_future_bar"] == 1
    assert "adjusted_price_unavailable" in out["events"][0]["reasons"]


def test_missing_timezone_is_excluded():
    out = mod.evaluate([event(published_at_utc="2026-10-05T12:30:00")], prices(),
                       as_of="2026-10-20T00:00:00Z")
    assert out["excluded"] == 1


def test_market_wide_event_can_use_explicit_market_proxy():
    market_event = event(tickers=[])
    out = mod.evaluate([market_event], prices(), as_of="2026-10-20T00:00:00Z",
                       adjusted_price_available=True, corporate_actions_verified=True,
                       market_proxy="AAA")
    assert out["ready"] == 1
    assert out["events"][0]["entity_id"] == "AAA"


def test_market_proxy_mode_uses_provider_adjusted_spy():
    out = mod.evaluate([event(tickers=[])], prices(ticker="SPY"),
                       as_of="2026-10-20T00:00:00Z",
                       market_proxy="SPY", research_mode="market_proxy_spy",
                       proxy_metadata={"adjusted_close_available": True})
    assert out["research_mode"] == "market_proxy_spy"
    assert out["ready"] == 1
    assert out["events"][0]["price_basis"] == "SPY_Adj_Close_provider"
    assert out["events"][0]["corporate_actions_basis"] == "provider_adjustment_only"


def test_duplicate_and_invalid_bars_are_excluded():
    dup = pd.concat([prices(), prices().head(1)], ignore_index=True)
    out = mod.evaluate([event()], dup, as_of="2026-10-20T00:00:00Z")
    assert out["excluded"] == 1
    bad = prices()
    bad.loc[0, "High"] = 1
    out = mod.evaluate([event()], bad, as_of="2026-10-20T00:00:00Z")
    assert out["excluded"] == 1


def test_no_entry_bar_is_pending():
    out = mod.evaluate([event()], prices().head(1), as_of="2026-10-20T00:00:00Z")
    assert out["pending_future_bar"] == 1
    assert "pending_future_1d_bar" in out["events"][0]["reasons"]


def test_after_close_uses_next_session():
    out = mod.evaluate([event(published_at_utc="2026-10-05T20:30:00Z",
                              first_seen_at_utc="2026-10-05T20:31:00Z",
                              event_time_utc="2026-10-05T20:30:00Z")],
                       prices(), as_of="2026-10-20T00:00:00Z")
    assert out["events"][0]["entry_bar_date"] == "2026-10-06"
