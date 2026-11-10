# -*- coding: utf-8 -*-
"""Tests for SEC identity enrichment; no network."""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import enrich_missing_ticker_identity as mod  # noqa: E402


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        return FakeResponse(self.payload)


def test_latest_filing_prefers_8k_and_builds_url():
    payload = {
        "cik": "123",
        "filings": {"recent": {
            "form": ["10-K", "8-K"],
            "filingDate": ["2024-02-01", "2024-03-01"],
            "accessionNumber": ["0001-24-000001", "0001-24-000002"],
            "primaryDocument": ["a.htm", "b.htm"],
        }},
    }
    out = mod.latest_filing(payload)
    assert out["form"] == "8-K"
    assert out["filing_date"] == "2024-03-01"
    assert "000124000002" in out["url"]


def test_enrich_keeps_membership_removal_separate_from_delisting(tmp_path):
    cls = pd.DataFrame([{"ticker": "ATVI", "category": "x"}])
    membership = pd.DataFrame([{
        "symbol": "ATVI", "cik": "718877", "name": "Activision",
        "date_added": "2015-08-31", "date_removed": "2023-10-18",
    }])
    payload = {
        "cik": "718877", "name": "Activision Blizzard",
        "tickers": [],
        "formerNames": [{"name": "ACTIVISION INC", "from": "1995", "to": "2008"}],
        "filings": {"recent": {
            "form": ["8-K"], "filingDate": ["2023-10-16"],
            "accessionNumber": ["0001-23-000001"], "primaryDocument": ["a.htm"],
        }},
    }
    session = FakeSession(payload)
    out = mod.enrich(cls, membership, tmp_path, session)
    row = out.iloc[0]
    assert row["cik"] == "0000718877"
    assert row["event_type"] == "removed_from_sp500_not_necessarily_delisted"
    assert row["event_effective_date"] == "2023-10-18"
    assert row["announcement_available_date"] == "2023-10-16"
    assert row["identity_confidence"] == "high"
    assert "ACTIVISION" in row["former_names"]
    assert session.calls == 1


def test_cache_prevents_second_request(tmp_path):
    payload = {"name": "X", "filings": {"recent": {}}}
    session = FakeSession(payload)
    first = mod.fetch_submissions("0000000001", tmp_path, session, sleeper=lambda _: None)
    second = mod.fetch_submissions("0000000001", tmp_path, session, sleeper=lambda _: None)
    assert first == second
    assert session.calls == 1
    assert json.loads((tmp_path / "CIK0000000001.json").read_text())["name"] == "X"
