# -*- coding: utf-8 -*-
"""Tests for manual batch capture and batch summaries."""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import capture_batch as b  # noqa: E402
import event_capture_store as s  # noqa: E402

URL = "https://www.federalreserve.gov/newsevents/pressreleases/monetary20261029a.htm"
HTML = "<title>Federal Reserve Board - FOMC statement</title><p>For release at 2:00 p.m. EDT</p><p>Statement</p><p>Implementation Note</p>"


def fake_fetch(url, now=None, **kwargs):
    return s.parse_fomc_statement(HTML, url, datetime.fromisoformat("2026-10-29T18:30:00+00:00"))


def test_batch_summary_new_duplicate_and_resume(tmp_path, monkeypatch):
    monkeypatch.setattr(b, "fetch", fake_fetch)
    store = tmp_path / "capture.jsonl"
    a = b.run([URL], store, user_agent="test", batch_id="b1")
    assert a["counts"]["new"] == 1
    b2 = b.run([URL], store, user_agent="test", batch_id="b2")
    assert b2["counts"]["duplicate"] == 1
    assert b2["counts"]["new"] == 0
    rows = [json.loads(x) for x in store.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["first_seen_at_utc"] == rows[1]["first_seen_at_utc"]
    batches = [json.loads(x) for x in (tmp_path / "capture.jsonl.batches.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [x["batch_id"] for x in batches] == ["b1", "b2"]


def test_batch_rejects_non_whitelisted_url(tmp_path, monkeypatch):
    monkeypatch.setattr(b, "fetch", fake_fetch)
    out = b.run(["https://example.com/x"], tmp_path / "capture.jsonl", user_agent="test")
    assert out["counts"]["failed"] == 1
    assert out["records"][0]["status"] == "rejected_url"
