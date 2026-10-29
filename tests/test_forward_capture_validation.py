# -*- coding: utf-8 -*-
"""Tests for current forward capture and late-observation semantics."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "research"


def read(name):
    return [json.loads(x) for x in (ROOT / name).read_text(encoding="utf-8").splitlines() if x.strip()]


def test_current_capture_is_late_not_pit():
    rows = read("fomc_forward_capture_current_2026-10-29.jsonl")
    assert len(rows) == 2
    assert len({r["event_id"] for r in rows}) == 1
    assert rows[0]["first_seen_at_utc"] == rows[1]["first_seen_at_utc"]
    assert rows[0]["version"] == rows[1]["version"] == 1
    assert rows[0]["pit_status"] == "late_observation_not_pit"
    assert rows[0]["pit_eligible"] is False
    assert rows[0]["observation_kind"] == "late_observation_of_old_event"


def test_old_2025_capture_is_migrated():
    rows = read("fomc_forward_capture_2026-10-29.jsonl")
    assert rows[-1]["event_id"] == "20250319"
    assert rows[-1]["pit_status"] == "late_observation_not_pit"
    assert rows[-1]["pit_eligible"] is False
    assert rows[-1]["first_seen_at_utc"] is not None


def test_no_live_pit_record_exists_yet():
    rows = read("fomc_forward_capture_current_2026-10-29.jsonl")
    assert not any(r.get("pit_eligible") is True for r in rows)
