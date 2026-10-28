# -*- coding: utf-8 -*-
"""Tests for machine-readable recovery audit; no network."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import build_recovery_audit as mod  # noqa: E402


def test_identity_only_is_not_recovered(tmp_path):
    identity = tmp_path / "identity.csv"
    pd.DataFrame([{
        "ticker": "ATVI", "cik": "0000718877", "identity_confidence": "high",
        "membership_removed": "2023-10-18", "membership_added": "2015-08-31",
        "identity_evidence_url": "https://data.sec.gov/x",
    }]).to_csv(identity, index=False)
    price = tmp_path / "price.csv"
    pd.DataFrame({"Date": ["2020-01-02"], "Ticker": ["OTHER"], "Close": [1]}).to_csv(price, index=False)
    failed = tmp_path / "failed.csv"
    pd.DataFrame({"ticker": ["ATVI"], "evidence": ["delisted"]}).to_csv(failed, index=False)
    out = mod.build(identity, price, failed)
    row = out.iloc[0]
    assert row["identity_verified"] is True or row["identity_verified"] == True
    assert row["valid_ohlcv_rows"] == 0
    assert row["recovery_status"] == "identity_only"
    assert row["independent_crosscheck_available"] == False


def test_rows_are_not_validated_without_independent_crosscheck(tmp_path):
    identity = tmp_path / "identity.csv"
    pd.DataFrame([{
        "ticker": "AAA", "cik": "1", "identity_confidence": "high",
        "membership_removed": "2020-01-01", "membership_added": "2019-01-01",
        "identity_evidence_url": "u",
    }]).to_csv(identity, index=False)
    price = tmp_path / "price.csv"
    pd.DataFrame({"Date": ["2020-01-02"], "Ticker": ["AAA"], "Close": [1]}).to_csv(price, index=False)
    failed = tmp_path / "failed.csv"
    pd.DataFrame({"ticker": ["AAA"], "evidence": ["e"]}).to_csv(failed, index=False)
    out = mod.build(identity, price, failed)
    assert out.iloc[0]["recovery_status"] == "recovered_but_unverified"
