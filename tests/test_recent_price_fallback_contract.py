# -*- coding: utf-8 -*-
"""Tests for the recent-panel fallback contract; synthetic data only."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import recent_price_fallback_contract as mod  # noqa: E402


def policy(**kw):
    base = {"target_date": "2026-10-28", "approved_providers": ["APPROVED"],
            "rights_verified": True, "panel_price_basis": "raw",
            "requires_adjusted_close": False, "reference_close": 437.33}
    base.update(kw)
    return base


def row(provider="APPROVED", date="2026-10-28", close=437.33, high=444.805,
        open_=444.68, low=426.91, basis="raw", **kw):
    d = {"provider": provider, "date": date, "Open": open_, "High": high,
         "Low": low, "Close": close, "Volume": 1163860, "price_basis": basis,
         "source_url": "https://example.test/HUBB", "fetched_at": "2026-10-29T00:00:00Z",
         "evidence_sha256": "a" * 64}
    d.update(kw)
    return d


def test_primary_valid_does_not_trigger_fallback():
    out = mod.evaluate(row(provider="YAHOO"), None, policy())
    assert out["status"] == "primary_ok"
    assert out["action"] == "no_fallback"


def test_missing_or_invalid_primary_checks_candidate():
    bad = row(provider="YAHOO", close=None)
    out = mod.evaluate(bad, None, policy())
    assert out["status"] == "blocked"
    assert "primary_missing_close" in out["reasons"]


def test_valid_approved_candidate_is_accepted_with_provenance():
    out = mod.evaluate(None, row(), policy())
    assert out["status"] == "accepted"
    assert out["candidate"]["provider"] == "APPROVED"
    assert out["candidate"]["evidence_sha256"] == "a" * 64


def test_unapproved_nasdaq_is_rejected():
    out = mod.evaluate(None, row(provider="NASDAQ"), policy())
    assert out["status"] == "blocked"
    assert "provider_not_approved" in out["reasons"]


def test_bad_ohlc_date_and_basis_are_rejected():
    out = mod.evaluate(None, row(open_=500.0), policy())
    assert "candidate_invalid_ohlc" in out["reasons"]
    out = mod.evaluate(None, row(date="2026-10-29"), policy())
    assert "date_mismatch" in out["reasons"]
    out = mod.evaluate(None, row(basis="adjusted"), policy())
    assert "price_basis_mismatch" in out["reasons"]


def test_missing_provenance_duplicate_and_conflict_are_rejected():
    no_hash = row(evidence_sha256="")
    assert "missing_evidence_hash" in mod.evaluate(None, no_hash, policy())["reasons"]
    dup = row(duplicate_of_existing=True)
    assert "duplicate_existing_row" in mod.evaluate(None, dup, policy())["reasons"]
    conflict = row(close=430.0)
    assert "close_conflict" in mod.evaluate(None, conflict, policy())["reasons"]


def test_rights_unverified_is_rejected():
    out = mod.evaluate(None, row(), policy(rights_verified=False))
    assert out["status"] == "blocked"
    assert "rights_unverified" in out["reasons"]
