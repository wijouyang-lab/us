# -*- coding: utf-8 -*-
"""Fixture checks for minimal Fed/SPY event study."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "research"


def test_event_study_counts_and_costs():
    d = json.loads((ROOT / "fed_event_study_2026-10-29.json").read_text(encoding="utf-8"))
    assert d["events_total"] == 114
    assert d["events_with_windows"] == 114
    assert d["unique_entry_dates"] == 84
    assert d["cost_bps_one_way"] == 5.0
    assert d["sample"]["n"] == 84
    assert d["sample"]["mean_net_1d"] < d["sample"]["mean_gross_1d"]
    assert d["sample"]["mean_net_5d"] < d["sample"]["mean_gross_5d"]


def test_event_study_is_explicitly_counterfactual():
    d = json.loads((ROOT / "fed_event_study_2026-10-29.json").read_text(encoding="utf-8"))
    assert d["observation_mode"] == "retrospective_counterfactual_not_pit"
    assert "PIT" in d["note"]
    assert "overlapping" in d["note"]
