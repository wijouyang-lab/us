# -*- coding: utf-8 -*-
"""Tests for fail-closed delisted identity/series gate."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import delisted_security_gate as g  # noqa: E402

RECORD = {"ticker": "TWTR", "cik": "0001418091", "company": "TWITTER, INC.",
          "ticker_valid_from": "2013-11-07", "ticker_valid_to": "2022-10-27",
          "last_trade_date": "2022-10-27", "event_date": "2022-10-27"}


def frame(start="2013-11-07", end="2022-10-27"):
    idx = pd.bdate_range(start, end)
    return pd.DataFrame({"Open": 10.0, "High": 11.0, "Low": 9.0, "Close": 10.5}, index=idx)


def test_valid_series_and_terms_approved():
    out = g.evaluate(RECORD, frame(), terms_status="approved", independent_source=True)
    assert out["approved"] is True


def test_ticker_reuse_rejected():
    out = g.evaluate(RECORD, frame("2020-01-02", "2026-10-28"), terms_status="approved",
                     independent_source=True)
    assert "series_extends_after_ticker_end" in out["errors"]
    assert out["approved"] is False


def test_cik_ticker_interval_mismatch_rejected():
    rec = dict(RECORD, last_trade_date="2023-01-01")
    out = g.evaluate(rec, frame(), terms_status="approved", independent_source=True)
    assert "last_trade_after_ticker_end" in out["errors"]


def test_terms_unresolved_blocks():
    out = g.evaluate(RECORD, frame(), terms_status="UNRESOLVED", independent_source=True)
    assert "terms_unresolved" in out["errors"]
    assert out["approved"] is False


def test_no_independent_source_blocks():
    out = g.evaluate(RECORD, frame(), terms_status="approved", independent_source=False)
    assert "no_independent_crosscheck" in out["errors"]


def test_duplicate_and_bad_ohlc_rejected():
    f = frame()
    f = pd.concat([f, f.iloc[[0]]])
    out = g.evaluate(RECORD, f, terms_status="approved", independent_source=True)
    assert "duplicate_dates" in out["errors"]
    f2 = frame()
    f2.iloc[0, f2.columns.get_loc("High")] = 1.0
    out2 = g.evaluate(RECORD, f2, terms_status="approved", independent_source=True)
    assert "invalid_ohlc" in out2["errors"]


def test_canonical_write_blocked():
    out = g.evaluate(RECORD, frame(), terms_status="approved", independent_source=True,
                     canonical_write=True)
    assert "canonical_write_not_allowed" in out["errors"]
