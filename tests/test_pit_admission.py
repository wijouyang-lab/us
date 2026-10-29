# -*- coding: utf-8 -*-
"""Tests for strict PIT admission."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import pit_admission as p  # noqa: E402

BASE = {
    "event_id": "x", "published_at": "2026-10-29T18:00:00Z",
    "first_seen_at_utc": "2026-10-29T18:30:00Z",
    "research_ready_at_utc": "2026-10-29T18:30:00Z",
    "decision_at_utc": "2026-10-29T19:00:00Z",
    "parse_status": "exact", "source_evidence": "official_fed_page",
    "published_at_evidence": "official_release_time_in_page",
    "decision_evidence": "strategy_log",
    "is_simulated": False, "is_historical_backfill": False,
    "observation_kind": "live_forward_observation",
}


def test_only_full_evidence_admitted():
    out = p.admit(BASE)
    assert out["admitted"] is True
    assert out["reasons"] == []


def test_simulation_flag_missing_rejected():
    r = dict(BASE)
    del r["is_simulated"]
    out = p.admit(r)
    assert "simulation_flag_missing" in out["reasons"]


def test_unknown_source_or_published_evidence_rejected():
    assert "source_evidence_not_verified" in p.admit(dict(BASE, source_evidence="unknown"))["reasons"]
    assert "published_at_evidence_missing" in p.admit(dict(BASE, published_at_evidence=None))["reasons"]


def test_naive_time_rejected():
    out = p.admit(dict(BASE, published_at="2026-10-29T18:00:00"))
    assert "published_time_missing_or_naive" in out["reasons"]


def test_late_and_backfill_and_simulated_rejected():
    assert "late_observation" in p.admit(dict(BASE, first_seen_at_utc="2026-10-30T18:00:00Z",
                                             research_ready_at_utc="2026-10-30T18:00:00Z",
                                             observation_kind="late_observation_of_old_event"))["reasons"]
    assert "historical_backfill" in p.admit(dict(BASE, is_historical_backfill=True))["reasons"]
    assert "simulated_record" in p.admit(dict(BASE, is_simulated=True))["reasons"]


def test_decision_missing_or_early_rejected():
    assert "decision_time_missing" in p.admit(dict(BASE, decision_at_utc=None))["reasons"]
    assert "decision_before_research_ready" in p.admit(dict(BASE, decision_at_utc="2026-10-29T18:00:00Z"))["reasons"]
    assert "decision_evidence_missing" in p.admit(dict(BASE, decision_evidence=None))["reasons"]


def test_stored_flags_do_not_bypass():
    out = p.admit(dict(BASE, pit_eligible=True, pit_status="forward_observed",
                       source_evidence="unknown"))
    assert out["admitted"] is False


def test_backfill_and_missing_backfill_flag_fail_closed():
    assert "historical_backfill" in p.admit(dict(BASE, is_historical_backfill=True))["reasons"]
    r = dict(BASE)
    del r["is_historical_backfill"]
    assert "historical_backfill_flag_missing" in p.admit(r)["reasons"]


def test_future_synthetic_decision_does_not_fix_missing_evidence():
    out = p.admit(dict(BASE, source_evidence=None, decision_at_utc="2099-01-01T00:00:00Z"))
    assert out["admitted"] is False
    assert "source_evidence_not_verified" in out["reasons"]
