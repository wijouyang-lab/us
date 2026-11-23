# -*- coding: utf-8 -*-
"""Tests for SEC event factor construction."""

import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
from event_factor_engine import build  # noqa: E402


def frame():
    return pd.DataFrame([
        {"ticker": "AAA", "cik": "1", "accession": "a1", "form": "8-K", "filing_date": "2024-01-02",
         "acceptance_datetime": "2024-01-02T21:30:00Z", "items": "2.02"},
        {"ticker": "AAA", "cik": "1", "accession": "a2", "form": "8-K", "filing_date": "2024-01-10",
         "acceptance_datetime": "2024-01-10T21:30:00Z", "items": "5.02"},
        {"ticker": "BBB", "cik": "2", "accession": "b1", "form": "10-Q", "filing_date": "2024-01-03",
         "acceptance_datetime": "2024-01-03T12:00:00Z", "items": ""},
    ])


def test_event_types_and_8k_count():
    out = build(frame(), list(pd.bdate_range("2024-01-01", periods=20)))
    assert out.Earnings_Release_Indicator.sum() == 2
    assert out.Management_Change_Indicator.sum() == 1
    assert out[out.event_id == "a2"].SEC_8K_Event_Count.iloc[0] == 2


def test_after_close_uses_next_session():
    out = build(frame(), list(pd.bdate_range("2024-01-01", periods=20)))
    assert out[out.event_id == "a1"].trade_date.iloc[0] == "2024-01-03"


def test_no_pit_claim():
    out = build(frame(), list(pd.bdate_range("2024-01-01", periods=20)))
    assert out.pit_eligible.eq(False).all()


def test_unavailable_fundamentals_not_fabricated():
    out = build(frame(), list(pd.bdate_range("2024-01-01", periods=20)))
    for col in ("Revenue_Growth", "EPS_Growth", "Gross_Margin_Change", "FCF_Change"):
        assert out[col].isna().all()
