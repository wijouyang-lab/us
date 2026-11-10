# -*- coding: utf-8 -*-
"""Fixture checks for the Fed retrospective index; no network."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "research"


def test_fed_retrospective_index_is_not_pit():
    data = json.loads((ROOT / "fed_2026_press_retrospective_2026-10-29.json").read_text(encoding="utf-8"))
    assert data["retrospective_only"] is True
    assert data["count"] == len(data["events"]) == 114
    assert all(e["observation_mode"] == "retrospective_backfill" for e in data["events"])
    assert all(e["pit_eligible"] is False for e in data["events"])
    assert all(e["first_seen_at_utc"] is None for e in data["events"])
    assert all(e["timestamp_precision"] == "date_only" for e in data["events"])
