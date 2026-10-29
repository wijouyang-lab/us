# -*- coding: utf-8 -*-
"""Fixture checks for the AKShare coverage assessment; no network."""

from pathlib import Path

import pandas as pd

CSV = Path(__file__).resolve().parents[1] / "docs" / "research" / "akshare_503_coverage_2026-10-28.csv"


def test_akshare_coverage_is_complete_and_valid():
    df = pd.read_csv(CSV)
    assert len(df) == 503
    assert df.ticker.nunique() == 503
    assert df.error.isna().all()
    assert df.status.eq(200).all()
    ohlcv = df[["open", "high", "low", "close", "volume"]]
    assert (ohlcv > 0).all().all()
    assert (df.high >= df[["open", "close", "low"]].max(axis=1)).all()
    assert (df.low <= df[["open", "close", "high"]].min(axis=1)).all()


def test_akshare_hubb_row_is_valid_and_not_adj_close():
    df = pd.read_csv(CSV).set_index("ticker")
    row = df.loc["HUBB"]
    assert row.close == 437.33
    assert row.open == 444.68
    assert row.high == 444.805
    assert row.low == 426.91
    assert row.volume > 0
    assert "Adj_Close" not in df.columns
def test_raw_and_qfq_evidence_hashes_are_stable():
    import hashlib
    root = CSV.parent / "akshare_2026-10-28"
    assert hashlib.sha256((root / "sina_raw.js").read_bytes()).hexdigest() == \
        "3b8c52094e5099773b682a035f92cb68a16f6ecdd59d4e5868d7d5c6813f53ce"
    assert hashlib.sha256((root / "sina_qfq.js").read_bytes()).hexdigest() == \
        "87f459583c7a56bd8ffea7c3952c94ce6c5e83a5bbac678e75fc5692085ad97c"
