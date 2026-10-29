# -*- coding: utf-8 -*-
"""Fixture checks for PIT sample audit."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "research"


def test_pit_audit_counts_and_rejections():
    d = json.loads((ROOT / "pit_sample_audit_2026-10-29.json").read_text(encoding="utf-8"))
    assert d["unique_events"] == 3
    assert d["pit_admitted"] == 0
    assert d["late_observations"] == 2
    assert d["historical_backfills"] == 1
    assert d["simulated_records"] == 0
    assert d["real_first_seen_records"] == 2
    assert "20100127" in d["events"]
    assert "late_observation" in d["events"]["20250319"]
