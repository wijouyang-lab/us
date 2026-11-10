# -*- coding: utf-8 -*-
"""Fixture checks for second-round expanded coverage."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "research"


def test_expanded_panel_uses_more_names_than_complete_case():
    data = json.loads((ROOT / "restricted_503_factor_expanded_2026-10-29.json").read_text(encoding="utf-8"))
    assert data["tickers"] == 503
    assert data["rows"] == 1239013
    assert data["benchmark_test"]["n"] == 45
    assert data["benchmark_test"]["ann_return"] > 0.13
    test = [r for r in data["results"] if r["sample"] == "test_2023_2026"]
    assert len(test) == 5
    assert all(r["n"] == 45 for r in test)
    assert all(r["bh_q_test"] > 0.05 for r in test)


def test_missing_ticker_classification_has_38_rows():
    import pandas as pd
    df = pd.read_csv(ROOT / "missing_ticker_classification_2026-10-29.csv")
    assert len(df) == 38
    assert df[df.Ticker == "HUBB"]["category"].iloc[0] == "provider_missing_latest_date"
    assert df[df.Ticker == "FISV"]["category"].iloc[0] == "single_date_gap"
