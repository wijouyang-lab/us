# -*- coding: utf-8 -*-
"""Tests for the research-only Alpha Vantage adapter; no network."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import alpha_vantage_provider as av  # noqa: E402


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append(params)
        return FakeResponse(self.payload)


def payload(adj=True):
    rows = {
        "2026-01-02": {"1. open": "10", "2. high": "12", "3. low": "9",
                        "4. close": "11", "6. volume": "1000"},
        "2026-01-05": {"1. open": "11", "2. high": "13", "3. low": "10",
                        "4. close": "12", "6. volume": "1200"},
    }
    if adj:
        for r in rows.values():
            r["5. adjusted close"] = "11.5"
    return {"Time Series (Daily)": rows}


def make(tmp_path, key="SECRET-KEY", **cfg):
    session = FakeSession(payload(adj=cfg.pop("adj", True)))
    config = av.ProviderConfig(cache_dir=tmp_path, min_interval_seconds=0, **cfg)
    return av.AlphaVantageProvider(api_key=key, config=config, session=session), session


def test_missing_key_makes_no_request(tmp_path):
    provider = av.AlphaVantageProvider(api_key="", config=av.ProviderConfig(cache_dir=tmp_path))
    result = av.probe(provider, "AVB")
    assert result["status"] == "SKIPPED_NO_API_KEY"


def test_parse_and_cache_avoid_duplicate_request(tmp_path):
    provider, session = make(tmp_path)
    df = provider.fetch_daily("AVB")
    assert len(df) == 2
    assert df["Adj_Close"].notna().all()
    provider.fetch_daily("AVB")
    assert len(session.calls) == 1


def test_daily_limit_fails_closed(tmp_path):
    provider, session = make(tmp_path, daily_limit=2)
    provider.fetch_daily("AAA")
    provider.fetch_daily("BBB")
    with pytest.raises(av.RateLimitExceeded):
        provider.fetch_daily("CCC")
    assert len(session.calls) == 2


def test_missing_adjusted_column_is_not_silently_accepted(tmp_path):
    provider, _ = make(tmp_path, adj=False)
    with pytest.raises(av.ProviderError, match="adjusted close is missing"):
        provider.fetch_daily("AVB")


def test_api_key_is_redacted_from_errors(tmp_path):
    provider, _ = make(tmp_path)
    provider.session = FakeSession({"Error Message": "bad SECRET-KEY"})
    with pytest.raises(av.ProviderError) as exc:
        provider.fetch_daily("AVB")
    assert "SECRET-KEY" not in str(exc.value)
    assert "REDACTED" in str(exc.value) or "bad" in str(exc.value)


def test_cache_written_without_key_in_filename(tmp_path):
    provider, _ = make(tmp_path)
    provider.fetch_daily("AVB")
    names = [p.name for p in tmp_path.iterdir()]
    assert "AVB.json" in names
    assert all("SECRET" not in n for n in names)
