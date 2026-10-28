# -*- coding: utf-8 -*-
"""Tests for incremental price append; no network."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import update_recent_prices_incremental as mod  # noqa: E402


def test_only_dates_after_last_are_appended_and_invalid_rows_dropped():
    existing = pd.DataFrame([
        {"Date": "2026-10-14", "Ticker": "AAA", "Open": 10, "High": 11, "Low": 9,
         "Close": 10.5, "Volume": 100, "schema_version": "phase2b.v1"},
    ])
    downloaded = pd.DataFrame([
        {"Date": "2026-10-14", "Ticker": "AAA", "Open": 10, "High": 11, "Low": 9,
         "Close": 10.5, "Volume": 100, "schema_version": "phase2b.v1"},
        {"Date": "2026-10-15", "Ticker": "AAA", "Open": 10, "High": 11, "Low": 9,
         "Close": 10.8, "Volume": 120, "schema_version": "phase2b.v1"},
        {"Date": "2026-10-16", "Ticker": "AAA", "Open": 10, "High": 8, "Low": 9,
         "Close": 10, "Volume": 120, "schema_version": "phase2b.v1"},
        {"Date": "2026-10-15", "Ticker": "AAA", "Open": 10, "High": 11, "Low": 9,
         "Close": 10.8, "Volume": 120, "schema_version": "phase2b.v1"},
    ])
    out, report = mod.append_recent(existing, downloaded)
    assert report["new_rows"] == 1
    assert report["new_dates"] == ["2026-10-15"]
    assert out["Date"].max() == pd.Timestamp("2026-10-15").date()
    assert len(out) == 2


def test_repeated_append_is_idempotent_and_keeps_history():
    existing = pd.DataFrame([
        {"Date": "2026-10-14", "Ticker": "AAA", "Open": 10, "High": 11, "Low": 9,
         "Close": 10.5, "Volume": 100, "schema_version": "phase2b.v1"},
    ])
    downloaded = pd.DataFrame([
        {"Date": "2026-10-15", "Ticker": "AAA", "Open": 10, "High": 11, "Low": 9,
         "Close": 10.8, "Volume": 120, "schema_version": "phase2b.v1"},
    ])
    first, _ = mod.append_recent(existing, downloaded)
    second, report = mod.append_recent(first, downloaded)
    assert report["new_rows"] == 0
    assert len(second) == 2
    assert second[second.Date.astype(str) == "2026-10-14"].Close.iloc[0] == 10.5


def test_missing_new_data_is_reported_without_synthetic_rows():
    existing = pd.DataFrame([
        {"Date": "2026-10-14", "Ticker": "AAA", "Open": 10, "High": 11, "Low": 9,
         "Close": 10.5, "Volume": 100, "schema_version": "phase2b.v1"},
    ])
    empty = pd.DataFrame(columns=mod.COLUMNS)
    out, report = mod.append_recent(existing, empty)
    assert report["new_rows"] == 0
    assert len(out) == 1
