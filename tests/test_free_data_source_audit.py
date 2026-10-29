# -*- coding: utf-8 -*-
"""Fixture checks for MarketParquet/ADGSTUDIOS source audit."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "research"
AUDIT = ROOT / "marketparquet_source_audit_2026-10-29.json"


def test_marketparquet_sample_metadata():
    d = json.loads(AUDIT.read_text(encoding="utf-8"))
    mp = {s["source"]: s for s in d["sources"]}["MarketParquet"]
    assert mp["http"] == 200
    assert mp["rows"] == 6503
    assert mp["date_min"] == "2026-10-28"
    assert mp["date_max"] == "2026-10-28"
    assert mp["status"] == "RECENT_ONLY_NOT_HISTORICAL"
    assert len(mp["sha256"]) == 64
    assert mp["quality"]["duplicate_date_symbol"] == 0
    assert mp["quality"]["invalid_ohlc"] == 0


def test_adgstudios_is_network_unverified_not_no_data():
    d = json.loads(AUDIT.read_text(encoding="utf-8"))
    adg = {s["source"]: s for s in d["sources"]}["ADGSTUDIOS Stocks API"]
    assert adg["http"] == 502
    assert adg["status"] == "UNVERIFIED_NETWORK_502"


def test_no_raw_parquet_is_committed():
    # The license forbids raw-file redistribution; only metadata is committed.
    assert not any(p.suffix == ".parquet" for p in ROOT.rglob("*.parquet"))
