# -*- coding: utf-8 -*-
"""Tests for event capture store; no live network required."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import event_capture_store as s  # noqa: E402

HTML = """<html><title>Federal Reserve Board - FOMC statement</title>
<p>For release at 2:00 p.m. EDT</p></html>"""


def obs(now="2026-10-29T14:00:00Z", html=HTML):
    return s.parse_fomc_statement(html, "https://www.federalreserve.gov/newsevents/pressreleases/monetary20240320a.htm",
                                  datetime.fromisoformat(now.replace("Z", "+00:00")))


def test_parse_exact_timezone(tmp_path):
    r = obs()
    assert r["parse_status"] == "exact"
    assert r["published_at"] == "2024-03-20T18:00:00Z"
    assert r["source_timezone"] == "EDT"


def test_first_seen_is_preserved(tmp_path):
    p = tmp_path / "store.jsonl"
    a = s.store_observation(p, obs("2026-10-29T14:00:00Z"))
    b = s.store_observation(p, obs("2026-10-29T15:00:00Z"))
    assert a["first_seen_at_utc"] == "2026-10-29T14:00:00Z"
    assert b["first_seen_at_utc"] == "2026-10-29T14:00:00Z"
    assert b["version"] == 1


def test_content_update_increments_version(tmp_path):
    p = tmp_path / "store.jsonl"
    s.store_observation(p, obs("2026-10-29T14:00:00Z"))
    b = s.store_observation(p, obs("2026-10-29T15:00:00Z", HTML + " revised"))
    assert b["version"] == 2
    assert b["first_seen_at_utc"] == "2026-10-29T14:00:00Z"


def test_backfill_has_no_first_seen_and_is_not_pit(tmp_path):
    p = tmp_path / "store.jsonl"
    r = s.store_observation(p, obs(), backfill=True)
    assert r["first_seen_at_utc"] is None
    assert r["pit_status"] == "retrospective_non_PIT"
    assert r["is_historical_backfill"] is True


def test_http_error_is_recorded(tmp_path):
    p = tmp_path / "store.jsonl"
    r = s.store_observation(p, {"event_id": None, "source_url": "x", "http_status": 503,
                                "parse_status": "http_error", "fetched_at_utc": "2026-10-29T14:00:00Z"})
    assert r["parse_status"] == "http_error"
    assert r["http_status"] == 503
