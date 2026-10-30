# -*- coding: utf-8 -*-
"""Tests for historical index membership and PIT boundaries."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
from historical_universe import HistoricalUniverse  # noqa: E402


def make(path):
    pd.DataFrame({
        "date": ["2020-01-01", "2020-06-01", "2020-06-02"],
        "tickers": ["AAA,BBB", "AAA,CCC", "AAA,CCC"],
    }).to_csv(path, index=False)
    return HistoricalUniverse(path)


def test_membership_enters_and_exits_on_boundary(tmp_path):
    h = make(tmp_path / "u.csv")
    assert h.get_historical_universe("2020-01-15") == {"AAA", "BBB"}
    assert h.get_historical_universe("2020-06-01") == {"AAA", "CCC"}
    assert "BBB" not in h.get_historical_universe("2020-06-01")


def test_no_future_members_and_delisted_stays_historical(tmp_path):
    h = make(tmp_path / "u.csv")
    early = h.get_historical_universe("2020-01-15")
    assert "CCC" not in early
    assert "BBB" in early


def test_stale_snapshot_is_not_pit(tmp_path):
    h = make(tmp_path / "u.csv")
    q = h.query("2020-06-20")
    assert q["status"] == "STALE_SNAPSHOT"
    assert q["pit_eligible"] is False
    assert q["missing_reason"] == "stale_membership_snapshot"


def test_third_party_membership_not_admitted_to_pit(tmp_path):
    h = make(tmp_path / "u.csv")
    assert h.get_historical_universe("2020-06-01", pit_only=True) == set()
    assert h.query("2020-06-01")["confidence"] == "third_party_medium"


def test_repeated_query_is_deterministic(tmp_path):
    h = make(tmp_path / "u.csv")
    assert h.query("2020-06-01") == h.query("2020-06-01")
