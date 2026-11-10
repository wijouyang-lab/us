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


def test_null_close_and_invalid_ohlc_are_dropped():
    existing = pd.DataFrame([
        {"Date": "2026-10-27", "Ticker": "HUBB", "Open": 430.64, "High": 444.67,
         "Low": 429.36, "Close": 434.28, "Volume": 1820595,
         "schema_version": "phase2b.v1"},
    ])
    downloaded = pd.DataFrame([
        {"Date": "2026-10-28", "Ticker": "HUBB", "Open": 444.68, "High": 444.055,
         "Low": 426.91, "Close": None, "Volume": 1163816,
         "schema_version": "phase2b.v1"},
    ])
    out, report = mod.append_recent(existing, downloaded)
    assert report["new_rows"] == 0
    assert len(out) == 1
    assert out.Date.max() == pd.Timestamp("2026-10-27").date()


def test_missing_new_data_is_reported_without_synthetic_rows():
    existing = pd.DataFrame([
        {"Date": "2026-10-14", "Ticker": "AAA", "Open": 10, "High": 11, "Low": 9,
         "Close": 10.5, "Volume": 100, "schema_version": "phase2b.v1"},
    ])
    empty = pd.DataFrame(columns=mod.COLUMNS)
    out, report = mod.append_recent(existing, empty, target_date=pd.Timestamp("2026-10-15").date())
    assert report["new_rows"] == 0
    assert report["target_date_missing"] is True
    assert len(out) == 1


def test_previous_session_relabeled_as_target_is_not_appended():
    existing = pd.DataFrame([
        {"Date": "2026-10-27", "Ticker": "AOS", "Open": 62.0, "High": 62.54, "Low": 61.04,
         "Close": 62.06, "Volume": 1185400, "schema_version": "phase2b.v1"},
    ])
    # Same OHLCV as 10/27 but falsely labeled 10/28.
    downloaded = pd.DataFrame([
        {"Date": "2026-10-28", "Ticker": "AOS", "Open": 62.0, "High": 62.54, "Low": 61.04,
         "Close": 62.06, "Volume": 1185400, "schema_version": "phase2b.v1"},
    ])
    out, report = mod.append_recent(existing, downloaded, target_date=pd.Timestamp("2026-10-28").date())
    assert report["new_rows"] == 0
    assert report["identical_previous_rows"] == 1
    assert len(out) == 1
    assert out.Date.max() == pd.Timestamp("2026-10-27").date()


def test_target_not_present_and_no_prior_fill():
    existing = pd.DataFrame([
        {"Date": "2026-10-27", "Ticker": "AAA", "Open": 10, "High": 11, "Low": 9,
         "Close": 10.5, "Volume": 100, "schema_version": "phase2b.v1"},
    ])
    downloaded = pd.DataFrame([
        {"Date": "2026-10-27", "Ticker": "AAA", "Open": 10, "High": 11, "Low": 9,
         "Close": 10.5, "Volume": 100, "schema_version": "phase2b.v1"},
    ])
    out, report = mod.append_recent(existing, downloaded, target_date=pd.Timestamp("2026-10-28").date())
    assert report["new_rows"] == 0
    assert report["target_date_missing"] is True
    assert len(out) == 1
