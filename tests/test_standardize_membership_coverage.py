# -*- coding: utf-8 -*-
"""Tests for daily membership interval reconstruction and price coverage."""

import sys
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import standardize_membership_coverage as mod  # noqa: E402


def _price(path):
    rows = []
    for d in pd.bdate_range("2020-01-02", "2020-12-31"):
        for ticker in ("AAA", "BBB"):
            rows.append({"Date": d.date().isoformat(), "Ticker": ticker, "Close": 10})
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_coiltrade_reconstruction_and_annual_coverage(tmp_path):
    coil = tmp_path / "coil.json"
    coil.write_text(
        '{"current": ["AAA"], "changes": ['
        '{"date": "2020-01-02", "added": "", "removed": ""},'
        '{"date": "2020-06-01", "added": "", "removed": "AAA"}'
        ']}', encoding="utf-8"
    )
    # Use a nonempty change so the first/last bounds are defined.
    intervals = mod.coiltrade_intervals(coil, pd.Timestamp("2020-01-01").date(), pd.Timestamp("2020-12-31").date())
    assert any(x["ticker"] == "AAA" for x in intervals)
    norm = mod.normalize(intervals, "coiltrade", {"AAA": "0000000001"})
    detail, annual = mod.coverage(norm, pd.read_csv(_price(tmp_path / "price.csv")), "coiltrade")
    assert not detail.empty and not annual.empty
    assert annual["member_day_coverage"].between(0, 1).all()


def test_shardul_yaml_changes_are_loaded(tmp_path):
    d = tmp_path / "shardul"
    d.mkdir()
    (d / "2020.yaml").write_text(yaml.safe_dump({
        "year": 2020,
        "tickers_on_Jan_1": ["AAA"],
        "changes": {"2020-06-01": {"difference": ["AAA"], "union": ["BBB"]}},
    }), encoding="utf-8")
    intervals = mod.shardul_intervals(d, pd.Timestamp("2020-01-01").date(), pd.Timestamp("2020-12-31").date())
    assert any(x["ticker"] == "AAA" for x in intervals)
    assert any(x["ticker"] == "BBB" for x in intervals)
