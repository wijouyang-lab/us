# -*- coding: utf-8 -*-
"""Fixture checks for the AKShare route/terms matrix; no live network."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "research"


def test_route_statuses_and_terms_are_explicit():
    d = json.loads((ROOT / "akshare_route_matrix_2026-10-29.json").read_text(encoding="utf-8"))
    assert d["terms"]["status"] == "UNRESOLVED"
    by = {r["route"]: r for r in d["routes"]}
    assert by["sina"]["status"] == "PARTIAL"
    assert by["sina"]["samples"]["TWTR"] == "PASS"
    assert by["sina"]["samples"]["ADCT"] == "REJECTED_ticker_reuse"
    assert by["eastmoney"]["status"] == "UNVERIFIED"
    assert by["futu"]["status"] == "UNVERIFIED"
    assert d["canonical_write"] is False
    assert d["bulk_expansion"] is False


def test_raw_publication_requires_written_permission():
    d = json.loads((ROOT / "akshare_route_matrix_2026-10-29.json").read_text(encoding="utf-8"))
    text = d["terms"]["confirmed"]["raw_copy_publication"]
    assert "written authorization" in text
    assert any("long-term storage" in x for x in d["terms"]["unresolved"])
