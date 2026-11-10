# -*- coding: utf-8 -*-
"""Tests for historical constituent audit and source-boundary handling."""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "research"))
import historical_constituent_audit as h  # noqa: E402


def test_ticker_normalization_matches_panel_format():
    assert h.norm("BRK.B") == "BRK-B"
    assert h.norm("bf.b") == "BF-B"


def test_snapshot_uses_latest_date_not_future():
    exp = pd.DataFrame({"date": pd.to_datetime(["2020-01-01", "2020-06-01"]),
                        "ticker": ["AAA", "BBB"]})
    assert h.snapshot_on(exp, pd.Timestamp("2020-05-31")) == {"AAA"}
    assert h.snapshot_on(exp, pd.Timestamp("2020-06-01")) == {"BBB"}


def test_yearly_component_counts_are_plausible():
    y = pd.read_csv(ROOT / "docs/research/historical_constituent_2026-10-29_yearly.csv")
    assert len(y) == 11
    assert y.chino_count.min() >= 400
    assert y.chino_count.max() <= 520
    assert y[y.year == 2026].missing.iloc[0] == 0


def test_missing_unique_is_202():
    m = pd.read_csv(ROOT / "docs/research/historical_constituent_missing_unique_2026-10-29.csv")
    assert len(m) == 202
    assert m.ticker.nunique() == 202
    assert m.last_year.max() <= 2026


def test_repo_identity_risk_is_not_zero():
    d = pd.read_csv(ROOT / "tools/research/data/sp500_components_history.csv")
    multi = d.groupby("symbol")["cik"].nunique()
    assert (multi > 1).sum() >= 10
def test_missing_classification_is_auditable_not_filled():
    m = pd.read_csv(ROOT / "docs/research/missing_202_reason_classification_2026-10-29.csv")
    assert len(m) == 202
    assert (m.price_status == "NO_SERIES_IN_CURRENT_PANEL").all()
    assert (m.action == "DO_NOT_FILL_WITHOUT_IDENTITY_AND_LEGAL_CLEARANCE").all()
    assert set(m.classification) == {"IDENTITY_REVIEW_REQUIRED", "PRELIMINARY_TICKER_REUSE_FLAG"}
