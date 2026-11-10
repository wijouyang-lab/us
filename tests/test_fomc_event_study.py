# -*- coding: utf-8 -*-
"""Fixture checks for FOMC multi-proxy event study."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "research"


def test_fomc_event_sample_and_proxies():
    d = json.loads((ROOT / "fomc_event_study_2026-10-29.json").read_text(encoding="utf-8"))
    assert d["events_total"] == 25
    assert d["events_used"] == 24
    assert len(d["proxies"]) == 5
    assert {r["proxy"] for r in d["proxies"]} == {"SPY", "QQQ", "IWM", "TLT", "GLD"}
    for r in d["proxies"]:
        assert r["n"] == 24
        assert r["unique_entry_dates"] == 24
        assert r["mean_net_1d"] < r["mean_gross_1d"]
        assert r["mean_net_5d"] < r["mean_gross_5d"]


def test_fomc_study_is_not_pit():
    d = json.loads((ROOT / "fomc_event_study_2026-10-29.json").read_text(encoding="utf-8"))
    assert d["observation_mode"] == "retrospective_counterfactual_not_pit"
    assert d["round_trip_cost_bps"] == 10
    assert "raw open/close" in d["price"]
def test_extended_fomc_2010_2025():
    d = json.loads((ROOT / "fomc_event_study_2010_2025_2026-10-29.json").read_text(encoding="utf-8"))
    assert d["events_used"] == 82
    assert len(d["proxies"]) == 5
    for r in d["proxies"]:
        assert r["n"] == 82
        assert r["unique_entry_dates"] == 82
        assert r["mean_net_1d"] < r["mean_gross_1d"]
