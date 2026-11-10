# -*- coding: utf-8 -*-
"""Tests for public membership coverage audit; no network."""

import json
import sys
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import audit_public_membership as mod  # noqa: E402


def test_membership_audit_counts_without_price_claims(tmp_path):
    coil = tmp_path / "coil.json"
    coil.write_text(json.dumps({
        "current": ["AAA"],
        "changes": [{"date": "2020-01-01", "added": "BBB", "removed": ""}],
    }), encoding="utf-8")
    shard = tmp_path / "shard"
    shard.mkdir()
    (shard / "sp500-ticker-changes-2020.yaml").write_text(
        yaml.safe_dump({"year": 2020, "tickers_on_Jan_1": ["AAA", "CCC"]}), encoding="utf-8"
    )
    price = tmp_path / "price.csv"
    pd.DataFrame({"Ticker": ["AAA"]}).to_csv(price, index=False)
    failed = tmp_path / "failed.csv"
    pd.DataFrame({"ticker": ["BBBB"]}).to_csv(failed, index=False)
    out = mod.audit(coil, shard, price, failed)
    assert out["coiltrade"]["failed_overlap"] == 0
    assert out["coiltrade"]["failed_missing"] == ["BBBB"]
    assert out["shardul"]["membership_not_in_price_panel"] == 1
    assert out["limitations"]
