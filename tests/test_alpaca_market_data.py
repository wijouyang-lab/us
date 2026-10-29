# -*- coding: utf-8 -*-
"""Alpaca adapter tests with fixed mock responses; no real key/network."""

import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import alpaca_market_data as mod  # noqa: E402


class Resp:
    def __init__(self, status, payload):
        self.status_code = status
        self.content = json.dumps(payload).encode()

    def json(self):
        return json.loads(self.content)


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"params": dict(params or {}), "headers": dict(headers or {})})
        if not self.responses:
            raise AssertionError("unexpected request")
        return self.responses.pop(0)


ENV = {"APCA_API_KEY_ID": "test-key", "APCA_API_SECRET_KEY": "test-secret"}


def test_missing_credentials_fail_before_request():
    with pytest.raises(mod.MissingCredentials):
        mod.fetch_daily_bars(["HUBB"], date(2026, 10, 27), date(2026, 10, 29), env={})


def test_pagination_and_provenance():
    s = Session([
        Resp(200, {"bars": {"HUBB": [{"t": "2026-10-28T04:00:00Z", "o": 444.68,
                                     "h": 444.805, "l": 426.91, "c": 437.33, "v": 1163860}]},
                  "next_page_token": "next"}),
        Resp(200, {"bars": {"HUBB": [{"t": "2026-10-29T04:00:00Z", "o": 438, "h": 440,
                                     "l": 436, "c": 439, "v": 1000}]}, "next_page_token": None}),
    ])
    out = mod.fetch_daily_bars(["hubb"], date(2026, 10, 28), date(2026, 10, 29), env=ENV, session=s)
    assert len(out["rows"]) == 2
    assert len(out["pages"]) == 2
    assert s.calls[1]["params"]["page_token"] == "next"
    assert out["has_adjusted_close_field"] is False
    assert out["rows"][0]["provider"] == "alpaca_market_data"


def test_rate_limit_and_permission_errors():
    with pytest.raises(mod.AlpacaError, match="429"):
        mod.fetch_daily_bars(["HUBB"], date(2026, 10, 28), date(2026, 10, 29), env=ENV,
                             session=Session([Resp(429, {})]))
    with pytest.raises(mod.AlpacaError, match="403"):
        mod.fetch_daily_bars(["HUBB"], date(2026, 10, 28), date(2026, 10, 29), env=ENV,
                             session=Session([Resp(403, {})]))


def test_missing_or_invalid_bar_survives_for_downstream_rejection():
    s = Session([Resp(200, {"bars": {"HUBB": [{"t": "2026-10-28T04:00:00Z",
                                                "o": 444.68, "h": 444.055, "l": 426.91,
                                                "c": None, "v": -1}]}, "next_page_token": None})])
    out = mod.fetch_daily_bars(["HUBB"], date(2026, 10, 28), date(2026, 10, 29), env=ENV, session=s)
    r = out["rows"][0]
    assert r["Close"] is None
    assert r["High"] < r["Open"]
    assert r["Volume"] < 0


def test_raw_adjustment_is_explicit_and_no_adj_close_is_claimed():
    s = Session([Resp(200, {"bars": {"HUBB": []}, "next_page_token": None})])
    out = mod.fetch_daily_bars(["HUBB"], date(2026, 10, 28), date(2026, 10, 29), env=ENV,
                               session=s, adjustment="raw")
    assert out["request"]["adjustment"] == "raw"
    assert out["has_adjusted_close_field"] is False
