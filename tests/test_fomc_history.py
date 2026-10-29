# -*- coding: utf-8 -*-
"""Fixture checks for extended FOMC history and capture records."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "research"


def test_history_has_2010_2025_and_exact_date_only_split():
    d = json.loads((ROOT / "fomc_2010_2025_combined_2026-10-29.json").read_text(encoding="utf-8"))
    assert d["count"] == 132
    assert d["exact"] == 83
    assert d["date_only"] == 49
    assert d["years"] == [str(y) for y in range(2010, 2026)]
    ids = [e["event_id"] for e in d["events"]]
    assert len(ids) == len(set(ids))


def test_live_and_backfill_capture_records():
    live = [json.loads(x) for x in (ROOT / "fomc_live_capture_final_2026-10-29.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(live) == 2
    assert live[0]["version"] == 1 and live[1]["version"] == 1
    assert live[0]["first_seen_at_utc"] == live[1]["first_seen_at_utc"]
    back = json.loads((ROOT / "fomc_backfill_capture_2026-10-29.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert back["first_seen_at_utc"] is None
    assert back["pit_status"] == "retrospective_non_PIT"
    assert back["parse_status"] == "date_only"
