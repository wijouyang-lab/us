# -*- coding: utf-8 -*-
"""Tests for missing-ticker classification; no network or production imports."""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import classify_missing_tickers as mod  # noqa: E402


def test_classify_renamed_active_and_unresolved():
    failures = [
        {"ticker": "OLD", "status": "failed", "recovery_method": "x", "fallback_error": "delisted 404"},
        {"ticker": "ACT", "status": "failed", "recovery_method": "x", "fallback_error": "price provider error"},
        {"ticker": "GONE", "status": "failed", "recovery_method": "x", "fallback_error": "delisted 404"},
    ]
    sec = {"NEW": {"ticker": "NEW"}, "ACT": {"ticker": "ACT"}}
    aliases = {"OLD": {"canonical_ticker": "NEW", "old_ticker": "OLD"}}
    rows = mod.classify(failures, sec, aliases, {"ACT"})
    by = {r["ticker"]: r for r in rows}
    assert by["OLD"]["category"] == "renamed_or_reorganized"
    assert by["OLD"]["canonical_ticker"] == "NEW"
    assert by["ACT"]["category"] == "active_listing_price_source_failure"
    assert by["ACT"]["in_current_10y_panel"] is True
    assert by["GONE"]["category"] == "delisted_acquired_or_unresolved_identity"
    assert by["GONE"]["recoverable_fields"] == "identity only"


def test_loader_does_not_invent_aliases(tmp_path):
    p = tmp_path / "aliases.csv"
    pd.DataFrame([{"old_ticker": "OLD", "canonical_ticker": "NEW"}]).to_csv(p, index=False)
    assert set(mod.load_aliases(p)) == {"OLD"}
