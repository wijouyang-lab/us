# -*- coding: utf-8 -*-
"""Contract tests for the low-frequency Qlib/OpenBB readiness audit."""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import audit_lowfreq_data as audit  # noqa: E402
import export_qlib_panel as exporter  # noqa: E402


def _price(path):
    rows = []
    for ticker in ("AAA", "BBB"):
        for d in pd.bdate_range("2025-01-02", periods=5):
            rows.append({"Date": d.date().isoformat(), "Ticker": ticker,
                         "Open": 10, "High": 11, "Low": 9, "Close": 10, "Volume": 1000,
                         "schema_version": "phase2b.v2"})
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _snapshot(path):
    rows = []
    for ticker in ("AAA", "BBB"):
        for d in pd.bdate_range("2025-01-02", periods=5):
            rows.append({"Scan_Date": d.date().isoformat(), "Technical_Date": d.date().isoformat(),
                         "Ticker": ticker, "Price": 10, "ATR_Pct": 2, "schema_version": "phase1.v1"})
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_audit_reports_clean_synthetic_panels(tmp_path):
    snap = audit.audit_snapshot(_snapshot(tmp_path / "snap.csv"))
    price = audit.audit_price_history(_price(tmp_path / "price.csv"))
    assert snap["status"] == "OK" and price["status"] == "OK"
    assert snap["duplicate_date_ticker"] == 0
    assert snap["scan_before_technical"] == 0
    assert price["nonpositive_close"] == 0
    assert "survivorship_note" in price


def test_export_creates_one_file_per_instrument_and_manifest(tmp_path):
    snap = _snapshot(tmp_path / "snap.csv")
    manifest = exporter.export_panel(snap, tmp_path / "qlib")
    assert manifest["instruments"].keys() == {"AAA", "BBB"}
    assert (tmp_path / "qlib" / "AAA.csv").exists()
    assert json.loads((tmp_path / "qlib" / "manifest.json").read_text(encoding="utf-8"))["instruments"]["AAA"]["rows"] == 5
