# -*- coding: utf-8 -*-
"""Tests for explicit PIT admission and sample audit."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import pit_admission as p  # noqa: E402

BASE = {"event_id": "x", "published_at": "2026-10-29T18:00:00Z",
        "first_seen_at_utc": "2026-10-29T18:30:00Z", "parse_status": "exact",
        "source_evidence": "official_fed_page", "is_simulated": False,
        "is_historical_backfill": False, "observation_kind": "live_forward_observation"}


def test_only_full_evidence_admitted():
    out = p.admit(BASE, decision_at="2026-10-29T19:00:00Z")
    assert out["admitted"] is True
    assert out["reasons"] == []


def test_late_old_event_rejected():
    r = dict(BASE, first_seen_at_utc="2026-10-30T18:00:00Z",
             observation_kind="late_observation_of_old_event",
             pit_status="late_observation_not_pit")
    out = p.admit(r, decision_at="2026-10-30T19:00:00Z")
    assert out["admitted"] is False
    assert "late_observation" in out["reasons"]


def test_simulated_and_backfill_rejected():
    out = p.admit(dict(BASE, is_simulated=True), decision_at="2026-10-29T19:00:00Z")
    assert "simulated_record" in out["reasons"]
    out = p.admit(dict(BASE, is_historical_backfill=True), decision_at="2026-10-29T19:00:00Z")
    assert "historical_backfill" in out["reasons"]


def test_missing_decision_or_source_rejected():
    out = p.admit(BASE)
    assert "decision_time_missing" in out["reasons"]
    out = p.admit(dict(BASE, source_evidence=None), decision_at="2026-10-29T19:00:00Z")
    assert "source_evidence_not_verified" in out["reasons"]


def test_missing_published_rejected():
    out = p.admit(dict(BASE, published_at=None), decision_at="2026-10-29T19:00:00Z")
    assert "published_time_missing" in out["reasons"]


def test_decision_before_observation_rejected():
    out = p.admit(BASE, decision_at="2026-10-29T18:00:00Z")
    assert "decision_before_first_seen" in out["reasons"]
def test_sec_acceptance_metadata_rejected():
    r = dict(BASE, source_evidence="sec_json_acceptance")
    out = p.admit(r, decision_at="2026-10-29T19:00:00Z")
    assert out["admitted"] is False
    assert "source_evidence_not_verified" in out["reasons"]
