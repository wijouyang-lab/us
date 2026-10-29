# -*- coding: utf-8 -*-
"""Fixture checks for provider licensing evidence; no network."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "research"


def test_no_candidate_is_marked_approved():
    data = json.loads((ROOT / "legal_terms_evidence_2026-10-29.json").read_text(encoding="utf-8"))
    assert data["sources"]
    assert all(s["approved"] is False for s in data["sources"])


def test_evidence_hashes_and_report_exist():
    data = json.loads((ROOT / "legal_terms_evidence_2026-10-29.json").read_text(encoding="utf-8"))
    alpha = next(s for s in data["sources"] if s["provider"] == "Alpha Vantage")
    alpaca = next(s for s in data["sources"] if s["provider"] == "Alpaca")
    assert len(alpha["sha256"]) == 64
    assert len(alpaca["sha256"]) == 64
    assert (ROOT / "LEGAL_MARKET_DATA_PROVIDER_COMPARISON.md").exists()
