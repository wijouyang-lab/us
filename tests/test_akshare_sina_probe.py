# -*- coding: utf-8 -*-
"""Fixture checks for the AKShare Sina probe; no live network."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "research"


def test_akshare_sina_probe_results():
    d = json.loads((ROOT / "akshare_sina_probe_2026-10-29.json").read_text(encoding="utf-8"))
    assert d["auth_required"] is False
    assert d["canonical_write"] is False
    by = {r["ticker"]: r for r in d["results"]}
    assert by["ADCT"]["status"] == "rejected"
    assert "series_starts_after_delisting_ticker_reuse" in by["ADCT"]["validator"]["reasons"]
    assert by["TWTR"]["status"] == "accepted"
    assert by["TWTR"]["rows"] == 2259
    assert by["TWTR"]["last"] == "2022-10-27"
    assert by["SIVB"]["status"] == "rejected"
    assert "invalid_ohlc" in by["SIVB"]["validator"]["reasons"]


def test_terms_not_cleared_for_import():
    d = json.loads((ROOT / "akshare_sina_probe_2026-10-29.json").read_text(encoding="utf-8"))
    assert "terms_confirmation_required" in d["terms"]
    assert d["canonical_write"] is False
