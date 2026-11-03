# -*- coding: utf-8 -*-
import hashlib
import json
from pathlib import Path
import pandas as pd
import pytest

from tools.research.pit_data_feasibility import audit

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data" / "research" / "pit_data"


def test_trial_has_20_unique_symbols_and_dates():
    a = audit()
    assert a["sample_symbols"] == 20
    assert a["sample_duplicate_rows"] == 0
    assert max(a["sample_last_dates"].values()) <= "2024-12-31"


def test_myl_anomaly_is_flagged():
    a = audit()
    assert "MYL" in a["sample_anomalies"]
    d = pd.read_csv(D / "finsaber_20.csv")
    last = d[d.symbol == "MYL"].iloc[-1]
    assert last["close"] < 1.0


def test_98_ticker_coverage_below_gate():
    a = audit()
    assert a["ticker_98_total"] == 98
    assert a["ticker_98_found"] == 93
    assert a["ticker_coverage"] < 0.98
    assert set(a["ticker_98_missing"]) == {"DAY", "TSO", "UA.C", "WYN", "YHOO"}


def test_other_sources_fail_delisted_coverage():
    a = audit()
    assert a["source_success_20"]["eodhd"] < 5
    assert a["source_success_20"]["twelve"] < 5
    assert a["source_success_20"]["nasdaq"] < 10


def test_membership_stops_before_holdout():
    a = audit()
    assert a["membership_max_date"] == "2019-01-11"


def test_manifest_hashes_match_files():
    m = json.loads((D / "manifest.json").read_text())
    for name, meta in m["files"].items():
        assert hashlib.sha256((D / name).read_bytes()).hexdigest() == meta["sha256"]
